from pathlib import Path
import re
from collections import defaultdict
from bs4 import BeautifulSoup

# ─────────────────────────── paths ────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
LOGS_DIR   = BASE_DIR / "logs"               # preferred folder layout
TAGS_DIR   = BASE_DIR / "tags"
INDEX_HTML = BASE_DIR / "index.html"
TAGS_INDEX = BASE_DIR / "tags.html"

if not LOGS_DIR.is_dir():                    # fall back to flat layout
    LOGS_DIR = BASE_DIR

LOGS_HTML = LOGS_DIR / "logs.html"
if not LOGS_HTML.is_file():
    raise FileNotFoundError("Cannot find logs.html in project")

TAGS_DIR.mkdir(exist_ok=True)                # ensure tags/ exists

# ───────────────────── helper functions ───────────────────────────────────────
def extract_logs():
    logs = []
    for file in sorted(LOGS_DIR.iterdir()):
        if file.suffix == ".html" and file.name != "logs.html":
            soup = BeautifulSoup(file.read_text("utf-8"), "html.parser")
            title = soup.select_one(".site-title")
            date  = soup.select_one(".log-date")
            if not (title and date):                      # skip half posts
                continue
            logs.append(
                {
                    "filename": file.name,
                    "title":    title.text.strip(),
                    "date":     date.text.strip(),
                    "tags":     [t.text.strip("#").split()[0]
                                 for t in soup.select(".log-tags a span")],
                    "excerpt":  (soup.select_one(".log-content p") or "").text,
                }
            )
    return logs[::-1]       # newest → oldest


def generate_log_html(log, prefix: Path | str = Path()):
    """Return one <div> snippet for a post."""
    prefix = Path(prefix)
    tag_links = "".join(
        f'<a href="{ (prefix / "tags" / f"tag-{tag.lower()}.html").as_posix() }">'
        f'<span>#{tag}</span></a>'
        for tag in log["tags"]
    )
    return (
        f'<div class="log-entry">\n'
        f'  <div class="log-date">{log["date"]}</div>\n'
        f'  <div class="log-title"><a href="{ (prefix / "logs" / log["filename"]).as_posix() }">'
        f'{log["title"]}</a></div>\n'
        f'  <div class="log-tags">{tag_links}</div>\n'
        f'  <p style="font-family: sans-serif;">{log["excerpt"]}</p>\n'
        f'</div>'
    )


def replace_block(file: Path, start: str, end: str, repl: str):
    """Replace text between two comment markers, inclusive."""
    text = file.read_text("utf-8")
    block = re.sub(f"{re.escape(start)}.*?{re.escape(end)}",
                   f"{start}\n{repl}\n{end}",
                   text, flags=re.DOTALL)
    file.write_text(block, "utf-8")

# ────────────────────── page updates ─────────────────────────────────────────
def update_index(logs):
    html = "\n".join(generate_log_html(l) for l in logs)
    replace_block(INDEX_HTML, "<!-- LOGS_START -->", "<!-- LOGS_END -->", html)


def update_logs_page(logs):
    html = "\n".join(generate_log_html(l) for l in logs)
    # Fix links **only inside logs/logs.html**
    html = (html
            .replace('href="logs/', 'href="')          # ./filename.html
            .replace('href="tags/', 'href="../tags/')) # ../tags/…
    replace_block(LOGS_HTML, "<!-- LOGS_START -->", "<!-- LOGS_END -->", html)


def update_tags_index(tag_map):
    html = "\n".join(
        f'<a href="tags/tag-{t.lower()}.html"><span>#{t} ({len(p)})</span></a>'
        for t, p in sorted(tag_map.items())
    )
    replace_block(TAGS_INDEX, "<!-- TAGS_START -->", "<!-- TAGS_END -->", html)


def create_tag_page(tag):
    path = TAGS_DIR / f"tag-{tag.lower()}.html"
    if path.exists():
        return
    stub = (
        '<!DOCTYPE html><html lang="en"><head>'
        '  <meta charset="UTF-8" />'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'  <title>#{tag}</title>'
        '  <link rel="stylesheet" href="../style.css" />'
        '</head><body>'
        '  <div class="grid-bg"></div>'
        '  <div class="hud-frame">'
        '    <nav class="nav-panel">'
        '      <a class="nav-item" href="../about.html">About Me</a>'
        '      <a class="nav-item" href="../now.html">Now</a>'
        '      <a class="nav-item" href="../gear.html">Gear</a>'
        '      <a class="nav-item" href="../ideas.html">Ideas</a>'
        '      <a class="nav-item" href="../tags.html">Tags</a>'
        '      <a class="nav-item" href="../logs/logs.html">Logs</a>'
        '    </nav>'
        '    <main class="main-content">'
        f'      <h1 class="site-title">#{tag}</h1>'
        '      <!-- LOGS_START -->'
        '      <!-- LOGS_END -->'
        '    </main>'
        '  </div>'
        '</body></html>'
    )
    path.write_text(stub, "utf-8")


def update_tag_pages(tag_map):
    for tag, posts in tag_map.items():
        create_tag_page(tag)
        html = "\n".join(generate_log_html(p, Path("..")) for p in posts)
        page = TAGS_DIR / f"tag-{tag.lower()}.html"
        replace_block(page, "<!-- LOGS_START -->", "<!-- LOGS_END -->", html)


def update_post_tag_links(logs):
    for log in logs:
        file = LOGS_DIR / log["filename"]
        soup = BeautifulSoup(file.read_text("utf-8"), "html.parser")
        tag_div = soup.find("div", class_="log-tags")
        if not tag_div:
            continue
        tag_div.clear()
        tag_div.append(BeautifulSoup(
            "".join(
                f'<a href="../tags/tag-{t.lower()}.html"><span>#{t}</span></a>'
                for t in log["tags"]
            ), "html.parser"))
        file.write_text(str(soup), "utf-8")

# ───────────────────────── driver ────────────────────────────────────────────
def run():
    logs = extract_logs()
    tag_map = defaultdict(list)
    for log in logs:
        for tag in log["tags"]:
            tag_map[tag].append(log)

    update_index(logs)
    update_logs_page(logs)            # ← fixes links inside logs/logs.html
    update_tags_index(tag_map)
    update_tag_pages(tag_map)
    update_post_tag_links(logs)

if __name__ == "__main__":
    run()
