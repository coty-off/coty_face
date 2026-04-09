import os
import shutil
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from api.celery_app import app as celery_app
from api.tasks import process_diplom


app = FastAPI(title="Diplom ML Pipeline")


@app.post("/process/")
async def start_processing(
    photo: UploadFile = File(..., description="Фото для анализа"),
) -> Dict[str, Any]:
    print("=== start_processing invoked ===")
    print(f"photo.filename: {photo.filename}")
    print(f"photo.content_type: {photo.content_type}")

    upload_dir = "/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    photo_path = os.path.join(upload_dir, photo.filename)

    print(f"Saving to: {photo_path}")

    # Сохраняем файл на диск
    with open(photo_path, "wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    print("File saved.")

    task = process_diplom.delay(photo_path)

    return {
        "task_id": task.id,
        "status": "processing",
        "check": f"http://localhost:8000/status/{task.id}",
    }


@app.get("/status/{task_id}")
async def get_status(task_id: str) -> Dict[str, Any]:
    task = process_diplom.AsyncResult(task_id)

    result: Optional[Dict[str, Any]] = None
    status: str = task.state

    if task.ready() and not task.failed():
        result = task.result
    elif task.failed():
        result = {
            "error": "task_failed",
            "exc_type": type(task.info).__name__ if hasattr(task.info, "__class__") else None,
            "exc": str(task.info) if task.info is not None else None,
        }
    elif task.state in ("PENDING", "STARTED", "RETRY"):
        result = {
            "error": "task_not_ready",
            "current_state": task.state,
        }

    return {
        "task_id": task_id,
        "status": status,
        "result": result,
    }