from __future__ import annotations

import sys
from copy import copy
from dataclasses import MISSING
from getopt import GetoptError, getopt, gnu_getopt
from pathlib import Path
from typing import TYPE_CHECKING, cast, final

from bicker._help import HelpConfig, HelpRenderer
from bicker._spec import LITERAL_TYPES, collect_spec
from bicker._style import Style, Styles, style

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from bicker._spec import Field, HelpKey, Spec, VersionKey


def parse_args[T](
    spec: type[T],
    argv: list[str] | tuple[str, ...] | None = None,
    *,
    help_keys: Sequence[HelpKey] = ("-h", "--help"),
    help_description: str = "Show this message and exit",
    version: str | None = None,
    version_keys: Sequence[VersionKey] = ("--version",),
    version_description: str = "Show the version and exit",
    prog: str | None = None,
    description: str | None = None,
    epilog: str | None = None,
    examples: list[str] | tuple[str, ...] = (),
    usage_on_error: bool = True,
    use_shorthand_usage: bool = False,
) -> T:
    """Parse command-line arguments into an instance of `spec`.

    Each value is converted to its field's type: `str`, `int`, `float`, a `Literal` of strings
    or ints (only its values are allowed), or a `list` of these. Parsing follows GNU
    conventions: options and positionals can be mixed, and everything after `--` is a
    positional. Output is colored in a terminal unless `NO_COLOR` is set.

    Args:
        spec: A class whose annotated attributes are declared with `pos()`, `opt()` or
            `flag()`. It must be constructible with no arguments.
        argv: The arguments to parse. Defaults to `sys.argv[1:]`.
        help_keys: The keys that print help and exit. Pass `()` to disable help.
        help_description: The help text for the help option itself.
        version: The version to print, e.g. `"1.2.0"`. Without it, there's no version option.
        version_keys: The keys that print the program name and version, then exit. Add `"-V"`
            to support the short key too.
        version_description: The help text for the version option itself.
        prog: The program name shown in help. Defaults to the file name of `sys.argv[0]`.
        description: Text shown below the usage line in help.
        epilog: Text shown at the end of help.
        examples: Example argument lists, each shown in help after the program name.
        usage_on_error: Whether to print the usage line after an error.
        use_shorthand_usage: Whether the usage line shows `[options]` instead of expanding each
            option.

    Returns:
        An instance of `spec` with each declared attribute set to its parsed or default value.

    Raises:
        TypeError: If `spec` is declared incorrectly.
        SystemExit: With code 0 after printing help to stdout, or code 1 after printing an
            error (and usage) to stderr.

    Example:
        ```python
        from bicker import flag, opt, parse_args, pos


        class Args:
            src: str = pos(description="File to read")
            count: int = opt(1, short="-c", description="How many times")
            verbose: bool = flag(short="-v")


        args = parse_args(Args)  # e.g. `prog in.txt -c 3 -v`
        ```
    """
    version_keys = version_keys if version else ()
    reserved: dict[str, str] = dict.fromkeys(help_keys, "help_keys")
    reserved |= dict.fromkeys(version_keys, "version_keys")
    root = collect_spec(spec, reserved)
    cfg = HelpConfig(
        prog=prog or Path(sys.argv[0]).name,
        help_keys=help_keys,
        help_description=help_description,
        version_keys=version_keys,
        version_description=version_description,
        description=description,
        epilog=epilog,
        examples=examples,
        use_shorthand_usage=use_shorthand_usage,
    )

    argv = sys.argv[1:] if argv is None else argv
    path, argv = _find_commands(root, argv)

    # Help wins over any other error; after "--" everything is a positional
    options_part = argv[: argv.index("--")] if "--" in argv else argv
    if any(key in options_part for key in help_keys):
        print(HelpRenderer(path, cfg, sys.stdout).help())
        sys.exit(0)
    if version and any(key in options_part for key in version_keys):
        print(style(cfg.prog, Styles.PROG, sys.stdout), style(version, Styles.VERSION, sys.stdout))
        sys.exit(0)

    try:
        all_options = [field for level in path for field in level.options]
        values, raw_positionals = _parse_options(all_options, argv)
        values |= _parse_positionals(path[-1], raw_positionals)
    except _ParseError as e:
        print(f"{style('error', Styles.ERROR_PREFIX)} {e}", file=sys.stderr)
        if usage_on_error:
            print("\n" + HelpRenderer(path, cfg, sys.stderr).usage(), file=sys.stderr)
        sys.exit(1)

    return cast("T", _instantiate(path, values))


