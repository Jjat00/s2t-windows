"""
Genera assets/icon.ico con un ícono de micrófono en estilo Vercel dark.
Run: uv run python scripts/generate_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "assets" / "icon.ico"
OUT.parent.mkdir(exist_ok=True)

SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_mic(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fg = "#ededed"
    stroke = max(1, round(size * 0.055))

    # ── background circle ────────────────────────────────────────────────
    d.ellipse([0, 0, size - 1, size - 1], fill="#000000")

    # ── mic capsule (rounded rectangle) ─────────────────────────────────
    cx      = size / 2
    cap_w   = size * 0.30
    cap_h   = size * 0.36
    cap_top = size * 0.10
    cap_bot = cap_top + cap_h
    d.rounded_rectangle(
        [cx - cap_w / 2, cap_top, cx + cap_w / 2, cap_bot],
        radius=cap_w / 2,
        fill=fg,
    )

    # ── stand arc (U opening upward under the capsule) ───────────────────
    arc_r = size * 0.26
    # Bounding box centred at (cx, cap_bot) so arc tips sit at capsule level
    ab = [cx - arc_r, cap_bot - arc_r, cx + arc_r, cap_bot + arc_r]
    d.arc(ab, start=0, end=180, fill=fg, width=stroke)

    # ── vertical stem ────────────────────────────────────────────────────
    stem_top = cap_bot + arc_r          # bottom of arc
    stem_bot = size * 0.86
    d.line([cx, stem_top, cx, stem_bot], fill=fg, width=stroke)

    # ── base ─────────────────────────────────────────────────────────────
    base = size * 0.20
    d.line([cx - base, stem_bot, cx + base, stem_bot], fill=fg, width=stroke)

    return img


images = [draw_mic(s) for s in SIZES]
images[0].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[1:])
print(f"Icon saved: {OUT}  ({len(SIZES)} sizes)")
