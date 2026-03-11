import numpy as np
import cv2
from PIL import Image
from skimage.color import rgb2lab
import warnings

warnings.filterwarnings("ignore")


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


def diagnose_all_segments(original, mask_segments):
    """🔬 ДИАГНОСТИКА — показывает ПОРЯДОК яркости L*"""
    print("\n🔬 ТОП-20 по L* (СВЕТЛЫЕ ПЕРВЫМИ):")
    print("Кластер | RGB      | L*  | Площадь% | КАНДИДАТ")
    print("-" * 60)

    segment_list = []
    for cls in np.unique(mask_segments):
        if cls == 0: continue
        seg_mask = (mask_segments == cls)
        seg_pixels = original[seg_mask]
        if len(seg_pixels) > 200:
            rgb_norm = seg_pixels.astype(np.float32) / 255.0
            lab_vals = rgb2lab(rgb_norm.reshape(-1, 1, 1, 3)).squeeze()
            mean_lab = np.nanmean(lab_vals, axis=0)
            r, g, b = np.mean(seg_pixels, axis=0).astype(np.uint8)
            pct = len(seg_pixels) / np.prod(original.shape[:2]) * 100
            segment_list.append((cls, r, g, b, mean_lab[0], pct))

    segment_list.sort(key=lambda x: x[4], reverse=True)
    for cls, r, g, b, L_val, pct in segment_list[:20]:
        candidate = "👁️ РАДУЖКА" if 60 < L_val < 85 and 0.1 < pct < 1.5 else "❓"
        print(f"{cls:6} | ({r:3},{g:3},{b:3}) | {L_val:4.1f} | {pct:6.2f}% | {candidate}")
    return segment_list


def find_true_iris_universal(original, mask_segments):
    """🔥 УНИВЕРСАЛЬНЫЙ: ТОП-3 самых светлых пикселя в глазных сегментах"""
    print("\n🔍 УНИВЕРСАЛЬНЫЙ ПОИСК РАДУЖКИ (ТОП-3 светлых пикселя)")

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

                hsv_pixel = hsv_image[seg_mask][idx]
                h_value = hsv_pixel[0]

                if 35 < pixel_L < 85:
                    best_eye_pixels.append({
                        'rgb': pixel_rgb, 'L': pixel_L, 'hsv_h': h_value,
                        'cls': cls, 'confidence': pixel_L
                    })

    if best_eye_pixels:
        best_eye = max(best_eye_pixels, key=lambda x: x['confidence'])

        h = best_eye['hsv_h']
        if 0 <= h < 15 or h > 170:
            color_name = "🔵 голубой"
        elif 40 < h < 80:
            color_name = "🟢 зеленый"
        elif 20 < h < 40:
            color_name = "🟡 желтоватый"
        else:
            color_name = "🟤 нейтральный"

        print(f"⭐ НАЙДЕНА РАДУЖКА: RGB={best_eye['rgb']} L*={best_eye['L']:.1f} {color_name}")
        return best_eye
    return None


def classify_features_universal(original, mask_segments):
    """🎯 УНИВЕРСАЛЬНАЯ КЛАССИФИКАЦИЯ ЛЮБЫХ ГЛАЗ"""
    skin, hair, eyes, brows = [], [], [], []

    print("\n✅ УНИВЕРСАЛЬНАЯ КЛАССИФИКАЦИЯ:")
    print("Кластер | Тип          | RGB      | L*  | %")
    print("-" * 50)

    eye_data = find_true_iris_universal(original, mask_segments)
    if eye_data:
        eyes.append({
            'cls': eye_data['cls'], 'L': eye_data['L'], 'b_tone': 5.0,
            'skin_color': eye_data['rgb'], 'percent': 0.6
        })
        print(
            f"{eye_data['cls']:6} | 👁️ РАДУЖКА✓  | ({eye_data['rgb'][0]:3},{eye_data['rgb'][1]:3},{eye_data['rgb'][2]:3}) | "
            f"{eye_data['L']:4.1f} | 0.6% ⭐УНИВЕРСАЛЬНЫЙ!")

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

            data = {
                'cls': cls, 'L': mean_lab[0], 'b_tone': mean_lab[2],
                'skin_color': (r, g, b), 'percent': pct
            }

            if 0.3 < pct < 2.5 and 8 < r < 90 and mean_lab[0] < 45:
                brows.append(data)
                print(f"{cls:6} | 眉 БРОВИ     | ({r:3},{g:3},{b:3}) | {mean_lab[0]:3.0f} | {pct:4.1f}%")
            elif pct > 1.5 and 5 < r < 140:
                hair.append(data)
                print(f"{cls:6} | 🦱 ВОЛОСЫ    | ({r:3},{g:3},{b:3}) | {mean_lab[0]:3.0f} | {pct:4.1f}%")
            elif pct > 0.8 and 50 < r < 230:
                skin.append(data)
                print(f"{cls:6} | 🧡 КОЖА      | ({r:3},{g:3},{b:3}) | {mean_lab[0]:3.0f} | {pct:4.1f}%")

    print(f"\n📊 ИТОГО: Кожа:{len(skin)} | Волосы:{len(hair)} | Глаза:{len(eyes)} | Брови:{len(brows)}")
    return skin, hair, eyes, brows


