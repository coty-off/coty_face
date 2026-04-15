

import argparse
import os
import numpy as np
import cv2
from PIL import Image
from skimage.color import rgb2lab
import warnings

warnings.filterwarnings("ignore")

# ==================== КЛАССЫ face-parsing.PyTorch ====================
TARGET_CLASSES = {
    1: "skin",
    2: "l_brow",
    3: "r_brow",
    4: "l_eye",
    5: "r_eye",
    17: "hair"
}

class ColorAnalyzer:
    def rgb_to_cielab_full(self, rgb):
        rgb_norm = np.array([[rgb]], dtype=np.float32) / 255.0
        lab = rgb2lab(rgb_norm)
        return lab[0, 0, 0], lab[0, 0, 1], lab[0, 0, 2]

    def analyze_feature(self, rgb, feature_type):
        l_star, a_star, b_star = self.rgb_to_cielab_full(rgb)
        chroma = np.sqrt(a_star ** 2 + b_star ** 2)
        hue_deg = np.degrees(np.arctan2(b_star, a_star)) % 360

        if feature_type == 'skin':
            is_warm = (0 <= hue_deg <= 60) or (300 <= hue_deg <= 360)
        elif feature_type in ['hair', 'brows']:
            is_warm = (20 <= hue_deg <= 50) or (300 <= hue_deg <= 340)
        else:
            is_warm = (0 <= hue_deg <= 40) or (300 <= hue_deg <= 360)

        return {
            'rgb': rgb,
            'hex': f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}",
            'l_star': round(l_star, 1),
            'b_star': round(b_star, 1),
            'hue_deg': round(hue_deg, 1),
            'temperature': "ТЕПЛЫЙ" if is_warm else "ХОЛОДНЫЙ",
            'chroma': round(chroma, 1)
        }

# ==================== ФУНКЦИИ ПАЛИТРЫ  ====================
def map_chroma_to_saturation(avg_chroma):
    if avg_chroma >= 45:
        return "ВЫСОКАЯ", 80.0
    elif avg_chroma <= 25:
        return "НИЗКАЯ", 30.0
    else:
        return "СРЕДНЯЯ", 55.0

def make_raw_L_levels(michelson, steps=5):
    if michelson < 0.30:
        base_top, base_bottom = 85, 55
    elif michelson < 0.50:
        base_top, base_bottom = 80, 40
    else:
        base_top, base_bottom = 70, 25
    return list(np.linspace(base_top, base_bottom, steps))

def clamp_L_levels_to_user(raw_levels, L_min_user, L_max_user):
    raw_clamped = [min(max(L, L_min_user), L_max_user) for L in raw_levels]
    L_top_user = max(raw_clamped)
    L_bottom_user = min(raw_clamped)
    if L_top_user <= L_bottom_user:
        return [L_top_user]
    return list(np.linspace(L_top_user, L_bottom_user, len(raw_levels)))

def generate_personal_palette(color_type, michelson, avg_chroma, L_min_user, L_max_user):
    saturation_cat, C = map_chroma_to_saturation(avg_chroma)
    raw_L_levels = make_raw_L_levels(michelson)  # ← raw_L_levels
    L_levels_user = clamp_L_levels_to_user(raw_L_levels, L_min_user, L_max_user)

    print(f"\n АНАЛИЗ ПАЛИТРЫ:")
    print(f"   Цветотип: {color_type}")
    print(f"   Насыщенность: {saturation_cat} (C={C:.0f})")
    print(f"   L* raw: {raw_L_levels}")
    print(f"   L* user: {L_levels_user}")

    hue_shift = -15 if color_type == "ТЕПЛЫЙ" else 15
    base_hues = {
        'Красный': 0, 'Оранжевый': 30, 'Жёлтый': 60, 'Зелёный': 120,
        'Бирюзовый': 170, 'Синий': 230, 'Фиолетовый': 280,
        'Розовый': 320, 'Коричневый': 25
    }

    palette = []
    for name, base_h in base_hues.items():
        h = (base_h + hue_shift) % 360
        for i, L in enumerate(L_levels_user):
            a = C * np.cos(np.radians(h))
            b = C * np.sin(np.radians(h))
            lab = np.array([[[L, a, b]]], dtype=np.float32)
            rgb = cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)[0][0]
            rgb = np.clip(rgb * 255, 0, 255).astype(np.uint8)
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

            palette.append({
                "name": f"{name} {i + 1}",
                "base_name": name,
                "hex": hex_color,
                "L": round(L, 1),
                "chroma": round(C, 1),
                "hue_deg": round(h, 1),
                "L_user_normalized": True
            })

    return palette, L_levels_user

