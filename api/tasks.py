from typing import Dict, Any

from api.celery_app import app
import cv2
import numpy as np
from PIL import Image
import os


@app.task(bind=True, queue="segment")
def process_diplom(self, photo_path: str) -> Dict[str, Any]:
    print(f"[segment] process_diplom: photo_path={photo_path}")

    # 1. Проверяем, существует ли файл
    if not os.path.exists(photo_path):
        meta = {
            "error": "file_not_found",
            "exc": f"File does not exist: {photo_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    if not os.path.isfile(photo_path):
        meta = {
            "error": "not_a_file",
            "exc": f"Not a file: {photo_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    # 2. Пробуем прочитать через OpenCV
    try:
        image = cv2.imread(photo_path)
        if image is None:
            meta = {
                "error": "cv2_cannot_read",
                "exc": f"cv2.imread returned None for {photo_path}. Check file format or corruption.",
                "exc_type": "FileNotFoundError",
                "file_size": os.path.getsize(photo_path),
            }
            self.update_state(state="FAILURE", meta=meta)
            return meta

        # Тут можно добавить логи
        print(f"[segment] Image shape: {image.shape}, dtype: {image.dtype}")

        # 3. Ваша логика сегментации (заглушка)
        result = {
            "status": "success",
            "segment_status": "done",
            "body_bbox": [0, 0, 100, 100],
            "skin_pixels": 10000,
            "image_shape": list(image.shape),
            "image_dtype": str(image.dtype),
            "file_size": os.path.getsize(photo_path),
        }

        self.update_state(state="SUCCESS", meta=result)
        return result

    except Exception as exc:
        meta = {
            "error": "task_failed",
            "exc_type": type(exc).__name__,
            "exc": str(exc),
        }
        self.update_state(state="FAILURE", meta=meta)
        raise


@app.task(bind=True, queue="colors")
def process_colors(
    self,
    segment_path: str,
    original_path: str,
) -> Dict[str, Any]:
    print(f"[colors] process_colors: segment_path={segment_path}, original_path={original_path}")

    # 1. Проверяем файлы
    if not os.path.exists(segment_path):
        meta = {
            "error": "segment_file_not_found",
            "exc": f"Segment file does not exist: {segment_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    if not os.path.isfile(segment_path):
        meta = {
            "error": "segment_not_a_file",
            "exc": f"Segment path is not a file: {segment_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    if not os.path.exists(original_path):
        meta = {
            "error": "original_file_not_found",
            "exc": f"Original file does not exist: {original_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    if not os.path.isfile(original_path):
        meta = {
            "error": "original_not_a_file",
            "exc": f"Original path is not a file: {original_path}",
            "exc_type": "FileNotFoundError",
        }
        self.update_state(state="FAILURE", meta=meta)
        return meta

    try:
        # 2. Сегментированное (mask)
        mask = cv2.imread(segment_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            meta = {
                "error": "cv2_cannot_read_segment",
                "exc": f"cv2.imread returned None for segment {segment_path}. Check file format.",
                "exc_type": "FileNotFoundError",
                "file_size": os.path.getsize(segment_path),
            }
            self.update_state(state="FAILURE", meta=meta)
            return meta

        print(f"[colors] mask shape: {mask.shape}, dtype: {mask.dtype}")

        # 3. Оригинальное изображение
        image = cv2.imread(original_path)
        if image is None:
            meta = {
                "error": "cv2_cannot_read_original",
                "exc": f"cv2.imread returned None for original {original_path}. Check file format.",
                "exc_type": "FileNotFoundError",
                "file_size": os.path.getsize(original_path),
            }
            self.update_state(state="FAILURE", meta=meta)
            return meta

        print(f"[colors] original image shape: {image.shape}, dtype: {image.dtype}")

        # 4. Ваша логика «цветового ядра» (ваша Coty-заглушка)
        result = {
            "status": "success",
            "skin_tone": "warm",
            "color_distribution": {"r": 0.4, "g": 0.3, "b": 0.3},
            "tone_temperature": "warm",
            "contrast": "high",
            "mask_shape": list(mask.shape),
            "image_shape": list(image.shape),
            "file_size_segment": os.path.getsize(segment_path),
            "file_size_original": os.path.getsize(original_path),
        }

        self.update_state(state="SUCCESS", meta=result)
        return result

    except Exception as exc:
        meta = {
            "error": "task_failed",
            "exc_type": type(exc).__name__,
            "exc": str(exc),
        }
        self.update_state(state="FAILURE", meta=meta)
        raise