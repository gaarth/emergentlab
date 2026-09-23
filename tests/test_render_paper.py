"""V3: render_paper.py. Every test runs in a tmp dir so real paper.html / frames/ are never touched."""
import os, pathlib, shutil, subprocess, sys
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "render_paper.py"
SECTIONS = ["Abstract", "Question", "Method", "Search summary", "Findings", "Dead ends", "Limitations", "Next experiments"]


def png(path, noise=False, size=256):
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.random.randint(0, 256, (size, size), dtype=np.uint8) if noise else np.zeros((64, 64), dtype=np.uint8)
    Image.fromarray(arr).save(path)


def render(cwd, env=None):
    p = subprocess.run([sys.executable, str(SCRIPT)], cwd=cwd, capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    return (cwd / "paper.html").read_text(encoding="utf-8"), p


def test_fake_paper(tmp_path):
    shutil.copy(ROOT / "fixtures/paper_fake.md", tmp_path / "paper.md")
    png(tmp_path / "frames/n0_20.png")
    html, _ = render(tmp_path)
    assert "<table>" in html
    for s in SECTIONS:
        assert f">{s}</h2>" in html, s
    assert "data:image/png;base64," in html
    assert 'src="frames/' not in html
    assert 'href="/app/dist/index.html#n17"' in html   # (n17) citation became a link into the app


def test_missing_image_dropped(tmp_path):
    (tmp_path / "paper.md").write_text("# T\n\n## Findings\n\n![](frames/nope.png)\n\ntext\n", encoding="utf-8")
    html, p = render(tmp_path)
    assert "nope.png" not in html.split("<body>")[1]
    assert "<img" not in html
    assert "Findings" in html


def test_utf8_on_cp1252_console(tmp_path):
    text = "# Title → ≥ — \U0001F9EC\n\n## Findings\n\nfitness ≥ 2 → copies — done \U0001F9EC (n3)\n"
    (tmp_path / "paper.md").write_text(text, encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
    html, _ = render(tmp_path, env)
    for ch in ["→", "≥", "—", "\U0001F9EC"]:
        assert ch in html


def test_size_with_20_images(tmp_path):
    lines = ["# T", "", "## Findings", ""]
    for i in range(20):
        png(tmp_path / f"frames/n{i}_20.png", noise=True)
        lines.append(f"![n{i} t=20](frames/n{i}_20.png)")
    (tmp_path / "paper.md").write_text("\n".join(lines), encoding="utf-8")
    html, _ = render(tmp_path)
    assert html.count("data:image/png;base64,") == 20
    assert len(html.encode("utf-8")) < 5 * 1024 * 1024


def test_explicit_paths_and_md_relative_images(tmp_path):
    (tmp_path / "sub").mkdir()
    png(tmp_path / "sub/frames/n0_0.png")
    (tmp_path / "sub/in.md").write_text("# T\n\n![](frames/n0_0.png)\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), "sub/in.md", "out.html"], cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "data:image/png;base64," in (tmp_path / "out.html").read_text(encoding="utf-8")
