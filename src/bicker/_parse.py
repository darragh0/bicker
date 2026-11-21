import sys
from dataclasses import MISSING, dataclass
from getopt import GetoptError, gnu_getopt
from typing import (
    TYPE_CHECKING,
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

from bicker._style import style

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


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


def _fields(spec: type[object], hints: Mapping[str, _Converter]) -> dict[str, _Field]:
    fields: dict[str, _Field] = {}

    for name in hints:
        field = getattr(spec, name, None)
        if not isinstance(field, _Field):
            msg = f"{name!r} must be declared with pos(), opt() or flag()"
            raise TypeError(msg)
        fields[name] = field

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

        # getopt's own message for this leaks its spec format ("count=, color=")
        if key not in names_by_key and len(matches) > 1:
            listed = ", ".join(style(k, "opt") for k in matches)
            _fail(f"option {style(key, 'opt')} is ambiguous: {listed}")

        _fail(e.msg.replace(key, style(key, "opt")))

    option_values: dict[str, object] = {}
    # raw in this context: str version of object (e.g., "3" = raw version of 3)
    for key, raw in option_pairs:
        name = names_by_key[key]
        option_values[name] = (
            True if hints[name] is bool else _convert(key, hints[name], raw, style_key="opt")
        )

    return option_values, raw_positionals


def _convert(label: str, tp: _Converter, raw: str, *, style_key: str) -> object:
    if get_origin(tp) is Literal:
        literals: tuple[object, ...] = get_args(tp)
        choices_by_raw = {str(choice): choice for choice in literals}

        if raw not in choices_by_raw:
            listed = ", ".join(
                style(raw_choice, type(choice).__name__)
                for raw_choice, choice in choices_by_raw.items()
            )
            msg = f"{style(label, style_key)} must be one of: {listed}"
            _fail(msg)
        return choices_by_raw[raw]

    try:
        return tp(raw)
    except ValueError:
        msg = (
            f"{style(label, style_key)} expects {style(tp.__name__, 'type')}, "
            f"got {style(raw, 'string')}"
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
        _fail(f"missing {noun}: {', '.join(style(name, 'pos') for name in missing)}")

    if extra := raw_positionals[len(positional_fields) :]:
        noun = "positional" if len(extra) == 1 else "positionals"
        _fail(f"unexpected {noun}: {', '.join(style(raw, 'str') for raw in extra)}")

    return {
        name: _convert(name, hints[name], raw, style_key="pos")
        for name, raw in zip(positional_fields, raw_positionals, strict=False)
    }


def _fail(msg: str) -> NoReturn:
    pre = style(None, "error_prefix")
    sys.exit(f"{pre}{msg}")
