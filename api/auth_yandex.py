# api/auth_yandex.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import httpx
import os
import json

from .database import get_db
from .models import AdminUser
from .auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID")
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET")
YANDEX_REDIRECT_URI = os.getenv("YANDEX_REDIRECT_URI", "https://cotybynutta.cloudpub.ru/auth/yandex/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cotybynutta.cloudpub.ru")


@router.get("/yandex/login")
async def yandex_login():
    if not YANDEX_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Yandex OAuth not configured")
    
    auth_url = (
        f"https://oauth.yandex.ru/authorize?"
        f"response_type=code&"
        f"client_id={YANDEX_CLIENT_ID}&"
        f"redirect_uri={YANDEX_REDIRECT_URI}&"
        f"scope=login:info login:email"
    )
    return {"auth_url": auth_url}


@router.get("/yandex/callback")
async def yandex_callback(code: str, db: Session = Depends(get_db)):
    print(f"[YANDEX] ====== START CALLBACK ======")
    print(f"[YANDEX] Code: {code[:30]}...")

    if not code:
        return HTMLResponse(content="""
        <html><body><h1>Ошибка: нет кода</h1></body></html>
        """, status_code=400)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Получаем токен от Яндекса
            token_response = await client.post(
                "https://oauth.yandex.ru/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": YANDEX_CLIENT_ID,
                    "client_secret": YANDEX_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            print(f"[YANDEX] Token status: {token_response.status_code}")

            if token_response.status_code != 200:
                error_text = token_response.text
                print(f"[YANDEX] Token error: {error_text}")
                return HTMLResponse(content=f"""
                <html><body>
                    <h1>Ошибка авторизации</h1>
                    <p>{error_text}</p>
                    <a href="/login">Вернуться на вход</a>
                </body></html>
                """, status_code=400)

            token_data = token_response.json()
            yandex_token = token_data.get("access_token")

            if not yandex_token:
                return HTMLResponse(content="""
                <html><body>
                    <h1>Ошибка: нет токена</h1>
                    <a href="/login">Вернуться на вход</a>
                </body></html>
                """, status_code=400)

            # Получаем информацию о пользователе
            user_response = await client.get(
                "https://login.yandex.ru/info",
                headers={"Authorization": f"OAuth {yandex_token}"}
            )

            if user_response.status_code != 200:
                return HTMLResponse(content="""
                <html><body>
                    <h1>Ошибка получения данных пользователя</h1>
                    <a href="/login">Вернуться на вход</a>
                </body></html>
                """, status_code=400)

            user_info = user_response.json()
            print(f"[YANDEX] User info: {json.dumps(user_info, indent=2)}")

    except Exception as e:
        print(f"[YANDEX] EXCEPTION: {str(e)}")
        return HTMLResponse(content=f"""
        <html><body>
            <h1>Ошибка при входе через Яндекс</h1>
            <p>{str(e)}</p>
            <a href="/login">Вернуться на вход</a>
        </body></html>
        """, status_code=400)

    email = user_info.get("default_email")
    if not email:
        return HTMLResponse(content="""
        <html><body>
            <h1>Ошибка: нет email от Яндекса</h1>
            <a href="/login">Вернуться на вход</a>
        </body></html>
        """, status_code=400)

    # Находим или создаем пользователя
    user = db.query(AdminUser).filter(AdminUser.email == email).first()
    if not user:
        print(f"[YANDEX] Creating user: {email}")
        user = AdminUser(
            email=email,
            full_name=user_info.get("real_name") or user_info.get("login") or "Yandex User",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        print(f"[YANDEX] User found: {user.id}")

    # Создаем JWT токен
    access_token = create_access_token(data={"id": user.id, "email": user.email})
    print(f"[YANDEX] JWT created")

    # 🔥 ВОЗВРАЩАЕМ HTML СТРАНИЦУ, А НЕ JSON!
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Вход через Яндекс</title>
        <style>
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #faf7f5;
            }}
            .container {{
                text-align: center;
                padding: 50px;
                background: white;
                border-radius: 20px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                max-width: 400px;
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid #f3f3f3;
                border-top: 4px solid #9f6b5e;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            h2 {{
                color: #333;
                margin: 0 0 10px;
                font-weight: 500;
            }}
            p {{
                color: #666;
                margin: 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="spinner"></div>
            <h2>Вход выполнен успешно!</h2>
            <p>Перенаправление...</p>
        </div>
        <script>
            // Сохраняем токен
            localStorage.setItem('access_token', '{access_token}');
            console.log('✅ Токен сохранен');
            
            // Перенаправляем на главную
            setTimeout(function() {{
                window.location.href = '{FRONTEND_URL}';
            }}, 1000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, status_code=200)