def _find_commands(root: Spec, argv: Sequence[str]) -> tuple[list[Spec], list[str]]:
    """Find the given commands: the specs from `root` down, and `argv` without command names.

    Stops early on anything unexpected (e.g. an unknown option), which the full parse reports.
    """
    path = [root]
    rest = list(argv)
    start = 0  # Where the current command's arguments begin

    while path[-1].commands:
        # Unlike gnu_getopt, getopt stops at the first positional: here, the command name
        fields_by_key = {key: f for spec in path for f in spec.options for key in f.keys}
        try:
            _, after = getopt(rest[start:], *_getopt_spec(fields_by_key))
        except GetoptError:
            break
        if not after or (command := path[-1].find_command(after[0])) is None:
            break

        start = len(rest) - len(after)
        del rest[start]
        path.append(command)

    return path, rest


def _instantiate(path: Sequence[Spec], values: Mapping[Field, object]) -> object:
    """Build each command's instance, innermost first, and return the outermost."""
    command: object = None
    for spec in reversed(path):
        instance = spec.cls()
        for field in (*spec.options, *spec.positionals):
            setattr(instance, field.name, values.get(field, _default(field)))
        if spec.command_attr:
            setattr(instance, spec.command_attr, command)
        command = instance
    return command


def _default(field: Field) -> object:
    """Copy the default, so a mutable one (e.g. a list) isn't shared between parses.

    A list without a default (a positional or required option allowed none) starts empty.
    """
    return [] if field.is_list and field.default is MISSING else copy(field.default)


def _getopt_spec(fields_by_key: Mapping[str, Field]) -> tuple[str, list[str]]:
    """Format the keys for getopt: short `"c:"` and long `"count="` take a value."""
    shorts = "".join(
        k[1] + ("" if f.is_flag else ":")
        for k, f in fields_by_key.items()
        if not k.startswith("--")
    )
    longs = [
        k[2:] + ("" if f.is_flag else "=") for k, f in fields_by_key.items() if k.startswith("--")
    ]
    return shorts, longs


def _parse_options(
    option_fields: Sequence[Field],
    argv: Sequence[str],
) -> tuple[dict[Field, object], list[str]]:

    fields_by_key = {key: field for field in option_fields for key in field.keys}

    try:
        option_pairs, raw_positionals = gnu_getopt(argv, *_getopt_spec(fields_by_key))
    except GetoptError as e:
        raise _ParseError(_getopt_error_message(e, fields_by_key)) from None

    option_values: dict[Field, object] = {}
    repeated: dict[Field, list[object]] = {}
    # raw in this context: str version of object (e.g., "3" = raw version of 3)
    for key, raw in option_pairs:
        field = fields_by_key[key]
        value = True if field.is_flag else _convert(key, field, raw)
        if field.is_list:
            repeated.setdefault(field, []).append(value)
        else:
            option_values[field] = value

    for field, values in repeated.items():
        _check_count(field.label, field, len(values))

    given = option_values | repeated
    if missing := [f.label for f in option_fields if f.is_required and f not in given]:
        noun = "option" if len(missing) == 1 else "options"
        msg = f"missing required {noun}: {', '.join(style(key, Styles.OPT) for key in missing)}"
        raise _ParseError(msg)

    return given, raw_positionals


def _getopt_error_message(e: GetoptError, fields_by_key: Mapping[str, Field]) -> str:
    key = f"--{e.opt}" if f"--{e.opt}" in e.msg else f"-{e.opt}"
    matches = [k for k in fields_by_key if k.startswith(key)]

    # getopt's own messages for these leak its spec format ("count=, color=")
    if not e.opt:  # e.g. "--=x"
        return f"option {style(key, _key_style(key, fields_by_key))} not recognized"

    if key not in fields_by_key and len(matches) > 1:
        listed = ", ".join(style(k, _key_style(k, fields_by_key)) for k in matches)
        return f"option {style(key, _key_style(key, fields_by_key))} is ambiguous: {listed}"

    return e.msg.replace(key, style(key, _key_style(key, fields_by_key)))


