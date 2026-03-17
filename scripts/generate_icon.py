"""
Utility script to generate a simple icon.ico for the app.
Run once: uv run python scripts/generate_icon.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

sizes = [16, 32,48, 64, 128, 256]
images = []
for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(80, 160, 80),
        outline=(255, 255, 255),
        width=max(1, size // 16),
    )
    images.append(img)

out_path = Path(__file__).parent.parent / "assets" / "icon.ico"
out_path.parent.mkdir(exist_ok=True)
images[0].save(
    out_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[1:],
)
print(f"Icon saved to {out_path}")
