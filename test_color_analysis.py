"""Tests for the color_analysis module."""

import pytest

from color_analysis import (
    ColorProfile,
    ColorTypeAnalyzer,
    ContrastLevel,
    Season,
    Undertone,
    _contrast_ratio,
    _undertone_score,
    analyze_color_type,
    classify_season,
    detect_undertone,
    hex_to_rgb,
    measure_contrast,
    rgb_to_hex,
    rgb_to_luminance,
)


# ---------------------------------------------------------------------------
# hex_to_rgb
# ---------------------------------------------------------------------------

class TestHexToRgb:
    def test_six_digit_hex(self):
        assert hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_three_digit_hex(self):
        assert hex_to_rgb("#fff") == (255, 255, 255)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_without_hash(self):
        assert hex_to_rgb("f1c27d") == (241, 194, 125)

    def test_uppercase(self):
        assert hex_to_rgb("#F1C27D") == (241, 194, 125)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#gg0000")

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#12345")


# ---------------------------------------------------------------------------
# rgb_to_hex
# ---------------------------------------------------------------------------

class TestRgbToHex:
    def test_white(self):
        assert rgb_to_hex(255, 255, 255) == "#ffffff"

    def test_black(self):
        assert rgb_to_hex(0, 0, 0) == "#000000"

    def test_roundtrip(self):
        original = "#3b1f0e"
        r, g, b = hex_to_rgb(original)
        assert rgb_to_hex(r, g, b) == original


# ---------------------------------------------------------------------------
# rgb_to_luminance
# ---------------------------------------------------------------------------

class TestRgbToLuminance:
    def test_black_is_zero(self):
        assert rgb_to_luminance(0, 0, 0) == pytest.approx(0.0)

    def test_white_is_one(self):
        assert rgb_to_luminance(255, 255, 255) == pytest.approx(1.0, rel=1e-3)

    def test_red(self):
        # Red has a well-known relative luminance of ~0.2126
        lum = rgb_to_luminance(255, 0, 0)
        assert 0.20 < lum < 0.22

    def test_luminance_order(self):
        # White > mid-grey > black
        assert rgb_to_luminance(255, 255, 255) > rgb_to_luminance(128, 128, 128) > rgb_to_luminance(0, 0, 0)


# ---------------------------------------------------------------------------
# undertone score / detect_undertone
# ---------------------------------------------------------------------------

class TestUndertoneScore:
    def test_warm_skin_positive(self):
        # Golden/yellow-toned skin
        score = _undertone_score(241, 194, 125)
        assert score > 0

    def test_cool_skin_negative(self):
        # Pinkish-cool skin
        score = _undertone_score(230, 180, 200)
        assert score < 0


class TestDetectUndertone:
    def test_warm(self):
        assert detect_undertone((241, 194, 125)) == Undertone.WARM

    def test_cool(self):
        assert detect_undertone((200, 170, 210)) == Undertone.COOL

    def test_neutral(self):
        # Balanced beige with no strong warm/cool bias
        result = detect_undertone((210, 180, 165), threshold=0.3)
        assert result == Undertone.NEUTRAL

    def test_threshold_respected(self):
        # With a very high threshold, near-neutral scores are classified neutral
        result = detect_undertone((241, 194, 125), threshold=10.0)
        assert result == Undertone.NEUTRAL


# ---------------------------------------------------------------------------
# contrast helpers
# ---------------------------------------------------------------------------

class TestContrastRatio:
    def test_same_luminance(self):
        ratio = _contrast_ratio(0.5, 0.5)
        assert ratio == pytest.approx(1.0)

    def test_black_white(self):
        # ~21:1 per WCAG spec
        ratio = _contrast_ratio(0.0, 1.0)
        assert ratio > 20.0

    def test_order_independent(self):
        assert _contrast_ratio(0.1, 0.8) == pytest.approx(_contrast_ratio(0.8, 0.1))


