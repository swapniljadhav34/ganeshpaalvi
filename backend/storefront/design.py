"""
The Paalvi design kit: every shape, animation and effect the owner can pick in the admin.

This file is the single source of truth. The admin dropdowns, the admin preview and the
website all read these same definitions (the website gets them through /api/bootstrap),
so what you pick in the admin is exactly what visitors see.
"""

import math


def _polygon(points):
    return "polygon(" + ", ".join(f"{x:.1f}% {y:.1f}%" for x, y in points) + ")"


def _scallop(n=14, depth=6):
    """A soft scalloped 'seal' outline (like a premium badge)."""
    pts = []
    for i in range(n * 8):
        a = 2 * math.pi * i / (n * 8)
        r = 50 - depth / 2 + (depth / 2) * math.cos(a * n)
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    return _polygon(pts)


def _star(n=8, inner=38):
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n - math.pi / 2
        r = 50 if i % 2 == 0 else inner
        pts.append((50 + r * math.cos(a), 50 + r * math.sin(a)))
    return _polygon(pts)


def _wave_bottom(waves=3, amp=4):
    pts = [(0, 0), (100, 0)]
    steps = 40
    for i in range(steps, -1, -1):
        x = 100 * i / steps
        pts.append((x, 100 - amp - amp * math.sin(2 * math.pi * waves * i / steps)))
    return _polygon(pts)


# ---------------------------------------------------------------------------
# Shapes — applied to photos, videos, galleries and product images.
# Each value is CSS (React style names). "square": True keeps a 1:1 box.
# ---------------------------------------------------------------------------
_TICKET = ("radial-gradient(circle 18px at 0 50%, #0000 97%, #000) left / 51% 100% no-repeat, "
           "radial-gradient(circle 18px at 100% 50%, #0000 97%, #000) right / 51% 100% no-repeat")

SHAPES = {
    "rectangle": {"label": "Sharp rectangle", "css": {"borderRadius": "0px"}},
    "soft": {"label": "Soft corners", "css": {"borderRadius": "16px"}},
    "rounded": {"label": "Rounded (pebble-soft)", "css": {"borderRadius": "28px"}},
    "squircle": {"label": "Squircle", "css": {"borderRadius": "32%"}},
    "pill": {"label": "Pill / capsule", "css": {"borderRadius": "999px"}},
    "circle": {"label": "Circle", "css": {"borderRadius": "50%"}, "square": True},
    "oval": {"label": "Oval", "css": {"borderRadius": "50%"}},
    "arch": {"label": "Arch (round top)", "css": {"borderRadius": "999px 999px 28px 28px"}},
    "arch_full": {"label": "Tall arch window", "css": {"borderRadius": "1000px 1000px 0 0"}},
    "arch_inverted": {"label": "Bowl (round bottom)", "css": {"borderRadius": "28px 28px 999px 999px"}},
    "pebble": {"label": "Pebble", "css": {"borderRadius": "42% 58% 55% 45% / 48% 42% 58% 52%"}},
    "blob": {"label": "Organic blob", "css": {"borderRadius": "63% 37% 54% 46% / 55% 48% 52% 45%"}},
    "droplet": {"label": "Water droplet", "css": {"borderRadius": "0 50% 50% 50%"}, "square": True},
    "leaf": {"label": "Leaf", "css": {"borderRadius": "4px 60% 4px 60%"}},
    "ticket": {"label": "Ticket (side notches)", "css": {"borderRadius": "20px", "WebkitMask": _TICKET, "mask": _TICKET}},
    "hexagon": {"label": "Hexagon", "css": {"clipPath": _polygon([(25, 0), (75, 0), (100, 50), (75, 100), (25, 100), (0, 50)])}},
    "diamond": {"label": "Diamond", "css": {"clipPath": _polygon([(50, 0), (100, 50), (50, 100), (0, 50)])}, "square": True},
    "octagon": {"label": "Octagon", "css": {"clipPath": _polygon([(30, 0), (70, 0), (100, 30), (100, 70), (70, 100), (30, 100), (0, 70), (0, 30)])}},
    "slanted": {"label": "Slanted bottom", "css": {"clipPath": _polygon([(0, 0), (100, 0), (100, 86), (0, 100)])}},
    "parallelogram": {"label": "Parallelogram", "css": {"clipPath": _polygon([(10, 0), (100, 0), (90, 100), (0, 100)])}},
    "wave": {"label": "Wavy bottom edge", "css": {"clipPath": _wave_bottom()}},
    "seal": {"label": "Scalloped seal", "css": {"clipPath": _scallop()}, "square": True},
    "star": {"label": "Soft star", "css": {"clipPath": _star(10, 40)}, "square": True},
}

