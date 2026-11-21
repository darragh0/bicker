import os
import sys
from typing import Final, NamedTuple, TextIO, final


@final
class Style(NamedTuple):
    code: str
    fmt: str = "{}"


@final
class Styles:
    PROG: Final = Style("1;96")
    POS: Final = Style("96")
    OPTIONAL_POS: Final = Style("2;96", "[{}]")
    OPT: Final = Style("96")
    TYPE: Final = Style("95")
    STR: Final = Style("32", '"{}"')
    INT: Final = Style("34")
    ERROR_PREFIX: Final = Style("91")


def style(text: str, style_: Style, stream: TextIO | None = None) -> str:
    # Looked up per call so redirected streams (pytest, redirect_stderr) are respected;
    # sys.stderr is None when there's no console (e.g. pythonw)
    out = stream or sys.stderr
    use_color = out is not None and out.isatty() and not os.environ.get("NO_COLOR")
    formatted = style_.fmt.format(text)
    return f"\x1b[{style_.code}m{formatted}\x1b[0m" if use_color else formatted
