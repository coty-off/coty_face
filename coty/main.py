"""
НАУЧНЫЙ АНАЛИЗ: CIE LCh ТЕПЛОТА + MICHELSON КОНТРАСТ + ПЕРСОНАЛЬНАЯ ПАЛИТРА
"""
import argparse
import os
import numpy as np
import cv2
from PIL import Image
from skimage.color import rgb2lab
import warnings

warnings.filterwarnings("ignore")


# ==================== ТОЧНАЯ ТАБЛИЦА СЕГМЕНТОВ ====================
SEGMENT_MAP = {
    0:  ("background", [255, 0, 0]),
    1:  ("skin",       [255, 85, 0]),
    2:  ("l_brow",     [255, 170, 0]),
    3:  ("r_brow",     [255, 0, 85]),
    4:  ("l_eye",      [255, 0, 170]),
    5:  ("r_eye",      [0, 255, 0]),
    6:  ("eye_g",      [85, 255, 0]),
    7:  ("l_ear",      [170, 255, 0]),
    8:  ("r_ear",      [0, 255, 85]),
    9:  ("ear_r",      [0, 255, 170]),
    10: ("hair",       [0, 0, 255]),
    11: ("nose",       [85, 0, 255]),
    12: ("mouth",      [170, 0, 255]),
    13: ("u_lip",      [0, 85, 255]),
    14: ("l_lip",      [0, 170, 255]),
    15: ("neck",       [255, 255, 0]),
    16: ("neck_l",     [255, 255, 85]),
    17: ("cloth",      [255, 255, 170]),
    18: ("hat",        [255, 0, 255])
}

IMPORTANT_SEGMENTS = {1: "skin", 2: "brow", 3: "brow", 4: "eye", 5: "eye", 10: "hair"}


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
        elif feature_type in ['hair', 'brow']:
            is_warm = (20 <= hue_deg <= 50) or (300 <= hue_deg <= 340)
        else:
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


def get_feature_mask(colored_mask, target_color, tolerance=25):
    diff = np.abs(colored_mask.astype(np.int32) - np.array(target_color, dtype=np.int32))
    return np.all(diff <= tolerance, axis=-1)


def smart_align_images(original_path, mask_path):
    original = np.array(Image.open(original_path).convert("RGB"))
    colored_mask = cv2.imread(mask_path)
    if colored_mask is None:
        raise FileNotFoundError(f"Не могу загрузить маску: {mask_path}")

    colored_mask = cv2.cvtColor(colored_mask, cv2.COLOR_BGR2RGB)

    # Приводим маску к размеру оригинала
    if colored_mask.shape[:2] != original.shape[:2]:
        print(f"[COTY] Resize mask {colored_mask.shape[:2]} → {original.shape[:2]}")
        colored_mask = cv2.resize(colored_mask, (original.shape[1], original.shape[0]),
                                  interpolation=cv2.INTER_NEAREST)

    print(f"[COTY] Original: {original.shape}, Mask: {colored_mask.shape}")
    return original, colored_mask


def find_true_iris_universal(original, colored_mask, color_analyzer):
    print("\n[ Iris ] Поиск радужки...")
    best = None
    for cls_id in [4, 5]:
        color = SEGMENT_MAP[cls_id][1]
        mask = get_feature_mask(colored_mask, color)
        pixels = original[mask]
        if len(pixels) < 80:
            continue
        lab = rgb2lab(pixels.astype(np.float32)/255.0)
        idx = np.argmax(lab[:, 0])
        rgb = tuple(pixels[idx].astype(int))
        analysis = color_analyzer.analyze_feature(rgb, 'eyes')
        if best is None or lab[idx, 0] > best.get('L', 0):
            best = {'cls': cls_id, 'L': lab[idx, 0], 'color_analysis': analysis, 'rgb': rgb}
    if best:
        print(f"[ Iris ] Найдена радужка: {best['color_analysis']['hex']} L*={best['L']:.1f}")
    return best


