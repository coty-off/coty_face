# api/tasks.py
from api.celery_app import app
import subprocess
import os
from pathlib import Path
import traceback
import time

@app.task(bind=True, queue="segment")
def process_segment(self, photo_path: str) -> dict:
    """1-й воркер: сегментация лица"""
    print(f"[SEGMENT] Start: {photo_path}")

    try:
        base_name = Path(photo_path).stem
        output_dir = f"/photos/{base_name}_segment"
        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            "python", "/app/project/face_parsing/test.py",
            "--input", photo_path,
            "--output_dir", output_dir
        ]

        print(f"[SEGMENT] Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            cwd="/app/project/face_parsing"
        )

        if result.returncode != 0:
            print(f"[SEGMENT] ❌ test.py failed:\n{result.stderr}")
            raise RuntimeError(result.stderr)

        # === ИСПРАВЛЕНИЕ: используем реальные имена файлов ===
        vis_path = f"{output_dir}/parsing_map_on_im.jpg"
        mask_path = f"{output_dir}/parsing_map_on_im.png"   # ← вот это главное изменение

        if not os.path.exists(mask_path):
            # Дополнительная проверка на случай других имён
            print(f"[SEGMENT] Warning: Expected mask {mask_path} not found. Checking files...")
            files = os.listdir(output_dir)
            print(f"[SEGMENT] Files in output_dir: {files}")
            raise FileNotFoundError(f"Mask not created. Expected: {mask_path}")

        print(f"[SEGMENT] ✅ Mask created successfully: {mask_path} ({os.path.getsize(mask_path)} bytes)")
        print(f"[SEGMENT] Visualization: {vis_path}")

        # Запускаем второй воркер
        color_task = process_colors.delay(mask_path, photo_path)

        return {
            "status": "segment_done",
            "mask_path": mask_path,
            "vis_path": vis_path,
            "original_path": photo_path,
            "color_task_id": str(color_task.id)
        }

    except Exception as e:
        print(f"[SEGMENT] ❌ ERROR: {str(e)}")
        print(traceback.format_exc())
        return {"status": "segment_failed", "error": str(e)}


@app.task(bind=True, queue="colors")
def process_colors(self, mask_path: str, original_path: str) -> dict:
    """2-й воркер: цветовой анализ"""
    print(f"[COTY] === COLOR ANALYSIS STARTED ===")
    print(f"[COTY] Mask: {mask_path}")
    print(f"[COTY] Original: {original_path}")

    try:
        if not os.path.exists(mask_path):
            raise FileNotFoundError(f"Mask file not found: {mask_path}")

        print(f"[COTY] Mask size: {os.path.getsize(mask_path)} bytes")

        base_name = Path(original_path).stem
        output_dir = f"/uploads/{base_name}_coty"
        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            "python", "/app/coty/main.py",
            "--original", original_path,
            "--mask", mask_path,
            "--output_dir", output_dir
        ]

        print(f"[COTY] Running: {' '.join(cmd)}")
        start_time = time.time()

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd="/app/coty")

        duration = time.time() - start_time

        if result.returncode != 0:
            print(f"[COTY] ❌ Failed with code {result.returncode}")
            print(f"[COTY] STDERR:\n{result.stderr}")
            raise RuntimeError(result.stderr)

        print(f"[COTY] ✅ Successfully finished in {duration:.1f} seconds")
        print(f"[COTY] Results saved to: {output_dir}")

        return {
            "status": "complete",
            "output_dir": output_dir,
            "files": {
                "visual": f"{output_dir}/{base_name}_smart_analysis_visual.png",
                "legend": f"{output_dir}/{base_name}_smart_legend.png",
                "palette_html": f"{output_dir}/{base_name}_personal_palette.html"
            }
        }

    except Exception as e:
        print(f"[COTY] ❌ ERROR: {str(e)}")
        print(traceback.format_exc())
        return {"status": "failed", "error": str(e)}