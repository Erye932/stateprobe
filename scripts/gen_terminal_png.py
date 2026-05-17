"""Generate a PNG screenshot of the terminal output for README."""

from rich.console import Console
from stateprobe.detector import diagnose
import stateprobe.cli as cli
from playwright.sync_api import sync_playwright
from pathlib import Path

# 1. Generate terminal HTML
report = diagnose(
    "你是一位顶级 AI 专家，请彻底全面深入仔细完整地分析所有角度，尽量多讲优点和潜力",
    target_name="calm_reasoning",
    model_name="v4-pro",
)

rec = Console(record=True, width=88, force_terminal=True)
cli.console = rec
cli.render_terminal(report)

html_body = rec.export_html(inline_styles=True)

page_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {
    background: #1a1b26;
    margin: 0;
    padding: 24px;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
}
pre {
    font-size: 13px;
    line-height: 1.35;
    white-space: pre;
}
</style></head>
<body>
""" + html_body + """
</body></html>"""

html_path = Path("docs/images/terminal_preview.html")
html_path.parent.mkdir(parents=True, exist_ok=True)
html_path.write_text(page_html, encoding="utf-8")

# 2. Screenshot with Playwright
out_path = Path("docs/images/demo_terminal.png")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={"width": 920, "height": 800},
        device_scale_factor=2,
    )
    page.goto("file:///" + str(html_path.resolve()).replace("\\", "/"))
    page.wait_for_timeout(1500)
    # Clip top portion: header + axes + alignment + pollution + structural
    page.screenshot(
        path=str(out_path),
        clip={"x": 0, "y": 0, "width": 920, "height": 780},
    )
    browser.close()

print(f"PNG saved: {out_path} ({out_path.stat().st_size:,} bytes)")