# ---------------------------------------------------------------------------
# Entrance animations — how a block appears when scrolled into view.
# "from" / "to" use Framer Motion names (x, y, scale, rotate, rotateX, rotateY, skewY,
# opacity, filter, clipPath). Numbers are px / degrees.
# ---------------------------------------------------------------------------
ENTRANCES = {
    "none": {"label": "No animation", "from": {}, "to": {}},
    "fade": {"label": "Fade in", "from": {"opacity": 0}, "to": {"opacity": 1}},
    "fade_up": {"label": "Fade up", "from": {"opacity": 0, "y": 48}, "to": {"opacity": 1, "y": 0}},
    "fade_down": {"label": "Fade down", "from": {"opacity": 0, "y": -48}, "to": {"opacity": 1, "y": 0}},
    "slide_left": {"label": "Slide in from right", "from": {"opacity": 0, "x": 90}, "to": {"opacity": 1, "x": 0}},
    "slide_right": {"label": "Slide in from left", "from": {"opacity": 0, "x": -90}, "to": {"opacity": 1, "x": 0}},
    "zoom_in": {"label": "Zoom in", "from": {"opacity": 0, "scale": 0.82}, "to": {"opacity": 1, "scale": 1}},
    "zoom_out": {"label": "Zoom out (settle)", "from": {"opacity": 0, "scale": 1.18}, "to": {"opacity": 1, "scale": 1}},
    "blur_in": {"label": "Blur to sharp", "from": {"opacity": 0, "filter": "blur(18px)", "scale": 1.04},
                "to": {"opacity": 1, "filter": "blur(0px)", "scale": 1}},
    "flip_up": {"label": "Flip up (3D)", "from": {"opacity": 0, "rotateX": 65, "y": 40, "transformPerspective": 900},
                "to": {"opacity": 1, "rotateX": 0, "y": 0, "transformPerspective": 900}},
    "flip_side": {"label": "Swing in (3D)", "from": {"opacity": 0, "rotateY": -55, "transformPerspective": 900},
                  "to": {"opacity": 1, "rotateY": 0, "transformPerspective": 900}},
    "rotate_in": {"label": "Rotate in", "from": {"opacity": 0, "rotate": -9, "y": 40}, "to": {"opacity": 1, "rotate": 0, "y": 0}},
    "skew_up": {"label": "Skew up", "from": {"opacity": 0, "skewY": 7, "y": 70}, "to": {"opacity": 1, "skewY": 0, "y": 0}},
    "wipe_up": {"label": "Wipe reveal (bottom → top)", "from": {"clipPath": "inset(100% 0% 0% 0%)"}, "to": {"clipPath": "inset(0% 0% 0% 0%)"}},
    "wipe_left": {"label": "Wipe reveal (left → right)", "from": {"clipPath": "inset(0% 100% 0% 0%)"}, "to": {"clipPath": "inset(0% 0% 0% 0%)"}},
    "iris": {"label": "Circle reveal", "from": {"clipPath": "circle(0% at 50% 50%)"}, "to": {"clipPath": "circle(100% at 50% 50%)"}},
    "bounce": {"label": "Bounce up", "from": {"opacity": 0, "y": 80}, "to": {"opacity": 1, "y": 0}, "spring": True},
    "drop_in": {"label": "Drop in", "from": {"opacity": 0, "y": -90, "scale": 1.06}, "to": {"opacity": 1, "y": 0, "scale": 1}, "spring": True},
}

