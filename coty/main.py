"""
НАУЧНЫЙ АНАЛИЗ: CIE LCh ТЕПЛОТА + MICHELSON КОНТРАСТ + ПЕРСОНАЛЬНАЯ ПАЛИТРА (ОТТЕНКИ В ГРАНИЦАХ)
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


# ---------- УЛУЧШЕННЫЕ ФУНКЦИИ ПАЛИТРЫ ----------

def map_chroma_to_saturation(avg_chroma):
    """Средняя chroma → категория насыщенности + значение C."""
    if avg_chroma >= 45:
        return "ВЫСОКАЯ", 80.0
    elif avg_chroma <= 25:
        return "НИЗКАЯ", 30.0
    else:
        return "СРЕДНЯЯ", 55.0


def make_raw_L_levels(michelson, steps=5):
    """1. ТЕОРЕТИЧЕСКАЯ лесенка L* по контрастности."""
    if michelson < 0.30:  # Низкая → светлые
        base_top, base_bottom = 85, 55
    elif michelson < 0.50:  # Средняя
        base_top, base_bottom = 80, 40
    else:  # Высокая → тёмные
        base_top, base_bottom = 70, 25

    return list(np.linspace(base_top, base_bottom, steps))


def clamp_L_levels_to_user(raw_levels, L_min_user, L_max_user):
    """
    2. НОРМАЛИЗАЦИЯ лесенки в границы пользователя:
    - не темнее L_min_user
    - не светлее L_max_user
    - растягиваем/сжимаем внутри диапазона
    """
    # Обрезаем по границам пользователя
    raw_clamped = [min(max(L, L_min_user), L_max_user) for L in raw_levels]

    # Если диапазон сжался до точки — возвращаем её
    L_top_user = max(raw_clamped)
    L_bottom_user = min(raw_clamped)

    if L_top_user <= L_bottom_user:
        return [L_top_user]

    # Растягиваем обратно на нужное количество шагов
    return list(np.linspace(L_top_user, L_bottom_user, len(raw_levels)))


def generate_personal_palette(color_type, michelson, avg_chroma, L_min_user, L_max_user):
    """
    ✅ ПЕРСОНАЛЬНАЯ ПАЛИТРА ПО 4 КРИТЕРИЯМ:
    1. Теплота → сдвиг hue
    2. Насыщенность → C
    3. Контраст → теоретическая лесенка L*
    4. Границы пользователя → нормализованная лесенка L*_user
    """
    saturation_cat, C = map_chroma_to_saturation(avg_chroma)

    # 1. Теоретическая лесенка по контрасту
    raw_L_levels = make_raw_L_levels(michelson)

    # 2. Нормализация в границы пользователя
    L_levels_user = clamp_L_levels_to_user(raw_L_levels, L_min_user, L_max_user)

    print(f"\n🎨 АНАЛИЗ ПАЛИТРЫ:")
    print(f"   Цветотип: {color_type}")
    print(f"   Насыщенность: {saturation_cat} (C={C:.0f})")
    print(f"   L* raw: {raw_L_levels}")
    print(f"   L* user: {L_levels_user} ← В ГРАНИЦАХ [{L_min_user:.1f}-{L_max_user:.1f}]")

    # Тепло/холодный сдвиг
    hue_shift = -15 if color_type == "ТЕПЛЫЙ" else 15

    # Базовые цвета
    base_hues = {
        'Красный': 0, 'Оранжевый': 30, 'Жёлтый': 60, 'Зелёный': 120,
        'Бирюзовый': 170, 'Синий': 230, 'Фиолетовый': 280, 'Розовый': 320, 'Коричневый': 25
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
                "name": f"{name} {i+1}",
                "base_name": name,
                "hex": hex_color,
                "L": round(L, 1),
                "chroma": round(C, 1),
                "hue_deg": round(h, 1),
                "L_user_normalized": True
            })

    print(f"   Сгенерировано цветов: {len(palette)}")
    return palette, L_levels_user


# ---------- [ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ БЕЗ ИЗМЕНЕНИЙ] ----------

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
        print(f"{cls:6} | ({r:3},{g:3},{b:3}) | {L_val:4.1f} | "
              f"{color_info['temperature']:7} | {color_info['hue_deg']:4}° | {pct:6.2f}%")
    return segment_list


def classify_features_universal(original, mask_segments, color_analyzer):
    skin, hair, eyes, brows = [], [], [], []

    print("\nКЛАССИФИКАЦИЯ 4 ЭЛЕМЕНТОВ:")
    print("Кластер | Тип      | HEX     | L*  | Теплота | %")
    print("-" * 55)

    eye_data = find_true_iris_universal(original, mask_segments, color_analyzer)
    if eye_data:
        eyes.append({'cls': eye_data['cls'], 'L': eye_data['L'],
                    'color_analysis': eye_data['color_analysis'], 'percent': 0.6})
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

            if 0.3 < pct < 2.5 and 8 < r < 90 and mean_lab[0] < 45:
                color_info = color_analyzer.analyze_feature((r, g, b), 'brows')
                brows.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})
            elif pct > 1.5 and 5 < r < 140:
                color_info = color_analyzer.analyze_feature((r, g, b), 'hair')
                hair.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})
            elif pct > 0.8 and 50 < r < 230:
                color_info = color_analyzer.analyze_feature((r, g, b), 'skin')
                skin.append({'cls': cls, 'L': mean_lab[0], 'color_analysis': color_info, 'percent': pct})

    print(f"\nНайдено: Кожа:{len(skin)} | Волосы:{len(hair)} | Глаза:{len(eyes)} | Брови:{len(brows)}")
    return skin, hair, eyes, brows


def find_true_iris_universal(original, mask_segments, color_analyzer):
    print("\nПОИСК РАДУЖКИ...")
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

    # MICHELSON CONTRAST + ГРАНИЦЫ L*
    L_values = [seg['L'] for seg in all_segments]
    L_max = max(L_values)
    L_min = min(L_values)
    michelson_contrast = (L_max - L_min) / (L_max + L_min)

    print(f"\nMICHELSON CONTRAST = {michelson_contrast:.3f}")
    contrast_type = "Низкая" if michelson_contrast < 0.30 else "Средняя" if michelson_contrast < 0.50 else "Высокая"
    print(f"{contrast_type} контрастность")
    print(f"ГРАНИЦЫ L*: {L_min:.1f} (темный) — {L_max:.1f} (светлый)")

    # ЦВЕТОТИП
    warm_count = sum(1 for seg in all_segments if 'ТЕПЛЫЙ' in seg['color_analysis']['temperature'])
    color_type = "ТЕПЛЫЙ" if warm_count > len(all_segments) / 2 else "ХОЛОДНЫЙ"

    print(f"\nЦВЕТОТИП: {color_type} ({warm_count}/{len(all_segments)} элементов)")

    avg_L = np.mean(L_values)
    avg_chroma = np.mean([seg['color_analysis']['chroma'] for seg in all_segments])

    print("=" * 90)
    return {
        'michelson': michelson_contrast,
        'contrast_type': contrast_type,
        'color_type': color_type,
        'avg_L': avg_L,
        'avg_chroma': avg_chroma,
        'L_min_user': L_min,  # ✅ САМЫЙ ТЁМНЫЙ
        'L_max_user': L_max   # ✅ САМЫЙ СВЕТЛЫЙ
    }


def create_smart_colored_visualization(original, mask_segments, skin, hair, eyes, brows):
    gray = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY)
    gray_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    smart_visual = gray_rgb.copy()

    best_skin = max(skin, key=lambda x: x['L']) if skin else None
    if best_skin:
        print(f"🧡 САМЫЙ ЯРКИЙ КОЖА: кластер {best_skin['cls']} L*={best_skin['L']:.1f}")

    features = []
    if eyes: features.append(('Eyes', eyes[0]))
    if brows: features.append(('Brows', brows[0]))
    if hair: features.append(('Hair', hair[0]))
    if best_skin: features.append(('Skin', best_skin))

    for name, seg in features:
        cls_id = int(seg['cls'])
        seg_mask = (mask_segments == cls_id)
        seg_pixels = original[seg_mask]
        if len(seg_pixels) > 0:
            avg_rgb = np.mean(seg_pixels, axis=0).astype(np.uint8)
            smart_visual[seg_mask] = avg_rgb

    legend = np.ones((200, 350, 3), np.uint8) * 255
    y = 40
    for name, seg in features:
        cls_id = int(seg['cls'])
        seg_mask = (mask_segments == cls_id)
        seg_pixels = original[seg_mask]
        if len(seg_pixels) > 0:
            avg_rgb = np.mean(seg_pixels, axis=0).astype(np.uint8)
            legend[y - 30:y + 5, 30:80] = avg_rgb
            cv2.putText(legend, name, (100, y), cv2.FONT_HERSHEY_PLAIN, 1.2, (0, 0, 0), 2)
            y += 45

    cv2.imwrite("smart_analysis_visual.png", cv2.cvtColor(smart_visual, cv2.COLOR_RGB2BGR))
    cv2.imwrite("smart_legend.png", cv2.cvtColor(legend, cv2.COLOR_RGB2BGR))
    print("✅ 🧡 ВИЗУАЛИЗАЦИЯ ГОТОВА!")


def generate_html_palette_report(html_path, palette, result, L_levels_user):
    html_blocks = []
    current_base = ""

    for c in palette:
        if c["base_name"] != current_base:
            html_blocks.append(f'<h3 style="margin-top:25px;">{c["base_name"]}</h3>')
            current_base = c["base_name"]

        html_blocks.append(
            f'<div class="color-block" style="background:{c["hex"]};">'
            f'<span>{c["name"]}<br>{c["hex"]}<br>L*={c["L"]}<br>C={c["chroma"]}</span></div>'
        )

    html = f"""
    <!DOCTYPE html>
    <html><head><meta charset="utf-8">
    <title>Персональная палитра (L* в ваших границах)</title>
    <style>
        body {{ font-family:Arial, sans-serif; background:#f0f8ff; margin:20px; line-height:1.4; }}
        h1 {{ border-bottom:3px solid #1e90ff; padding-bottom:15px; color:#1e3a8a; }}
        h3 {{ color:#2b5aa0; margin:25px 0 15px 0; border-left:4px solid #87ceeb; padding-left:10px; }}
        .summary {{ background:#e6f3ff; padding:20px; border-radius:10px; margin-bottom:25px; border:2px solid #b0e0e6; }}
        .color-block {{
            width:145px; height:105px; display:inline-block; margin:5px;
            border:2px solid #4682b4; color:#000; text-align:center;
            vertical-align:top; font-size:11px; padding:3px; border-radius:10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .color-block span {{ display:block; margin-top:3px; background:rgba(255,255,255,0.9); border-radius:5px; }}
    </style>
    </head>
    <body>
      <h1>🎨 Персональная цветовая палитра<br><small>(все оттенки в ваших L* границах)</small></h1>
      
      <div class="summary">
        <h2>📊 Ваши характеристики:</h2>
        <p><b>Цветотип:</b> {result['color_type']}<br>
           <b>Контрастность:</b> {result['contrast_type']} (Michelson={result['michelson']:.3f})<br>
           <b>🎯 L* границы:</b> <span style="color:#d2691e; font-weight:bold;">{result['L_min_user']:.1f}–{result['L_max_user']:.1f}</span><br>
           <b>🌈 L* уровни палитры:</b> {L_levels_user}<br>
           <b>Средняя L*:</b> {result['avg_L']:.1f} | <b>Chroma:</b> {result['avg_chroma']:.1f}</p>
      </div>
      
      {''.join(html_blocks)}
      
      <div style="margin-top:30px; padding:15px; background:#f0f8ff; border-radius:8px; font-size:14px; color:#444;">
        <b>🔬 Логика:</b> Каждый базовый цвет адаптирован под <u>ваши</u> теплоту, насыщенность 
        и <b>строго</b> ограничен вашим диапазоном L* ({result['L_min_user']:.0f}–{result['L_max_user']:.0f}).
      </div>
    </body></html>
    """

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML‑палитра сохранена: {html_path}")


# ---------- ЗАПУСК ----------

if __name__ == "__main__":
    print("✅ CIE LCh + MICHELSON + ПАЛИТРА (L* В ГРАНИЦАХ ПОЛЬЗОВАТЕЛЯ)")
    print("=" * 80)

    color_analyzer = ColorAnalyzer()
    original, mask, centers = smart_align_images("whomen.jpg", "whomen-1.jpg")

    diagnose_all_segments(original, mask, color_analyzer)
    skin, hair, eyes, brows = classify_features_universal(original, mask, color_analyzer)
    result = detailed_4features_analysis(skin, hair, eyes, brows)

    create_smart_colored_visualization(original, mask, skin, hair, eyes, brows)
    cv2.imwrite("lch_michelson_analysis.png", mask * 15)

    # ✅ ПЕРСОНАЛЬНАЯ ПАЛИТРА С НОРМАЛИЗАЦИЕЙ L*
    palette, L_levels_user = generate_personal_palette(
        color_type=result['color_type'],
        michelson=result['michelson'],
        avg_chroma=result['avg_chroma'],
        L_min_user=result['L_min_user'],
        L_max_user=result['L_max_user']
    )

    generate_html_palette_report("personal_palette_user_bounds.html", palette, result, L_levels_user)

    print("\n🎉 ГОТОВО! Проверьте personal_palette_user_bounds.html")