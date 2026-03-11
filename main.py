"""
НАУЧНЫЙ АНАЛИЗ: CIE LCh ТЕПЛОТА + MICHELSON КОНТРАСТ
"""

import numpy as np
import cv2
from PIL import Image
from skimage.color import rgb2lab
import warnings

warnings.filterwarnings("ignore")


class ColorAnalyzer:
    """CIE LCh для КОЖИ/ВОЛОС/ГЛАЗ/БРОВЕЙ"""

    def rgb_to_cielab_full(self, rgb):
        rgb_norm = np.array([[rgb]], dtype=np.float32) / 255.0
        lab = rgb2lab(rgb_norm)
        return lab[0, 0, 0], lab[0, 0, 1], lab[0, 0, 2]  # L*, a*, b*

    def analyze_feature(self, rgb, feature_type):
        """ТЕПЛОТА по типу элемента"""
        l_star, a_star, b_star = self.rgb_to_cielab_full(rgb)
        chroma = np.sqrt(a_star ** 2 + b_star ** 2)
        hue_deg = np.degrees(np.arctan2(b_star, a_star)) % 360

        # ПРАВИЛЬНЫЕ ДИАПАЗОНЫ ПО ЦВЕТОТИПАМ
        if feature_type == 'skin':  # КОЖА
            is_warm = (0 <= hue_deg <= 60) or (300 <= hue_deg <= 360)
        elif feature_type in ['hair', 'brows']:  # ВОЛОСЫ/БРОВИ
            is_warm = (20 <= hue_deg <= 50) or (300 <= hue_deg <= 340)
        else:  # ГЛАЗА
            is_warm = (0 <= hue_deg <= 40) or (300 <= hue_deg <= 360)

        temperature = "ТЕПЛЫЙ" if is_warm else "ХОЛОДНЫЙ"

        return {
            'rgb': rgb,
            'hex': f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
            'l_star': round(l_star, 1),
            'b_star': round(b_star, 1),
            'hue_deg': round(hue_deg, 1),
            'temperature': temperature,
            'chroma': round(chroma, 1)
        }


def smart_align_images(original_path, mask_path):
    original = np.array(Image.open(original_path))
    colored_mask = cv2.imread(mask_path)
    orig_h, orig_w = original.shape[:2]
    mask_resized = cv2.resize(colored_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)

    mask_rgb = cv2.cvtColor(mask_resized, cv2.COLOR_BGR2RGB)
    pixels = mask_rgb.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 15, None, criteria, 20, cv2.KMEANS_RANDOM_CENTERS)
    mask_segments = labels.flatten().reshape(orig_h, orig_w).astype(np.uint8)
    return original, mask_segments, centers


def diagnose_all_segments(original, mask_segments, color_analyzer):
    """ТОП-20 по L* С ТЕПЛОТОЙ"""
    print("\nТОП-20 по L* (LCh ТЕПЛОТА):")
    print("Кластер | RGB      | L*  | Теплота | Hue° | Площадь%")
    print("-" * 65)

    segment_list = []
    for cls in np.unique(mask_segments):
        if cls == 0: continue
        seg_mask = (mask_segments == cls)
        seg_pixels = original[seg_mask]
        if len(seg_pixels) > 200:
            r, g, b = np.mean(seg_pixels, axis=0).astype(np.uint8)
            rgb_norm = seg_pixels.astype(np.float32) / 255.0
            lab_vals = rgb2lab(rgb_norm.reshape(-1, 1, 1, 3)).squeeze()
            mean_lab = np.nanmean(lab_vals, axis=0)
            pct = len(seg_pixels) / np.prod(original.shape[:2]) * 100

            color_info = color_analyzer.analyze_feature((int(r), int(g), int(b)), 'skin')
            segment_list.append((cls, r, g, b, mean_lab[0], pct, color_info))

    segment_list.sort(key=lambda x: x[4], reverse=True)
    for cls, r, g, b, L_val, pct, color_info in segment_list[:20]:
        candidate = "РАДУЖКА" if 60 < L_val < 85 and 0.1 < pct < 1.5 else "?"
        print(f"{cls:6} | ({r:3},{g:3},{b:3}) | {L_val:4.1f} | "
              f"{color_info['temperature']:7} | {color_info['hue_deg']:4}° | "
              f"{pct:6.2f}% | {candidate}")
    return segment_list


