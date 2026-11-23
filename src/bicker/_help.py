from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TextIO, final

from bicker._style import Style, Styles, style, visible_len

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence

    from bicker._spec import Field, HelpKey

_PAD: Final = "  "


@final
@dataclass(frozen=True, kw_only=True)
class HelpConfig:
    """The `parse_args` settings that shape help and usage output."""

    prog: str
    help_keys: Collection[HelpKey]
    help_description: str
    description: str | None
    epilog: str | None
    examples: Sequence[str]
    use_shorthand_usage: bool


@final
class HelpRenderer:
    """Build help and usage text, styled for `stream` (stdout for help, stderr for errors)."""

    def __init__(self, fields: Sequence[Field], cfg: HelpConfig, stream: TextIO) -> None:
        self._cfg = cfg
        self._stream = stream
        # Required positionals always precede optional ones, so these are in display order
        self._positionals = [field for field in fields if field.is_pos]
        self._options = [field for field in fields if not field.is_pos]

    def help(self) -> str:
        cfg = self._cfg
        pos_entries = [
            (self._pos_label(field, Styles.OPTIONAL_POS), field.description)
            for field in self._positionals
        ]
        opt_entries = [
            (self._option_entry(field.keys, field.style, field.metavar), field.description)
            for field in self._options
        ]
        if cfg.help_keys:
            help_entry = self._option_entry(cfg.help_keys, Styles.FLAG, None)
            opt_entries.append((help_entry, cfg.help_description))

        # Descriptions start in one column across both sections
        width = max((visible_len(entry) for entry, _ in pos_entries + opt_entries), default=0)

        sections = [self.usage()]
        if cfg.description:
            sections.append(cfg.description)
        if pos_entries:
            lines = [_described(entry, desc, width) for entry, desc in pos_entries]
            sections.append(self._section("Positionals", lines))
        if opt_entries:
            lines = [_described(entry, desc, width) for entry, desc in opt_entries]
            sections.append(self._section("Options", lines))
        if cfg.examples:
            sections.append(self._section("Examples", map(self._example, cfg.examples)))
        if cfg.epilog:
            sections.append(cfg.epilog)
        return "\n\n".join(sections)

    def usage(self) -> str:
        if not self._options:
            options = []
        elif self._cfg.use_shorthand_usage:
            options = [self._st("options", Styles.USAGE_OPT)]
        else:
            # "..." after a list option: it can be repeated
            options = [
                self._st(self._usage_option(field), Styles.USAGE_OPT)
                + ("..." if field.is_list else "")
                for field in self._options
            ]
        positionals = [
            self._pos_label(field, Styles.USAGE_OPTIONAL_POS) for field in self._positionals
        ]
        heading = [self._st("Usage", Styles.HEADING), self._st(self._cfg.prog, Styles.PROG)]
        return " ".join([*heading, *options, *positionals])

    def _st(self, text: str, style_: Style) -> str:
        return style(text, style_, self._stream)

    def _section(self, title: str, lines: Iterable[str]) -> str:
        return "\n".join([self._st(title, Styles.HEADING), *(_PAD + line for line in lines)])

    def _pos_label(self, field: Field, optional_style: Style) -> str:
        """Style the positional's name, plus `...` if it takes many values."""
        label = field.name + ("..." if field.is_list else "")
        return self._st(label, Styles.POS if field.is_required else optional_style)

    def _usage_option(self, field: Field) -> str:
        """`-v`, `-c COUNT` or `--color {red,blue}`: the first key, plus a placeholder."""
        key = self._st(field.keys[0], field.style)
        return f"{key} {self._st(field.metavar, Styles.METAVAR)}" if field.metavar else key

    def _option_entry(self, keys: Collection[str], style_: Style, metavar: str | None) -> str:
        """`-c, --count COUNT`, `    --color {a,b}` or `-h`, with long keys in one column."""
        ordered = sorted(keys, key=len)  # Short first
        # Shorts are always 2 chars ("-c"), so "-c, " or 4 spaces lines up every long key
        indent = "    " if ordered[0].startswith("--") else ""
        entry = indent + ", ".join(self._st(key, style_) for key in ordered)
        return entry + (f" {self._st(metavar, Styles.METAVAR)}" if metavar else "")

    def _example(self, example: str) -> str:
        """Prefix `prog` and style known keys (e.g. `-w`) as in the options list."""
        styles_by_key = {key: field.style for field in self._options for key in field.keys}
        words = [
            self._st(word, styles_by_key[word]) if word in styles_by_key else word
            for word in example.split()
        ]
        return " ".join([self._st(self._cfg.prog, Styles.PROG), *words])


def _described(entry: str, description: str | None, width: int) -> str:
    """Append `description` after `entry`, padded so descriptions start at `width` + 2."""
    if not description:
        return entry
    return entry + " " * (width - visible_len(entry) + 2) + description
