"""
server/storage/database.py
SQLite 数据库连接与会话管理
为 Pet/Event/DailyReport 提供持久化存储
"""
import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("pet_translator.storage")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "storage", "data.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ========== SQLAlchemy 模型 ==========

class PetModel(Base):
    """宠物数据库模型"""
    __tablename__ = "pets"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    species = Column(String(50), default="")
    breed = Column(String(100), default="")
    age = Column(Integer, default=0)
    avatar_url = Column(String(500), default="")
    personality_tags = Column(JSON, default=list)
    health_notes = Column(Text, default="")
    quiet_hours = Column(JSON, default=list)
    owner_id = Column(String(50), default="default", index=True)
    created_at = Column(String(50), default="")
    updated_at = Column(String(50), default="")


class EventModel(Base):
    """事件数据库模型"""
    __tablename__ = "events"

    id = Column(String(50), primary_key=True, index=True)
    pet_id = Column(String(50), nullable=False, index=True)
    timestamp = Column(String(50), default="", index=True)
    source_type = Column(String(20), default="")
    source_ref = Column(String(200), default="")
    animal = Column(String(50), default="")
    behavior = Column(String(100), default="")
    confidence = Column(Float, default=0.0)
    is_alert = Column(Boolean, default=False, index=True)
    severity = Column(String(20), default="info", index=True)
    period = Column(String(50), default="")
    interpretation = Column(Text, default="")
    suggestion = Column(Text, default="")
    evidence_paths = Column(JSON, default=dict)
    feedback = Column(Text, default="")
    created_at = Column(String(50), default="")


class ReportModel(Base):
    """日报数据库模型"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(String(20), nullable=False, index=True)
    pet_id = Column(String(50), index=True)
    pet_name = Column(String(100), default="")
    health_score = Column(Integer, default=0)
    health_status = Column(String(50), default="")
    total_events = Column(Integer, default=0)
    alert_count = Column(Integer, default=0)
    event_breakdown = Column(JSON, default=dict)
    hourly_chart = Column(JSON, default=dict)
    top_alerts = Column(JSON, default=list)
    suggestions = Column(JSON, default=list)


# ========== 数据库初始化与操作 ==========

def init_db():
    """初始化数据库，创建所有表"""
    Base.metadata.create_all(bind=engine)
    logger.info(f"数据库已初始化: {DB_PATH}")


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """上下文管理器获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ========== 数据迁移辅助函数 ==========

def migrate_json_to_sqlite():
    """从 JSON 文件迁移数据到 SQLite，处理重复项"""
    import json
    from storage.schema import Pet, Event, DailyReport

    init_db()

    # 迁移宠物数据
    pets_path = os.path.join(BASE_DIR, "storage", "pets.json")
    if os.path.exists(pets_path):
        with open(pets_path, "r", encoding="utf-8") as f:
            pets_data = json.load(f)
        
        # 去重：按 id 分组，保留最后一条
        seen_ids = set()
        unique_pets = []
        for pet_dict in reversed(pets_data):
            pid = pet_dict.get("id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_pets.append(pet_dict)
        unique_pets.reverse()
        
        with get_db_session() as db:
            for pet_dict in unique_pets:
                pet = Pet.from_dict(pet_dict)
                existing = db.query(PetModel).filter(PetModel.id == pet.id).first()
                if not existing:
                    db.add(PetModel(
                        id=pet.id,
                        name=pet.name,
                        species=pet.species,
                        breed=pet.breed,
                        age=pet.age,
                        avatar_url=pet.avatar_url,
                        personality_tags=pet.personality_tags,
                        health_notes=pet.health_notes,
                        quiet_hours=pet.quiet_hours,
                        owner_id=pet.owner_id,
                        created_at=pet.created_at,
                        updated_at=pet.updated_at,
                    ))
        logger.info(f"迁移了 {len(unique_pets)} 条宠物数据（去重后）")

    # 迁移事件数据
    events_path = os.path.join(BASE_DIR, "storage", "events.json")
    if os.path.exists(events_path):
        with open(events_path, "r", encoding="utf-8") as f:
            events_data = json.load(f)
        
        # 去重：按 id 分组，保留最后一条
        seen_ids = set()
        unique_events = []
        for event_dict in reversed(events_data):
            eid = event_dict.get("id")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                unique_events.append(event_dict)
        unique_events.reverse()
        
        with get_db_session() as db:
            for event_dict in unique_events:
                event = Event.from_dict(event_dict)
                existing = db.query(EventModel).filter(EventModel.id == event.id).first()
                if not existing:
                    db.add(EventModel(
                        id=event.id,
                        pet_id=event.pet_id,
                        timestamp=event.timestamp,
                        source_type=event.source_type,
                        source_ref=event.source_ref,
                        animal=event.animal,
                        behavior=event.behavior,
                        confidence=event.confidence,
                        is_alert=event.is_alert,
                        severity=event.severity,
                        period=event.period,
                        interpretation=event.interpretation,
                        suggestion=event.suggestion,
                        evidence_paths=event.evidence_paths,
                        feedback=event.feedback,
                        created_at=event.created_at,
                    ))
        logger.info(f"迁移了 {len(unique_events)} 条事件数据（去重后）")


if __name__ == "__main__":
    init_db()
    print(f"数据库已创建: {DB_PATH}")