def classify_features_universal(original, mask_segments, color_analyzer):
    """4 ЭЛЕМЕНТА С ТЕПЛОТОЙ"""
    skin, hair, eyes, brows = [], [], [], []

    print("\nКЛАССИФИКАЦИЯ 4 ЭЛЕМЕНТОВ:")
    print("Кластер | Тип      | HEX     | L*  | Теплота | %")
    print("-" * 55)

    eye_data = find_true_iris_universal(original, mask_segments, color_analyzer)
    if eye_data:
        eyes.append({
            'cls': eye_data['cls'],
            'L': eye_data['L'],
            'color_analysis': eye_data['color_analysis'],
            'percent': 0.6
        })
        print(f"{eye_data['cls']:6} | ГЛАЗА  | {eye_data['color_analysis']['hex']:8} | "
              f"{eye_data['L']:4.1f} | {eye_data['color_analysis']['temperature']:8} | 0.6%")

    eye_cls = eye_data['cls'] if eye_data else -1
    for cls in np.unique(mask_segments):
        if cls == 0 or cls == eye_cls: continue
        seg_mask = (mask_segments == cls)
        seg_pixels = original[seg_mask]

        if len(seg_pixels) > 400:
            rgb_norm = seg_pixels.astype(np.float32) / 255.0
            lab_vals = rgb2lab(rgb_norm.reshape(-1, 1, 1, 3)).squeeze()
            mean_lab = np.nanmean(lab_vals, axis=0)

            if mean_lab[0] < 25: continue

            r, g, b = np.mean(seg_pixels, axis=0).astype(np.uint8)
            pct = len(seg_pixels) / np.prod(original.shape[:2]) * 100

            # ТЕПЛОТА ПО ТИПУ ЭЛЕМЕНТА
            if 0.3 < pct < 2.5 and 8 < r < 90 and mean_lab[0] < 45:
                color_info = color_analyzer.analyze_feature((r, g, b), 'brows')
                brows.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})
                print(f"{cls:6} | БРОВИ | {color_info['hex']:8} | {mean_lab[0]:4.1f} | "
                      f"{color_info['temperature']:8} | {pct:4.1f}%")

            elif pct > 1.5 and 5 < r < 140:
                color_info = color_analyzer.analyze_feature((r, g, b), 'hair')
                hair.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})
                print(f"{cls:6} | ВОЛОСЫ| {color_info['hex']:8} | {mean_lab[0]:4.1f} | "
                      f"{color_info['temperature']:8} | {pct:4.1f}%")

            elif pct > 0.8 and 50 < r < 230:
                color_info = color_analyzer.analyze_feature((r, g, b), 'skin')
                skin.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})
                print(f"{cls:6} | КОЖА  | {color_info['hex']:8} | {mean_lab[0]:4.1f} | "
                      f"{color_info['temperature']:8} | {pct:4.1f}%")

    print(f"\nНайдено: Кожа:{len(skin)} | Волосы:{len(hair)} | Глаза:{len(eyes)} | Брови:{len(brows)}")
    return skin, hair, eyes, brows


def find_true_iris_universal(original, mask_segments, color_analyzer):
    """РАДУЖКА с LCh"""
    print("\nПОИСК РАДУЖКИ...")
    hsv_image = cv2.cvtColor(original, cv2.COLOR_RGB2HSV)
    best_eye_pixels = []

    eye_candidates = [cls for cls in np.unique(mask_segments) if cls != 0 and
                      150 < np.sum(mask_segments == cls) < 2500]

    for cls in eye_candidates:
        seg_mask = (mask_segments == cls)
        seg_pixels = original[seg_mask]
        if len(seg_pixels) > 100:
            rgb_norm = seg_pixels.astype(np.float32) / 255.0
            lab_vals = rgb2lab(rgb_norm.reshape(-1, 1, 1, 3)).squeeze()
            brightest_indices = np.argsort(lab_vals[:, 0])[-3:][::-1]

            for idx in brightest_indices:
                pixel_rgb = tuple(seg_pixels[idx].astype(np.uint8))
                pixel_L = lab_vals[idx, 0]
                if 35 < pixel_L < 85:
                    color_info = color_analyzer.analyze_feature(pixel_rgb, 'eyes')
                    best_eye_pixels.append({
                        'rgb': pixel_rgb, 'L': pixel_L, 'cls': cls,
                        'confidence': pixel_L, 'color_analysis': color_info
                    })

    if best_eye_pixels:
        best_eye = max(best_eye_pixels, key=lambda x: x['confidence'])
        print(f"РАДУЖКА: {best_eye['color_analysis']['hex']} "
              f"{best_eye['color_analysis']['temperature']} L*={best_eye['L']:.1f}")
        return best_eye
    return None


