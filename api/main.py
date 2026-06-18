# api/main.py
from api.models import AdminUser, Measurement
import uuid
import httpx
from fastapi import HTTPException
import os
import magic
from dotenv import load_dotenv
from typing import Optional, List
from pydantic import BaseModel

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy.orm import Session

from api.tasks import process_segment
from api.celery_app import app as celery_app
from celery.result import AsyncResult

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Импорт авторизации
from api.auth import get_current_user, router as auth_router
from api.auth_yandex import router as yandex_router
from api.database import create_tables, get_db


# ========== PYDANTIC МОДЕЛИ ДЛЯ ОТВЕТА ==========

class PaletteColor(BaseModel):
    """Один цвет из палитры"""
    name: str
    hex: str
    L: float

class FilesResult(BaseModel):
    """Файлы с результатами"""
    legend_base64: Optional[str] = None
    visual_base64: Optional[str] = None
    palette_html: Optional[str] = None

class AnalysisResult(BaseModel):
    """Результат анализа"""
    status: str
    color_type: str
    palette: List[PaletteColor] = []
    files: Optional[FilesResult] = None
    output_dir: Optional[str] = None

class StatusResponse(BaseModel):
    """Ответ на запрос статуса"""
    task_id: str
    status: str
    result: Optional[AnalysisResult] = None
    files: Optional[FilesResult] = None
    info: Optional[str] = None
    error: Optional[str] = None


# ========== СОЗДАНИЕ ПРИЛОЖЕНИЯ ==========

app = FastAPI(title="Diplom Color Analysis", version="0.1.0")

# Настройка rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ========== ФУНКЦИЯ ПРОВЕРКИ ФАЙЛОВ ==========

async def validate_image_file(file: UploadFile) -> tuple[bool, str]:
    """Проверка файла на безопасность"""
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    
    if size > 10 * 1024 * 1024:
        return False, "Файл слишком большой (максимум 10 МБ)"
    
    contents = await file.read(1024)
    await file.seek(0)
    
    mime = magic.from_buffer(contents, mime=True)
    allowed_mimes = ['image/jpeg', 'image/png', 'image/webp']
    if mime not in allowed_mimes:
        return False, f"Недопустимый тип файла: {mime}"
    
    signatures = {
        b'\xff\xd8\xff': 'jpeg',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'RIFF': 'webp'
    }
    
    is_valid = any(contents.startswith(sig) for sig in signatures)
    if not is_valid:
        return False, "Файл повреждён или имеет неверный формат"
    
    return True, "OK"


# ========== CORS ==========
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

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(yandex_router)


# ========== OPENAPI ==========
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description="Diplom Color Analysis API",
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Вставьте токен в формате: Bearer <your_jwt_token>"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# ========== СТАРТАП ==========
@app.on_event("startup")
async def startup_event():
    create_tables()
    print(" База данных инициализирована")


# ========== АНАЛИЗ ЦВЕТОТИПА ==========
# /analyze → /color/analyze

