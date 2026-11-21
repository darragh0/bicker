from typing import Literal

from bicker import flag, opt, parse_args, pos


class Args:
    file: int = pos()
    out: int = pos(3)
    count: int = opt(1, "-c")
    color: Literal[3, "pink", "blue"] = opt(3)
    verbose: bool = flag("-v")


args = parse_args(Args)