# ==================== РАБОТА С ИНДЕКСНОЙ МАСКОЙ ====================
def load_index_mask(original_path, index_mask_path):
    original = np.array(Image.open(original_path).convert("RGB"))
    mask = cv2.imread(index_mask_path, cv2.IMREAD_GRAYSCALE)

    if mask is None:
        raise FileNotFoundError(f"Не удалось загрузить индексную маску: {index_mask_path}")

    print(f"Оригинал: {original.shape}")
    print(f"Индексная маска: {mask.shape}")

    if mask.shape[:2] != original.shape[:2]:
        mask = cv2.resize(mask, (original.shape[1], original.shape[0]), cv2.INTER_NEAREST)
        print(" Маска приведена к размеру оригинала")

    print(f"Классы в маске: {np.unique(mask)}")
    return original, mask

def extract_precise_features(original, mask):
    features = {'skin': [], 'hair': [], 'eyes': [], 'brows': []}

    print("\n ТОЧНЫЙ АНАЛИЗ ПО КЛАССАМ:")
    print("Класс | Название | Пикселей | L*")

    for class_id, name in TARGET_CLASSES.items():
        seg_mask = (mask == class_id)
        pixels = original[seg_mask]

        if len(pixels) > 100:
            avg_rgb = np.mean(pixels, axis=0).astype(np.uint8)
            rgb_norm = pixels.astype(np.float32) / 255.0
            lab_vals = rgb2lab(rgb_norm.reshape(-1, 1, 1, 3)).squeeze()
            mean_L = np.nanmean(lab_vals[:, 0])

            item = {'cls': class_id, 'L': mean_L, 'rgb': tuple(avg_rgb)}

            if name == 'skin':
                features['skin'].append(item)
            elif name == 'hair':
                features['hair'].append(item)
            elif name in ['l_eye', 'r_eye']:
                features['eyes'].append(item)
            elif name in ['l_brow', 'r_brow']:
                features['brows'].append(item)

            print(f"{class_id:4} | {name:8} | {len(pixels):6} | {mean_L:5.1f}")

    return features['skin'], features['hair'], features['eyes'], features['brows']