def detailed_4features_analysis(skin, hair, eyes, brows):
    """LCh ТЕПЛОТА + MICHELSON КОНТРАСТ"""
    print("\n" + "=" * 90)
    print("НАУЧНЫЙ АНАЛИЗ: CIE LCh + MICHELSON (4 ЭЛЕМЕНТА)")
    print("=" * 90)

    all_segments = []
    feature_names = {'skin': 'КОЖА', 'hair': 'ВОЛОСЫ', 'eyes': 'ГЛАЗА', 'brows': 'БРОВИ'}

    for segments, ftype in [(skin, 'skin'), (hair, 'hair'), (eyes, 'eyes'), (brows, 'brows')]:
        if segments:
            avg_rgb = tuple(np.mean([s['color_analysis']['rgb'] for s in segments], axis=0).astype(int))
            color_analyzer = ColorAnalyzer()
            avg_color = color_analyzer.analyze_feature(avg_rgb, ftype)

            avg = {
                'name': feature_names[ftype],
                'L': np.mean([s['L'] for s in segments]),
                'color_analysis': avg_color,
                'rgb': avg_rgb,
                'pct': sum([s.get('percent', 0.5) for s in segments]),
                'count': len(segments)
            }
            all_segments.append(avg)

    print("\n4 ЭЛЕМЕНТА (LCh Анализ):")
    print("Элемент | HEX     | L*   | Теплота | Hue° | %")
    print("-" * 55)

    for seg in all_segments:
        print(f"{seg['name']:8} | {seg['color_analysis']['hex']:8} | "
              f"{seg['L']:4.1f} | {seg['color_analysis']['temperature']:8} | "
              f"{seg['color_analysis']['hue_deg']:4}° | {seg['pct']:4.1f}%")

    # MICHELSON CONTRAST
    L_values = [seg['L'] for seg in all_segments]
    L_max = max(L_values)
    L_min = min(L_values)
    michelson_contrast = (L_max - L_min) / (L_max + L_min)

    print(f"\nMICHELSON CONTRAST = {michelson_contrast:.3f}")
    if michelson_contrast < 0.30:
        contrast_type = "Низкая"
    elif michelson_contrast < 0.50:
        contrast_type = "Средняя"
    else:
        contrast_type = "Высокая"
    print(f"{contrast_type} контрастность")

    # ЦВЕТОТИП (голосование)
    warm_count = sum(1 for seg in all_segments if 'ТЕПЛЫЙ' in seg['color_analysis']['temperature'])
    color_type = "ТЕПЛЫЙ" if warm_count > len(all_segments) / 2 else "ХОЛОДНЫЙ"

    print(f"\nЦВЕТОТИП: {color_type} ({warm_count}/{len(all_segments)} элементов)")
    print(f"\nHEX КОДЫ:")
    for seg in all_segments:
        print(f"   {seg['name']}: {seg['color_analysis']['hex']}")

    print("=" * 90)
    return {'michelson': michelson_contrast, 'contrast_type': contrast_type, 'color_type': color_type}


# ЗАПУСК
if __name__ == "__main__":
    print("LCh ТЕПЛОТА + MICHELSON КОНТРАСТ")
    print("=" * 80)

    color_analyzer = ColorAnalyzer()
    original, mask, centers = smart_align_images("whomen.jpg", "whomen-1.jpg")

    diagnose_all_segments(original, mask, color_analyzer)
    skin, hair, eyes, brows = classify_features_universal(original, mask, color_analyzer)
    result = detailed_4features_analysis(skin, hair, eyes, brows)

    cv2.imwrite("lch_michelson_analysis.png", mask * 15)
    print("\nlch_michelson_analysis.png — ГОТОВ!")
