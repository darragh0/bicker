"""Resize images: a tour of bicker's features. Try `uv run demo.py -h`."""

from typing import Literal

from bicker import flag, opt, parse_args, pos


class Args:
    # Positionals: required ones come first, optional ones (with a default) after
    src: str = pos(description="Image to resize")
    dst: str = pos("out.png", description="Where to save the result")

    # Options: a default, an optional short key, and optional metavar/description
    width: int = opt(800, "-w", metavar="PX", description="Target width in pixels")
    scale: float = opt(1.0, description="Extra scale factor")
    fmt: Literal["png", "jpg", "webp"] = opt("png", "-f", description="Output format")

    # Flags: False unless given
    verbose: bool = flag("-v", description="Print what's happening")
    dry_run: bool = flag(description="Don't write anything")


args = parse_args(
    Args,
    description="Resize an image and save it in another format.",
    examples=["cat.jpg", "cat.jpg small.webp -w 400 -f webp -v"],
)

# The type checker knows every attribute's type, e.g. `args.fmt` is Literal["png", "jpg", "webp"]
print(f"{args.src} -> {args.dst} ({args.fmt}, {args.width}px x {args.scale})")
if args.verbose:
    print("verbose on" + (", dry run" if args.dry_run else ""))