def detailed_4features_analysis(skin, hair, eyes, brows, color_analyzer):
    print("\n" + "=" * 90)
    print("НАУЧНЫЙ АНАЛИЗ: CIE LCh + MICHELSON (4 ЭЛЕМЕНТА)")
    print("=" * 90)

    all_segments = []
    feature_names = {'skin': 'КОЖА', 'hair': 'ВОЛОСЫ', 'eyes': 'ГЛАЗА', 'brows': 'БРОВИ'}

    for ftype, segments in [('skin', skin), ('eyes', eyes), ('brows', brows)]:
        if segments:
            best_seg = max(segments, key=lambda x: x['L'])
            avg_rgb = best_seg['rgb']
            avg_color = color_analyzer.analyze_feature(avg_rgb, ftype)
            all_segments.append({
                'name': feature_names[ftype],
                'L': best_seg['L'],
                'color_analysis': avg_color,
                'rgb': avg_rgb,
                'is_cluster': False
            })

    if hair:
        sorted_hair = sorted(hair, key=lambda x: x['L'])
        hair_segments = []

        if len(sorted_hair) == 1:
            seg = sorted_hair[0]
            avg_color = color_analyzer.analyze_feature(seg['rgb'], 'hair')
            hair_segments.append({
                'name': 'ВОЛОСЫ',
                'L': seg['L'],
                'color_analysis': avg_color,
                'rgb': seg['rgb'],
                'is_cluster': False
            })
        else:
            low_seg = sorted_hair[0]
            mid_seg = sorted_hair[len(sorted_hair) // 2]
            high_seg = sorted_hair[-1]

            low_info = color_analyzer.analyze_feature(low_seg['rgb'], 'hair')
            mid_info = color_analyzer.analyze_feature(mid_seg['rgb'], 'hair')
            high_info = color_analyzer.analyze_feature(high_seg['rgb'], 'hair')

            print(f"\n ВОЛОСЫ: база + средний тон + блики")
            print(f"   LOW : {low_info['hex']} L*={low_seg['L']:.1f} {low_info['temperature']}")
            print(f"   MID : {mid_info['hex']} L*={mid_seg['L']:.1f} {mid_info['temperature']}")
            print(f"   HIGH: {high_info['hex']} L*={high_seg['L']:.1f} {high_info['temperature']}")

            w_low, w_mid, w_high = 0.45, 0.35, 0.20

            warm_score = 0.0
            cool_score = 0.0
            avg_L_hair = low_seg['L'] * w_low + mid_seg['L'] * w_mid + high_seg['L'] * w_high
            avg_chroma_hair = low_info['chroma'] * w_low + mid_info['chroma'] * w_mid + high_info['chroma'] * w_high

            for info, w in [(low_info, w_low), (mid_info, w_mid), (high_info, w_high)]:
                if info['temperature'] == 'ТЕПЛЫЙ':
                    warm_score += w
                else:
                    cool_score += w

            hair_temp = 'ТЕПЛЫЙ' if warm_score >= cool_score else 'ХОЛОДНЫЙ'
            if abs(warm_score - cool_score) < 0.15:
                hair_temp = 'НЕЙТРАЛЬНЫЙ'

            hair_color = dict(high_info)
            hair_color['temperature'] = hair_temp
            hair_color['chroma'] = round(avg_chroma_hair, 1)

            hair_segments.append({
                'name': 'ВОЛОСЫ',
                'L': round(avg_L_hair, 1),
                'color_analysis': hair_color,
                'rgb': high_seg['rgb'],
                'is_cluster': False
            })

        all_segments.extend(hair_segments)

    print("\n4 ЭЛЕМЕНТА (LCh Анализ):")
    print("Элемент | HEX     | L*   | Теплота | Hue°")
    print("-" * 55)

    for seg in all_segments:
        print(f"{seg['name']:8} | {seg['color_analysis']['hex']:8} | "
              f"{seg['L']:4.1f} | {seg['color_analysis']['temperature']:8} | "
              f"{seg['color_analysis']['hue_deg']:4}°")

    L_values = [seg['L'] for seg in all_segments]
    L_max = max(L_values)
    L_min = min(L_values)
    michelson_contrast = (L_max - L_min) / (L_max + L_min)

    print(f"\nMICHELSON CONTRAST = {michelson_contrast:.3f}")
    contrast_type = "Низкая" if michelson_contrast < 0.30 else "Средняя" if michelson_contrast < 0.50 else "Высокая"
    print(f"{contrast_type} контрастность")
    print(f"ГРАНИЦЫ L*: {L_min:.1f} — {L_max:.1f}")

    warm_score = 0.0
    cool_score = 0.0

    def get_feature_weight(name, is_cluster=False):
        if name == "КОЖА":
            return 3.0
        if name == "ГЛАЗА":
            return 3.5
        if name == "БРОВИ":
            return 1.5
        if name == "ВОЛОСЫ":
            return 1.2
        return 1.0

    for seg in all_segments:
        w = get_feature_weight(seg['name'], seg.get('is_cluster', False))
        temp = seg['color_analysis']['temperature']
        if temp == "ТЕПЛЫЙ":
            warm_score += w
        elif temp == "ХОЛОДНЫЙ":
            cool_score += w

    if warm_score - cool_score >= 0.8:
        color_type = "ТЕПЛЫЙ"
    elif cool_score - warm_score >= 0.8:
        color_type = "ХОЛОДНЫЙ"
    else:
        color_type = "НЕЙТРАЛЬНЫЙ"

    print(f"\nWARM SCORE = {warm_score:.2f}")
    print(f"COOL SCORE = {cool_score:.2f}")
    print(f"ЦВЕТОТИП: {color_type}")
    print("=" * 90)

    avg_L = np.mean(L_values)
    avg_chroma = np.mean([seg['color_analysis']['chroma'] for seg in all_segments])

    return {
        'michelson': michelson_contrast,
        'contrast_type': contrast_type,
        'color_type': color_type,
        'avg_L': avg_L,
        'avg_chroma': avg_chroma,
        'L_min_user': L_min,
        'L_max_user': L_max,
        'all_segments': all_segments
    }

def create_smart_colored_visualization(original, mask, skin, hair, eyes, brows, all_segments, output_dir, base_name):
    gray_rgb = cv2.cvtColor(cv2.cvtColor(original, cv2.COLOR_RGB2GRAY), cv2.COLOR_GRAY2RGB)
    smart_visual = gray_rgb.copy()

    features = []
    if eyes:
        features.append(('Eyes', eyes[0]))
    if brows:
        features.append(('Brows', brows[0]))
    if skin:
        features.append(('Skin', skin[0]))
    if hair:
        features.append(('Hair', hair[0]))

    for name, seg in features:
        if 'cls' in seg:
            cls_id = seg['cls']
            seg_mask = (mask == cls_id)
            smart_visual[seg_mask] = seg['rgb']

    legend_height = max(60 + len(all_segments) * 35, 200)
    legend = np.ones((legend_height, 500, 3), np.uint8) * 255

    cv2.putText(legend, "COLOR ANALYSIS (Hair highlights included)", (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    y = 70
    for seg in all_segments:
        legend[y - 25:y - 5, 30:80] = seg['rgb']
        name_text = {"КОЖА": "SKIN", "ГЛАЗА": "EYES", "БРОВИ": "BROWS", "ВОЛОСЫ": "HAIR"}.get(seg['name'], seg['name'])
        cv2.putText(legend, name_text, (100, y),
                    cv2.FONT_HERSHEY_PLAIN, 1.2, (0, 0, 0), 2)

        cv2.putText(legend, seg['color_analysis']['hex'], (100, y + 18),
                    cv2.FONT_HERSHEY_PLAIN, 0.9, (40, 40, 40), 2)

        temp_short = "T" if "ТЕПЛЫЙ" in seg['color_analysis']['temperature'] else ("N" if "НЕЙТРАЛЬНЫЙ" in seg['color_analysis']['temperature'] else "C")
        color_temp = (0, 0, 255) if temp_short == "T" else (0, 140, 255) if temp_short == "N" else (100, 150, 255)
        cv2.putText(legend, temp_short, (250, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, color_temp, 3)

        cv2.putText(legend, f"L*:{seg['L']:5.1f}", (320, y),
                    cv2.FONT_HERSHEY_PLAIN, 1.1, (0, 0, 0), 2)

        y += 38

    visual_path = os.path.join(output_dir, f"{base_name}_smart_analysis_visual.png")
    legend_path = os.path.join(output_dir, f"{base_name}_smart_legend_detailed.png")

    cv2.imwrite(visual_path, cv2.cvtColor(smart_visual, cv2.COLOR_RGB2BGR))
    cv2.imwrite(legend_path, cv2.cvtColor(legend, cv2.COLOR_RGB2BGR))
    print(" ЛЕГЕНДА ГОТОВА!")

def generate_html_palette_report(html_path, palette, result, L_levels_user):
    html_blocks = []
    current_base = ""
    for c in palette:
        if c["base_name"] != current_base:
            html_blocks.append(f'<h3>{c["base_name"]}</h3>')
            current_base = c["base_name"]
        html_blocks.append(
            f'<div class="color-block" style="background:{c["hex"]};">'
            f'<span>{c["name"]}<br>{c["hex"]}<br>L*={c["L"]}</span></div>'
        )

    html = f"""
<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Персональная палитра</title>
<style>
body {{font-family:Arial; background:#f0f8ff; margin:20px;}}
h1 {{border-bottom:3px solid #1e90ff; color:#1e3a8a;}}
.summary {{background:#e6f3ff; padding:20px; border-radius:10px; margin-bottom:25px;}}
.color-block {{width:145px; height:105px; display:inline-block; margin:5px;
              border:2px solid #4682b4; color:#000; text-align:center;
              vertical-align:top; font-size:11px; padding:3px; border-radius:10px;}}
</style></head><body>
<h1> Персональная палитра (L* в ваших границах)</h1>
<div class="summary">
<h2> Характеристики:</h2>
<p><b>Цветотип:</b> {result['color_type']}<br>
<b>Контраст:</b> {result['contrast_type']} (Michelson={result['michelson']:.3f})<br>
<b>L* границы:</b> <span style="color:#d2691e;">{result['L_min_user']:.1f}–{result['L_max_user']:.1f}</span></p>
</div>{''.join(html_blocks)}</body></html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f" HTML: {html_path}")

# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", "-o", required=True)
    parser.add_argument("--mask", "-m", required=True)
    parser.add_argument("--output_dir", "-d", required=True)
    args = parser.parse_args()

    print(" НАУЧНЫЙ АНАЛИЗ CIE LCh + ПЕРСОНАЛЬНАЯ ПАЛИТРА")
    print("=" * 80)

    os.makedirs(args.output_dir, exist_ok=True)

    color_analyzer = ColorAnalyzer()
    original, mask = load_index_mask(args.original, args.mask)

    skin, hair, eyes, brows = extract_precise_features(original, mask)
    result = detailed_4features_analysis(skin, hair, eyes, brows, color_analyzer)

    base_name = os.path.splitext(os.path.basename(args.original))[0]

    create_smart_colored_visualization(original, mask, skin, hair, eyes, brows, result['all_segments'], args.output_dir, base_name)

    palette, L_levels_user = generate_personal_palette(
        result['color_type'], result['michelson'],
        result['avg_chroma'], result['L_min_user'], result['L_max_user']
    )

    html_path = os.path.join(args.output_dir, f"{base_name}_personal_palette.html")
    generate_html_palette_report(html_path, palette, result, L_levels_user)
    print(f"\n[COTY]  АНАЛИЗ ЗАВЕРШЁН! Результаты в: {args.output_dir}")

if __name__ == "__main__":
    main()