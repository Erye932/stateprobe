"""Export mermaid blocks from docs/diagrams.md to PNG via mermaid.ink.

Strategy: parse the markdown for fenced ```mermaid``` blocks under each
``## 图 N: <name>`` heading, base64-encode the diagram source, and GET it
from https://mermaid.ink/img/<b64>?type=png. No local install required.

Run from repo root:
    python scripts/export_diagrams.py
"""

from __future__ import annotations

import base64
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "docs" / "diagrams.md"
OUT_DIR = REPO_ROOT / "docs" / "images"

HEADING_RE = re.compile(r"^##\s+图\s*(\d+)[：:]?\s*(.+?)\s*$", re.MULTILINE)
MERMAID_BLOCK_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)

# Stable English slugs by figure number. Heading in diagrams.md may be in
# Chinese only, in which case the auto-slugifier degrades to a generic
# name. These overrides keep filenames meaningful and stable.
SLUG_OVERRIDES = {
    1: "hybrid_pipeline",
    2: "wrong_vs_right_arch",
    3: "polite_sycophancy_demo",
    4: "v02_to_v04_roadmap",
}

# mermaid.ink occasionally drops connections; retry transient failures.
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0


def slugify(text: str) -> str:
    """Build a filesystem-friendly slug from a Chinese/English heading.

    The slug is lossy but stable; we keep ASCII letters and digits, drop
    punctuation, and replace anything else with underscores.
    """
    text = text.replace("·", "_").replace("/", "_")
    cleaned = []
    last_was_underscore = False
    for ch in text:
        if ch.isalnum() and ord(ch) < 128:
            cleaned.append(ch.lower())
            last_was_underscore = False
        else:
            if not last_was_underscore:
                cleaned.append("_")
                last_was_underscore = True
    slug = "".join(cleaned).strip("_")
    return slug or "diagram"


def split_sections(markdown: str) -> list[tuple[int, str, str]]:
    """Return (figure_number, slug, section_text) for each ``## 图 N: …`` block.

    section_text starts at the heading and ends right before the next ``##``
    heading (or EOF). This lets us scope the mermaid extraction to one
    figure at a time so each figure picks up its own mermaid block.
    """
    sections = []
    matches = list(HEADING_RE.finditer(markdown))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        n = int(m.group(1))
        title = m.group(2).strip()
        sections.append((n, slugify(title), markdown[start:end]))
    return sections


def encode_for_mermaid_ink(diagram_source: str) -> str:
    """Base64-encode the diagram source the way mermaid.ink expects."""
    raw = diagram_source.encode("utf-8")
    # mermaid.ink wants url-safe base64 without padding stripped
    return base64.urlsafe_b64encode(raw).decode("ascii")


def fetch_png(diagram_source: str, *, bg: str = "white") -> bytes:
    """Fetch a PNG from mermaid.ink, with retry on transient failures."""
    encoded = encode_for_mermaid_ink(diagram_source)
    url = f"https://mermaid.ink/img/{encoded}?type=png&bgColor={bg}"
    req = Request(url, headers={"User-Agent": "stateprobe-diagram-export/1.0"})
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"mermaid.ink returned HTTP {resp.status}")
                return resp.read()
        except Exception as exc:  # noqa: BLE001 — broad on purpose, want retry
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    assert last_exc is not None
    raise last_exc


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: {SOURCE} not found", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    markdown = SOURCE.read_text(encoding="utf-8")
    sections = split_sections(markdown)
    if not sections:
        print("ERROR: no '## 图 N:' headings found", file=sys.stderr)
        return 1

    exported = 0
    failed = 0
    for n, auto_slug, body in sections:
        mermaid_match = MERMAID_BLOCK_RE.search(body)
        if not mermaid_match:
            print(f"  图 {n} ({auto_slug}): no mermaid block, skipping")
            continue

        diagram_source = mermaid_match.group(1).strip()
        slug = SLUG_OVERRIDES.get(n, auto_slug)
        out_path = OUT_DIR / f"diagram_{n:02d}_{slug}.png"

        print(f"  图 {n} ({slug}) → {out_path.name} ...", end=" ", flush=True)
        try:
            png_bytes = fetch_png(diagram_source)
            out_path.write_bytes(png_bytes)
            print(f"OK ({len(png_bytes):,} bytes)")
            exported += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: {exc}")
            failed += 1

    print()
    print(f"Exported {exported} diagram(s) to {OUT_DIR.relative_to(REPO_ROOT)}")
    if failed:
        print(f"WARN: {failed} diagram(s) failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
