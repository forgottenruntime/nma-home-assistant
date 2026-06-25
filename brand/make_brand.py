"""Generate brand artwork for the NMA Mobile Credentials integration.

Produces, in this same folder:

    icon.png      256x256   rounded-square badge
    icon@2x.png   512x512
    logo.png      ~440x256  wordmark (icon + "NMA Mobile Credentials")
    logo@2x.png   ~880x512

Run:
    python3 brand/make_brand.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).parent
PALETTE_TOP = (25, 118, 210)     # HA-aligned blue (#1976D2)
PALETTE_BOTTOM = (0, 137, 123)   # teal (#00897B)
INK = (255, 255, 255)            # white phone/key on the badge
DARK = (15, 23, 42)              # slate-900 for wordmark text


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def linear_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    """Vertical linear gradient image."""
    w, h = size
    base = Image.new("RGB", size, top)
    pixels = base.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(w):
            pixels[x, y] = (r, g, b)
    return base


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """L-mode mask: rounded rectangle filled with 255 inside, 0 outside."""
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0], size[1]), radius, fill=255)
    return m


def find_font(size: int) -> ImageFont.FreeTypeFont:
    """Find a reasonable bold sans-serif font (macOS-friendly fallbacks)."""
    candidates = [
        "/System/Library/Fonts/SFNSRounded.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


# --------------------------------------------------------------------------- #
# Icon glyph: white phone with a key on its screen
# --------------------------------------------------------------------------- #
def draw_glyph(img: Image.Image) -> None:
    """Draw a white smartphone-with-key glyph centered on `img`."""
    w, h = img.size
    cx, cy = w / 2, h / 2
    d = ImageDraw.Draw(img, "RGBA")

    # Phone body — vertical rounded rectangle.
    pw = w * 0.46
    ph = h * 0.64
    px0, py0 = cx - pw / 2, cy - ph / 2
    px1, py1 = cx + pw / 2, cy + ph / 2
    radius = int(min(pw, ph) * 0.18)
    stroke_w = max(2, int(w * 0.025))

    d.rounded_rectangle((px0, py0, px1, py1), radius=radius,
                        outline=INK + (255,), width=stroke_w)

    # Speaker grille — small horizontal pill near the top of the phone.
    grille_w = pw * 0.28
    grille_h = max(2, int(h * 0.012))
    gx0 = cx - grille_w / 2
    gy0 = py0 + ph * 0.08
    d.rounded_rectangle(
        (gx0, gy0, gx0 + grille_w, gy0 + grille_h),
        radius=grille_h, fill=INK + (255,),
    )

    # Home indicator — small horizontal pill near the bottom of the phone.
    home_w = pw * 0.30
    home_h = max(2, int(h * 0.012))
    hx0 = cx - home_w / 2
    hy0 = py1 - ph * 0.08 - home_h
    d.rounded_rectangle(
        (hx0, hy0, hx0 + home_w, hy0 + home_h),
        radius=home_h, fill=INK + (255,),
    )

    # Key sitting inside the screen area (bow + shaft + 2 teeth).
    # Bow = circle.
    bow_r = pw * 0.18
    bow_cx = cx - pw * 0.10
    bow_cy = cy
    d.ellipse(
        (bow_cx - bow_r, bow_cy - bow_r, bow_cx + bow_r, bow_cy + bow_r),
        outline=INK + (255,), width=stroke_w,
    )
    # Bow inner hole — subtract by painting a smaller filled circle in bg.
    # Instead we leave the outline only, which already reads as a bow.

    # Shaft = rectangle to the right of the bow.
    shaft_h = bow_r * 0.55
    shaft_x0 = bow_cx + bow_r * 0.85
    shaft_y0 = bow_cy - shaft_h / 2
    shaft_x1 = px1 - pw * 0.12
    shaft_y1 = bow_cy + shaft_h / 2
    d.rounded_rectangle(
        (shaft_x0, shaft_y0, shaft_x1, shaft_y1),
        radius=int(shaft_h * 0.4),
        fill=INK + (255,),
    )

    # Two teeth on the bottom edge of the shaft.
    tooth_w = (shaft_x1 - shaft_x0) * 0.16
    tooth_h = shaft_h * 0.9
    for i, frac in enumerate((0.55, 0.85)):
        tx0 = shaft_x0 + (shaft_x1 - shaft_x0) * frac - tooth_w / 2
        ty0 = shaft_y1
        d.rounded_rectangle(
            (tx0, ty0, tx0 + tooth_w, ty0 + tooth_h),
            radius=int(tooth_w * 0.3),
            fill=INK + (255,),
        )


# --------------------------------------------------------------------------- #
# Icon (square badge)
# --------------------------------------------------------------------------- #
def make_icon(size: int) -> Image.Image:
    """Rounded square gradient badge with phone-key glyph."""
    # Render at 2x then downsample for crisp AA edges.
    s = size * 2
    badge = linear_gradient((s, s), PALETTE_TOP, PALETTE_BOTTOM)
    mask = rounded_mask((s, s), int(s * 0.22))
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(badge, (0, 0), mask)

    # Subtle inner glow / highlight at top to lift the gradient.
    glow = Image.new("L", (s, s), 0)
    ImageDraw.Draw(glow).ellipse(
        (-s * 0.15, -s * 0.55, s * 1.15, s * 0.45),
        fill=70,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.06))
    highlight = Image.new("RGBA", (s, s), (255, 255, 255, 0))
    highlight.putalpha(glow)
    out = Image.alpha_composite(out, _masked(highlight, mask))

    draw_glyph(out)
    return out.resize((size, size), Image.LANCZOS)


def _masked(img: Image.Image, mask: Image.Image) -> Image.Image:
    """Apply an alpha mask to an RGBA image, returning a new RGBA image."""
    r, g, b, a = img.split()
    a = Image.eval(a, lambda v: v)  # copy
    a = Image.composite(a, Image.new("L", img.size, 0), mask)
    return Image.merge("RGBA", (r, g, b, a))


# --------------------------------------------------------------------------- #
# Logo (icon + wordmark)
# --------------------------------------------------------------------------- #
def make_logo(height: int) -> Image.Image:
    """Icon on the left + 'NMA' wordmark + 'Mobile Credentials' subtitle."""
    icon = make_icon(height)
    gap = int(height * 0.18)

    # Reserve space for the text by measuring with a tmp draw.
    title_size = int(height * 0.54)
    subtitle_size = int(height * 0.20)
    title_font = find_font(title_size)
    subtitle_font = find_font(subtitle_size)

    tmp = Image.new("RGBA", (10, 10))
    tdraw = ImageDraw.Draw(tmp)
    title_w = tdraw.textlength("NMA", font=title_font)
    subtitle_w = tdraw.textlength("Mobile Credentials", font=subtitle_font)
    text_w = int(max(title_w, subtitle_w))

    total_w = height + gap + text_w + int(height * 0.05)
    out = Image.new("RGBA", (total_w, height), (0, 0, 0, 0))
    out.alpha_composite(icon, (0, 0))

    d = ImageDraw.Draw(out)
    text_x = height + gap

    # Vertically centre the two-line block.
    title_h = title_size
    subtitle_h = subtitle_size
    block_h = title_h + int(height * 0.04) + subtitle_h
    block_y0 = (height - block_h) // 2

    d.text((text_x, block_y0 - int(height * 0.06)), "NMA",
           font=title_font, fill=DARK + (255,))
    d.text(
        (text_x, block_y0 + title_h - int(height * 0.06)),
        "Mobile Credentials",
        font=subtitle_font,
        fill=(71, 85, 105, 255),
    )
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    icon_1x = make_icon(256)
    icon_2x = make_icon(512)
    logo_1x = make_logo(256)
    logo_2x = make_logo(512)

    icon_1x.save(OUT_DIR / "icon.png", optimize=True)
    icon_2x.save(OUT_DIR / "icon@2x.png", optimize=True)
    logo_1x.save(OUT_DIR / "logo.png", optimize=True)
    logo_2x.save(OUT_DIR / "logo@2x.png", optimize=True)

    for p in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        size = (OUT_DIR / p).stat().st_size
        print(f"  {p:14s} {size:>7d} bytes")


if __name__ == "__main__":
    main()
