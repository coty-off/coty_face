# api/auth.py 
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
import re
import html                              

from dotenv import load_dotenv          
load_dotenv()                           

from .models import AdminUser, AdminToken
from .database import get_db

from pydantic import BaseModel, EmailStr, Field, field_validator
# SlowAPI для rate limiting 
from slowapi import Limiter 
from slowapi.util import get_remote_address 
from .models import AnalysisHistory

limiter = Limiter(key_func=get_remote_address)  

SECRET_KEY = os.getenv("SECRET_KEY")

# Защита от ошибки, если SECRET_KEY не задан
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не найден в .env файле! Проверьте переменные окружения.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(description="Вставьте токен")
router = APIRouter(prefix="/auth", tags=["auth"])

# ========== ФУНКЦИИ БЕЗОПАСНОСТИ ==========

def sanitize_string(input_str: str) -> str:
    """Удаляет потенциально опасные символы (SQL-инъекции, XSS)"""
    if not input_str:
        return input_str
    # Удаляем опасные символы
    dangerous_chars = r'[\'\"\\;*%<>]'
    cleaned = re.sub(dangerous_chars, '', input_str)
    # Экранируем HTML
    return html.escape(cleaned)


def escape_html(text: str) -> str:
    """Экранирует HTML-символы для защиты от XSS"""
    return html.escape(text)


# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(db: Session, email: str, password: str):
    user = db.query(AdminUser).filter(
        AdminUser.email == email, 
        AdminUser.is_active == True
    ).first()
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials.strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Token is empty")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Пробуем разные возможные варианты ключей из токена
        account_id = (
            payload.get("sub") or 
            payload.get("id") or 
            payload.get("user_id") or 
            str(payload.get("user", {}).get("id", ""))
        )
        email = payload.get("email") or payload.get("user", {}).get("email")

        if not account_id:
            print("❌ Токен не содержит user id. Payload:", payload)
            raise HTTPException(status_code=401, detail="Invalid token: no user identifier")

        print(f"🔑 Токен decoded. account_id = {account_id}, email = {email}")

    except JWTError as e:
        print("❌ JWT Decode Error:", str(e))
        raise HTTPException(status_code=401, detail="Invalid token")

    # Ищем пользователя
    user = db.query(AdminUser).filter(AdminUser.account_id == account_id).first()

    # Создаём пользователя автоматически, если его нет
    if user is None:
        user = AdminUser(
            account_id=account_id,
            email=email or f"{account_id}@noemail.local",
            full_name=email or "User",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"✅ Создан новый пользователь в coty-face: {account_id}")

    return user


get_current_active_admin = get_current_user

"""
@router.post("/login")
@limiter.limit("5/minute")      # не более 5 попыток входа в минуту
async def login(
    request: Request,            #  для rate limiting
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    db.query(AdminToken).filter(AdminToken.user_id == user.id).delete()
    db.commit()
    access_token = create_access_token(data={"id": user.id, "email": user.email})
    token_obj = AdminToken(
        user_id=user.id,
        token=access_token,
        expires_at=datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        ip_address="unknown",
        user_agent="swagger"
    )
    db.add(token_obj)
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}


# ========== РЕГИСТРАЦИЯ ==========

class UserRegistration(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    
    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 4:
            raise ValueError('Пароль должен содержать минимум 4 символа')
        return v
    
    @field_validator('full_name')
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Zа-яА-Я\s-]+$', v):
            raise ValueError('Имя может содержать только буквы, пробелы и дефисы')
        return v


@router.post("/register")
async def register(
    user_data: UserRegistration,
    db: Session = Depends(get_db)
):
    existing_user = db.query(AdminUser).filter(
        AdminUser.email == user_data.email
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже зарегистрирован"
        )
    hashed_password = get_password_hash(user_data.password)
    new_user = AdminUser(
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=hashed_password,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = create_access_token(data={"id": new_user.id, "email": new_user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name
        }
    }
    """

# ========== ИСТОРИЯ АНАЛИЗОВ ==========



@router.get("/history")
async def get_analysis_history(
    current_user: AdminUser = Depends(get_current_active_admin),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """Получить историю анализов текущего пользователя"""
    analyses = db.query(AnalysisHistory).filter(
        AnalysisHistory.user_id == current_user.id
    ).order_by(AnalysisHistory.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "analyses": [
            {
                "id": a.id,
                "color_type": a.color_type,
                "contrast_level": a.contrast_level,
                "original_photo_path": a.original_photo_path,
                "legend_path": a.legend_path,
                "visual_path": a.visual_path,
                "palette_html_path": a.palette_html_path,
                "created_at": a.created_at.isoformat()
            } for a in analyses
        ],
        "total": len(analyses)
    }


@router.get("/history/{analysis_id}")
async def get_analysis_detail(
    analysis_id: int,
    current_user: AdminUser = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Получить детали конкретного анализа"""
    analysis = db.query(AnalysisHistory).filter(
        AnalysisHistory.id == analysis_id,
        AnalysisHistory.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    
    return {
        "id": analysis.id,
        "color_type": analysis.color_type,
        "michelson_contrast": analysis.michelson_contrast,
        "contrast_level": analysis.contrast_level,
        "original_photo_path": analysis.original_photo_path,
        "legend_path": analysis.legend_path,
        "visual_path": analysis.visual_path,
        "palette_html_path": analysis.palette_html_path,
        "created_at": analysis.created_at.isoformat()
    }