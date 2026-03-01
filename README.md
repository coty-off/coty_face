# coty_face

Personal color type analysis library.

Analyzes skin tone, hair color, and eye color to determine:

- **Undertone** – warm, cool, or neutral
- **Color season** – Spring, Summer, Autumn, or Winter
- **Contrast level** – high, medium, or low

## Requirements

Python 3.9+ (no external dependencies — uses only the standard library).

## Quick start

```python
from color_analysis import analyze_color_type

profile = analyze_color_type(
    skin="#f1c27d",   # hex or (R, G, B) tuple
    hair="#3b1f0e",
    eyes="#5c3d2e",   # optional
)

print(profile.undertone)        # Undertone.WARM
print(profile.season)           # Season.SPRING
print(profile.contrast_level)   # ContrastLevel.MEDIUM
print(profile.description)
# Warm and light/bright – golden undertones with high clarity. …
```

### Using the class directly

```python
from color_analysis import ColorTypeAnalyzer

analyzer = ColorTypeAnalyzer(skin=(241, 194, 125), hair=(59, 31, 14))
profile = analyzer.analyze()
```

## API

### `analyze_color_type(skin, hair, eyes=None) → ColorProfile`

Convenience wrapper. Accepts hex strings (`"#rrggbb"` / `"#rgb"`) or
`(R, G, B)` tuples.

### `ColorTypeAnalyzer(skin, hair, eyes=None)`

Class with a single `.analyze()` method that returns a `ColorProfile`.

### `ColorProfile` (frozen dataclass)

| Field | Type | Description |
|---|---|---|
| `undertone` | `Undertone` | `WARM`, `COOL`, or `NEUTRAL` |
| `season` | `Season` | `SPRING`, `SUMMER`, `AUTUMN`, or `WINTER` |
| `contrast_level` | `ContrastLevel` | `HIGH`, `MEDIUM`, or `LOW` |
| `skin_luminance` | `float` | Relative luminance of skin tone (0–1) |
| `skin_undertone_score` | `float` | Positive = warm, negative = cool |
| `description` | `str` | Human-readable style recommendation |

### Low-level helpers

| Function | Description |
|---|---|
| `hex_to_rgb(hex_color)` | Parse a CSS hex color to an `(R, G, B)` tuple |
| `rgb_to_hex(r, g, b)` | Convert `(R, G, B)` to a hex string |
| `rgb_to_luminance(r, g, b)` | Relative luminance (WCAG 2.1) |
| `detect_undertone(skin_rgb)` | Classify skin undertone |
| `measure_contrast(skin, hair, eyes)` | Determine personal contrast level |
| `classify_season(undertone, contrast, luminance)` | Map to color season |

## Running the tests

```bash
pip install pytest
pytest test_color_analysis.py -v
```
