#!/usr/bin/env python3
"""
Builds the public blog from posts/*.json (only APPROVED posts live in posts/).

Creates:
  blog/index.html                     latest posts (paginated)
  blog/page/N/index.html              more pages
  blog/category/<name>/...            one listing per category
  blog/<slug>/index.html              one static page per article (good for SEO)
  sitemap-blog.xml
"""
import html
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, read_json, sanitize_html, slugify  # noqa: E402

CFG = read_json(os.path.join(ROOT, "scripts", "feeds.json"), {}) or {}
SITE = (os.environ.get("SITE_URL") or CFG.get("site_url") or "https://clickdy.com").rstrip("/")
SITE_NAME = CFG.get("site_name", "Clickdy")
PER_PAGE = int(CFG.get("posts_per_page", 12))
DISCLOSURE = CFG.get("disclosure", "")
POSTS_DIR = os.path.join(ROOT, "posts")
BLOG_DIR = os.path.join(ROOT, "blog")
MARK = "<!-- clickdy-generated -->"
RESERVED = {"page", "category"}

e = html.escape

CSS = """
:root{--bg:#05070F;--bg-deep:#020308;--panel:#0D1730;--panel-border:#1B2A4E;--teal:#2BE0C4;--teal-dim:rgba(43,224,196,.14);
--text:#EAF0F4;--muted:#7C8AAC;--glass:rgba(255,255,255,.045);--glass-hover:rgba(255,255,255,.075);--glass-border:rgba(255,255,255,.10);--hl:rgba(255,255,255,.28)}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:radial-gradient(ellipse 60% 45% at 15% 5%,rgba(43,224,196,.07),transparent 60%),radial-gradient(ellipse 55% 40% at 88% 10%,rgba(80,120,255,.06),transparent 60%),var(--bg);
color:var(--text);font-family:'Inter',sans-serif;min-height:100vh;display:flex;flex-direction:column;overflow-x:hidden}
a{color:inherit;text-decoration:none}
h1,h2,h3{font-family:'Bricolage Grotesque',sans-serif;letter-spacing:-.02em}
.mono{font-family:'IBM Plex Mono',monospace;letter-spacing:.06em}
header.site{position:sticky;top:14px;z-index:20;margin:14px 14px 0;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 22px;
background:var(--glass);backdrop-filter:blur(22px) saturate(160%);-webkit-backdrop-filter:blur(22px) saturate(160%);border:1px solid var(--glass-border);border-radius:18px;box-shadow:inset 0 1px 0 var(--hl),0 12px 40px rgba(0,0,0,.3)}
.brand{display:flex;align-items:center;gap:9px;font-weight:700;font-size:.9rem}
.brand img{width:26px;height:26px;border-radius:50%;object-fit:cover;box-shadow:0 0 14px rgba(43,224,196,.35)}
nav.top{display:flex;gap:6px;font-size:.8rem;color:var(--muted)}
nav.top a{padding:8px 13px;border-radius:9px}
nav.top a:hover,nav.top a.on{color:var(--teal);background:var(--teal-dim)}
@media(max-width:620px){nav.top a.hide-sm{display:none}}
main{flex:1;width:100%;max-width:1140px;margin:0 auto;padding:56px 6vw 80px}
.eyebrow{font-size:.68rem;color:var(--teal);text-transform:uppercase;display:block;margin-bottom:12px}
.page-title{font-size:clamp(1.9rem,4vw,2.8rem);font-weight:800;line-height:1.1;margin-bottom:12px}
.page-sub{color:var(--muted);max-width:560px;line-height:1.6;margin-bottom:28px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:34px}
.chip{font-family:'Quicksand',sans-serif;font-size:.8rem;font-weight:600;padding:8px 16px;border-radius:100px;background:var(--glass);border:1px solid var(--glass-border);color:var(--muted);transition:.2s}
.chip:hover{border-color:rgba(43,224,196,.4);color:var(--text)}
.chip.on{background:var(--teal);border-color:var(--teal);color:#04231E}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px}
.card{position:relative;overflow:hidden;display:flex;flex-direction:column;gap:12px;padding:26px 24px;background:var(--glass);backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%);
border:1px solid var(--glass-border);border-radius:18px;box-shadow:inset 0 1px 0 var(--hl),0 8px 32px rgba(0,0,0,.25);transition:border-color .2s,transform .2s,background .2s}
.card:hover{border-color:rgba(43,224,196,.45);transform:translateY(-4px);background:var(--glass-hover)}
.tag{font-family:'Quicksand',sans-serif;font-size:.66rem;font-weight:700;color:var(--teal);text-transform:uppercase;letter-spacing:.06em}
.card h3{font-family:'Quicksand',sans-serif;font-size:1.1rem;font-weight:700;line-height:1.35}
.card p{font-family:'Quicksand',sans-serif;color:var(--muted);font-size:.88rem;line-height:1.55;flex:1}
.meta{font-family:'IBM Plex Mono',monospace;font-size:.68rem;color:var(--muted)}
.empty{padding:60px 20px;text-align:center;color:var(--muted);border:1px dashed var(--glass-border);border-radius:18px}
.pager{display:flex;justify-content:center;align-items:center;gap:18px;margin-top:44px;font-size:.85rem;color:var(--muted)}
.pager a{padding:9px 18px;border-radius:10px;border:1px solid var(--glass-border);background:var(--glass)}
.pager a:hover{border-color:var(--teal);color:var(--teal)}
article.post{max-width:740px;margin:0 auto}
.crumbs{font-size:.75rem;color:var(--muted);margin-bottom:22px}
.crumbs a:hover{color:var(--teal)}
article.post h1{font-size:clamp(1.8rem,4vw,2.6rem);font-weight:800;line-height:1.15;margin:12px 0 14px}
.lede{color:var(--muted);font-size:1.05rem;line-height:1.6;margin-bottom:18px}
.byline{padding-bottom:22px;margin-bottom:28px;border-bottom:1px solid var(--panel-border)}
.content{font-size:1.02rem;line-height:1.8;color:#D6DEE8}
.content p{margin-bottom:1.15em}
.content h2{font-size:1.4rem;margin:1.6em 0 .6em;color:var(--text)}
.content h3{font-size:1.15rem;margin:1.4em 0 .5em}
.content ul,.content ol{margin:0 0 1.2em 1.3em}
.content li{margin-bottom:.45em}
.content a{color:var(--teal);text-decoration:underline;text-underline-offset:3px}
.content blockquote{border-left:3px solid var(--teal);padding:4px 0 4px 18px;margin:1.2em 0;color:var(--muted)}
.source-box{margin-top:36px;padding:20px 22px;border-radius:16px;background:var(--glass);border:1px solid var(--glass-border);font-size:.86rem;line-height:1.6;color:var(--muted)}
.source-box a{color:var(--teal);text-decoration:underline;text-underline-offset:3px}
.source-box p+p{margin-top:8px;font-size:.78rem}
.related{max-width:1140px;margin:64px auto 0}
.related h2{font-size:1.2rem;margin-bottom:18px}
footer.site{padding:28px 6vw;border-top:1px solid var(--glass-border);background:var(--glass);color:var(--muted);font-size:.8rem;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
footer.site a:hover{color:var(--teal)}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800'
         '&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&family=Quicksand:wght@500;600;700&display=swap" rel="stylesheet">')


# ------------------------------------------------------------ helpers
def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_iso(value):
    try:
        dt = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def fmt_date(value):
    dt = parse_iso(value)
    return dt.strftime("%d %b %Y") if dt.year > 1970 else ""


def load_posts():
    posts = []
    if not os.path.isdir(POSTS_DIR):
        return posts
    for name in os.listdir(POSTS_DIR):
        if not name.endswith(".json"):
            continue
        data = read_json(os.path.join(POSTS_DIR, name), None)
        if not isinstance(data, dict) or not data.get("title") or not data.get("body_html"):
            print("skipping invalid post file:", name)
            continue
        slug = slugify(data.get("slug") or name[:-5])
        if slug in RESERVED:
            slug = "post-" + slug
        data["slug"] = slug
        data["body_html"] = sanitize_html(data["body_html"])
        data["category"] = str(data.get("category") or "Tech")
        data["published_at"] = data.get("published_at") or data.get("created_at") or ""
        posts.append(data)
    posts.sort(key=lambda p: parse_iso(p["published_at"]), reverse=True)
    return posts


def clean_generated():
    """Remove only files this script generated earlier (identified by the marker)."""
    if not os.path.isdir(BLOG_DIR):
        return
    for dirpath, _dirs, files in os.walk(BLOG_DIR):
        if "index.html" in files:
            p = os.path.join(dirpath, "index.html")
            try:
                with open(p, "r", encoding="utf-8") as f:
                    if MARK in f.read(600):
                        os.remove(p)
            except OSError:
                pass
    for dirpath, _dirs, _files in os.walk(BLOG_DIR, topdown=False):
        if dirpath != BLOG_DIR and not os.listdir(dirpath):
            os.rmdir(dirpath)


def shell(title, desc, canonical, body, nav_on="blog", og_type="website", jsonld=None):
    ld = ""
    if jsonld:
        ld = '<script type="application/ld+json">%s</script>' % json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")
    nav = [("/", "Home", "home", ""), ("/index.html#tools", "Tools", "tools", "hide-sm"),
           ("/blog/", "Blog", "blog", ""), ("/about.html", "About", "about", "hide-sm"), ("/contact.html", "Contact", "contact", "hide-sm")]
    nav_html = "".join('<a href="%s" class="%s%s">%s</a>' % (h, c, " on" if k == nav_on else "", t) for h, t, k, c in nav)
    return """<!DOCTYPE html>
