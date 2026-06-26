"""Generate brand artwork for the NMA Mobile Credentials integration.

Outputs into ``custom_components/nma/brand/`` so Home Assistant's local
brands proxy (HA 2026.3+) serves them at
``/api/brands/integration/nma/<image>`` — making the logo appear on the
Integrations page and device cards. No home-assistant/brands PR is needed
(that repo no longer accepts custom-integration submissions).

Files produced:

    icon.png            256x256   rounded gradient badge + phone/key glyph
    icon@2x.png         512x512
    logo.png            ~440x256  badge + wordmark, DARK text (light UI)
    logo@2x.png         ~880x512
    dark_logo.png       ~440x256  badge + wordmark, LIGHT text (dark UI)
    dark_logo@2x.png    ~880x512

The badge icon has its own coloured background, so it reads well on both
light and dark themes; no separate dark_icon is required (HA falls back to
icon.png for dark themes automatically).

Run:
    python3 scripts/make_brand.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "nma" / "brand"

PALETTE_TOP = (25, 118, 210)     # HA-aligned blue (#1976D2)
PALETTE_BOTTOM = (0, 137, 123)   # teal (#00897B)
INK = (255, 255, 255)            # white phone/key on the badge

# Wordmark colours per theme.
LIGHT_TITLE = (15, 23, 42)       # slate-900
LIGHT_SUBTITLE = (71, 85, 105)   # slate-600
DARK_TITLE = (255, 255, 255)     # white
DARK_SUBTITLE = (148, 163, 184)  # slate-400


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def linear_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
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
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0], size[1]), radius, fill=255)
    return m


def find_font(size: int) -> ImageFont.FreeTypeFont:
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


def _masked(img: Image.Image, mask: Image.Image) -> Image.Image:
    r, g, b, a = img.split()
    a = Image.composite(a, Image.new("L", img.size, 0), mask)
    return Image.merge("RGBA", (r, g, b, a))


# --------------------------------------------------------------------------- #
# Glyph: white phone with a key
# --------------------------------------------------------------------------- #
def draw_glyph(img: Image.Image) -> None:
    w, h = img.size
    cx, cy = w / 2, h / 2
    d = ImageDraw.Draw(img, "RGBA")

    pw = w * 0.46
    ph = h * 0.64
    px0, py0 = cx - pw / 2, cy - ph / 2
    px1, py1 = cx + pw / 2, cy + ph / 2
    radius = int(min(pw, ph) * 0.18)
    stroke_w = max(2, int(w * 0.025))

    d.rounded_rectangle((px0, py0, px1, py1), radius=radius,
                        outline=INK + (255,), width=stroke_w)

    grille_w = pw * 0.28
    grille_h = max(2, int(h * 0.012))
    gx0 = cx - grille_w / 2
    gy0 = py0 + ph * 0.08
    d.rounded_rectangle((gx0, gy0, gx0 + grille_w, gy0 + grille_h),
                        radius=grille_h, fill=INK + (255,))

    home_w = pw * 0.30
    home_h = max(2, int(h * 0.012))
    hx0 = cx - home_w / 2
    hy0 = py1 - ph * 0.08 - home_h
    d.rounded_rectangle((hx0, hy0, hx0 + home_w, hy0 + home_h),
                        radius=home_h, fill=INK + (255,))

    bow_r = pw * 0.18
    bow_cx = cx - pw * 0.10
    bow_cy = cy
    d.ellipse((bow_cx - bow_r, bow_cy - bow_r, bow_cx + bow_r, bow_cy + bow_r),
              outline=INK + (255,), width=stroke_w)

    shaft_h = bow_r * 0.55
    shaft_x0 = bow_cx + bow_r * 0.85
    shaft_y0 = bow_cy - shaft_h / 2
    shaft_x1 = px1 - pw * 0.12
    shaft_y1 = bow_cy + shaft_h / 2
    d.rounded_rectangle((shaft_x0, shaft_y0, shaft_x1, shaft_y1),
                        radius=int(shaft_h * 0.4), fill=INK + (255,))

    tooth_w = (shaft_x1 - shaft_x0) * 0.16
    tooth_h = shaft_h * 0.9
    for frac in (0.55, 0.85):
        tx0 = shaft_x0 + (shaft_x1 - shaft_x0) * frac - tooth_w / 2
        ty0 = shaft_y1
        d.rounded_rectangle((tx0, ty0, tx0 + tooth_w, ty0 + tooth_h),
                            radius=int(tooth_w * 0.3), fill=INK + (255,))


# --------------------------------------------------------------------------- #
# Icon
# --------------------------------------------------------------------------- #
def make_icon(size: int) -> Image.Image:
    s = size * 2
    badge = linear_gradient((s, s), PALETTE_TOP, PALETTE_BOTTOM)
    mask = rounded_mask((s, s), int(s * 0.22))
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(badge, (0, 0), mask)

    glow = Image.new("L", (s, s), 0)
    ImageDraw.Draw(glow).ellipse((-s * 0.15, -s * 0.55, s * 1.15, s * 0.45), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.06))
    highlight = Image.new("RGBA", (s, s), (255, 255, 255, 0))
    highlight.putalpha(glow)
    out = Image.alpha_composite(out, _masked(highlight, mask))

    draw_glyph(out)
    return out.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------- #
# Logo (icon + wordmark), theme-aware text colour
# --------------------------------------------------------------------------- #
def make_logo(height: int, title_color, subtitle_color) -> Image.Image:
    icon = make_icon(height)
    gap = int(height * 0.18)

    title_size = int(height * 0.54)
    subtitle_size = int(height * 0.20)
    title_font = find_font(title_size)
    subtitle_font = find_font(subtitle_size)

    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    title_w = tmp.textlength("NMA", font=title_font)
    subtitle_w = tmp.textlength("Mobile Credentials", font=subtitle_font)
    text_w = int(max(title_w, subtitle_w))

    total_w = height + gap + text_w + int(height * 0.05)
    out = Image.new("RGBA", (total_w, height), (0, 0, 0, 0))
    out.alpha_composite(icon, (0, 0))

    d = ImageDraw.Draw(out)
    text_x = height + gap
    title_h = title_size
    subtitle_h = subtitle_size
    block_h = title_h + int(height * 0.04) + subtitle_h
    block_y0 = (height - block_h) // 2

    d.text((text_x, block_y0 - int(height * 0.06)), "NMA",
           font=title_font, fill=title_color + (255,))
    d.text((text_x, block_y0 + title_h - int(height * 0.06)),
           "Mobile Credentials", font=subtitle_font, fill=subtitle_color + (255,))
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {
        "icon.png": make_icon(256),
        "icon@2x.png": make_icon(512),
        "logo.png": make_logo(256, LIGHT_TITLE, LIGHT_SUBTITLE),
        "logo@2x.png": make_logo(512, LIGHT_TITLE, LIGHT_SUBTITLE),
        "dark_logo.png": make_logo(256, DARK_TITLE, DARK_SUBTITLE),
        "dark_logo@2x.png": make_logo(512, DARK_TITLE, DARK_SUBTITLE),
    }
    for name, img in outputs.items():
        img.save(OUT_DIR / name, optimize=True)
        size = (OUT_DIR / name).stat().st_size
        print(f"  {name:18s} {size:>7d} bytes")
    print(f"\nWritten to {OUT_DIR}")


if __name__ == "__main__":
    main()
