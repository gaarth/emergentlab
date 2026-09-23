"""paper.md -> paper.html with frames inlined as base64. lab.py calls this with no args.

usage: python render_paper.py [paper.md] [paper.html]
Image paths are resolved relative to the .md file's folder, then the current directory.
"""
import base64, html as htmllib, pathlib, re, sys
import markdown

for s in (sys.stdout, sys.stderr):   # never crash on a cp1252 console
    try: s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

MIME = {".png": "image/png", ".gif": "image/gif", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

CSS = """
body{max-width:780px;margin:48px auto;padding:0 24px;font:17px/1.65 Georgia,"Times New Roman",serif;background:#fff;color:#1a1a1a}
h1{text-align:center;font-size:30px;line-height:1.25;margin:0 0 6px}
.byline{text-align:center;color:#666;font-size:14px;margin-bottom:32px}
h2{font-size:21px;margin:34px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px;color:#b8471f}
h2#abstract + p,h2#abstract + p + p{margin:0 36px;font-size:15.5px;color:#333;font-style:italic}
table{border-collapse:collapse;margin:14px auto;font-size:14.5px}
td,th{border:1px solid #ccc;padding:5px 10px} th{background:#f5f1ee}
code{background:#f3f3f3;padding:1px 4px;border-radius:3px;font-size:14px}
pre{background:#f6f6f6;padding:10px;overflow:auto}
figure{display:inline-block;margin:8px;text-align:center;vertical-align:top}
figure img{width:180px;image-rendering:pixelated;border:1px solid #ccc}
figcaption{font-size:12.5px;color:#666;max-width:180px}
a.cite{color:#b8471f;text-decoration:none;border-bottom:1px dotted #b8471f}
footer{margin-top:48px;border-top:1px solid #ddd;padding-top:10px;color:#888;font-size:13px}
"""


def inline_images(page_html, bases):
    def repl(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]*)"', tag)
        if not src or src.group(1).startswith(("data:", "http://", "https://")):
            return tag
        rel = htmllib.unescape(src.group(1))
        path = next((b / rel for b in bases if (b / rel).is_file()), None)
        if path is None:
            print(f"warning: image not found, dropped: {rel}", file=sys.stderr)
            return ""
        alt = re.search(r'alt="([^"]*)"', tag)
        cap = alt.group(1) if alt and alt.group(1) else htmllib.escape(path.stem)
        b64 = base64.b64encode(path.read_bytes()).decode()
        mime = MIME.get(path.suffix.lower(), "image/png")
        return f'<figure><img src="data:{mime};base64,{b64}" alt="{cap}"><figcaption>{cap}</figcaption></figure>'
    return re.sub(r"<img\b[^>]*>", repl, page_html)


def link_citations(page_html):
    """(n17) / (n3, n17) in body text -> links to the node in the viewer."""
    def cite(m):
        ids = re.sub(r"\bn(\d+)\b", lambda k: f'<a class="cite" href="/app/dist/index.html#n{k.group(1)}">n{k.group(1)}</a>', m.group(1))
        return f"({ids})"
    def text(m):
        return ">" + re.sub(r"\((n\d+(?:\s*[,;]\s*n\d+)*)\)", cite, m.group(1)) + "<"
    return re.sub(r">([^<]+)<", text, page_html)


def render(md_path="paper.md", out_path="paper.html"):
    md_path, out_path = pathlib.Path(md_path), pathlib.Path(out_path)
    md = md_path.read_text(encoding="utf-8", errors="replace")
    body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc"])
    body = link_citations(inline_images(body, [md_path.resolve().parent, pathlib.Path.cwd()]))
    title = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title_txt = re.sub(r"<[^>]+>", "", title.group(1)) if title else "Lab report"
    if title:   # byline right under the title
        body = body.replace(title.group(0), title.group(0) +
                            '<div class="byline">Autonomous Discovery Lab · Claude Fable 5.1</div>', 1)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title_txt}</title><style>{CSS}</style></head>
<body>{body}
<footer>Written autonomously by Claude Fable 5.1 from tree.json · Claude Community Mumbai Build Day ·
<a href="/app/dist/index.html">open the live tree</a></footer></body></html>"""
    out_path.write_text(page, encoding="utf-8")
    print(f"{out_path} written ({len(page) // 1024} KB)")


if __name__ == "__main__":
    render(*sys.argv[1:3])
