# api/tasks.py
from api.celery_app import app
import subprocess
import os
from pathlib import Path
import traceback
import time
import shutil

@app.task(bind=True, queue="segment")
def process_segment(self, photo_path: str) -> dict:
    print(f"[SEGMENT] Start: {photo_path}")

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

        print(f"[SEGMENT]  Index mask: {index_mask_path} ({os.path.getsize(index_mask_path)} bytes)")

        color_task = process_colors.delay(photo_path, index_mask_path)

        return {
            "status": "segment_done",
            "mask_path": index_mask_path,
            "original_path": photo_path,
            "color_task_id": str(color_task.id)
        }

    except Exception as e:
        print(f"[SEGMENT] ❌ ERROR: {str(e)}")
        print(traceback.format_exc())
        return {"status": "segment_failed", "error": str(e)}


@app.task(bind=True, queue="colors")
def process_colors(self, original_path: str, index_mask_path: str) -> dict:
    print(f"[COTY] === START ===")
    print(f"[COTY] Original   : {original_path}")
    print(f"[COTY] Index mask : {index_mask_path}")

    try:
        if not os.path.exists(index_mask_path):
            raise FileNotFoundError(f"Index mask not found: {index_mask_path}")

        base_name = Path(original_path).stem
        output_dir = f"/uploads/{base_name}_coty"
        os.makedirs(output_dir, exist_ok=True)

        final_index_path = os.path.join(output_dir, "parsing_map_on_im.png")
        shutil.copy2(index_mask_path, final_index_path)
        print(f"[COTY]  Index mask copied to {final_index_path}")

        cmd = [
            "python", "/app/coty/main.py",
            "--original", original_path,
            "--mask", final_index_path,
            "--output_dir", output_dir
        ]

        print(f"[COTY] Running main.py with timeout 300s...")
        start_time = time.time()

        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300, 
            cwd="/app/coty"
        )

        duration = time.time() - start_time

        print(f"[COTY] main.py return code: {result.returncode}")
        print(f"[COTY] Duration: {duration:.1f}s")

        if result.returncode != 0:
            print(f"[COTY] STDERR:\n{result.stderr}")
            raise RuntimeError(f"main.py failed: {result.stderr}")

        print(f"[COTY] STDOUT:\n{result.stdout}")
        print(f"[COTY]  SUCCESS! Results in: {output_dir}")

        return {
            "status": "complete",
            "output_dir": output_dir,
            "files": {
                "visual": f"{output_dir}/{base_name}_smart_analysis_visual.png",
                "legend": f"{output_dir}/{base_name}_smart_legend.png",
                "palette_html": f"{output_dir}/{base_name}_personal_palette.html",
                "index_mask": final_index_path
            }
        }

    except Exception as e:
        print(f"[COTY] ❌ ERROR: {str(e)}")
        print(traceback.format_exc())
        return {"status": "failed", "error": str(e)}