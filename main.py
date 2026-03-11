"""
Научные стандарты для любого RGB/HEX цвета (CIE LCh Hue алгоритм)
"""

import numpy as np
from skimage.color import rgb2lab

class ColorAnalyzer:
    """ ТЕПЛОТА (LCh Hue) + ЯРКОСТЬ (Luma/CIELAB L*) - НАУЧНЫЙ СТАНДАРТ"""

    def __init__(self):
        #  ТЕПЛОТА теперь по LCh Hue (CIE 1976 стандарт)
        # ЯРКОСТЬ остается прежней
        self.bright_threshold = 70  # >70% = ЯРКИЙ
        self.dark_threshold = 30    # <30% = ТЕМНЫЙ

    def hex_to_rgb(self, hex_color):
        """#FF1493 → (255, 20, 147)"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def rgb_to_luma(self, rgb):
        """ ЛУМА (ITU-R BT.601) Y = 0.299R + 0.587G + 0.114B"""
        r, g, b = [x / 255.0 for x in rgb]
        return (0.299 * r + 0.587 * g + 0.114 * b) * 100

    def rgb_to_cielab_full(self, rgb):
        """ ПОЛНЫЙ CIELAB: L*, a*, b* (CIE 1976)"""
        rgb_norm = np.array([[rgb]], dtype=np.float32) / 255.0
        lab = rgb2lab(rgb_norm)
        return lab[0, 0, 0], lab[0, 0, 1], lab[0, 0, 2]  # L*, a*, b*

    def is_warm_color(self, hue_deg):
        """ НАУЧНЫЙ АЛГОРИТМ ТЕПЛОТЫ (CIE LCh)"""
        # Теплые зоны: ближе к желтому/красному по цветовому кругу
        return (0 <= hue_deg <= 90) or (180 <= hue_deg <= 225) or (270 <= hue_deg <= 360)

    def classify_color_full(self, color_input):
        """
         ПОЛНЫЙ НАУЧНЫЙ АНАЛИЗ: LCh Теплота + Luma Яркость
        Вход: '#FF1493' или (255, 20, 147)
        """
        # RGB
        if isinstance(color_input, str):
            rgb = self.hex_to_rgb(color_input)
        else:
            rgb = color_input

        hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        #  1. LCh ТЕПЛОТА (замена b*)
        l_star, a_star, b_star = self.rgb_to_cielab_full(rgb)
        chroma = np.sqrt(a_star**2 + b_star**2)
        hue_deg = np.degrees(np.arctan2(b_star, a_star)) % 360

        temperature = "🟡 ТЕПЛЫЙ" if self.is_warm_color(hue_deg) else "🔵 ХОЛОДНЫЙ"

        # 🖤 2. Luma ЯРКОСТЬ (остается ТАК ЖЕ)
        luma = self.rgb_to_luma(rgb)
        if luma > self.bright_threshold:
            brightness = "☀️ ЯРКИЙ"
        elif luma < self.dark_threshold:
            brightness = "🌒 ТЕМНЫЙ"
        else:
            brightness = "🌓 СРЕДНИЙ"

        return {
            'hex': hex_color,
            'rgb': rgb,
            'temperature': temperature,
            'brightness': brightness,
            'hue_deg': round(hue_deg, 1),      # ← НОВОЕ!
            'chroma': round(chroma, 1),        # ← НОВОЕ!
            'luma': round(luma, 1),
            'l_star': round(l_star, 1)
        }

    def batch_analyze(self, colors):
        """ АНАЛИЗ МНОГИХ ЦВЕТОВ (обновленный вывод)"""
        print(" НАУЧНЫЙ АНАЛИЗ LCh ТЕПЛОТЫ + Luma ЯРКОСТИ (CIE 1976)")
        print("=" * 80)
        print("Цвет     | Теплота | Яркость | Hue° | Chroma | Luma")
        print("-" * 80)

        results = []
        warm_count = bright_count = 0

        for color in colors:
            result = self.classify_color_full(color)
            results.append(result)

            if '🟡' in result['temperature']: warm_count += 1
            if '☀️' in result['brightness']: bright_count += 1

            print(f"{result['hex']:8} | {result['temperature']:8} | "
                  f"{result['brightness']:8} | {result['hue_deg']:4}° | "
                  f"{result['chroma']:6} | {result['luma']:4}")

        print("-" * 80)
        print(f" ТЕПЛЫХ: {warm_count}/{len(colors)} | "
              f"ЯРКИХ: {bright_count}/{len(colors)}")

        return results

#  ДЕМО с тестовыми теплыми/холодными
if __name__ == "__main__":
    analyzer = ColorAnalyzer()

    # ТЕСТОВЫЕ ЦВЕТА (теплые + холодные)
    test_colors = [
        '#FF7F50',   # 🟡 Теплый красный (коралл)
        '#C71585',   # 🔵 Холодный красный (малина)
        '#CC7722',   # 🟡 Теплый желтый (охра)
        '#FFFF99',   # 🔵 Холодный желтый (лимон)
        '#6B8E23',   # 🟡 Теплый зеленый (олива)
        '#50C878',   # 🔵 Холодный зеленый (изумруд)
        '#00BFFF',   # 🟡 Теплый синий (бирюза)
        '#4169E1',   # 🔵 Холодный синий (королевский)
    ]

    results = analyzer.batch_analyze(test_colors)

    print("\n ОДИНОЧНЫЙ ТЕСТ:")
    single = analyzer.classify_color_full('#FF1493')
    print(f"Электрический розовый: {single['temperature']} + "
          f"{single['brightness']} (Hue°={single['hue_deg']})")