class TestMeasureContrast:
    def test_high_contrast(self):
        # Fair skin vs very dark hair
        result = measure_contrast((240, 220, 200), (20, 10, 5))
        assert result == ContrastLevel.HIGH

    def test_low_contrast(self):
        # Similar skin and hair tones
        result = measure_contrast((200, 170, 140), (190, 160, 130))
        assert result == ContrastLevel.LOW

    def test_eye_color_included(self):
        # Providing a dark eye colour should not lower a high-contrast result
        result = measure_contrast(
            (240, 220, 200),  # fair skin
            (240, 220, 200),  # same hair → low contrast with skin
            (20, 10, 5),      # but very dark eyes → should push to high
        )
        assert result == ContrastLevel.HIGH


# ---------------------------------------------------------------------------
# classify_season
# ---------------------------------------------------------------------------

class TestClassifySeason:
    def test_warm_light_spring(self):
        assert classify_season(Undertone.WARM, ContrastLevel.MEDIUM, 0.5) == Season.SPRING

    def test_warm_deep_autumn(self):
        assert classify_season(Undertone.WARM, ContrastLevel.MEDIUM, 0.10) == Season.AUTUMN

    def test_cool_light_summer(self):
        assert classify_season(Undertone.COOL, ContrastLevel.LOW, 0.50) == Season.SUMMER

    def test_cool_high_contrast_winter(self):
        assert classify_season(Undertone.COOL, ContrastLevel.HIGH, 0.50) == Season.WINTER

    def test_cool_deep_winter(self):
        assert classify_season(Undertone.COOL, ContrastLevel.MEDIUM, 0.10) == Season.WINTER

    def test_neutral_light_summer(self):
        assert classify_season(Undertone.NEUTRAL, ContrastLevel.LOW, 0.50) == Season.SUMMER

    def test_neutral_deep_winter(self):
        assert classify_season(Undertone.NEUTRAL, ContrastLevel.MEDIUM, 0.05) == Season.WINTER


# ---------------------------------------------------------------------------
# ColorTypeAnalyzer / analyze_color_type
# ---------------------------------------------------------------------------

class TestColorTypeAnalyzer:
    def test_returns_color_profile(self):
        analyzer = ColorTypeAnalyzer("#f1c27d", "#3b1f0e")
        profile = analyzer.analyze()
        assert isinstance(profile, ColorProfile)

    def test_tuple_input(self):
        profile = ColorTypeAnalyzer((241, 194, 125), (59, 31, 14)).analyze()
        assert isinstance(profile, ColorProfile)

    def test_with_eye_color(self):
        profile = ColorTypeAnalyzer("#f1c27d", "#3b1f0e", "#5c3d2e").analyze()
        assert isinstance(profile, ColorProfile)

    def test_spring_profile(self):
        # Light, warm-toned skin + dark-medium hair
        profile = analyze_color_type("#f5d9b5", "#8b5e3c")
        assert profile.undertone == Undertone.WARM
        assert profile.season == Season.SPRING

    def test_winter_profile(self):
        # Cool-toned skin + jet-black hair (high contrast, cool)
        profile = analyze_color_type("#e5c8d8", "#0a0a0a")
        assert profile.undertone == Undertone.COOL
        assert profile.season == Season.WINTER

    def test_autumn_profile(self):
        # Deep, warm skin tone
        profile = analyze_color_type("#6b3d2e", "#2a1008")
        assert profile.undertone == Undertone.WARM
        assert profile.season == Season.AUTUMN

    def test_profile_has_description(self):
        profile = analyze_color_type("#f1c27d", "#3b1f0e")
        assert isinstance(profile.description, str)
        assert len(profile.description) > 0

    def test_profile_luminance_in_range(self):
        profile = analyze_color_type("#f1c27d", "#3b1f0e")
        assert 0.0 <= profile.skin_luminance <= 1.0

    def test_hex_case_insensitive(self):
        p1 = analyze_color_type("#F1C27D", "#3B1F0E")
        p2 = analyze_color_type("#f1c27d", "#3b1f0e")
        assert p1 == p2

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError):
            ColorTypeAnalyzer("#gg0000", "#000000")
