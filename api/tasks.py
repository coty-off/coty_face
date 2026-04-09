# api/tasks.py
from api.celery_app import app
import subprocess
import os
from pathlib import Path
import traceback

@app.task(bind=True, queue="segment")
def process_segment(self, photo_path: str) -> dict:
    """1-й воркер: face-parsing (сегментация лица)"""
    print(f"[SEGMENT] Start processing: {photo_path}")

    try:
        photo_full = photo_path                    # уже приходит как /uploads/xxx.jpg
        base_name = Path(photo_path).stem
        output_dir = f"/photos/{base_name}_segment"

        os.makedirs(output_dir, exist_ok=True)

        print(f"[SEGMENT] Input: {photo_full}")
        print(f"[SEGMENT] Output dir: {output_dir}")

        cmd = [
            "python", "/app/project/face_parsing/test.py",
            "--input", photo_full,
            "--output_dir", output_dir
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=150,
            cwd="/app/project/face_parsing"
        )

        if result.returncode != 0:
            print(f"[SEGMENT] ❌ test.py failed with code {result.returncode}")
            print(f"[SEGMENT] stderr:\n{result.stderr}")
            raise RuntimeError(f"Face parsing failed: {result.stderr}")

        print(f"[SEGMENT] ✅ test.py finished successfully")
        print(f"[SEGMENT] stdout:\n{result.stdout}")

        # Пути к результатам сегментации
        vis_path = f"{output_dir}/parsing_map_on_im.jpg"
        mask_path = f"{output_dir}/parsing_map.png"

        # Запускаем второй воркер
        color_task = process_colors.delay(mask_path, photo_path)

        return {
            "status": "segment_done",
            "vis_path": vis_path,
            "mask_path": mask_path,
            "original_path": photo_path,
            "color_task_id": color_task.id,
            "output_dir": output_dir
        }

    except Exception as e:
        print(f"[SEGMENT] ❌ Exception: {str(e)}")
        print(traceback.format_exc())
        return {"status": "segment_failed", "error": str(e)}


@app.task(bind=True, queue="colors")
def process_colors(self, mask_path: str, original_path: str) -> dict:
    """2-й воркер: цветовой анализ + палитра"""
    print(f"[COTY] Start: original={original_path}, mask={mask_path}")

    try:
        base_name = Path(original_path).stem
        output_dir = f"/uploads/{base_name}_coty"
        os.makedirs(output_dir, exist_ok=True)

        print(f"[COTY] Output directory: {output_dir}")

        cmd = [
            "python", "/app/coty/main.py",
            "--original", original_path,
            "--mask", mask_path,
            "--output_dir", output_dir
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=200,
            cwd="/app/coty"
        )

        if result.returncode != 0:
            print(f"[COTY] ❌ main.py failed with code {result.returncode}")
            print(f"[COTY] stderr:\n{result.stderr}")
            raise RuntimeError(f"Color analysis failed: {result.stderr}")

        print(f"[COTY] ✅ main.py finished successfully")
        print(f"[COTY] stdout:\n{result.stdout}")

        return {
            "status": "complete",
            "output_dir": output_dir,
            "files": {
                "smart_visual": f"{output_dir}/{base_name}_smart_analysis_visual.png",
                "legend": f"{output_dir}/{base_name}_smart_legend.png",
                "palette_html": f"{output_dir}/{base_name}_personal_palette.html"
            },
            "original": original_path,
            "mask": mask_path
        }

    except Exception as e:
        print(f"[COTY] ❌ Exception: {str(e)}")
        print(traceback.format_exc())
        return {"status": "failed", "error": str(e)}