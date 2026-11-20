import sys
from collections.abc import Mapping, Sequence
from dataclasses import MISSING, dataclass
from getopt import GetoptError, gnu_getopt
from typing import Final, Literal, NoReturn, Protocol, cast, get_args, get_origin, get_type_hints, overload

__all__: Final = ["flag", "opt", "parse_args", "pos"]


class _Converter(Protocol):
    __name__: str

    def __call__(self, raw: str, /) -> object: ...


@dataclass(frozen=True)
class _Field:
    default: object
    short: str | None = None
    positional: bool = False


# T only in the return type is intentional: it's inferred from the field's annotation
@overload
def pos[T]() -> T: ...  # pyright: ignore[reportInvalidTypeVarUse]
@overload
def pos[T](default: T) -> T: ...
def pos(default: object = MISSING) -> object:
    return _Field(default, positional=True)


def opt[T](default: T, short: str | None = None) -> T:
    return cast("T", _Field(default, short))


def flag(short: str | None = None) -> bool:
    return opt(False, short)


def parse_args[T](spec: type[T], argv: Sequence[str] | None = None) -> T:
    hints: dict[str, _Converter] = get_type_hints(spec)

    fields = _fields(spec, hints)
    positional_fields = {name: field for name, field in fields.items() if field.positional}
    option_fields = {name: field for name, field in fields.items() if not field.positional}

    option_values, raw_positionals = _parse_options(option_fields, hints, sys.argv[1:] if argv is None else argv)
    positional_values = _parse_positionals(positional_fields, hints, raw_positionals)

    values = {name: field.default for name, field in fields.items()}
    values |= option_values
    values |= positional_values

    args = spec()
    for name, value in values.items():
        setattr(args, name, value)
    return args


def _fields(spec: type, hints: Mapping[str, _Converter]) -> dict[str, _Field]:
    fields: dict[str, _Field] = {}

    for name in hints:
        field = getattr(spec, name, None)
        if not isinstance(field, _Field):
            raise TypeError(f"{name!r} must be declared with pos(), opt() or flag()")
        fields[name] = field

    # False (required) sorts before True (optional)
    is_optional = [field.default is not MISSING for field in fields.values() if field.positional]
    if is_optional != sorted(is_optional):
        raise TypeError("required positionals must precede optional ones")

    return fields


def _parse_options(
    option_fields: Mapping[str, _Field],
    hints: Mapping[str, _Converter],
    argv: Sequence[str],
) -> tuple[dict[str, object], list[str]]:

    names_by_key = {f"--{name.replace('_', '-')}": name for name in option_fields}
    names_by_key |= {field.short: name for name, field in option_fields.items() if field.short}

    # getopt's spec format: short "c:" / long "count=" mean the option takes a value
    shorts = ""
    longs: list[str] = []
    for key, name in names_by_key.items():
        takes_value = hints[name] is not bool
        if key.startswith("--"):
            longs.append(key[2:] + ("=" if takes_value else ""))
        else:
            shorts += key[1] + (":" if takes_value else "")

    try:
        option_pairs, raw_positionals = gnu_getopt(argv, shorts, longs)
    except GetoptError as e:
        _fail(str(e))

    option_values: dict[str, object] = {}
    for key, raw in option_pairs:
        name = names_by_key[key]
        option_values[name] = True if hints[name] is bool else _convert(key, hints[name], raw)

    return option_values, raw_positionals


def _parse_positionals(
    positional_fields: Mapping[str, _Field],
    hints: Mapping[str, _Converter],
    raw_positionals: Sequence[str],
) -> dict[str, object]:

    required = [name for name, field in positional_fields.items() if field.default is MISSING]

    too_few = len(raw_positionals) < len(required)
    too_many = len(raw_positionals) > len(positional_fields)
    if too_few or too_many:
        usage = " ".join(name if name in required else f"[{name}]" for name in positional_fields)
        _fail(f"expected positionals: {usage}")

    return {name: _convert(name, hints[name], raw) for name, raw in zip(positional_fields, raw_positionals)}


def _convert(label: str, tp: _Converter, raw: str) -> object:
    if get_origin(tp) is Literal:
        literals: tuple[object, ...] = get_args(tp)
        str_choices = {str(choice): choice for choice in literals}

        if raw not in str_choices:
            _fail(f"{label} must be one of: {', '.join(str_choices)}")
        return str_choices[raw]

    try:
        return tp(raw)
    except ValueError:
        _fail(f"{label} expects {tp.__name__}, got {raw!r}")


def _fail(msg: str) -> NoReturn:
    sys.exit(f"error: {msg}")
