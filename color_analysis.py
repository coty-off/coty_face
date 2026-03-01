"""
Color type analysis module for personal color profiling.

Analyzes skin tone, hair color, and eye color to determine:
- Undertone: warm, cool, or neutral
- Color season: Spring, Summer, Autumn, or Winter
- Contrast level: high, medium, or low
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class Undertone(str, Enum):
    WARM = "warm"
    COOL = "cool"
    NEUTRAL = "neutral"


class Season(str, Enum):
    SPRING = "Spring"   # warm + light/bright
    SUMMER = "Summer"   # cool + light/muted
    AUTUMN = "Autumn"   # warm + deep/muted
    WINTER = "Winter"   # cool + deep/bright


class ContrastLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class ColorProfile:
    """Result of a full color type analysis."""

    undertone: Undertone
    season: Season
    contrast_level: ContrastLevel
    skin_luminance: float        # 0–1
    skin_undertone_score: float  # positive = warm, negative = cool
    description: str


# ---------------------------------------------------------------------------
# Low-level color helpers
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_color: str) -> RGB:
    """Convert a CSS hex color string to an (R, G, B) tuple (0–255)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: #{hex_color}")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert R, G, B integers (0–255) to a CSS hex string."""
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_luminance(r: int, g: int, b: int) -> float:
    """Return the relative luminance of an sRGB color (0–1).

    Uses the WCAG 2.1 formula for perceptual brightness.
    """
    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Return HSV components (hue 0–360, saturation 0–1, value 0–1)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return (h * 360.0, s, v)


# ---------------------------------------------------------------------------
# Undertone detection
# ---------------------------------------------------------------------------

def _undertone_score(r: int, g: int, b: int) -> float:
    """Compute an undertone score from skin-tone RGB values.

    Positive values indicate warm (yellow/peach/golden) undertones.
    Negative values indicate cool (pink/blue/rosy) undertones.
    Values near zero are neutral.

    The heuristic compares the red–blue channel ratio against the
    green channel to separate warm and cool bias:
        warm  → high (R + a portion of G) relative to B
        cool  → high B (and/or pink = high R with low G) relative to G
    """
    # Normalize to 0-1
    rn, gn, bn = r / 255.0, g / 255.0, b / 255.0

    # Warm indicator: yellow = R+G high, B low
    warm_component = (rn + gn) / 2.0 - bn

    # Cool indicator: blue or pink = B high or (R high, G low)
    cool_component = bn - gn

    return warm_component - cool_component


def detect_undertone(skin_rgb: RGB, threshold: float = 0.05) -> Undertone:
    """Classify skin undertone from RGB.

    Parameters
    ----------
    skin_rgb:
        Representative skin-tone colour as (R, G, B) in 0–255.
    threshold:
        Absolute score below which the undertone is considered neutral.
    """
    score = _undertone_score(*skin_rgb)
    if score > threshold:
        return Undertone.WARM
    if score < -threshold:
        return Undertone.COOL
    return Undertone.NEUTRAL


# ---------------------------------------------------------------------------
# Contrast level
# ---------------------------------------------------------------------------

