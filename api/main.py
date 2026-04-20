# api/main.py
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api.tasks import process_segment
from api.celery_app import app as celery_app
from celery.result import AsyncResult

# Импорт авторизации
from api.auth import get_current_active_admin, router as auth_router
from api.database import create_tables

app = FastAPI(title="Diplom Color Analysis", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтируем папки
app.mount("/uploads", StaticFiles(directory="/uploads"), name="uploads")
app.mount("/photos", StaticFiles(directory="/photos"), name="photos")

# Подключаем роутер авторизации
app.include_router(auth_router)


# === КАСТОМНАЯ OpenAPI СХЕМА — решает проблему с формой Authorize ===
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Diplom Color Analysis API",
        routes=app.routes,
    )
    
    # Добавляем правильную Bearer-схему
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Вставьте токен в формате: Bearer <your_jwt_token>"
        }
    }
    
    # Применяем схему ко всем защищённым эндпоинтам
    for path in openapi_schema["paths"].values():
        for method in path.values():
            if isinstance(method, dict) and "security" in method:
                method["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# Создаём таблицы при старте
@app.on_event("startup")
async def startup_event():
    create_tables()
    print("✅ База данных инициализирована")


@app.post("/analyze")
async def analyze_photo(
    current_user = Depends(get_current_active_admin),
    file: UploadFile = File(...)
):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    filename = f"{uuid.uuid4()}_{file.filename}"
    orig_path = f"/uploads/{filename}"

    with open(orig_path, "wb") as f:
        content = await file.read()
        f.write(content)

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
            "files": res.get("files") if isinstance(res, dict) else None
        }
    return {
        "task_id": task_id,
        "status": result.status,
        "info": "Task is still processing"
    }


@app.get("/")
async def root():
    return {
        "message": "Diplom Color Analysis API is running",
        "docs": "/docs"
    }