def _key_style(key: str, fields_by_key: Mapping[str, Field]) -> Style:
    """Return the key's field style (flag vs option), or the option style for unknown keys."""
    field = fields_by_key.get(key)
    return field.style if field else Styles.OPT


def _convert(label: str, field: Field, raw: str) -> object:
    # A field that takes values is either a scalar or a `Literal` (see `_check_type`)
    typ = field.scalar_typ
    if typ is None:
        return _convert_choice(label, field, raw)

    try:
        return typ(raw)
    except ValueError:
        msg = (
            f"{style(label, field.style)} expects {style(typ.__name__, Styles.TYPE)}, "
            f"got {style(raw, Styles.STR_VALUE)}"
        )
        raise _ParseError(msg) from None


def _convert_choice(label: str, field: Field, raw: str) -> object:
    choices_by_raw = {str(choice): choice for choice in field.choices}
    if raw not in choices_by_raw:
        listed = ", ".join(
            style(raw_choice, LITERAL_TYPES[type(choice)])
            for raw_choice, choice in choices_by_raw.items()
        )
        msg = f"{style(label, field.style)} must be one of: {listed}"
        raise _ParseError(msg)
    return choices_by_raw[raw]


def _parse_positionals(spec: Spec, raw_positionals: Sequence[str]) -> dict[Field, object]:
    """Convert the positionals, or check the command if `spec` has one (and so no positionals).

    A known command was already taken out of `raw_positionals` by `_find_commands`.
    """
    if spec.commands:
        names = ", ".join(style(name, Styles.COMMAND) for name in spec.commands)
        if raw_positionals:
            raw = style(raw_positionals[0], Styles.STR_VALUE)
            msg = f"unknown command {raw} (one of: {names})"
            raise _ParseError(msg)
        if spec.command_required:
            msg = f"missing command (one of: {names})"
            raise _ParseError(msg)
        return {}

    pos_fields = spec.positionals
    values: dict[Field, object] = {}
    rest = list(raw_positionals)

    # Each positional takes its values in order: 1 for a single value, N for nargs=N,
    # and (only possible for the last one) up to its max for a variable-count list
    for i, field in enumerate(pos_fields):
        if not rest:
            if missing := [f.name for f in pos_fields[i:] if f.is_required]:
                noun = "positional" if len(missing) == 1 else "positionals"
                msg = f"missing {noun}: {', '.join(style(name, Styles.POS) for name in missing)}"
                raise _ParseError(msg)
            break

        if not field.is_list:
            values[field] = _convert(field.name, field, rest.pop(0))
            continue

        _, high = field.nargs_range
        taken, rest = (rest, []) if high is None else (rest[:high], rest[high:])
        _check_count(field.name, field, len(taken))
        values[field] = [_convert(field.name, field, raw) for raw in taken]

    if rest:
        noun = "positional" if len(rest) == 1 else "positionals"
        msg = f"unexpected {noun}: {', '.join(style(raw, Styles.STR_VALUE) for raw in rest)}"
        raise _ParseError(msg)

    return values


def _check_count(label: str, field: Field, count: int) -> None:
    lo, hi = field.nargs_range
    if count < lo or (hi is not None and count > hi):
        msg = f"{style(label, field.style)} expects {_expected_count(lo, hi)}, got {count}"
        raise _ParseError(msg)


def _expected_count(low: int, high: int | None) -> str:
    """`exactly 2 values`, `at least 1 value`, `at most 3 values` or `1 to 3 values`."""
    if low == high:
        text = f"exactly {low}"
    elif high is None:
        text = f"at least {low}"
    elif low == 0:
        text = f"at most {high}"
    else:
        text = f"{low} to {high}"
    shown = low if high is None else high
    return f"{text} value{'' if shown == 1 else 's'}"


@final
class _ParseError(Exception):
    """Bad command-line input; `parse_args` turns it into usage + error message + exit."""
