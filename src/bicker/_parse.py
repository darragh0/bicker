import sys
from dataclasses import MISSING
from getopt import GetoptError, gnu_getopt
from typing import TYPE_CHECKING, Literal, NoReturn, get_args, get_origin, get_type_hints

from bicker._spec import collect_fields
from bicker._style import Style, Styles, style, style_value

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from bicker._spec import Converter, Field


def parse_args[T](spec: type[T], argv: Sequence[str] | None = None) -> T:
    fields = collect_fields(spec, get_type_hints(spec))
    pos_fields = {name: field for name, field in fields.items() if field.is_pos}
    option_fields = {name: field for name, field in fields.items() if not field.is_pos}

    option_values, raw_positionals = _parse_options(
        option_fields, sys.argv[1:] if argv is None else argv
    )
    pos_values = _parse_positionals(pos_fields, raw_positionals)

    values = {name: field.default for name, field in fields.items()}
    values |= option_values
    values |= pos_values

    args = spec()
    for name, value in values.items():
        setattr(args, name, value)
    return args


def _parse_options(
    option_fields: Mapping[str, Field],
    argv: Sequence[str],
) -> tuple[dict[str, object], list[str]]:

    names_by_key = {f"--{name.replace('_', '-')}": name for name in option_fields}
    names_by_key |= {field.short: name for name, field in option_fields.items() if field.short}

    # getopt's spec format: short "c:" / long "count=" mean the option takes a value
    shorts = "".join(
        k[1] + ("" if option_fields[n].is_flag else ":")
        for k, n in names_by_key.items()
        if not k.startswith("--")
    )
    longs = [
        k[2:] + ("" if option_fields[n].is_flag else "=")
        for k, n in names_by_key.items()
        if k.startswith("--")
    ]

    try:
        option_pairs, raw_positionals = gnu_getopt(argv, shorts, longs)
    except GetoptError as e:
        key = f"--{e.opt}" if f"--{e.opt}" in e.msg else f"-{e.opt}"
        matches = [k for k in names_by_key if k.startswith(key)]

        # getopt's own messages for these leak its spec format ("count=, color=")
        if not e.opt:  # e.g. "--=x"
            _fail(f"option {style(key, Styles.OPT)} not recognized")

        if key not in names_by_key and len(matches) > 1:
            listed = ", ".join(style(k, Styles.OPT) for k in matches)
            _fail(f"option {style(key, Styles.OPT)} is ambiguous: {listed}")

        _fail(e.msg.replace(key, style(key, Styles.OPT)))

    option_values: dict[str, object] = {}
    # raw in this context: str version of object (e.g., "3" = raw version of 3)
    for key, raw in option_pairs:
        name = names_by_key[key]
        field = option_fields[name]
        option_values[name] = (
            True if field.is_flag else _convert(key, field.tp, raw, label_style=Styles.OPT)
        )

    return option_values, raw_positionals


def _convert(label: str, tp: Converter, raw: str, *, label_style: Style) -> object:
    if get_origin(tp) is Literal:
        literals: tuple[object, ...] = get_args(tp)
        choices_by_raw = {str(choice): choice for choice in literals}

        if raw not in choices_by_raw:
            listed = ", ".join(
                style_value(raw_choice, choice) for raw_choice, choice in choices_by_raw.items()
            )
            msg = f"{style(label, label_style)} must be one of: {listed}"
            _fail(msg)
        return choices_by_raw[raw]

    try:
        return tp(raw)
    except ValueError:
        msg = (
            f"{style(label, label_style)} expects {style(tp.__name__, Styles.TYPE)}, "
            f"got {style(raw, Styles.STR)}"
        )
        _fail(msg)


def _parse_positionals(
    pos_fields: Mapping[str, Field],
    raw_positionals: Sequence[str],
) -> dict[str, object]:

    required = [name for name, field in pos_fields.items() if field.default is MISSING]

    if missing := required[len(raw_positionals) :]:
        noun = "positional" if len(missing) == 1 else "positionals"
        _fail(f"missing {noun}: {', '.join(style(name, Styles.POS) for name in missing)}")

    if extra := raw_positionals[len(pos_fields) :]:
        noun = "positional" if len(extra) == 1 else "positionals"
        _fail(f"unexpected {noun}: {', '.join(style(raw, Styles.STR) for raw in extra)}")

    return {
        name: _convert(name, field.tp, raw, label_style=Styles.POS)
        for (name, field), raw in zip(pos_fields.items(), raw_positionals, strict=False)
    }


def _fail(msg: str) -> NoReturn:
    sys.exit(f"{style('error:', Styles.ERROR_PREFIX)} {msg}")
