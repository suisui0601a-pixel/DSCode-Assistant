"""Safe Markdown rendering for use with a PySide6 QTextBrowser."""

from __future__ import annotations

from typing import Final

import bleach
import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound


ALLOWED_TAGS: Final[set[str]] = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

def _allow_attribute(tag: str, name: str, value: str) -> bool:
    if name == "class":
        return tag in {"code", "div", "span"}
    if tag == "a" and name == "href":
        return value.startswith("#")
    if tag == "a" and name == "title":
        return True
    return False


class MarkdownRenderer:
    """Convert Markdown into a sanitized QTextBrowser-compatible HTML fragment."""

    def render(self, markdown_text: str) -> str:
        """Render Markdown with fenced code blocks and safe HTML output."""
        rendered_html = markdown.markdown(
            markdown_text,
            extensions=["fenced_code", "codehilite", "tables", "sane_lists"],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "noclasses": False,
                }
            },
            output_format="html5",
        )
        return self.sanitize(rendered_html)

    def highlight_code(self, code: str, language: str | None = None) -> str:
        """Return sanitized syntax-highlighted HTML for a code snippet."""
        try:
            lexer = get_lexer_by_name(language) if language else TextLexer()
        except ClassNotFound:
            lexer = TextLexer()

        highlighted_html = highlight(
            code,
            lexer,
            HtmlFormatter(noclasses=False),
        )
        return self.sanitize(highlighted_html)

    def sanitize(self, html: str) -> str:
        """Remove executable content, resource loading, and unsafe HTML."""
        return bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=_allow_attribute,
            protocols=set(),
            strip=True,
            strip_comments=True,
        )