@app.post("/color/analyze", response_model=dict)
@limiter.limit("10/minute")
async def analyze_color(
    request: Request,
    current_user = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """Отправить фото на анализ цветотипа"""
    is_valid, error_msg = await validate_image_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    filename = f"{uuid.uuid4()}_{file.filename}"
    orig_path = f"/uploads/{filename}"

    with open(orig_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    task = process_segment.delay(orig_path, current_user.id)

    return {
        "task_id": task.id,
        "status": "processing",
        "original_path": orig_path,
        "message": "Фото отправлено на сегментацию → цветовой анализ",
        "check_status": f"/status/{task.id}"
    }


# ========== СТАТУС ЗАДАЧИ ЦВЕТОТИПА ==========

@app.get("/status/{task_id}", response_model=StatusResponse)
async def task_status(task_id: str):
    """
    Получить статус задачи и результат анализа цветотипа.
    """
    result = AsyncResult(task_id, app=celery_app)
    
    # Если задача ещё не готова
    if not result.ready():
        return StatusResponse(
            task_id=task_id,
            status=result.status,
            info="Task is still processing"
        )
    
    # Если задача упала
    if result.status == "FAILURE":
        return StatusResponse(
            task_id=task_id,
            status=result.status,
            error=str(result.result) if result.result else "Unknown error"
        )
    
    res = result.result
    
    # 🔥 ЕСЛИ ЭТО segment_done — берём color_task_id и ждём его
    if res.get("status") == "segment_done":
        color_task_id = res.get("color_task_id")
        if color_task_id:
            color_result = AsyncResult(color_task_id, app=celery_app)
            if color_result.ready():
                res = color_result.result  # ← подменяем на результат process_colors
            else:
                return StatusResponse(
                    task_id=task_id,
                    status="PROCESSING",
                    info="Color analysis in progress"
                )
    
    # ✅ ТЕПЕРЬ res — это результат process_colors (с палитрой и Base64)
    try:
        palette_data = res.get("palette", [])
        palette = [PaletteColor(**p) for p in palette_data] if palette_data else []
        
        files_data = res.get("files", {})
        files = FilesResult(
            legend_base64=files_data.get("legend_base64"),
            visual_base64=files_data.get("visual_base64"),
            palette_html=files_data.get("palette_html")
        ) if files_data else None
        
        analysis_result = AnalysisResult(
            status=res.get("status", "complete"),
            color_type=res.get("color_type", "НЕ ОПРЕДЕЛЁН"),
            palette=palette,
            files=files,
            output_dir=res.get("output_dir")
        )
        
        return StatusResponse(
            task_id=task_id,
            status=result.status,
            result=analysis_result,
            files=files
        )
        
    except Exception as e:
        return StatusResponse(
            task_id=task_id,
            status=result.status,
            error=f"Error parsing result: {str(e)}"
        )


# ========== ВНЕШНИЙ API (coty_body) - ПРОКСИ ==========

EXTERNAL_BODY_API_URL = os.getenv("EXTERNAL_BODY_API_URL")
# → https://beggarly-emerging-sharksucker.cloudpub.ru/api


# 1. Анализ фигуры  /analyze
@app.post("/analyze")
@limiter.limit("5/minute")
async def analyze_body(
    request: Request,
    current_user = Depends(get_current_user),
    front_photo: UploadFile = File(...),
    profile_photo: UploadFile = File(...),
    height: float = Form(...),
    db: Session = Depends(get_db)
):
    """Прокси на внешний API: POST /analyze (анализ фигуры)"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    for file in [front_photo, profile_photo]:
        is_valid, error = await validate_image_file(file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        await file.seek(0)
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            front_data = await front_photo.read()
            profile_data = await profile_photo.read()
            
            files = {
                "front_photo": (front_photo.filename, front_data, front_photo.content_type),
                "profile_photo": (profile_photo.filename, profile_data, profile_photo.content_type)
            }
            data = {"height": height}
            
            #  /analyze
            response = await client.post(
                f"{EXTERNAL_BODY_API_URL}/analyze",
                files=files,
                data=data
            )
            response.raise_for_status()
            result = response.json()
            
            measurement = Measurement(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                body_type=result.get("body_type"),
                chest_cm=result.get("chest_cm"),
                waist_cm=result.get("waist_cm"),
                hips_cm=result.get("hips_cm"),
                height_cm=height,
                source="photo",
                notes=result.get("notes", "")
            )
            db.add(measurement)
            db.commit()
            
            return {
                "measurement_id": measurement.id,
                "body_type": result.get("body_type"),
                "chest_cm": result.get("chest_cm"),
                "waist_cm": result.get("waist_cm"),
                "hips_cm": result.get("hips_cm"),
                "height_cm": height,
                "recommendations": result.get("recommendations", []),
                "message": "Анализ фигуры выполнен успешно!"
            }
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 2. Получить статус задачи фигуры — ПРОКСИ
@app.get("/analyze/{task_id}")
async def get_analyze_task_status(
    task_id: str,
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: GET /analyze/{task_id}"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EXTERNAL_BODY_API_URL}/analyze/{task_id}"
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 3. История измерений — ПРОКСИ
@app.get("/measurements")
async def list_measurements(
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: GET /me/measurements"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EXTERNAL_BODY_API_URL}/me/measurements"
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 4. Создать измерение — ПРОКСИ
@app.post("/measurements")
async def create_measurement(
    data: dict,
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: POST /me/measurements"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EXTERNAL_BODY_API_URL}/me/measurements",
                json=data
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 5. Получить детали измерения — ПРОКСИ
@app.get("/measurements/{measurement_id}")
async def get_measurement(
    measurement_id: str,
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: GET /me/measurements/{measurement_id}"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EXTERNAL_BODY_API_URL}/me/measurements/{measurement_id}"
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 6. Обновить измерение — ПРОКСИ
@app.put("/measurements/{measurement_id}")
async def update_measurement(
    measurement_id: str,
    data: dict,
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: PUT /me/measurements/{measurement_id}"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{EXTERNAL_BODY_API_URL}/me/measurements/{measurement_id}",
                json=data
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 7. Удалить измерение — ПРОКСИ
@app.delete("/measurements/{measurement_id}")
async def delete_measurement(
    measurement_id: str,
    current_user = Depends(get_current_user)
):
    """Прокси на внешний API: DELETE /me/measurements/{measurement_id}"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{EXTERNAL_BODY_API_URL}/me/measurements/{measurement_id}"
            )
            response.raise_for_status()
            return {"message": "Deleted successfully"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис анализа фигуры не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ошибка внешнего сервиса: {e.response.text[:200]}..."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


        # ========== ПРОКСИ ДЛЯ АВТОРИЗАЦИИ (coty_body) ==========

# 1. ПРОКСИ ДЛЯ РЕГИСТРАЦИИ
@app.post("/auth/register")
async def proxy_register(request: Request):
    """Прокси на внешний API: POST /auth/register"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        data = await request.json()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EXTERNAL_BODY_API_URL}/auth/register",
                json=data
            )
            response.raise_for_status()
            return response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис авторизации не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 2. ПРОКСИ ДЛЯ ЛОГИНА
@app.post("/auth/login")
async def proxy_login(request: Request):
    """Прокси на внешний API: POST /auth/login"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        form_data = await request.form()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EXTERNAL_BODY_API_URL}/auth/login",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис авторизации не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 3. ПРОКСИ ДЛЯ ЯНДЕКСА
@app.get("/auth/yandex/login")
async def proxy_yandex_login():
    """Прокси на внешний API: GET /auth/yandex/login"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EXTERNAL_BODY_API_URL}/auth/yandex/login"
            )
            response.raise_for_status()
            return response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис авторизации не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# 4. ПРОКСИ ДЛЯ CALLBACK ЯНДЕКСА
@app.get("/auth/yandex/callback")
async def proxy_yandex_callback(code: str):
    """Прокси на внешний API: GET /auth/yandex/callback"""
    if not EXTERNAL_BODY_API_URL:
        raise HTTPException(status_code=500, detail="EXTERNAL_BODY_API_URL не настроен")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EXTERNAL_BODY_API_URL}/auth/yandex/callback",
                params={"code": code}
            )
            response.raise_for_status()
            return response.json()
    
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Сервис авторизации не отвечает")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "Diplom Color Analysis API is running",
        "docs": "/docs"
    }