"""Generate the 1280x640 GitHub social preview image.

GitHub renders this image (Repo Settings -> General -> Social preview) on
Twitter / HN / Reddit / X / Slack link cards. Spec: 1280x640 PNG, ideally
< 1MB. We render a high-star convention banner: large A2 hero on top, a
terminal-style preview of `stateprobe skill preview` below, install hint
in the footer.

Run from the repo root:

    python scripts/generate_social_preview.py

Outputs ``docs/images/social_preview.png``.

The script is intentionally self-contained (no template files, no extra
asset deps) so the social preview can be regenerated after future hero
or branding changes without external tooling.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "social_preview.png"

W, H = 1280, 640

# Tailwind slate / accent palette — matches the dark-mode terminal feel
# of the Carbon screenshot we used as a reference during the launch
# repackaging.
BG = (15, 23, 42)         # slate-900
PANEL = (30, 41, 59)      # slate-800
HAIRLINE = (51, 65, 85)   # slate-700
FG = (241, 245, 249)      # slate-100
MUTED = (148, 163, 184)   # slate-400
CYAN = (34, 211, 238)     # cyan-400
AMBER = (251, 191, 36)    # amber-400
GREEN = (134, 239, 172)   # green-300
RED = (252, 165, 165)     # red-300


def load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Try a list of font filenames and return the first one that loads.

    Looks in the current dir and ``C:/Windows/Fonts`` (the script targets
    Windows-first because that's where the project is developed; the
    fallbacks cover macOS/Linux common fonts too).
    """
    search_dirs = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path("."),
    ]
    for name in candidates:
        for base in search_dirs:
            candidate = base / name
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size)
                except OSError:
                    continue
        # Also try by bare name (PIL searches system paths)
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Sans-serif heavy for the hero. Cascadia Mono / Consolas for the
    # terminal block (Carbon-like). Fallback chain covers Win/macOS/Linux.
    f_hero = load_font(
        ["seguisb.ttf", "Inter-Bold.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"],
        72,
    )
    f_sub = load_font(
        ["segoeui.ttf", "Inter-Regular.ttf", "Arial.ttf", "DejaVuSans.ttf"],
        28,
    )
    f_mono = load_font(
        [
            "CascadiaMono.ttf",
            "CascadiaCode.ttf",
            "consola.ttf",
            "Menlo.ttc",
            "DejaVuSansMono.ttf",
            "cour.ttf",
        ],
        20,
    )
    f_label = load_font(
        ["segoeui.ttf", "Inter-Regular.ttf", "Arial.ttf", "DejaVuSans.ttf"],
        18,
    )
    f_brand = load_font(
        ["seguisb.ttf", "Inter-Bold.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"],
        22,
    )

    # --- Brand strip (top-left, small) ---------------------------------
    draw.text((80, 50), "StateProbe", font=f_brand, fill=MUTED)

    # --- Hero ----------------------------------------------------------
    draw.text((80, 100), "The attention layer", font=f_hero, fill=FG)
    draw.text((80, 184), "for LLM agents.", font=f_hero, fill=CYAN)

    # --- Subline -------------------------------------------------------
    draw.text(
        (80, 288),
        "See what the model fires — before agents ship.",
        font=f_sub,
        fill=MUTED,
    )

    # --- Terminal panel ------------------------------------------------
    tx, ty = 80, 360
    tw, th = 1120, 220
    draw.rounded_rectangle(
        (tx, ty, tx + tw, ty + th), radius=14, fill=PANEL, outline=HAIRLINE, width=1
    )
    # Traffic lights
    cy = ty + 24
    for i, color in enumerate([(239, 68, 68), (251, 191, 36), (34, 197, 94)]):
        cx0 = tx + 22 + i * 26
        draw.ellipse((cx0, cy, cx0 + 14, cy + 14), fill=color)

    # Terminal text block
    cx = tx + 30
    line_y = ty + 60
    line_h = 28

    draw.text((cx, line_y), "$ stateprobe skill preview ...", font=f_mono, fill=GREEN)
    line_y += int(line_h * 1.4)

    draw.text((cx, line_y), "!  rewrite_planned_focus", font=f_mono, fill=AMBER)
    line_y += line_h
    draw.text(
        (cx, line_y),
        "   plan misses user's actual must — don't ship.",
        font=f_mono,
        fill=FG,
    )
    line_y += line_h + 6
    draw.text(
        (cx, line_y),
        "   user wants:    safety guidance, current APIs only",
        font=f_mono,
        fill=GREEN,
    )
    line_y += line_h
    draw.text(
        (cx, line_y),
        "   agent planned: enumerate deprecated APIs (the opposite)",
        font=f_mono,
        fill=RED,
    )

    # --- Footer --------------------------------------------------------
    draw.text((80, 596), "pip install stateprobe", font=f_label, fill=MUTED)

    url = "github.com/Erye932/stateprobe"
    url_bbox = draw.textbbox((0, 0), url, font=f_label)
    url_w = url_bbox[2] - url_bbox[0]
    draw.text((W - 80 - url_w, 596), url, font=f_label, fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"saved {OUT.relative_to(ROOT)} ({W}x{H})")


if __name__ == "__main__":
    main()
