"""
auth/database.py
SQLite 数据库 - 用户模型与 CRUD 操作
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger("pet_translator.auth")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "auth", "users.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _utc_now() -> datetime:
    """Return naive UTC for the existing SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


class UserModel(Base):
    """用户数据库模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


def init_db():
    """初始化数据库，创建表"""
    Base.metadata.create_all(bind=engine)
    logger.info(f"✅ 认证数据库已初始化: {DB_PATH}")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


def create_user(username: str, email: str, password: str, display_name: str = "") -> Optional[dict]:
    """创建新用户"""
    db = SessionLocal()
    try:
        # 检查用户名是否已存在
        if db.query(UserModel).filter(UserModel.username == username).first():
            return None
        if db.query(UserModel).filter(UserModel.email == email).first():
            return None
        user = UserModel(
            username=username,
            email=email,
            hashed_password=_hash_password(password),
            display_name=display_name or username,
            created_at=_utc_now(),
            updated_at=_utc_now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建用户失败: {e}")
        return None
    finally:
        db.close()


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """验证用户登录"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(
            (UserModel.username == username) | (UserModel.email == username)
        ).first()
        if not user:
            return None
        if not _verify_password(password, user.hashed_password):
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"验证用户失败: {e}")
        return None
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """通过 ID 获取用户"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
        }
    finally:
        db.close()
