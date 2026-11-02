"""Shared helpers for the Clickdy news system (standard library only)."""
import html
import json
import os
import re
import unicodedata
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(text, max_len=70):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "post"


# ---------- HTML sanitizer (allow-list) ----------
ALLOWED_TAGS = {"p", "h2", "h3", "ul", "ol", "li", "strong", "em", "b", "i", "blockquote", "a"}


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []  # (tag, was_emitted)
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if re.match(r"^https?://", href, re.I):
                self.out.append('<a href="%s" target="_blank" rel="nofollow noopener noreferrer">'
                                % html.escape(href, quote=True))
                self.stack.append(("a", True))
            else:
                self.stack.append(("a", False))
            return
        self.out.append("<%s>" % tag)
        self.stack.append((tag, True))

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip:
            self.out.append("<br>")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            if self.skip:
                self.skip -= 1
            return
        if self.skip:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                while len(self.stack) > i:
                    t, emitted = self.stack.pop()
                    if emitted:
                        self.out.append("</%s>" % t)
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self):
        while self.stack:
            t, emitted = self.stack.pop()
            if emitted:
                self.out.append("</%s>" % t)
        return "".join(self.out).strip()


def sanitize_html(raw):
    parser = _Cleaner()
    parser.feed(raw or "")
    parser.close()
    return parser.result()
