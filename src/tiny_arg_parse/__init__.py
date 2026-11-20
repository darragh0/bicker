import sys
from collections.abc import Sequence
from typing import Final, Literal, NoReturn, Protocol, get_args, get_origin, get_type_hints

__all__: Final = ["parse_args"]


class _Converter(Protocol):
    __name__: str

    def __call__(self, raw: str, /) -> object: ...


def parse_args[T](spec: type[T], argv: Sequence[str] | None = None) -> T:
    hints: dict[str, _Converter] = get_type_hints(spec)
    flags = [name for name, tp in hints.items() if tp is bool]
    positionals = [name for name in hints if name not in flags and not hasattr(spec, name)]
    values: dict[str, object] = {name: getattr(spec, name) for name in hints if name not in positionals}
    values |= dict.fromkeys(flags, False)

    tokens = list(sys.argv[1:] if argv is None else argv)
    given: list[str] = []
    while tokens:
        token = tokens.pop(0)
        if not token.startswith("--"):
            given.append(token)
            continue
        name = token[2:].replace("-", "_")
        if name not in values:
            _fail(f"unknown option {token}")
        if name in flags:
            values[name] = True
        elif not tokens:
            _fail(f"{token} expects a value")
        else:
            values[name] = _convert(token, hints[name], tokens.pop(0))

    if len(given) != len(positionals):
        _fail(f"expected {len(positionals)} positional(s) ({', '.join(positionals)}), got {len(given)}")
    values |= {name: _convert(name, hints[name], raw) for name, raw in zip(positionals, given)}

    args = object.__new__(spec)
    for name, value in values.items():
        setattr(args, name, value)
    return args


def _convert(label: str, tp: _Converter, raw: str) -> object:
    if get_origin(tp) is Literal:
        choices: tuple[object, ...] = get_args(tp)
        for choice in choices:
            if raw == str(choice):
                return choice
        _fail(f"{label} must be one of: {', '.join(map(str, choices))}")
    try:
        return tp(raw)
    except ValueError:
        _fail(f"{label} expects {tp.__name__}, got {raw!r}")


def _fail(msg: str) -> NoReturn:
    sys.exit(f"error: {msg}")
