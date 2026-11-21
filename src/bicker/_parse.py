import sys
from getopt import GetoptError, gnu_getopt
from typing import TYPE_CHECKING, NoReturn

from bicker._spec import LITERAL_TYPES, collect_fields
from bicker._style import Fragments, Styles, style

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from bicker._spec import Field


def parse_args[T](spec: type[T], argv: Sequence[str] | None = None) -> T:
    fields = collect_fields(spec)

    pos_fields = [field for field in fields if field.is_pos]
    option_fields = [field for field in fields if not field.is_pos]
    argv = sys.argv[1:] if argv is None else argv

    option_values, raw_positionals = _parse_options(option_fields, argv)
    pos_values = _parse_positionals(pos_fields, raw_positionals)

    values = {field.name: field.default for field in fields}
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

    fields_by_key = {field.long_key: field for field in option_fields}
    fields_by_key |= {field.short: field for field in option_fields if field.short}

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
        _fail(_getopt_error_message(e, fields_by_key))

    option_values: dict[str, object] = {}
    # raw in this context: str version of object (e.g., "3" = raw version of 3)
    for key, raw in option_pairs:
        field = fields_by_key[key]
        option_values[field.name] = True if field.is_flag else _convert(key, field, raw)

    return option_values, raw_positionals


def _getopt_error_message(e: GetoptError, fields_by_key: Mapping[str, Field]) -> str:
    key = f"--{e.opt}" if f"--{e.opt}" in e.msg else f"-{e.opt}"
    matches = [k for k in fields_by_key if k.startswith(key)]

    # getopt's own messages for these leak its spec format ("count=, color=")
    if not e.opt:  # e.g. "--=x"
        return f"option {style(key, Styles.OPT)} not recognized"

    if key not in fields_by_key and len(matches) > 1:
        listed = ", ".join(style(k, Styles.OPT) for k in matches)
        return f"option {style(key, Styles.OPT)} is ambiguous: {listed}"

    return e.msg.replace(key, style(key, Styles.OPT))


def _convert(label: str, field: Field, raw: str) -> object:
    if field.choices:
        choices_by_raw = {str(choice): choice for choice in field.choices}

        if raw not in choices_by_raw:
            listed = ", ".join(
                style(raw_choice, LITERAL_TYPES[type(choice)])
                for raw_choice, choice in choices_by_raw.items()
            )
            msg = f"{style(label, field.label_style)} must be one of: {listed}"
            _fail(msg)
        return choices_by_raw[raw]

    try:
        return field.tp(raw)
    except ValueError:
        msg = (
            f"{style(label, field.label_style)} expects {style(field.tp.__name__, Styles.TYPE)}, "
            f"got {style(raw, Styles.STR)}"
        )
        _fail(msg)


def _parse_positionals(
    pos_fields: Sequence[Field],
    raw_positionals: Sequence[str],
) -> dict[str, object]:

    required = [field.name for field in pos_fields if field.is_required]

    if missing := required[len(raw_positionals) :]:
        noun = "positional" if len(missing) == 1 else "positionals"
        _fail(f"missing {noun}: {', '.join(style(name, Styles.POS) for name in missing)}")

    if extra := raw_positionals[len(pos_fields) :]:
        noun = "positional" if len(extra) == 1 else "positionals"
        _fail(f"unexpected {noun}: {', '.join(style(raw, Styles.STR) for raw in extra)}")

    return {
        field.name: _convert(field.name, field, raw)
        for field, raw in zip(pos_fields, raw_positionals, strict=False)
    }


def _fail(msg: str) -> NoReturn:
    sys.exit(f"{style(Fragments.ERROR_PREFIX, Styles.ERROR_PREFIX)}{msg}")
