import os
import re
import sys
from typing import Final, NamedTuple, TextIO, final

_RESET: Final = "\x1b[0m"
_ANSI_CODE: Final = re.compile(r"\x1b\[[0-9;]*m")


@final
class Style(NamedTuple):
    code: str
    fmt: str = "{}"


@final
class Styles:
    PROG: Final = Style("1;96")
    POS: Final = Style("96")
    OPTIONAL_POS: Final = Style("96", "[{}]")
    OPT: Final = Style("96")
    FLAG: Final = Style("96")
    TYPE: Final = Style("94")
    STR_VALUE: Final = Style("32", '"{}"')
    INT_VALUE: Final = Style("34")
    METAVAR: Final = Style("2;96")
    ELLIPSIS: Final = Style("96", "{}")
    VERSION: Final = Style("92")
    # --------------------------------------------
    ERROR_PREFIX: Final = Style("91", "{}:")
    HEADING: Final = Style("92;1", "{}:")
    USAGE_OPTIONAL_POS: Final = Style("2;96", "[{}]")
    USAGE_OPT: Final = Style("96;2", "[{}]")


def style(text: str, style_: Style, stream: TextIO | None = None) -> str:
    out = stream or sys.stderr
    use_color = out is not None and out.isatty() and not os.environ.get("NO_COLOR")
    fmted = style_.fmt.format(text)

    if not use_color:
        return fmted

    start = f"\x1b[{style_.code}m"
    # Re-apply style after any inner reset, so nested styles don't cancel the outer one
    return start + fmted.replace(_RESET, _RESET + start) + _RESET


def visible_len(text: str) -> int:
    """Length as rendered in a terminal, ignoring color codes."""
    return len(_ANSI_CODE.sub("", text))
