# api/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

from .models import AdminUser, AdminToken
from .database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-in-production-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

security = HTTPBearer(description="Вставьте токен")

router = APIRouter(prefix="/auth", tags=["auth"])


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
    db: Session = Depends(get_db)
):
    token = credentials.credentials.strip()

    # Убираем "Bearer " любое количество раз
    while token.startswith("Bearer "):
        token = token[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Token is empty")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(AdminUser).filter(
        AdminUser.id == user_id, 
        AdminUser.is_active == True
    ).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


get_current_active_admin = get_current_user


@router.post("/login")
async def login(
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