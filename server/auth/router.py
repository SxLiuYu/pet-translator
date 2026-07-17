"""auth/router.py - 认证相关 API 路由"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from auth.database import create_user, authenticate_user, init_db
from auth.dependencies import create_access_token, get_current_user
from auth.schemas import UserRegister, UserLogin, UserResponse, TokenResponse

logger = logging.getLogger("pet_translator.auth")

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse)
async def register(req: UserRegister):
    """用户注册"""
    user = create_user(
        username=req.username,
        email=req.email,
        password=req.password,
        display_name=req.display_name,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名或邮箱已被注册",
        )
    token = create_access_token({"sub": str(user["id"]), "username": user["username"]})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLogin):
    """用户登录"""
    user = authenticate_user(username=req.username, password=req.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token({"sub": str(user["id"]), "username": user["username"]})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(**user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse(**current_user)