def classify_features_universal(original, colored_mask, color_analyzer):
    print("\n[ Classification ] Определение сегментов:")
    skin = hair = eyes = brows = []

    for cls_id, feature_name in IMPORTANT_SEGMENTS.items():
        color = SEGMENT_MAP[cls_id][1]
        mask = get_feature_mask(colored_mask, color, tolerance=25)
        pixels = original[mask]
        area = np.sum(mask)

        if area < 300:
            continue

        avg_rgb = tuple(np.mean(pixels, axis=0).astype(int))
        analysis = color_analyzer.analyze_feature(avg_rgb, feature_name)

        item = {
            'cls': cls_id,
            'L': float(np.mean(pixels[:, 0])) if len(pixels) > 0 else 50.0,
            'color_analysis': analysis,
            'percent': float(area) / (original.shape[0] * original.shape[1]) * 100,
            'rgb': avg_rgb
        }

        if feature_name == "skin": skin.append(item)
        elif feature_name == "hair": hair.append(item)
        elif feature_name == "brow": brows.append(item)
        elif feature_name == "eye": eyes.append(item)

        print(f"  Класс {cls_id} → {feature_name:6} | {analysis['hex']} | L*={analysis['l_star']:4.1f} | {analysis['temperature']} | {item['percent']:.2f}%")

    if not eyes:
        iris = find_true_iris_universal(original, colored_mask, color_analyzer)
        if iris:
            eyes = [iris]

    return skin, hair, eyes, brows


def detailed_4features_analysis(skin, hair, eyes, brows):
    print("\n" + "="*80)
    print("НАУЧНЫЙ АНАЛИЗ: CIE LCh + MICHELSON")
    print("="*80)

    all_segments = []
    for segments, name in [(skin, "КОЖА"), (hair, "ВОЛОСЫ"), (eyes, "ГЛАЗА"), (brows, "БРОВИ")]:
        if not segments:
            continue
        avg_rgb = tuple(np.mean([s['color_analysis']['rgb'] for s in segments], axis=0).astype(int))
        avg_L = np.mean([s['L'] for s in segments])
        color_analyzer = ColorAnalyzer()
        analysis = color_analyzer.analyze_feature(avg_rgb, name.lower() if name != "БРОВИ" else "brow")

        all_segments.append({
            'name': name,
            'L': avg_L,
            'color_analysis': analysis,
            'percent': sum(s.get('percent', 0.5) for s in segments)
        })

    L_values = [s['L'] for s in all_segments]
    L_max = max(L_values) if L_values else 70
    L_min = min(L_values) if L_values else 40
    michelson = (L_max - L_min) / (L_max + L_min) if L_max + L_min > 0 else 0.0

    warm_count = sum(1 for s in all_segments if "ТЕПЛЫЙ" in s['color_analysis']['temperature'])
    color_type = "ТЕПЛЫЙ" if warm_count > len(all_segments) / 2 else "ХОЛОДНЫЙ"

    avg_chroma = np.mean([s['color_analysis']['chroma'] for s in all_segments]) if all_segments else 30

    print(f"Подтон → {color_type}")
    print(f"Michelson Contrast = {michelson:.3f}")
    print(f"L* границы: {L_min:.1f} — {L_max:.1f}")

    return {
        'color_type': color_type,
        'michelson': michelson,
        'avg_chroma': avg_chroma,
        'L_min_user': L_min,
        'L_max_user': L_max
    }


def generate_personal_palette(color_type, michelson, avg_chroma, L_min_user, L_max_user):
    # Твоя оригинальная функция палитры (оставлена без изменений)
    def map_chroma_to_saturation(avg_chroma):
        if avg_chroma >= 45: return "ВЫСОКАЯ", 80.0
        elif avg_chroma <= 25: return "НИЗКАЯ", 30.0
        else: return "СРЕДНЯЯ", 55.0

    def make_raw_L_levels(michelson, steps=5):
        if michelson < 0.30: return list(np.linspace(85, 55, steps))
        elif michelson < 0.50: return list(np.linspace(80, 40, steps))
        else: return list(np.linspace(70, 25, steps))

    def clamp_L_levels_to_user(raw_levels, L_min_user, L_max_user):
        clamped = [min(max(L, L_min_user), L_max_user) for L in raw_levels]
        return list(np.linspace(max(clamped), min(clamped), len(raw_levels)))

    saturation_cat, C = map_chroma_to_saturation(avg_chroma)
    raw_L = make_raw_L_levels(michelson)
    L_levels = clamp_L_levels_to_user(raw_L, L_min_user, L_max_user)

    hue_shift = -15 if color_type == "ТЕПЛЫЙ" else 15
    base_hues = {'Красный':0, 'Оранжевый':30, 'Жёлтый':60, 'Зелёный':120,
                 'Бирюзовый':170, 'Синий':230, 'Фиолетовый':280, 'Розовый':320}

    palette = []
    for name, base_h in base_hues.items():
        h = (base_h + hue_shift) % 360
        for i, L in enumerate(L_levels):
            a = C * np.cos(np.radians(h))
            b = C * np.sin(np.radians(h))
            lab = np.array([[[L, a, b]]], dtype=np.float32)
            rgb = cv2.cvtColor(lab, cv2.COLOR_Lab2RGB)[0][0]
            rgb = np.clip(rgb * 255, 0, 255).astype(np.uint8)
            hex_color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            palette.append({"name": f"{name} {i+1}", "hex": hex_color, "L": round(L, 1), "chroma": round(C, 1)})

    return palette, L_levels


