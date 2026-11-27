"""Tiny, fully typed command-line argument parsing: declare your arguments as a class.

Example:
    ```python
    from typing import Literal

    from bicker import flag, opt, parse_args, pos


    class Args:
        src: str = pos(description="Image to resize")
        width: int = opt(800, short="-w", description="Target width in pixels")
        fmt: Literal["png", "jpg"] = opt("png", short="-f")
        verbose: bool = flag(short="-v")


    args = parse_args(Args)
    args.fmt  # Type checkers see Literal["png", "jpg"]
    ```
"""

from typing import Final

from bicker._declare import Nargs, cmd, command, flag, opt, pos
from bicker._help import HelpKey, VersionKey
from bicker._parse import parse_args

__all__: Final = [
    "HelpKey",
    "Nargs",
    "VersionKey",
    "cmd",
    "command",
    "flag",
    "opt",
    "parse_args",
    "pos",
]
