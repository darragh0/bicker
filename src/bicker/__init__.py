"""Tiny, fully typed command-line argument parsing: declare your arguments as a class.

Example:
    ```python
    from typing import Literal

    from bicker import flag, opt, parse_args, pos


    class Args:
        src: str = pos(description="Image to resize")
        width: int = opt(800, "-w", description="Target width in pixels")
        fmt: Literal["png", "jpg"] = opt("png", "-f")
        verbose: bool = flag("-v")


    args = parse_args(Args)
    args.fmt  # Type checkers see Literal["png", "jpg"]
    ```
"""

from typing import Final

from bicker._parse import parse_args
from bicker._spec import HelpKey, Nargs, VersionKey, flag, opt, pos

__all__: Final = ["HelpKey", "Nargs", "VersionKey", "flag", "opt", "parse_args", "pos"]
