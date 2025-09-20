# auth.py - исправленная версия для установки куки
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, Token, UserProfileUpdate
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.config import settings

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(
        (User.username == user.username) | (User.email == user.email)
    ).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    
    # Автоматическое разделение full_name на first_name и last_name
    first_name = None
    last_name = None
    if user.full_name:
        name_parts = user.full_name.strip().split()
        if len(name_parts) >= 1:
            first_name = name_parts[0]
        if len(name_parts) >= 2:
            last_name = name_parts[1]
    
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role,
        full_name=user.full_name,
        first_name=first_name,
        last_name=last_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
def login_user(user_credentials: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_credentials.username).first()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Возвращаем установку HttpOnly куки для продакшена (HTTPS)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=True,  # Требует HTTPS в production
        samesite="None",  # Для кросс-доменных запросов
        path="/"
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
def logout_user(response: Response):
    # Localhost настройки для удаления куки
    response.delete_cookie(
        key="access_token", 
        path="/",
        secure=True,
        samesite="None"
    )
    return {"message": "Successfully logged out"}

@router.put("/profile", response_model=UserResponse)
def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление профиля пользователя"""
    # Обновляем только переданные поля
    update_data = profile_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    # Обновляем full_name если изменились first_name или last_name
    if 'first_name' in update_data or 'last_name' in update_data:
        first_name = update_data.get('first_name', current_user.first_name)
        last_name = update_data.get('last_name', current_user.last_name)
        if first_name and last_name:
            current_user.full_name = f"{first_name} {last_name}"
        elif first_name:
            current_user.full_name = first_name
        elif last_name:
            current_user.full_name = last_name
    
    db.commit()
    db.refresh(current_user)
    return current_user