"""Logseq Doctor: heal your Markdown files."""

from __future__ import annotations

import os

import mistletoe
from mistletoe import parse_context, block_tokens, span_tokens
from mistletoe.renderers.base import BaseRenderer

from logseq_doctor.constants import CHAR_DASH

__version__ = "0.3.0"


class LogseqRenderer(BaseRenderer):
    """Render Markdown as an outline with bullets, like Logseq expects."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.render_map = {
            **self.render_map,
            "Document": self.render_inner,
        }
        self.current_level = 0
        self.bullet = "- "
        self.continuation = "  "

    def outline(self, indent: int, text: str, continuation: bool = False, nl: bool = True) -> str:
        """Render a line of text with the correct indentation."""
        leading_spaces = "  " * indent
        new_line_at_the_end = os.linesep if nl else ""
        return f"{leading_spaces}{self.continuation if continuation else self.bullet}{text}{new_line_at_the_end}"

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
        return self.render_inner(token)

    def render_html_span(self, token: span_tokens.HTMLSpan):
        return self.render_inner(token)


def flat_markdown_to_outline(markdown_contents: str) -> str:
    """Convert flat Markdown to an outline."""
    find_blocks = (block_tokens.FrontMatter, *BaseRenderer.default_block_tokens)
    context = parse_context.ParseContext(find_blocks)
    return mistletoe.markdown(markdown_contents, renderer=LogseqRenderer, parse_context=context)
