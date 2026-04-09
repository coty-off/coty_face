from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uuid
import os
from pathlib import Path
from celery.result import AsyncResult
from api.celery_app import app as celery_app

app = FastAPI(title="Diplom Color Analysis")

# Монтируем обе папки
app.mount("/uploads", StaticFiles(directory="/uploads"), name="uploads")
app.mount("/photos", StaticFiles(directory="/photos"), name="photos")

@app.post("/analyze")
async def analyze_photo(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only images allowed")
    
    filename = f"{uuid.uuid4()}_{file.filename}"
    orig_path = f"/uploads/{filename}"
    
    with open(orig_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    from api.tasks import process_segment
    task = process_segment.delay(orig_path)
    
    return {
        "task_id": task.id,
        "status": "processing",
        "original_path": orig_path,
        "message": "Фото отправлено на сегментацию → цветовой анализ",
        "check_status": f"/status/{task.id}"
    }

@app.get("/status/{task_id}")
async def task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    if result.ready():
        res = result.result
        return {
            "task_id": task_id,
            "status": result.status,
            "result": res,
            "files": res.get("files") if isinstance(res, dict) else {}
        }
    return {"task_id": task_id, "status": result.status}

@app.get("/")
async def root():
    return {"message": "API работает. Swagger: /docs"}