# create_admin.py
from api.database import SessionLocal
from api.models import AdminUser
from api.auth import get_password_hash

def create_admin():
    db = SessionLocal()

    # Удаляем старого администратора, если он есть
    db.query(AdminUser).filter(AdminUser.email == 'admin@example.com').delete()
    db.commit()

    # Создаём нового с правильным хешем
    hashed_password = get_password_hash('1234')

    admin = AdminUser(
        email='admin@example.com',
        full_name='Administrator',
        password_hash=hashed_password,
        is_active=True
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    print("=" * 70)
    print("✅ АДМИНИСТРАТОР УСПЕШНО СОЗДАН И ОБНОВЛЁН")
    print("=" * 70)
    print(f"ID           : {admin.id}")
    print(f"Email        : {admin.email}")
    print(f"Full Name    : {admin.full_name}")
    print(f"Password     : 1234")
    print(f"Password Hash: {admin.password_hash[:60]}...")  # показываем начало хеша
    print(f"Is Active    : {admin.is_active}")
    print(f"Created At   : {admin.created_at}")
    print("=" * 70)
    print("\nТеперь можно логиниться в Swagger:")
    print("→ Username : admin@example.com")
    print("→ Password : 1234")
    print("\nПосле успешного логина нажми кнопку Authorize и вставь токен.")

    db.close()

if __name__ == "__main__":
    create_admin()