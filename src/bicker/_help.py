import sys
from functools import partial
from typing import TYPE_CHECKING, TextIO

from bicker._style import Style, Styles, style, visible_len

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from bicker._spec import Field, HelpKey


def print_help(
    fields: Sequence[Field],
    *,
    prog: str,
    help_keys: Collection[HelpKey],
    help_description: str,
    description: str | None,
    epilog: str | None,
    examples: Sequence[str],
    use_shorthand_usage: bool,
) -> None:
    stream = sys.stdout
    st = partial(style, stream=stream)
    pad = "  "

    # Required positionals always precede optional ones, so pass is ordered correctly
    pos_entries = [
        (
            st(_pos_label(field), Styles.POS if field.is_required else Styles.OPTIONAL_POS),
            field.description,
        )
        for field in fields
        if field.is_pos
    ]

    opt_entries = [
        (
            _option_entry(field.short, field.long_key, field.style, field.metavar, stream),
            field.description,
        )
        for field in fields
        if not field.is_pos
    ]

    if help_keys:
        short = "-h" if "-h" in help_keys else None
        long = "--help" if "--help" in help_keys else None
        help_entry = _option_entry(short, long, Styles.FLAG, None, stream)
        opt_entries.append((help_entry, help_description))

    # Descriptions start in one column across both sections
    width = max((visible_len(entry) for entry, _ in pos_entries + opt_entries), default=0)
    pos_lines = [pad + _described(entry, desc, width) for entry, desc in pos_entries]
    opt_lines = [pad + _described(entry, desc, width) for entry, desc in opt_entries]

    sections = [
        format_usage(
            fields,
            prog=prog,
            stream=stream,
            use_shorthand=use_shorthand_usage,
        )
    ]
    if description:
        sections.append(description)
    if pos_lines:
        sections.append("\n".join([st("Positionals", Styles.HEADING), *pos_lines]))
    if opt_lines:
        sections.append("\n".join([st("Options", Styles.HEADING), *opt_lines]))
    if examples:
        example_lines = [pad + _styled_example(ex, prog, fields, stream) for ex in examples]
        sections.append("\n".join([st("Examples", Styles.HEADING), *example_lines]))
    if epilog:
        sections.append(epilog)

    print("\n\n".join(sections))


def format_usage(
    fields: Sequence[Field],
    *,
    prog: str,
    stream: TextIO,
    use_shorthand: bool = False,
) -> str:
    """Build the usage line, styled for `stream` (stdout for help, stderr for errors)."""
    st = partial(style, stream=stream)
    option_fields = [field for field in fields if not field.is_pos]

    # Required positionals always precede optional ones, so pass is ordered correctly
    positionals = [
        st(_pos_label(field), Styles.POS if field.is_required else Styles.USAGE_OPTIONAL_POS)
        for field in fields
        if field.is_pos
    ]

    if use_shorthand:
        options = [st("options", Styles.USAGE_OPT)] if option_fields else []
    else:
        # "..." after a list option: it can be repeated
        options = [
            st(_usage_option(field, stream), Styles.USAGE_OPT) + ("..." if field.is_list else "")
            for field in option_fields
        ]

    return " ".join([st("Usage", Styles.HEADING), st(prog, Styles.PROG), *options, *positionals])


def _usage_option(field: Field, stream: TextIO) -> str:
    """`-v`, `-c COUNT` or `--color {red,blue}`: short key if set, plus a placeholder."""
    st = partial(style, stream=stream)
    key = st(field.short or field.long_key, field.style)
    return f"{key} {st(field.metavar, Styles.METAVAR)}" if field.metavar else key


def _option_entry(
    short: str | None,
    long: str | None,
    style_: Style,
    metavar: str | None,
    stream: TextIO,
) -> str:
    """`-c, --count COUNT`, `    --color {a,b}` or `-h`, with long keys in one column."""
    st = partial(style, stream=stream)
    # Shorts are always 2 chars ("-c"), so "-c, " or 4 spaces lines up every long key
    short_col = (st(short, style_) + (", " if long else "")) if short else "    "
    long_col = st(long, style_) if long else ""
    value = f" {st(metavar, Styles.METAVAR)}" if metavar else ""
    return short_col + long_col + value


def _described(entry: str, description: str | None, width: int) -> str:
    """Append `description` after `entry`, padded so descriptions start at `width` + 2."""
    if not description:
        return entry
    return entry + " " * (width - visible_len(entry) + 2) + description


def _styled_example(example: str, prog: str, fields: Sequence[Field], stream: TextIO) -> str:
    """Prefix `prog` and style known keys (e.g. `-w`) as in the options list; leave the rest."""
    st = partial(style, stream=stream)
    styles_by_key = {field.long_key: field.style for field in fields if not field.is_pos}
    styles_by_key |= {field.short: field.style for field in fields if field.short}
    words = [
        st(word, styles_by_key[word]) if word in styles_by_key else word for word in example.split()
    ]
    return " ".join([st(prog, Styles.PROG), *words])


def _pos_label(field: Field) -> str:
    """Return the positional's name, plus `...` if it takes all remaining values."""
    return field.name + ("..." if field.is_list else "")
