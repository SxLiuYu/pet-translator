import sys

cam_mgr_path = r"C:\Users\mi\Documents\AgnesCode\projects\毛孩子翻译官\server\storage\repository.py"

with open(cam_mgr_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the add method to use upsert pattern
old_add = '''    def add(self, event: Event) -> Event:
        payload = event.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("timestamp"):
            payload["timestamp"] = payload["created_at"]

        with get_db_session() as db:
            db.add(EventModel(**{k: v for k, v in payload.items() if k in [
                "id", "pet_id", "timestamp", "source_type", "source_ref",
                "animal", "behavior", "confidence", "is_alert", "severity",
                "period", "interpretation", "suggestion", "evidence_paths",
                "feedback", "created_at"
            ]}))
        return Event.from_dict(payload)'''

new_add = '''    def add(self, event: Event) -> Event:
        payload = event.to_dict()
        if not payload.get("created_at"):
            payload["created_at"] = now_iso()
        if not payload.get("timestamp"):
            payload["timestamp"] = payload["created_at"]

        with get_db_session() as db:
            existing = db.query(EventModel).filter(EventModel.id == str(payload.get("id"))).first()
            if existing:
                for key, value in payload.items():
                    if hasattr(existing, key) and key != "id":
                        setattr(existing, key, value)
            else:
                db.add(EventModel(**{k: v for k, v in payload.items() if k in [
                    "id", "pet_id", "timestamp", "source_type", "source_ref",
                    "animal", "behavior", "confidence", "is_alert", "severity",
                    "period", "interpretation", "suggestion", "evidence_paths",
                    "feedback", "created_at"
                ]}))
        return Event.from_dict(payload)'''

content = content.replace(old_add, new_add)

with open(cam_mgr_path, "w", encoding="utf-8") as f:
    f.write(content)

print("repository.py 已更新")
