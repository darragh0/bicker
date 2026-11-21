import re
import sys
from collections import Counter
from dataclasses import MISSING, dataclass
from getopt import GetoptError, gnu_getopt
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    NoReturn,
    Protocol,
    cast,
    final,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)

from bicker._style import Style, Styles, style, style_value

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


# Supported value types; bool is supported separately, for flags only
_SCALAR_TYPES: Final[tuple[type, ...]] = (str, int, float)
_LITERAL_TYPES: Final[tuple[type, ...]] = (str, int)


class _Converter(Protocol):
    __name__: str

    def __call__(self, raw: str, /) -> object: ...


@final
@dataclass(frozen=True, kw_only=True)
class _Field:
    default: object
    short: str | None = None
    is_pos: bool = False


# T only in the return type is intentional: it's inferred from the field's annotation
@overload
def pos[T]() -> T: ...  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T) -> T: ...
def pos(default: object = MISSING) -> object:
    return _Field(default=default, is_pos=True)


def opt[T](default: T, short: str | None = None) -> T:
    return cast("T", _Field(default=default, short=short))


def flag(short: str | None = None) -> bool:
    return opt(default=False, short=short)


def parse_args[T](spec: type[T], argv: Sequence[str] | None = None) -> T:
    hints: dict[str, _Converter] = get_type_hints(spec)

    fields = _fields(spec, hints)
    positional_fields = {name: field for name, field in fields.items() if field.is_pos}
    option_fields = {name: field for name, field in fields.items() if not field.is_pos}

    option_values, raw_positionals = _parse_options(
        option_fields, hints, sys.argv[1:] if argv is None else argv
    )
    positional_values = _parse_positionals(positional_fields, hints, raw_positionals)

    values = {name: field.default for name, field in fields.items()}
    values |= option_values
    values |= positional_values

    args = spec()
    for name, value in values.items():
        setattr(args, name, value)
    return args


def _fields(spec: type[object], hints: Mapping[str, object]) -> dict[str, _Field]:
    fields: dict[str, _Field] = {}

    for name, tp in hints.items():
        field = getattr(spec, name, None)
        if not isinstance(field, _Field):
            msg = f"{name!r} must be declared with pos(), opt() or flag()"
            raise TypeError(msg)

        literal_args: tuple[object, ...] = get_args(tp) if get_origin(tp) is Literal else ()
        supported = (
            (isinstance(tp, type) and tp in _SCALAR_TYPES)
            or (tp is bool and not field.is_pos)
            or (literal_args and all(type(arg) in _LITERAL_TYPES for arg in literal_args))
        )
        if not supported:
            scalars = ", ".join(t.__name__ for t in _SCALAR_TYPES)
            literals = "/".join(t.__name__ for t in _LITERAL_TYPES)
            msg = (
                f"{name!r} has unsupported type {tp!r} "
                f"(supported: {scalars}, Literal of {literals}, and bool for flags)"
            )
            raise TypeError(msg)

        short = field.short
        if short is not None and not re.fullmatch(r"-[A-Za-z0-9]", short):
            msg = f"{name!r} has invalid short {short!r} (expected '-' plus one letter or digit)"
            raise TypeError(msg)

        fields[name] = field

    shorts = Counter(field.short for field in fields.values() if field.short)
    if duplicates := [short for short, count in shorts.items() if count > 1]:
        msg = f"short options used more than once: {', '.join(duplicates)}"
        raise TypeError(msg)

    # False (required) sorts before True (optional)
    is_optional = [field.default is not MISSING for field in fields.values() if field.is_pos]
    if is_optional != sorted(is_optional):
        msg = "required positionals must precede optional ones"
        raise TypeError(msg)

    return fields


def _parse_options(
    option_fields: Mapping[str, _Field],
    hints: Mapping[str, _Converter],
    argv: Sequence[str],
) -> tuple[dict[str, object], list[str]]:

    names_by_key = {f"--{name.replace('_', '-')}": name for name in option_fields}
    names_by_key |= {field.short: name for name, field in option_fields.items() if field.short}

    # getopt's spec format: short "c:" / long "count=" mean the option takes a value
    shorts = "".join(
        k[1] + ("" if hints[n] is bool else ":")
        for k, n in names_by_key.items()
        if not k.startswith("--")
    )
    longs = [
        k[2:] + ("" if hints[n] is bool else "=")
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
        option_values[name] = (
            True if hints[name] is bool else _convert(key, hints[name], raw, label_style=Styles.OPT)
        )

    return option_values, raw_positionals


def _convert(label: str, tp: _Converter, raw: str, *, label_style: Style) -> object:
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
    positional_fields: Mapping[str, _Field],
    hints: Mapping[str, _Converter],
    raw_positionals: Sequence[str],
) -> dict[str, object]:

    required = [name for name, field in positional_fields.items() if field.default is MISSING]

    if missing := required[len(raw_positionals) :]:
        noun = "positional" if len(missing) == 1 else "positionals"
        _fail(f"missing {noun}: {', '.join(style(name, Styles.POS) for name in missing)}")

    if extra := raw_positionals[len(positional_fields) :]:
        noun = "positional" if len(extra) == 1 else "positionals"
        _fail(f"unexpected {noun}: {', '.join(style(raw, Styles.STR) for raw in extra)}")

    return {
        name: _convert(name, hints[name], raw, label_style=Styles.POS)
        for name, raw in zip(positional_fields, raw_positionals, strict=False)
    }


def _fail(msg: str) -> NoReturn:
    sys.exit(f"{style('error:', Styles.ERROR_PREFIX)} {msg}")