TEXT_ANIMATIONS = {
    "none": "No animation",
    "fade": "Fade in",
    "rise_words": "Words rise from a mask (signature)",
    "rise_letters": "Letters rise one by one",
    "blur_words": "Words blur into focus",
    "typewriter": "Typewriter",
    "wave": "Letters wave (loops gently)",
    "scale_words": "Words pop in",
    "slide_words": "Words slide in from the side",
    "flip_letters": "Letters flip in (3D)",
    "scramble": "Decode / scramble",
    "shimmer": "Shimmering light sweep (loops)",
    "highlight": "Marker highlight sweep",
    "gradient_flow": "Flowing colour gradient (loops)",
}

HOVER_EFFECTS = {
    "none": "Nothing",
    "lift": "Lift up with soft shadow",
    "tilt_3d": "3D tilt follows the mouse",
    "magnetic": "Magnetic pull towards the mouse",
    "zoom": "Zoom the picture",
    "glow": "Soft colour glow",
    "shine": "Light sweep across",
    "rotate": "Gentle rotate",
    "spotlight": "Spotlight follows the mouse",
    "press": "Press down",
}

MEDIA_MOTIONS = {
    "none": "Still",
    "float": "Float up and down",
    "ken_burns": "Slow zoom & pan (Ken Burns)",
    "breathe": "Breathe (slow scale)",
    "sway": "Sway side to side",
    "slow_spin": "Very slow spin",
    "morph": "Shape morphs like liquid",
    "drift": "Drift in a slow circle",
    "scroll_parallax": "Parallax while scrolling",
}

GALLERY_STYLES = {
    "fade": "Cross-fade",
    "slide": "Slide",
    "zoom": "Zoom fade",
    "ken_burns": "Ken Burns cross-fade",
    "flip": "3D flip",
    "cube": "3D cube turn",
    "stack": "Card stack (swipe)",
    "coverflow": "Coverflow (3D carousel)",
    "marquee": "Endless scroll strip",
    "grid": "Grid / mosaic (all at once)",
    "polaroid": "Scattered polaroids",
    "blinds": "Venetian blinds wipe",
}

POINTER_EFFECTS = {
    "none": "Nothing",
    "parallax": "Layers follow the mouse (depth)",
    "tilt": "Whole block tilts in 3D",
    "spotlight": "Soft light follows the mouse",
    "ripple": "Ripples where you click / tap",
}

DECOR_SHAPES = {
    "none": "None",
    "blob": "Morphing blob",
    "orb": "Glowing gradient orb",
    "rings": "Concentric rings",
    "dots": "Dot grid",
    "waves": "Flowing wave lines",
    "arch_outline": "Arch outline",
    "bubbles": "Floating bubbles",
    "grid_lines": "Fine grid lines",
    "sparkles": "Twinkling sparkles",
    "leaves": "Drifting leaves",
}

DIVIDERS = {
    "none": "Straight edge",
    "wave": "Wave",
    "curve": "Soft curve",
    "tilt": "Tilted edge",
    "zigzag": "Zigzag",
    "arch": "Arch",
    "drip": "Drips",
    "mountains": "Layered hills",
    "scallop": "Scallops",
}

SPEEDS = {"slow": "Slow & calm", "normal": "Normal", "fast": "Quick & lively"}

