from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(default=False),
    trim_blocks=False,
    lstrip_blocks=False,
)
_md = MarkdownIt("commonmark").enable("table")


def render_markdown(template: str, **ctx: Any) -> str:
    return _env.get_template(template).render(**ctx)


def markdown_to_html(md: str) -> str:
    body = _md.render(md)
    return f'<article class="report">{body}</article>'
