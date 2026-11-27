"""Edit images: a tour of bicker's features. Try `uv run demo.py -h` and `demo.py resize -h`."""

from typing import Literal

from bicker import cmd, flag, opt, parse_args, pos


class Resize:
    """Resize an image and save it in another format."""

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


class ShowInfo:
    """Print an image's size and format."""

    files: list[str] = pos(description="Images to inspect")


# Commands: one class each; the name is the class name in kebab-case (`ShowInfo` -> `show-info`)
type Command = Resize | ShowInfo


class Args:
    # Flags: False unless given. Options declared here work before or after the command
    verbose: bool = flag(short="-v", description="Print what's happening")
    dry_run: bool = flag(long="--dry", description="Don't write anything")

    command: Command = cmd()


args = parse_args(
    Args,
    use_shorthand_usage=True,
    description="Edit images from the command line.",
    examples=[
        "resize cat.jpg -w 400",
        "-v resize cat.jpg small.webp -w 400 -f webp",
        "show-info a.png b.png",
    ],
    version="1.0.0",
)

# The type checker knows every attribute's type, and `match` narrows the command's
match args.command:
    case Resize() as resize:
        height = "auto" if resize.height is None else f"{resize.height}px"  # `int | None`
        print(f"{resize.src} -> {resize.dst} ({resize.fmt}, {resize.width}px x {height})")
        if resize.tags:
            print("tags:", ", ".join(resize.tags))
    case ShowInfo(files=files):
        for file in files:
            print(f"{file}: 800x600 png")

if args.verbose:
    print("verbose on" + (", dry run" if args.dry_run else ""))
