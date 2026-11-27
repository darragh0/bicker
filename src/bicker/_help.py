from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TextIO, final

from bicker._style import Style, Styles, style, visible_len

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence

    from bicker._spec import Field, HelpKey, Spec, VersionKey

_PAD: Final = "  "

# A help line before alignment: the styled keys or name, and the description
type _Entry = tuple[str, str | None]


@final
@dataclass(frozen=True, kw_only=True)
class HelpConfig:
    """The `parse_args` settings that shape help and usage output."""

    prog: str
    help_keys: Sequence[HelpKey]
    help_description: str
    # Empty when there's no version to show
    version_keys: Sequence[VersionKey]
    version_description: str
    description: str | None
    epilog: str | None
    examples: Sequence[str]
    use_shorthand_usage: bool


@final
class HelpRenderer:
    """Build help and usage text, styled for `stream` (stdout for help, stderr for errors).

    `path` holds the specs from the program down to the command the help is for.
    """

    def __init__(self, path: Sequence[Spec], cfg: HelpConfig, stream: TextIO) -> None:
        self._cfg = cfg
        self._stream = stream
        self._spec = path[-1]
        self._is_command = len(path) > 1
        self._prog = " ".join([cfg.prog, *(spec.name for spec in path[1:])])

        # Required positionals always precede optional ones, so these are in display order
        self._positionals = self._spec.positionals
        self._options = self._spec.options
        self._global_options = [field for spec in path[:-1] for field in spec.options]

    def help(self) -> str:
        cfg = self._cfg

        command_entries = [
            (self._st(name, Styles.COMMAND), _summary(command.description))
            for name, command in self._spec.commands.items()
        ]
        pos_entries = [
            (self._pos_label(field, Styles.OPTIONAL_POS), field.description)
            for field in self._positionals
        ]

        # Ungrouped options first, then each group in the order it first appears
        groups: dict[str, list[_Entry]] = {"Options": []}
        for field in self._options:
            groups.setdefault(field.group, []).append(self._field_entry(field))

        if cfg.help_keys:
            help_entry = self._option_entry(cfg.help_keys, Styles.FLAG, None)
            groups["Options"].append((help_entry, cfg.help_description))
        if cfg.version_keys:
            version_entry = self._option_entry(cfg.version_keys, Styles.FLAG, None)
            groups["Options"].append((version_entry, cfg.version_description))

        entry_sections = [
            ("Commands", command_entries),
            ("Positionals", pos_entries),
            *groups.items(),
            ("Global options", [self._field_entry(field) for field in self._global_options]),
        ]

        # Descriptions start in one column across all sections
        width = max(
            (visible_len(entry) for _, entries in entry_sections for entry, _ in entries),
            default=0,
        )

        # A command's help is described by its docstring; examples and epilog are the program's
        description = self._spec.description if self._is_command else cfg.description
        examples = () if self._is_command else cfg.examples
        epilog = None if self._is_command else cfg.epilog

        sections = [self.usage()]
        if description:
            sections.append(description)
        for title, entries in entry_sections:
            if entries:
                lines = [_described(entry, desc, width) for entry, desc in entries]
                sections.append(self._section(title, lines))
        if examples:
            sections.append(self._section("Examples", map(self._example, examples)))
        if epilog:
            sections.append(epilog)

        return "\n\n".join(sections)

    def usage(self) -> str:
        # Required options are listed even in shorthand usage, since they must be given
        shown = self._options
        options: list[str] = []
        if self._options and self._cfg.use_shorthand_usage:
            shown = tuple(field for field in self._options if field.is_required)
            options.append(self._st("options", Styles.USAGE_OPT))

        # "..." after a list option: it can be repeated
        options += [self._usage_option(field) + self._ellipsis(field) for field in shown]

        positionals = [
            self._pos_label(field, Styles.USAGE_OPTIONAL_POS) for field in self._positionals
        ]
        if self._spec.command_attr:
            positionals.append(self._st(self._spec.command_attr, Styles.COMMAND))
        heading = [self._st("Usage", Styles.HEADING), self._st(self._prog, Styles.PROG)]

        return " ".join([*heading, *options, *positionals])

    def _st(self, text: str, style_: Style) -> str:
        return style(text, style_, self._stream)

    def _section(self, title: str, lines: Iterable[str]) -> str:
        styled_title = self._st(title, Styles.HEADING)

        return "\n".join([styled_title, *(_PAD + line for line in lines)])

    def _pos_label(self, field: Field, optional_style: Style) -> str:
        """Style the positional's name, plus `...` if it takes many values."""
        style_ = Styles.POS if field.is_required else optional_style
        return self._st(field.name + self._ellipsis(field), style_)

    def _usage_option(self, field: Field) -> str:
        """`[-v]`, `[-c COUNT]` or `--color {red,blue}`: the first key, plus a placeholder.

        Brackets mark an option as optional, so a required one has none.
        """
        text = self._st(field.keys[0], field.style) + self._metavar(field.metavar)
        return text if field.is_required else self._st(text, Styles.USAGE_OPT)

    def _field_entry(self, field: Field) -> _Entry:
        return self._option_entry(field.keys, field.style, field.metavar), field.description

    def _option_entry(self, keys: Collection[str], style_: Style, metavar: str | None) -> str:
        """`-c, --count COUNT`, `    --color {a,b}` or `-h`, with long keys in one column."""
        ordered = sorted(keys, key=len)  # Short first
        # Shorts are always 2 chars ("-c"), so "-c, " or 4 spaces lines up every long key
        indent = "    " if ordered[0].startswith("--") else ""
        styled_keys = ", ".join(self._st(key, style_) for key in ordered)
        return indent + styled_keys + self._metavar(metavar)

    def _example(self, example: str) -> str:
        """Prefix `prog`, and style commands and known keys (e.g. `-w`) as in the help lists."""
        spec = self._spec
        styles_by_key = _styles_by_key(self._options)
        words = [self._st(self._prog, Styles.PROG)]

        for word in example.split():
            # Past a command's name, its own options are known too
            if command := spec.commands.get(word):
                spec = command
                styles_by_key |= _styles_by_key(command.options)
                words.append(self._st(word, Styles.COMMAND))
            elif word in styles_by_key:
                words.append(self._st(word, styles_by_key[word]))
            else:
                words.append(word)

        return " ".join(words)

    def _metavar(self, metavar: str | None) -> str:
        """` COUNT`, with its leading space, or `""` if there's no metavar."""
        return f" {self._st(metavar, Styles.METAVAR)}" if metavar else ""

    def _ellipsis(self, field: Field) -> str:
        """`...` if the field takes many values, else `""`."""
        return self._st("...", Styles.ELLIPSIS) if field.is_list else ""


def _described(entry: str, description: str | None, width: int) -> str:
    """Append `description` after `entry`, padded so descriptions start at `width` + 2."""
    if not description:
        return entry
    return entry + " " * (width - visible_len(entry) + 2) + description


def _summary(description: str | None) -> str | None:
    """Get the first line of a command's description, without its period, for the commands list."""
    return description.partition("\n")[0].removesuffix(".") if description else None


def _styles_by_key(options: Iterable[Field]) -> dict[str, Style]:
    return {key: field.style for field in options for key in field.keys}
