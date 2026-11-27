"""Resize images: a tour of bicker's features. Try `uv run demo.py -h`."""

from typing import Literal

from bicker import flag, opt, parse_args, pos


class Args:
    # Positionals: required by default; optional ones (with a default) come after
    src: str = pos(description="Image to resize")
    dst: str = pos("out.png", description="Where to save the result")

    # Options: a default, `None` unless given, or required; long key defaults to --name.
    # `group=` lists them under their own heading in help
    width: int = opt(
        required=True, short="-w", metavar="PX", description="Target width", group="Size"
    )
    height: int | None = opt(short="-H", metavar="PX", description="Target height", group="Size")
    scale: float = opt(1.0, description="Extra scale factor", group="Size")
    fmt: Literal["png", "jpg", "webp"] = opt(
        "png", short="-f", description="Output format", group="Output"
    )
    tags: list[str] = opt(
        [], short="-t", metavar="TAG", description="Tag to add (repeatable)", group="Output"
    )

    # Flags: False unless given
    verbose: bool = flag(short="-v", description="Print what's happening")
    dry_run: bool = flag(long="--dry", description="Don't write anything")


args = parse_args(
    Args,
    use_shorthand_usage=True,
    description="Resize an image and save it in another format.",
    examples=["cat.jpg -w 400", "cat.jpg small.webp -w 400 -H 300 -f webp -t pet -v"],
    version="1.0.0",
)

# The type checker knows every attribute's type, e.g. `args.height` is `int | None`
height = "auto" if args.height is None else f"{args.height}px"
print(f"{args.src} -> {args.dst} ({args.fmt}, {args.width}px x {height}, x{args.scale})")
if args.tags:
    print("tags:", ", ".join(args.tags))
if args.verbose:
    print("verbose on" + (", dry run" if args.dry_run else ""))