def generate_html_palette_report(html_path, palette, result, L_levels_user):
    blocks = [f'<div style="background:{c["hex"]};width:140px;height:100px;display:inline-block;margin:8px;border:2px solid #333;border-radius:8px;text-align:center;">'
              f'{c["name"]}<br>{c["hex"]}<br>L*={c["L"]}</div>' for c in palette]

    html = f"""
    <html><head><meta charset="utf-8"><title>Палитра</title>
    <style>body{{font-family:Arial;background:#f8f9fa;margin:30px;}} h1{{color:#1e3a8a;}}</style></head>
    <body>
        <h1>🎨 Ваша персональная цветовая палитра</h1>
        <p><b>Подтон:</b> {result['color_type']}<br>
           <b>Контрастность:</b> {result.get('michelson',0):.3f}<br>
           <b>L* границы:</b> {result['L_min_user']:.1f} — {result['L_max_user']:.1f}</p>
        {''.join(blocks)}
    </body></html>
    """
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def create_smart_colored_visualization(original, colored_mask, skin, hair, eyes, brows, output_dir, base_name):
    """Начинаем с цветного оригинала + закрашиваем сегменты"""
    visual = original.copy()   # ←←← НАЧИНАЕМ С ЦВЕТНОГО ФОТО

    legend = np.ones((300, 480, 3), dtype=np.uint8) * 255
    y = 50

    feature_list = [
        ("Eyes",  eyes[0] if eyes else None),
        ("Brows", brows[0] if brows else None),
        ("Hair",  hair[0] if hair else None),
        ("Skin",  skin[0] if skin else None)
    ]

    for name, seg in feature_list:
        if not seg: continue
        cls_id = seg['cls']
        if cls_id not in SEGMENT_MAP: continue

        target_color = SEGMENT_MAP[cls_id][1]
        mask = get_feature_mask(colored_mask, target_color)

        pixels = original[mask]
        if len(pixels) > 0:
            avg_rgb = np.mean(pixels, axis=0).astype(np.uint8)
            visual[mask] = avg_rgb   # закрашиваем реальным цветом

            # Легенда
            legend[y-35:y+30, 40:130] = avg_rgb
            cv2.putText(legend, name, (160, y), cv2.FONT_HERSHEY_PLAIN, 2.0, (0,0,0), 2)
            y += 75

    visual_path = os.path.join(output_dir, f"{base_name}_smart_analysis_visual.png")
    legend_path = os.path.join(output_dir, f"{base_name}_smart_legend.png")

    cv2.imwrite(visual_path, cv2.cvtColor(visual, cv2.COLOR_RGB2BGR))
    cv2.imwrite(legend_path, cv2.cvtColor(legend, cv2.COLOR_RGB2BGR))

    print(f"✅ Цветная визуализация и легенда сохранены")


# ==================== MAIN ====================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", "-o", required=True)
    parser.add_argument("--mask", "-m", required=True)
    parser.add_argument("--output_dir", "-d", required=True)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    original, colored_mask = smart_align_images(args.original, args.mask)
    color_analyzer = ColorAnalyzer()

    skin, hair, eyes, brows = classify_features_universal(original, colored_mask, color_analyzer)

    result = detailed_4features_analysis(skin, hair, eyes, brows)

    base_name = os.path.splitext(os.path.basename(args.original))[0]

    create_smart_colored_visualization(original, colored_mask, skin, hair, eyes, brows, args.output_dir, base_name)

    palette, L_levels_user = generate_personal_palette(
        result['color_type'], result['michelson'], result['avg_chroma'],
        result['L_min_user'], result['L_max_user']
    )

    html_path = os.path.join(args.output_dir, f"{base_name}_personal_palette.html")
    generate_html_palette_report(html_path, palette, result, L_levels_user)

    print(f"\n[COTY] ✅ АНАЛИЗ ЗАВЕРШЁН! Результаты в: {args.output_dir}")


if __name__ == "__main__":
    main()