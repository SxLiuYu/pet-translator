"""
scripts/cleanup_duplicates.py
清理重复宠物数据
通过 SQLAlchemy 模型操作数据库
"""
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from storage.database import PetModel, SessionLocal

logger = logging.getLogger("pet_translator.scripts")
logging.basicConfig(level=logging.INFO)


def cleanup_duplicates():
    """删除同名的重复宠物，保留最新创建的"""
    with SessionLocal() as db:
        all_pets = db.query(PetModel).all()
        logger.info(f"当前宠物数量: {len(all_pets)}")
        
        # 按 name+species 分组
        from collections import defaultdict
        groups = defaultdict(list)
        for pet in all_pets:
            key = (pet.name, pet.species)
            groups[key].append(pet)
        
        deleted = 0
        for (name, species), pets in groups.items():
            if len(pets) > 1:
                # 按 created_at 排序，保留最新的
                pets.sort(key=lambda p: p.created_at or "", reverse=True)
                keep = pets[0]
                for dup in pets[1:]:
                    logger.info(f"删除重复宠物: {dup.id} - {dup.name} ({dup.species})")
                    db.delete(dup)
                    deleted += 1
        
        db.commit()
        logger.info(f"清理完成，删除了 {deleted} 条重复记录")
        
        # 验证
        remaining = db.query(PetModel).all()
        logger.info(f"剩余宠物数量: {len(remaining)}")
        for p in remaining:
            logger.info(f"  - {p.id}: {p.name} ({p.species})")


if __name__ == "__main__":
    cleanup_duplicates()