<html lang="en">
<head>
%(mark)s
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(canon)s">
<link rel="icon" type="image/png" href="/assets/logo.png">
<meta property="og:type" content="%(og)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:url" content="%(canon)s">
<meta property="og:image" content="%(site)s/assets/logo.png">
<meta name="twitter:card" content="summary">
%(ld)s
%(fonts)s
<style>%(css)s</style>
</head>
<body>
<header class="site">
  <a href="/" class="brand"><img src="/assets/logo.png" alt="%(name)s logo">CLICKDY</a>
  <nav class="top">%(nav)s</nav>
</header>
<main>%(body)s</main>
<footer class="site">
  <div>&copy; %(year)s %(name)s. Built for speed.</div>
  <div class="mono"><a href="/blog/">Blog</a> &nbsp; <a href="/about.html">About</a> &nbsp; <a href="/contact.html">Contact</a> &nbsp; <a href="/privacy.html">Privacy</a></div>
</footer>
</body>
</html>
""" % {"mark": MARK, "title": e(title), "desc": e(desc), "canon": e(canonical), "og": og_type, "site": SITE, "ld": ld,
       "fonts": FONTS, "css": CSS, "name": e(SITE_NAME), "nav": nav_html, "body": body, "year": datetime.now().year}


def card(p):
    return ('<a class="card" href="/blog/%s/"><span class="tag">%s</span><h3>%s</h3><p>%s</p><span class="meta">%s &middot; %s</span></a>'
            % (e(p["slug"]), e(p["category"]), e(p["title"]), e(p.get("excerpt", "")), fmt_date(p["published_at"]), e(p.get("source_name", ""))))


def category_path(cat):
    return "/blog/category/%s/" % slugify(cat)


def build_listing(posts, base, heading, sub, categories, active_cat=None):
    pages = max(1, math.ceil(len(posts) / PER_PAGE))
    chips = '<a class="chip%s" href="/blog/">All</a>' % ("" if active_cat else " on")
    for c in categories:
        chips += '<a class="chip%s" href="%s">%s</a>' % (" on" if c == active_cat else "", category_path(c), e(c))
    urls = []
    for n in range(1, pages + 1):
        chunk = posts[(n - 1) * PER_PAGE: n * PER_PAGE]
        url_path = base if n == 1 else "%spage/%d/" % (base, n)
        grid = '<div class="grid">%s</div>' % "".join(card(p) for p in chunk) if chunk else \
            '<div class="empty">No articles yet. Fresh news will appear here soon.</div>'
        pager = ""
        if pages > 1:
            prev = ('<a href="%s" rel="prev">&larr; Newer</a>' % (base if n == 2 else "%spage/%d/" % (base, n - 1))) if n > 1 else ""
            nxt = ('<a href="%spage/%d/" rel="next">Older &rarr;</a>' % (base, n + 1)) if n < pages else ""
            pager = '<div class="pager">%s<span>Page %d of %d</span>%s</div>' % (prev, n, pages, nxt)
        body = ('<span class="eyebrow mono">%s</span><h1 class="page-title">%s</h1><p class="page-sub">%s</p>'
                '<nav class="chips">%s</nav>%s%s') % (e(SITE_NAME + " Blog"), e(heading), e(sub), chips, grid, pager)
        title = heading if n == 1 else "%s - Page %d" % (heading, n)
        write(os.path.join(ROOT, url_path.strip("/"), "index.html"),
              shell("%s | %s" % (title, SITE_NAME), sub, SITE + url_path, body))
        urls.append(url_path)
    return urls


def build_post(p, all_posts):
    url_path = "/blog/%s/" % p["slug"]
    canonical = SITE + url_path
    desc = p.get("excerpt") or p["title"]
    source = ""
    if p.get("source_url"):
        source = '<p>Source: <a href="%s" target="_blank" rel="nofollow noopener noreferrer">%s</a></p>' % (
            e(p["source_url"], quote=True), e(p.get("source_name") or "Original article"))
    if DISCLOSURE:
        source += "<p>%s</p>" % e(DISCLOSURE)
    source_box = '<div class="source-box">%s</div>' % source if source else ""
    related = [r for r in all_posts if r["slug"] != p["slug"] and r["category"] == p["category"]][:3]
    if len(related) < 3:
        related += [r for r in all_posts if r["slug"] != p["slug"] and r not in related][:3 - len(related)]
    related_html = ('<section class="related"><h2>More news</h2><div class="grid">%s</div></section>'
                    % "".join(card(r) for r in related)) if related else ""
    body = ('<article class="post"><div class="crumbs"><a href="/">Home</a> / <a href="/blog/">Blog</a> / <a href="%s">%s</a></div>'
            '<span class="tag">%s</span><h1>%s</h1><p class="lede">%s</p>'
            '<div class="byline meta">%s &middot; %s</div><div class="content">%s</div>%s</article>%s') % (
        category_path(p["category"]), e(p["category"]), e(p["category"]), e(p["title"]), e(p.get("excerpt", "")),
        fmt_date(p["published_at"]), e(SITE_NAME + " News"), p["body_html"], source_box, related_html)
    jsonld = {
        "@context": "https://schema.org", "@type": "NewsArticle", "headline": p["title"][:110], "description": desc,
        "datePublished": parse_iso(p["published_at"]).isoformat(), "dateModified": parse_iso(p["published_at"]).isoformat(),
        "mainEntityOfPage": canonical,
        "publisher": {"@type": "Organization", "name": SITE_NAME, "logo": {"@type": "ImageObject", "url": SITE + "/assets/logo.png"}},
    }
    write(os.path.join(ROOT, "blog", p["slug"], "index.html"),
          shell("%s | %s" % (p["title"], SITE_NAME), desc, canonical, body, og_type="article", jsonld=jsonld))
    return url_path


def main():
    posts = load_posts()
    clean_generated()
    os.makedirs(BLOG_DIR, exist_ok=True)

    categories = sorted({p["category"] for p in posts})
    urls = [(u, None) for u in build_listing(posts, "/blog/", "Latest Tech & AI News",
                                              "Fresh AI, tech and gadget news, summarised in plain language.", categories)]
    for c in categories:
        cat_posts = [p for p in posts if p["category"] == c]
        for u in build_listing(cat_posts, category_path(c), "%s News" % c,
                               "Latest %s news from %s." % (c, SITE_NAME), categories, active_cat=c):
            urls.append((u, None))
    for p in posts:
        urls.append((build_post(p, posts), parse_iso(p["published_at"]).date().isoformat()))

    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, last in urls:
        sm.append("  <url><loc>%s</loc>%s</url>" % (e(SITE + u), "<lastmod>%s</lastmod>" % last if last else ""))
    sm.append("</urlset>")
    write(os.path.join(ROOT, "sitemap-blog.xml"), "\n".join(sm) + "\n")
    print("Built %d post(s), %d category page group(s), %d URL(s) in sitemap." % (len(posts), len(categories), len(urls)))


if __name__ == "__main__":
    main()
