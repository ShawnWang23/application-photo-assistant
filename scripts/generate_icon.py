from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    size = 512
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, 492, 492), radius=105, fill="#172A56")
    draw.ellipse((285, -45, 555, 225), fill="#3157D5")
    draw.rounded_rectangle((105, 75, 407, 437), radius=34, fill="#F7F9FF")
    draw.ellipse((191, 128, 321, 258), fill="#A9C3FF")
    draw.rounded_rectangle((155, 266, 357, 377), radius=55, fill="#A9C3FF")
    accent = "#3157D5"
    width = 17
    length = 58
    for x, y, sx, sy in (
        (82, 95, 1, 1),
        (430, 95, -1, 1),
        (82, 417, 1, -1),
        (430, 417, -1, -1),
    ):
        draw.line((x, y, x + sx * length, y), fill=accent, width=width)
        draw.line((x, y, x, y + sy * length), fill=accent, width=width)
    output = Path(__file__).resolve().parents[1] / "assets" / "app.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )


if __name__ == "__main__":
    main()
