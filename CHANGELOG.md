# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.1.0] - 2026-11-27

### Added

- Help shows defaults, e.g. `[default: 800]`; turn it off with `parse_args(..., show_defaults=False)`
- Help descriptions wrap at the terminal width

## [2.0.0] - 2026-11-27

### Added

- `parse_args(..., version="1.2.0")` adds a `--version` option that prints the program name and version; `version_keys=`
  adds `-V`
- Required options: `opt(required=True)`
- Options without a default: `name: str | None = opt()` is `None` unless given
- `group=` on `opt()` and `flag()` lists them under their own heading in help
- Short-only options and flags: `opt(1, short="-O", long=False)`
- Commands: `command: Build | Test = cmd()`, including nested commands; optional with `| None`, and renamed or aliased
  with `@command("ls", aliases=("l",))`

### Changed

- **Breaking:** `short` is keyword-only in `opt()` and `flag()`: `opt(1, short="-c")`
- `help_keys` is now typed as a `Sequence`, so mypy accepts one-key tuples like `("-h",)`

### Fixed

- Fields typed with a `type X = ...` alias (e.g. `type Mode = Literal[...]`) were rejected as unsupported

## [1.0.0] - 2026-11-23

Initial release.

- Declare arguments as a class with `pos()`, `opt()` and `flag()`; `parse_args()` returns a typed instance
- `str`, `int`, `float` and `Literal` values, plus lists with `nargs`
- GNU-style parsing: `--key=value`, grouped short flags, unambiguous prefixes and `--`
- Help page with descriptions, examples and an epilog; usage shown after errors
- Colored output on terminals, respecting `NO_COLOR`
- Python 3.12+, no dependencies

[Unreleased]: https://github.com/darragh0/bicker/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/darragh0/bicker/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/darragh0/bicker/compare/v1.0.0...v2.0.0