# ---------------------------------------------------------------------------
# 24 hero layouts. "media" = how many photos/videos the layout looks best with.
# ---------------------------------------------------------------------------
HERO_LAYOUTS = {
    "cinematic": ("Cinematic full screen", "Full-screen video or photo, words bottom-left, settles as you scroll.", "1 video or photo"),
    "centered": ("Centered statement", "Full-screen media with words in the middle.", "1+"),
    "slideshow": ("Ken Burns slideshow", "Full-screen photos slowly zooming and cross-fading.", "3–6 photos"),
    "split_screen": ("Split screen", "Colour panel with words on one side, media fills the other half.", "1+"),
    "curtain": ("Curtain reveal", "Two panels slide apart to reveal the media.", "1"),
    "zoom_scroll": ("Zoom on scroll", "Media starts small in your chosen shape and grows to full screen as you scroll.", "1"),
    "spotlight": ("Torch spotlight", "Dark screen; a soft light follows the mouse to reveal the picture.", "1 photo"),
    "text_mask": ("Video inside text", "Giant headline filled with your video or photo.", "1 video"),
    "split_shape": ("Words + shaped media", "Words on the left, media in your chosen shape on the right.", "1+"),
    "split_shape_reverse": ("Shaped media + words", "Media in your shape on the left, words on the right.", "1+"),
    "arch_window": ("Arch window", "Tall arch-framed media in the middle with the headline across it.", "1+"),
    "product_spotlight": ("Product spotlight", "Big product shot with floating benefit chips that follow the mouse.", "1 product photo"),
    "tilt_card": ("3D tilt card", "Media on a large card that tilts as the mouse moves.", "1+"),
    "framed": ("Framed inset", "Media inside a soft frame with words on a frosted glass panel.", "1+"),
    "diagonal": ("Diagonal split", "Media and words divided by a bold diagonal.", "1+"),
    "orbit": ("Orbit", "Circular media in the middle with small photos orbiting around it.", "4–8 photos"),
    "collage": ("Floating collage", "Layered photos at different depths that move with the mouse.", "3–5 photos"),
    "bento": ("Bento grid", "A neat grid of photo and video tiles around your words.", "4–5"),
    "stacked_cards": ("Card stack", "A deck of photo cards that shuffles automatically (swipe on phones).", "3–6"),
    "polaroid": ("Polaroid scatter", "Scattered instant photos you can drag around.", "3–6 photos"),
    "marquee_wall": ("Moving photo wall", "Rows of photos gliding in opposite directions behind the words.", "6+ photos"),
    "coverflow": ("Coverflow carousel", "A 3D carousel of photos under the headline.", "4–8"),
    "kinetic_type": ("Kinetic typography", "Huge sliding words with a small media capsule.", "1"),
    "minimal_type": ("Minimal type + gradient", "Elegant words over a slow, living colour gradient. No media needed.", "0"),
}


def choices(registry, with_default=False):
    """Turn a registry into Django `choices`. `with_default` adds 'Use site default' (empty value)."""
    out = [("", "— Use site default —")] if with_default else []
    for key, val in registry.items():
        label = val["label"] if isinstance(val, dict) else (val[0] if isinstance(val, tuple) else val)
        out.append((key, label))
    return out


def registry_payload():
    """What the website needs to draw shapes and entrances exactly like the admin preview."""
    return {
        "shapes": {k: {"css": v["css"], "square": v.get("square", False)} for k, v in SHAPES.items()},
        "entrances": {k: {"from": v["from"], "to": v["to"], "spring": v.get("spring", False)} for k, v in ENTRANCES.items()},
    }


def admin_registry():
    """Everything the admin's visual pickers and preview need."""
    return {
        "shapes": {k: {"label": v["label"], "css": v["css"], "square": v.get("square", False)} for k, v in SHAPES.items()},
        "entrances": {k: {"label": v["label"], "from": v["from"], "to": v["to"]} for k, v in ENTRANCES.items()},
        "layouts": {k: {"label": v[0], "help": v[1], "media": v[2]} for k, v in HERO_LAYOUTS.items()},
    }
