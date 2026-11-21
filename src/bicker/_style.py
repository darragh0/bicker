from enum import Enum
from os import environ
from sys import stderr, stdout
from typing import Final

_STYLE_MAP: Final = {
    "prog": ("1;96", "{}"),
    "pos": ("96", "{}"),
    "optional_pos": ("2;96", "[{}]"),
    "opt": ("96", "{}"),
    "type": ("95", "{}"),
    "str": ("32", '"{}"'),
    "int": ("34", "{}"),
    "error_prefix": ("91", "error: "),
}


class _OutStream(Enum):
    STDOUT = stdout
    STDERR = stderr


def style(text: str | None, key: str, stream: _OutStream = _OutStream.STDERR) -> str:
    use_color = stream.value.isatty() and not environ.get("NO_COLOR")
    # Unknown keys (e.g. a type name like "bool") fall back to plain value styling
    code, fmt = _STYLE_MAP.get(key, _STYLE_MAP["str"])
    fmted = fmt if text is None else fmt.format(text)
    return f"\x1b[{code}m{fmted}\x1b[0m" if use_color else fmted