def _contrast_ratio(lum1: float, lum2: float) -> float:
    """WCAG 2.1 contrast ratio between two relative luminances."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def measure_contrast(
    skin_rgb: RGB,
    hair_rgb: RGB,
    eye_rgb: RGB | None = None,
) -> ContrastLevel:
    """Determine overall personal contrast from skin, hair, and optional eye color.

    High contrast  → ratio > 5  (e.g. very fair skin + jet-black hair)
    Medium contrast → ratio 2–5
    Low contrast   → ratio < 2  (e.g. similar skin and hair tones)
    """
    skin_lum = rgb_to_luminance(*skin_rgb)
    hair_lum = rgb_to_luminance(*hair_rgb)

    ratios = [_contrast_ratio(skin_lum, hair_lum)]

    if eye_rgb is not None:
        eye_lum = rgb_to_luminance(*eye_rgb)
        ratios.append(_contrast_ratio(skin_lum, eye_lum))

    ratio = max(ratios)

    if ratio > 5.0:
        return ContrastLevel.HIGH
    if ratio >= 2.0:
        return ContrastLevel.MEDIUM
    return ContrastLevel.LOW


# ---------------------------------------------------------------------------
# Season classification
# ---------------------------------------------------------------------------

_SEASON_DESCRIPTIONS: dict[Season, str] = {
    Season.SPRING: (
        "Warm and light/bright – golden undertones with high clarity. "
        "Best colours: peach, coral, warm yellow, camel, ivory."
    ),
    Season.SUMMER: (
        "Cool and light/muted – rosy or ashy undertones with soft contrast. "
        "Best colours: lavender, dusty rose, soft blue, mauve, cool grey."
    ),
    Season.AUTUMN: (
        "Warm and deep/muted – golden or earthy undertones with low-medium contrast. "
        "Best colours: terracotta, olive, rust, bronze, warm brown."
    ),
    Season.WINTER: (
        "Cool and deep/bright – clear, icy or stark contrasts. "
        "Best colours: pure white, black, icy blue, hot pink, royal purple."
    ),
}


def classify_season(
    undertone: Undertone,
    contrast_level: ContrastLevel,
    skin_luminance: float,
) -> Season:
    """Map undertone + contrast/luminance to one of the four color seasons.

    Decision rules
    --------------
    Warm + light or medium → Spring
    Warm + deep             → Autumn
    Cool + light            → Summer
    Cool + deep or high     → Winter
    Neutral follows luminance: light → Summer, deep → Winter,
    medium contrast → Spring or Autumn based on skin warmth proxy.
    """
    is_warm = undertone == Undertone.WARM
    is_cool = undertone == Undertone.COOL
    is_light = skin_luminance >= 0.35
    is_deep = skin_luminance < 0.20
    is_high_contrast = contrast_level == ContrastLevel.HIGH

    if is_warm:
        if is_deep:
            return Season.AUTUMN
        return Season.SPRING  # light or medium
    if is_cool:
        if is_light and not is_high_contrast:
            return Season.SUMMER
        return Season.WINTER
    # Neutral undertone
    if is_deep or is_high_contrast:
        return Season.WINTER
    if is_light:
        return Season.SUMMER
    return Season.SPRING


# ---------------------------------------------------------------------------
# Main analyser
# ---------------------------------------------------------------------------

class ColorTypeAnalyzer:
    """Determine a person's color type from representative facial colors.

    Parameters
    ----------
    skin:
        Skin tone as a hex string (e.g. ``"#f1c27d"``) or an ``(R, G, B)``
        tuple with values in the 0–255 range.
    hair:
        Hair color, same format as *skin*.
    eyes:
        Optional eye color, same format as *skin*.
    """

    def __init__(
        self,
        skin: str | RGB,
        hair: str | RGB,
        eyes: str | RGB | None = None,
    ) -> None:
        self.skin_rgb: RGB = hex_to_rgb(skin) if isinstance(skin, str) else skin
        self.hair_rgb: RGB = hex_to_rgb(hair) if isinstance(hair, str) else hair
        self.eye_rgb: RGB | None = (
            hex_to_rgb(eyes) if isinstance(eyes, str) else eyes
        )

    def analyze(self) -> ColorProfile:
        """Run the full color type analysis and return a :class:`ColorProfile`."""
        skin_lum = rgb_to_luminance(*self.skin_rgb)
        score = _undertone_score(*self.skin_rgb)
        undertone = detect_undertone(self.skin_rgb)
        contrast = measure_contrast(self.skin_rgb, self.hair_rgb, self.eye_rgb)
        season = classify_season(undertone, contrast, skin_lum)

        return ColorProfile(
            undertone=undertone,
            season=season,
            contrast_level=contrast,
            skin_luminance=round(skin_lum, 4),
            skin_undertone_score=round(score, 4),
            description=_SEASON_DESCRIPTIONS[season],
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def analyze_color_type(
    skin: str | RGB,
    hair: str | RGB,
    eyes: str | RGB | None = None,
) -> ColorProfile:
    """Shorthand for ``ColorTypeAnalyzer(skin, hair, eyes).analyze()``.

    Examples
    --------
    >>> profile = analyze_color_type("#f1c27d", "#3b1f0e")
    >>> profile.season
    <Season.SPRING: 'Spring'>
    """
    return ColorTypeAnalyzer(skin, hair, eyes).analyze()
