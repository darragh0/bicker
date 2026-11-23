# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-11-23

Initial release.

- Declare arguments as a class with `pos()`, `opt()` and `flag()`; `parse_args()` returns a typed instance
- `str`, `int`, `float` and `Literal` values, plus lists with `nargs`
- GNU-style parsing: `--key=value`, grouped short flags, unambiguous prefixes and `--`
- Help page with descriptions, examples and an epilog; usage shown after errors
- Colored output on terminals, respecting `NO_COLOR`
- Python 3.12+, no dependencies

[1.0.0]: https://github.com/darragh0/bicker/releases/tag/v1.0.0
