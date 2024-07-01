"""Logseq Doctor: heal your Markdown files."""

from __future__ import annotations

import os

import mistletoe
from mistletoe import parse_context, block_tokens, block_tokens_ext, span_tokens
from mistletoe.renderers.base import BaseRenderer

from logseq_doctor.constants import CHAR_DASH, CHARS_UL_LEADER, OL_MARKER

__version__ = "0.3.0"


class LogseqRenderer(BaseRenderer):
    """Render Markdown as an outline with bullets, like Logseq expects."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.render_map = {
            **self.render_map,
            "Document": self.render_document,
            "FrontMatter": self.render_front_matter,
        }
        self.current_level = 0
        self.bullet = "- "
        self.continuation = "  "

    def outline(self, indent: int, text: str, continuation: bool = False, nl: bool = True) -> str:
        """Render a line of text with the correct indentation."""
        leading_spaces = "  " * indent
        new_line_at_the_end = os.linesep if nl else ""
        return f"{leading_spaces}{self.continuation if continuation else self.bullet}{text}{new_line_at_the_end}"

    def render_document(self, token: block_tokens.Document) -> str:
        front_matter = self.render_front_matter(token.front_matter) if token.front_matter else ""
        return front_matter + self.render_inner(token)

    def render_front_matter(self, token: block_tokens.FrontMatter) -> str:
        return f"---{os.linesep}{token.content}---{os.linesep}"

    def render_heading(self, token: block_tokens.Heading | block_tokens.SetextHeading) -> str:
        """Setext headings: https://spec.commonmark.org/0.30/#setext-headings."""
        if isinstance(token, block_tokens.SetextHeading):
            # For now, only dealing with level 2 setext headers (dashes)
            return self.render_inner(token) + f"{os.linesep}{CHAR_DASH * 3}{os.linesep}"

        self.current_level = token.level
        hashes = "#" * token.level
        inner = self.render_inner(token)
        return self.outline(token.level - 1, f"{hashes} {inner}")

    def render_line_break(self, token: span_tokens.LineBreak) -> str:
        """Render a line break."""
        return token.content + os.linesep

    def render_paragraph(self, token: block_tokens.Paragraph) -> str:
        """Render a paragraph with the correct indentation."""
        input_lines = self.render_inner(token).strip().splitlines()
        output_lines: list[str] = [self.outline(self.current_level, line, nl=False) for line in input_lines]
        return os.linesep.join(output_lines) + os.linesep

    def render_link(self, token: span_tokens.Link) -> str:
        """Render a link as a Markdown link."""
        text = self.render_inner(token)
        url = token.target
        return f"[{text}]({url})"

    def render_list_item(self, token: block_tokens.ListItem) -> str:
        """Render a list item with the correct indentation."""
        if len(token.children) <= 1:
            return self.render_inner(token)

        self.current_level += 1

        inner = self.render_inner(token)
        headless_parent_with_children = inner.lstrip(f"{self.bullet} ")
        value_before_changing_level = self.outline(self.current_level - 1, headless_parent_with_children, nl=False)

        self.current_level -= 1
        return value_before_changing_level

    def render_thematic_break(self, token: block_tokens.ThematicBreak) -> str:  # noqa: ARG002
        """Render a horizontal rule as a line of dashes."""
        return f"{CHAR_DASH * 3}{os.linesep}"

    def render_strong(self, token: span_tokens.Strong) -> str:
        return f"**{self.render_inner(token)}**"

    def render_emphasis(self, token: span_tokens.Emphasis) -> str:
        return f"*{self.render_inner(token)}*"

    def render_inline_code(self, token: span_tokens.InlineCode) -> str:
        return f"`{self.render_inner(token)}`"

    def render_strikethrough(self, token: span_tokens.Strikethrough) -> str:
        return f"{self.render_inner(token)}"

    def render_image(self, token: span_tokens.Image):
        return f"![{token.title}]({token.src})"

    def render_auto_link(self, token: span_tokens.AutoLink):
        return f"<{token.target}>"

    # def render_escape_sequence(self, token):
    #     return self.render_inner(token)

    def render_quote(self, token: block_tokens.Quote) -> str:
        inner = self.render_inner(token)
        prefix_chars = self.current_level * 2 + 2
        prefixed = [
            line[0:prefix_chars] + "> " + line[prefix_chars:]
            if line != "" else ""
            for line in inner.split(os.linesep)
        ]
        return os.linesep.join(prefixed)

    def render_block_code(self, token: block_tokens.BlockCode) -> str:
        assert len(token.children) == 1, "BlockCode should have only one child."

        inner = "".join([self.outline(self.current_level, l, continuation=True) for l in token.children[0].content.splitlines()])
        close = self.outline(self.current_level, "```", continuation=True)
        return self.outline(self.current_level, f"```{token.language}{os.linesep}{inner}{close}")

    def render_list(self, token: block_tokens.List) -> str:
        ol = token.children and token.children[0].leader not in CHARS_UL_LEADER
        ol_marker = ""

        if ol:
            ol_marker = self.outline(self.current_level, OL_MARKER) if ol else ""
            self.current_level += 1
        inner = self.render_inner(token)

        if ol:
            self.current_level -= 1

        return ol_marker + inner

    def render_table(self, token: block_tokens_ext.Table):
        result = ""
        if token.header:
            result += self.render_table_row(token.header, is_header=True)
        rows = "".join([self.render_table_row(row) for row in token.children])
        result += rows[0:-1]
        return self.outline(self.current_level, result)

    def render_table_row(self, token: block_tokens_ext.TableRow, is_header: bool = False):
        result = "".join([self.render_table_cell(cell) for cell in token.children]) + "|"
        if is_header:
            result += os.linesep + self.outline(self.current_level, "| --- " * len(token.children) + "|", continuation=True)
        else:
            result = self.outline(self.current_level, result, continuation=True)
        return result

    def render_table_cell(self, token):
        return f"| {self.render_inner(token)} "

    def render_html_span(self, token: span_tokens.HTMLSpan):
        return token.content


def flat_markdown_to_outline(markdown_contents: str) -> str:
    """Convert flat Markdown to an outline."""
    blocks = (
        block_tokens.FrontMatter,
        *BaseRenderer.default_block_tokens,
    )
    context = parse_context.ParseContext(find_blocks=blocks)
    return mistletoe.markdown(
        markdown_contents,
        renderer=LogseqRenderer,
        parse_context=context,
        read_kwargs={"front_matter": True},
    )
