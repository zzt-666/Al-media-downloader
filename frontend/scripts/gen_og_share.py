"""One-off helper: generate public/og-share.png (1200x630)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
OUT = Path(__file__).resolve().parents[1] / "public" / "og-share.png"


def main() -> None:
    img = Image.new("RGBA", (W, H), (244, 247, 251, 255))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / (H - 1)
        r = int(244 + (232 - 244) * t)
        g = int(247 + (243 - 247) * t)
        b = int(251 + (255 - 251) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-120, -160, 420, 380), fill=(23, 119, 255, 28))
    od.ellipse((820, 280, 1380, 820), fill=(59, 155, 255, 22))
    od.ellipse((980, -80, 1280, 220), fill=(13, 94, 217, 18))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((528, 118, 672, 262), radius=28, fill="#1777ff")
    draw.polygon([(578, 155), (578, 225), (638, 190)], fill="#ffffff")

    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    for path in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\msyhbd.ttc",
    ):
        if Path(path).exists():
            font_title = ImageFont.truetype(path, 92)
            font_sub = ImageFont.truetype(path, 34)
            break

    def center_text(text: str, font: ImageFont.ImageFont, y: int, fill: str) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

    center_text("Linkora", font_title, 300, "#0f172a")
    center_text("Download & Summarize Videos", font_sub, 420, "#64748b")
    draw.rectangle((0, 610, W, 630), fill="#1777ff")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
