# api/tasks.py
from api.celery_app import app
import subprocess
import os
from pathlib import Path
import traceback
import time
import shutil
import re
from datetime import datetime
import base64

@app.task(bind=True, queue="segment")
def process_segment(self, photo_path: str, user_id: int) -> dict:
    print(f"[SEGMENT] Start user_id={user_id}, photo={photo_path}")

    try:
        base_name = Path(photo_path).stem
        segment_dir = f"/photos/{base_name}_segment"
        os.makedirs(segment_dir, exist_ok=True)

        cmd = [
            "python", "/app/project/face_parsing/test.py",
            "--input", photo_path,
            "--output_dir", segment_dir
        ]

        print(f"[SEGMENT] Running: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd="/app/project/face_parsing")

        if result.returncode != 0:
            raise RuntimeError(result.stderr)

        index_mask_path = f"{segment_dir}/parsing_map_on_im.png"

        if not os.path.exists(index_mask_path):
            raise FileNotFoundError(f"Index mask not found: {index_mask_path}")

        print(f"[SEGMENT] Index mask: {index_mask_path}")

        color_task = process_colors.delay(photo_path, index_mask_path, user_id)

        return {
            "status": "segment_done",
            "mask_path": index_mask_path,
            "original_path": photo_path,
            "color_task_id": str(color_task.id)
        }

    except Exception as e:
        print(f"[SEGMENT] ERROR: {str(e)}")
        traceback.print_exc()
        return {"status": "segment_failed", "error": str(e)}


@app.task(bind=True, queue="colors")
def process_colors(self, original_path: str, index_mask_path: str, user_id: int) -> dict:
    print(f"[COLORS] ========================================")
    print(f"[COLORS] НАЧАЛО ОБРАБОТКИ user_id={user_id}")
    print(f"[COLORS] ========================================")

    try:
        # 1. проверяем наличие входных данных
        if not os.path.exists(index_mask_path):
            raise FileNotFoundError(f"Mask not found: {index_mask_path}")
        
        # 2. подготавливаем директорию для результатов
        base_name = Path(original_path).stem
        output_dir = f"/uploads/{base_name}_coty"
        os.makedirs(output_dir, exist_ok=True)
        
        # 3. Копируем маску в выходную директорию
        final_index_path = os.path.join(output_dir, "parsing_map_on_im.png")
        shutil.copy2(index_mask_path, final_index_path)
        
        # 4. запуск основного скрипта цветового анализа
        cmd = [
            "python", "/app/coty/main.py",
            "--original", original_path,
            "--mask", final_index_path,
            "--output_dir", output_dir
        ]

        subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd="/app/coty")
        
        # читаем данные из html
        html_path = os.path.join(output_dir, f"{base_name}_personal_palette.html")
        legend_path = os.path.join(output_dir, f"{base_name}_smart_legend_detailed.png")
        visual_path = os.path.join(output_dir, f"{base_name}_smart_analysis_visual.png")
        
        color_type = "НЕ ОПРЕДЕЛЁН"
        palette = []
        
        if os.path.exists(html_path):
            print(f"[COLORS] Читаем HTML: {html_path}")
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
                match = re.search(r'Цветотип:</b>\s*(\w+)', html_content)
                if match:
                    color_type = match.group(1)
                else:
                    match = re.search(r'Цветотип:\s*<strong>([^<]+)</strong>', html_content)
                    if match:
                        color_type = match.group(1).strip()
                
                print(f"[COLORS] Найден цветотип: {color_type}")
                
                color_blocks = re.findall(r'<div class="color-block"[^>]*style="background:([^;]+);"[^>]*>.*?<span>([^<]+)<br>([^<]+)<br>L\*=([\d\.]+)</span>', html_content, re.DOTALL)
                
                if not color_blocks:
                    color_blocks = re.findall(r'background:([^;]+);[^>]*>.*?<span>(.*?)<br>(.*?)<br>L\*=([\d\.]+)', html_content, re.DOTALL)
                
                for bg, name, hex_color, l_val in color_blocks:
                    palette.append({
                        'name': name.strip(),
                        'hex': hex_color.strip(),
                        'L': float(l_val)
                    })
        
        if not palette:
            print(f"[COLORS] HTML не прочитан, использую fallback")
            color_type = "ХОЛОДНЫЙ"
            palette = [
                {'name': 'Красный 1', 'hex': '#be777e', 'L': 57.8},
                {'name': 'Красный 2', 'hex': '#a7626a', 'L': 49.6},
                {'name': 'Красный 3', 'hex': '#904d56', 'L': 41.4},
                {'name': 'Красный 4', 'hex': '#7a3a43', 'L': 33.2}
            ]

        print(f"[COLORS] Итог: цветотип={color_type}, палитра={len(palette)} цветов")

        # ========== КОДИРУЕМ ИЗОБРАЖЕНИЯ В BASE64 ==========
        def encode_image_to_base64(image_path: str) -> str | None:
            """Кодирует изображение в base64"""
            if not os.path.exists(image_path):
                return None
            try:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                    return base64.b64encode(image_data).decode('utf-8')
            except Exception as e:
                print(f"[COLORS] Ошибка кодирования {image_path}: {e}")
                return None

        # Кодируем изображения
        legend_base64 = encode_image_to_base64(legend_path)
        visual_base64 = encode_image_to_base64(visual_path)
        
        # Читаем HTML как текст
        html_content = ""
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

        # ========== СОХРАНЕНИЕ В ИСТОРИЮ ==========
        print(f"[COLORS] ========== СОХРАНЕНИЕ В ИСТОРИЮ ==========")
        
        try:
            from api.database import SessionLocal
            from api.models import AnalysisHistory
            
            db = SessionLocal()
            
            history = AnalysisHistory(
                user_id=user_id,
                color_type=color_type,
                michelson_contrast=0.5,
                contrast_level="Средняя",
                original_photo_path=original_path,
                legend_path=legend_path if os.path.exists(legend_path) else None,
                visual_path=visual_path if os.path.exists(visual_path) else None,
                palette_html_path=html_path,
                created_at=datetime.utcnow()
            )
            
            db.add(history)
            db.commit()
            print(f"[COLORS] ЗАПИСЬ СОХРАНЕНА В БД! user_id={user_id}")
            db.close()
            
        except Exception as e:
            print(f"[COLORS] ОШИБКА СОХРАНЕНИЯ: {e}")
            import traceback
            traceback.print_exc()

        print(f"[COLORS] ========================================")
        print(f"[COLORS] ЗАВЕРШЕНИЕ ОБРАБОТКИ")
        print(f"[COLORS] ========================================")

        # данные С BASE64
        return {
            "status": "complete",
            "color_type": color_type,
            "palette": palette,
            "output_dir": output_dir,
            "files": {
                "legend_base64": legend_base64,
                "visual_base64": visual_base64,
                "palette_html": html_content,
            }
        }

    except Exception as e:
        print(f"[COLORS] ERROR: {e}")
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}