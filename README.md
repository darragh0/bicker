# bicker

[![PyPI](https://img.shields.io/pypi/v/bicker)](https://pypi.org/project/bicker/)
[![Python](https://img.shields.io/pypi/pyversions/bicker)](https://pypi.org/project/bicker/)
[![CI](https://github.com/darragh0/bicker/actions/workflows/ci.yml/badge.svg)](https://github.com/darragh0/bicker/actions/workflows/ci.yml)

Tiny, fully typed CLI argument parser: declare your args as a class.

```sh
pip install bicker
```

No dependencies.

## Usage

```python
from typing import Literal

from bicker import flag, opt, parse_args, pos


class Args:
    src: str = pos(description="Image to resize")
    dst: str = pos("out.png", description="Where to save it")
    width: int = opt(required=True, short="-w", metavar="PX", description="Target width")
    height: int | None = opt(short="-H", metavar="PX", description="Target height")
    fmt: Literal["png", "jpg"] = opt("png", short="-f", description="Output format")
    verbose: bool = flag(short="-v", description="Print progress")


args = parse_args(Args)
```

`args` is an instance of `Args`, so type checkers know `args.height` is `int | None` and `args.fmt` is
`Literal["png", "jpg"]`.

```console
$ python resize.py -h
Usage: resize.py -w PX [-H PX] [-f {png,jpg}] [-v] src [dst]

Positionals:
  src                  Image to resize
  [dst]                Where to save it

Options:
  -w, --width PX       Target width
  -H, --height PX      Target height
  -f, --fmt {png,jpg}  Output format
  -v, --verbose        Print progress
  -h, --help           Show this message and exit

$ python resize.py cat.jpg -w 400 -f gif
error: -f must be one of: "png", "jpg"

Usage: resize.py -w PX [-H PX] [-f {png,jpg}] [-v] src [dst]
```

Output is colored in a terminal, unless `NO_COLOR` is set.

## Declaring arguments

| Declaration                | Gives                                                       |
| -------------------------- | ----------------------------------------------------------- |
| `pos()`                    | Required positional                                         |
| `pos(default)`             | Optional positional (after required ones)                   |
| `opt(default, short="-c")` | Option: `--name VALUE`, plus an optional short key          |
| `opt()`                    | Option that's `None` unless given (annotate it `T \| None`) |
| `opt(required=True)`       | Required option                                             |
| `flag(short="-v")`         | `bool` option with no value: `False` unless given           |

Each also takes:

- `description=`: its help text
- `long=` (options and flags): its long key -- defaults to the field name with `_` as `-`; `long=False` for a short-only
  one
- `metavar=` (options): its value's placeholder in help
- `group=` (options and flags): the help heading it's listed under, `Options` by default

**Types:** `str`, `int`, `float`, or a `Literal` of string/int values. Annotate a field as `list[...]` of any of these
to take several values:

```python
class Args:
    point: list[int] = pos(nargs=2)  # Exactly 2
    files: list[str] = pos()  # One or more: the remaining positionals
    tags: list[str] = opt([], short="-t")  # Repeatable: -t a -t b
    ids: list[int] = opt([], nargs=(1, 3))  # Given 1 to 3 times
```

A list positional must come last, unless `nargs` fixes its count.

Mistakes in the class itself (e.g. an unsupported type or a key used twice) raise `TypeError` as soon as `parse_args`
runs.

## Commands

Declare each command as a class, and the command field with `cmd()`:

```python
from bicker import cmd, flag, parse_args, pos


class Build:
    """Build the project."""

    release: bool = flag(short="-r")


class Test:
    """Run the tests."""

    pattern: str | None = pos(None)


class Args:
    verbose: bool = flag(short="-v")
    command: Build | Test = cmd()


args = parse_args(Args)
match args.command:
    case Build(release=release):
        print("release build" if release else "debug build")
    case Test(pattern=pattern):
        print(f"testing {pattern or 'everything'}")
```

- A command's name is its class name in kebab-case (`RunTests` is `run-tests`), or set it with
  `@command("ls", aliases=("l",))`
- Its docstring is its help text
- Global options (like `-v`) can go before or after it
- Add `| None` to make the command optional
- Commands can have their own subcommands

## Parsing

CLI parsing follows GNU conventions:

- Options and positionals can be mixed
- Values can be attached: `--width=400`, `-w400`
- Short flags can be grouped: `-vq`
- Long keys can be shortened to any unambiguous prefix: `--wid`
- Everything after `--` is a positional

`parse_args` takes `description=`, `epilog=` and `examples=` for the help page, `version=` to add a `--version` option,
and other settings like `prog=` and `help_keys=`. See docstring for more.

## Not supported (yet)

- Other value types (e.g. `Path`, `Enum`)
- Custom colors

Feature requests are welcome: [open an issue](https://github.com/darragh0/bicker/issues).

## License

MIT
