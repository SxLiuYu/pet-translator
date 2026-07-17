"""Test auth module"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from auth.database import init_db, create_user, authenticate_user, get_user_by_id
from auth.dependencies import create_access_token, decode_access_token


def test_create_and_authenticate_user(tmp_path):
    """测试用户创建和认证"""
    # 使用临时数据库
    import auth.database as db_module
    original_db = db_module.DB_PATH
    test_db = os.path.join(str(tmp_path), "test_users.db")
    db_module.DB_PATH = test_db
    db_module.SQLALCHEMY_DATABASE_URL = f"sqlite:///{test_db}"
    db_module.engine = db_module.create_engine(db_module.SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    db_module.SessionLocal = db_module.sessionmaker(autocommit=False, autoflush=False, bind=db_module.engine)
    db_module.Base.metadata.create_all(bind=db_module.engine)

    try:
        # 创建用户
        user = db_module.create_user("testuser", "test@example.com", "password123", "Test User")
        assert user is not None
        assert user["username"] == "testuser"
        assert user["email"] == "test@example.com"
        assert user["display_name"] == "Test User"

        # 重复创建应失败
        assert db_module.create_user("testuser", "other@example.com", "pass456") is None

        # 认证成功
        auth = db_module.authenticate_user("testuser", "password123")
        assert auth is not None
        assert auth["username"] == "testuser"

        # 认证失败（错误密码）
        assert db_module.authenticate_user("testuser", "wrongpass") is None

        # 通过邮箱认证
        auth = db_module.authenticate_user("test@example.com", "password123")
        assert auth is not None

        # 通过 ID 获取
        user_by_id = db_module.get_user_by_id(user["id"])
        assert user_by_id is not None
        assert user_by_id["username"] == "testuser"

        # 不存在的 ID
        assert db_module.get_user_by_id(999) is None
    finally:
        # 清理
        db_module.DB_PATH = original_db
        db_module.engine.dispose()
        import gc; gc.collect()
        import time; time.sleep(0.1)
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except PermissionError:
                pass  # Windows file lock


def test_jwt_token():
    """测试 JWT 令牌创建和解码"""
    token = create_access_token({"sub": "1", "username": "test"})
    assert token is not None
    assert len(token) > 20

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["username"] == "test"
    assert "exp" in payload

    # 无效令牌
    assert decode_access_token("invalid_token") is None
    assert decode_access_token("") is None
