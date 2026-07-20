#!/usr/bin/env python3
"""Build posts/*.md into <slug>/index.html and regenerate the home page list.

Usage: python3 build.py
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
POSTS_DIR = ROOT / "posts"
INDEX_FILE = ROOT / "index.html"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'><g stroke='black' stroke-width='6' stroke-linecap='round' transform='translate(32,32)'><line x1='0' y1='-22' x2='0' y2='22'/><line x1='0' y1='-22' x2='0' y2='22' transform='rotate(60)'/><line x1='0' y1='-22' x2='0' y2='22' transform='rotate(120)'/></g></svg>" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css" />
</head>
<body>
  <main class="container">

    <header class="site-header site-nav">
      <a href="https://blog.jem.fyi">Home</a>
      <a href="https://x.com/jemzhng" target="_blank">Twitter</a>
    </header>

    <div class="article-header">
      <h1 class="article-page-title">{title}</h1>
      <div class="article-page-date">{date_display}</div>
    </div>

    <div class="article-body">
{body}
    </div>

  </main>
</body>
</html>
"""

INDEX_START = "<!-- POSTS:START -->"
INDEX_END = "<!-- POSTS:END -->"


def parse_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError("Missing frontmatter (expected --- ... --- at top of file)")
    raw_meta, body = match.groups()
    meta = {}
    for line in raw_meta.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, body.strip()


def inline_md(text):
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def markdown_to_html(md):
    lines = md.splitlines()
    html_lines = []
    paragraph = []

    def flush():
        if paragraph:
            text = inline_md(" ".join(paragraph))
            html_lines.append(f"      <p>{text}</p>")
            paragraph.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1)) + 1  # top md heading -> h2
            html_lines.append(f"      <h{level}>{inline_md(heading.group(2))}</h{level}>")
            continue
        paragraph.append(stripped)
    flush()
    return "\n".join(html_lines)


def format_date(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%b ") + str(dt.day) + dt.strftime(", %Y"), dt


def slugify(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def build_post(md_path):
    meta, body_md = parse_frontmatter(md_path.read_text())
    title = meta["title"]
    slug = slugify(title)
    subtitle = meta.get("subtitle", "")
    date_display, date_obj = format_date(meta["date"])
    body_html = markdown_to_html(body_md)

    page = PAGE_TEMPLATE.format(title=title, date_display=date_display, body=body_html)
    out_dir = ROOT / slug
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(page)

    return {
        "slug": slug,
        "title": title,
        "subtitle": subtitle,
        "date_display": date_display,
        "date_obj": date_obj,
    }


def render_card(post):
    return (
        '      <div class="article-card">\n'
        f'        <a class="article-title" href="{post["slug"]}">{post["title"]}</a>\n'
        f'        <div class="article-subtitle">{post["subtitle"]}</div>\n'
        f'        <div class="article-date">{post["date_display"]}</div>\n'
        "      </div>"
    )


def update_index(posts):
    posts_sorted = sorted(posts, key=lambda p: p["date_obj"], reverse=True)
    cards = "\n\n".join(render_card(p) for p in posts_sorted)
    block = f"{INDEX_START}\n{cards}\n    {INDEX_END}"

    text = INDEX_FILE.read_text()
    pattern = re.compile(
        re.escape(INDEX_START) + r".*?" + re.escape(INDEX_END), re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"Could not find {INDEX_START} ... {INDEX_END} markers in index.html")
    text = pattern.sub(block, text)
    INDEX_FILE.write_text(text)


def push_to_origin():
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    if not status.strip():
        print("nothing to commit")
        return

    subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Update posts"], cwd=ROOT, check=True
    )
    subprocess.run(["git", "push", "origin"], cwd=ROOT, check=True)
    print("pushed to origin")


def main():
    md_files = sorted(POSTS_DIR.glob("*.md"))
    posts = [build_post(f) for f in md_files]

    seen = {}
    for p in posts:
        if p["slug"] in seen:
            raise ValueError(f'Slug collision: "{seen[p["slug"]]}" and "{p["title"]}" both slugify to "{p["slug"]}"')
        seen[p["slug"]] = p["title"]

    update_index(posts)
    for p in posts:
        print(f"built {p['slug']}/index.html")
    print(f"updated index.html with {len(posts)} post(s)")

    push_to_origin()


if __name__ == "__main__":
    main()
