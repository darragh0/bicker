import sys
from copy import copy
from dataclasses import MISSING
from getopt import GetoptError, gnu_getopt
from pathlib import Path
from typing import TYPE_CHECKING, final

from bicker._help import format_usage, print_help
from bicker._spec import LITERAL_TYPES, collect_fields
from bicker._style import Style, Styles, style

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from bicker._spec import Field, HelpKey


def parse_args[T](
    spec: type[T],
    argv: Sequence[str] | None = None,
    *,
    help_keys: Collection[HelpKey] = ("-h", "--help"),
    help_description: str = "Show this message and exit",
    prog: str | None = None,
    description: str | None = None,
    epilog: str | None = None,
    examples: Sequence[str] = (),
    usage_on_error: bool = True,
    use_shorthand_usage: bool = False,
) -> T:
    fields = collect_fields(spec, help_keys)
    prog = prog or Path(sys.argv[0]).name

    pos_fields = [field for field in fields if field.is_pos]
    option_fields = [field for field in fields if not field.is_pos]
    argv = sys.argv[1:] if argv is None else argv

    # Help wins over any other error; after "--" everything is a positional
    options_part = argv[: argv.index("--")] if "--" in argv else argv
    if any(key in options_part for key in help_keys):
        print_help(
            fields,
            prog=prog,
            help_keys=help_keys,
            help_description=help_description,
            description=description,
            epilog=epilog,
            examples=examples,
            use_shorthand_usage=use_shorthand_usage,
        )
        sys.exit(0)

    try:
        option_values, raw_positionals = _parse_options(option_fields, argv)
        pos_values = _parse_positionals(pos_fields, raw_positionals)
    except _ParseError as e:
        print(f"{style('error', Styles.ERROR_PREFIX)} {e}", file=sys.stderr)
        if usage_on_error:
            print(
                "\n"
                + format_usage(
                    fields,
                    prog=prog,
                    stream=sys.stderr,
                    use_shorthand=use_shorthand_usage,
                ),
                file=sys.stderr,
            )
        sys.exit(1)

    # Copied so a mutable default (e.g. a list) isn't shared between parses;
    # a list positional without a default (allowed when its min is 0) starts empty
    values: dict[str, object] = {
        field.name: [] if field.is_list and field.default is MISSING else copy(field.default)
        for field in fields
    }
    values |= option_values
    values |= pos_values

    args = spec()
    for name, value in values.items():
        setattr(args, name, value)
    return args


def _parse_options(
    option_fields: Sequence[Field],
    argv: Sequence[str],
) -> tuple[dict[str, object], list[str]]:

    fields_by_key = {key: field for field in option_fields for key in field.keys}

    # getopt's spec format: short "c:" / long "count=" mean the option takes a value
    shorts = "".join(
        k[1] + ("" if f.is_flag else ":")
        for k, f in fields_by_key.items()
        if not k.startswith("--")
    )
    longs = [
        k[2:] + ("" if f.is_flag else "=") for k, f in fields_by_key.items() if k.startswith("--")
    ]

    try:
        option_pairs, raw_positionals = gnu_getopt(argv, shorts, longs)
    except GetoptError as e:
        raise _ParseError(_getopt_error_message(e, fields_by_key)) from None

    option_values: dict[str, object] = {}
    repeated: dict[str, list[object]] = {}
    # raw in this context: str version of object (e.g., "3" = raw version of 3)
    for key, raw in option_pairs:
        field = fields_by_key[key]
        value = True if field.is_flag else _convert(key, field, raw)
        if field.is_list:
            repeated.setdefault(field.name, []).append(value)
        else:
            option_values[field.name] = value

    for field in option_fields:
        if field.is_list:
            _check_count(field.long_key, field, len(repeated.get(field.name, [])))

    return option_values | repeated, raw_positionals


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
    if field.choices:
        choices_by_raw = {str(choice): choice for choice in field.choices}

        if raw not in choices_by_raw:
            listed = ", ".join(
                style(raw_choice, LITERAL_TYPES[type(choice)])
                for raw_choice, choice in choices_by_raw.items()
            )
            msg = f"{style(label, field.style)} must be one of: {listed}"
            raise _ParseError(msg)
        return choices_by_raw[raw]

    try:
        return field.value_typ(raw)
    except ValueError:
        msg = (
            f"{style(label, field.style)} expects {style(field.value_typ.__name__, Styles.TYPE)}, "
            f"got {style(raw, Styles.STR_VALUE)}"
        )
        raise _ParseError(msg) from None


def _parse_positionals(
    pos_fields: Sequence[Field],
    raw_positionals: Sequence[str],
) -> dict[str, object]:

    values: dict[str, object] = {}
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
            values[field.name] = _convert(field.name, field, rest.pop(0))
            continue

        _, high = field.nargs_range
        taken, rest = (rest, []) if high is None else (rest[:high], rest[high:])
        _check_count(field.name, field, len(taken))
        values[field.name] = [_convert(field.name, field, raw) for raw in taken]

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
