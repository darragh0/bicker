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
    width: int = opt(800, short="-w", metavar="PX", description="Target width")
    fmt: Literal["png", "jpg"] = opt("png", short="-f", description="Output format")
    verbose: bool = flag(short="-v", description="Print progress")


args = parse_args(Args)
```

`args` is an `Args` instance, so your type checker knows `args.width` is an `int` and
`args.fmt` is `Literal["png", "jpg"]`.

```console
$ python resize.py -h
Usage: resize.py [-w PX] [-f {png,jpg}] [-v] src [dst]

Positionals:
  src                  Image to resize
  [dst]                Where to save it

Options:
  -w, --width PX       Target width
  -f, --fmt {png,jpg}  Output format
  -v, --verbose        Print progress
  -h, --help           Show this message and exit

$ python resize.py cat.jpg -f gif
error: -f must be one of: "png", "jpg"

Usage: resize.py [-w PX] [-f {png,jpg}] [-v] src [dst]
```

Output is colored in a terminal, unless `NO_COLOR` is set.

## Declaring arguments

| Declaration | Gives |
| --- | --- |
| `pos()` | A required positional |
| `pos(default)` | An optional positional (after the required ones) |
| `opt(default, short="-c")` | An option: `--name VALUE`, plus an optional short key |
| `opt()` | An option that's `None` unless given (annotate it `T \| None`) |
| `opt(required=True)` | A required option |
| `flag(short="-v")` | A `bool` option without a value, `False` unless given |

Each takes an optional `description=` for help. Options and flags also take `long=` to
change their long key (which defaults to the field name, with `_` as `-`), and options
take `metavar=` to change their placeholder in help.

**Types:** `str`, `int`, `float`, or a `Literal` of strings or ints (which only allows its
values). Annotate a field as `list[...]` of any of these to take several values:

```python
class Args:
    point: list[int] = pos(nargs=2)  # Exactly 2
    files: list[str] = pos()  # One or more: the remaining positionals
    tags: list[str] = opt([], short="-t")  # Repeatable: -t a -t b
    ids: list[int] = opt([], nargs=(1, 3))  # Given 1 to 3 times
```

A list positional must come last, unless `nargs` fixes its count.

Mistakes in the class itself (e.g. an unsupported type or a key used twice) raise
`TypeError` as soon as `parse_args` runs.

## Parsing

Command lines follow GNU conventions: options and positionals can be mixed, values can
be attached (`--width=400`, `-w400`), short flags can be grouped (`-vq`), long keys can be
shortened to any unambiguous prefix (`--wid`), and everything after `--` is a positional.

`parse_args` also takes `description=`, `epilog=` and `examples=` for the help page,
`version=` to add a `--version` option, and a few settings like `prog=` and `help_keys=`.
See its docstring for all of them.

## Not supported (yet)

- Subcommands
- Other value types (e.g. `Path`, `Enum`)
- Short-only options
- Custom colors

Feature requests are welcome: [open an issue](https://github.com/darragh0/bicker/issues).

## License

MIT
