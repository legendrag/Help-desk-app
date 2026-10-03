"""Allowlist sanitizer for knowledge-base HTML saved from the editor."""

from html import escape, unescape
from html.parser import HTMLParser


ALLOWED_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "caption",
    "code",
    "col",
    "colgroup",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}

VOID_TAGS = {"br", "col", "hr", "img"}

DROP_WITH_CONTENT = {
    "embed",
    "iframe",
    "math",
    "noscript",
    "object",
    "script",
    "style",
    "svg",
}

ALLOWED_ATTRS = {
    "a": {"href", "title", "target"},
    "col": {"span"},
    "img": {"alt", "height", "src", "title", "width"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}


def _safe_url(value):
    text = unescape(str(value or "")).replace("\x00", "")
    compact = "".join(text.lower().split())
    if compact.startswith(("javascript:", "vbscript:", "data:")):
        return None
    return text.strip()


def _clean_attrs(tag, attrs):
    allowed = ALLOWED_ATTRS.get(tag, set())
    rendered = []
    for name, value in attrs:
        if not name or value is None:
            continue
        attr = name.lower()
        if attr.startswith("on") or attr not in allowed:
            continue
        if attr in {"href", "src"}:
            value = _safe_url(value)
            if not value:
                continue
        if attr == "target" and value not in {"_blank", "_self"}:
            continue
        rendered.append(f' {attr}="{escape(str(value), quote=True)}"')
    if tag == "a" and any(part.startswith(' target="') for part in rendered):
        if not any(part.startswith(' rel="') for part in rendered):
            rendered.append(' rel="noopener noreferrer"')
    return "".join(rendered)


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, void=False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, void=True)

    def _start(self, tag, attrs, void):
        tag = (tag or "").lower()
        if self.skip_depth:
            if tag in DROP_WITH_CONTENT and not void:
                self.skip_depth += 1
            return
        if tag in DROP_WITH_CONTENT:
            if not void:
                self.skip_depth = 1
            return
        if tag not in ALLOWED_TAGS:
            return
        attr_html = _clean_attrs(tag, attrs)
        self.parts.append(f"<{tag}{attr_html}>")
        if tag not in VOID_TAGS and not void:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        if tag in DROP_WITH_CONTENT and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag not in self.stack:
            return
        while self.stack:
            open_tag = self.stack.pop()
            self.parts.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    def handle_data(self, data):
        if self.skip_depth or not data:
            return
        self.parts.append(escape(data))

    def finish(self):
        while self.stack:
            self.parts.append(f"</{self.stack.pop()}>")
        return "".join(self.parts)


def sanitize_article_html(value):
    """Drop scripts, event handlers, and javascript/data URLs. Keep editor markup."""
    parser = _Sanitizer()
    parser.feed(str(value or ""))
    parser.close()
    return parser.finish()