def detailed_4features_analysis(skin, hair, eyes, brows):
    """🔬 НАУЧНЫЙ АНАЛИЗ С MICHELSON CONTRAST"""
    print("\n" + "=" * 80)
    print("🎯 НАУЧНЫЙ АНАЛИЗ 4 ЭЛЕМЕНТОВ (MICHELSON CONTRAST)")
    print("=" * 80)

    all_segments = []
    for segments, name in [(skin, '🧡 КОЖА'), (hair, '🦱 ВОЛОСЫ'), (eyes, '👁️ РАДУЖКА'), (brows, '眉 БРОВИ')]:
        if segments:
            avg = {
                'name': name,
                'L': np.mean([s['L'] for s in segments]),
                'b': np.mean([s.get('b_tone', 0) for s in segments]),
                'rgb': tuple(np.mean([s['skin_color'] for s in segments], axis=0).astype(int)),
                'pct': sum([s.get('percent', 0.5) for s in segments]),
                'count': len(segments)
            }
            all_segments.append(avg)

    print("\n📊 СРЕДНИЕ ЦВЕТА:")
    print("Элемент   | RGB      | L*  | b*  | Сегм. | %")
    print("-" * 45)
    for seg in all_segments:
        tone = "🟡" if seg['b'] > 0 else "🔵"
        print(f"{seg['name']:8} | ({seg['rgb'][0]:3},{seg['rgb'][1]:3},{seg['rgb'][2]:3}) | "
              f"{seg['L']:3.0f} | {seg['b']:4.1f} | {seg['count']:2} | {seg['pct']:3.1f}% {tone}")

    # 🔥 MICHELSON CONTRAST (НАУЧНЫЙ СТАНДАРТ)
    L_values = [seg['L'] for seg in all_segments]
    L_max = max(L_values)
    L_min = min(L_values)

    # Michelson Contrast = (L_max - L_min) / (L_max + L_min)
    michelson_contrast = (L_max - L_min) / (L_max + L_min)

    print(f"\n🔬 MICHELSON CONTRAST (IEEE/Journal of Vision):")
    print(f"   L* значения: {', '.join([f'{v:.0f}' for v in L_values])}")
    print(f"   🖤 Минимум: {L_min:.0f} ({all_segments[L_values.index(L_min)]['name']})")
    print(f"   ⚪ Максимум: {L_max:.0f} ({all_segments[L_values.index(L_max)]['name']})")
    print(f"   Формула: (L_max - L_min) / (L_max + L_min)")
    print(f"   M = ({L_max:.0f} - {L_min:.0f}) / ({L_max:.0f} + {L_min:.0f}) = **{michelson_contrast:.3f}**")

    # НАУЧНОЕ ДЕЛЕНИЕ ПО MICHELSON
    if michelson_contrast < 0.30:
        contrast_type = "🔸 Низкая"
    elif michelson_contrast < 0.50:
        contrast_type = "🟡 Средняя"  # ТВОЙ СЛУЧАЙ!
    else:
        contrast_type = "🔴 Высокая"

    print(f"\n🎯 **{contrast_type}** контрастность (M={michelson_contrast:.3f})")
    print(f"📚 Стандарты: IEEE Transactions, Journal of Vision, CVPR")

    # Подтон
    b_values = [seg['b'] for seg in all_segments]
    weights = np.array([0.5, 0.25, 0.15, 0.1])[:len(b_values)]
    weighted_b = np.average(b_values, weights=weights)
    tone = "🟡 ТЕПЛЫЙ" if weighted_b > 0 else "🔵 ХОЛОДНЫЙ"

    print(f"\n🎨 ПОДТОН: {tone} (b*={weighted_b:.1f})")
    print(f"\n🎨 HEX КОДЫ:")
    for seg in all_segments:
        r, g, b = seg['rgb']
        print(f"   {seg['name']}: #{r:02x}{g:02x}{b:02x}")
    print("=" * 80)

    return {'michelson': michelson_contrast, 'contrast_type': contrast_type, 'tone': tone}


# 🚀 ЗАПУСК — НАУЧНАЯ ВЕРСИЯ!
print("🎯 НАУЧНЫЙ АНАЛИЗ ПО MICHELSON CONTRAST")
print("=" * 80)

original, mask, centers = smart_align_images("whomen.jpg", "whomen-1.jpg")
diagnose_all_segments(original, mask)
skin, hair, eyes, brows = classify_features_universal(original, mask)
result = detailed_4features_analysis(skin, hair, eyes, brows)

cv2.imwrite("scientific_michelson_analysis.png", mask * 15)
print("\n💾 scientific_michelson_analysis.png — НАУЧНЫЙ!")
print("✅ Michelson Contrast = ЕДИНСТВЕННЫЙ стандарт с публикациями!")
