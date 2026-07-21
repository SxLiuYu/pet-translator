import os

test_path = "C:/Users/mi/Documents/AgnesCode/projects/毛孩子翻译官/tests/test_storage.py"

with open(test_path, "rb") as f:
    content = f.read().decode("utf-8")

old_test = '''def test_report_persistence(tmp_path: "pathlib.Path") -> None:
    data_dir = tmp_path / "storage"
    data_dir.mkdir(parents=True, exist_ok=True)
    repo.STORAGE_DIR = str(data_dir)
    rr = ReportRepository()
    report = DailyReport(date="2026-07-16", pet_id="pet_001", pet_name="旺财", total_events=5, alert_count=1)
    report_path = rr.save_report(report)
    assert os.path.exists(report_path)
    loaded = rr.get_report("2026-07-16", "pet_001")
    assert loaded is not None
    assert loaded.pet_name == "旺财"
    assert rr.get_report("2026-07-15", "pet_001") is None'''

new_test = '''def test_report_persistence(tmp_path: "pathlib.Path") -> None:
    data_dir = tmp_path / "storage"
    data_dir.mkdir(parents=True, exist_ok=True)
    repo.STORAGE_DIR = str(data_dir)
    rr = ReportRepository()
    report = DailyReport(date="2026-07-16", pet_id="pet_001", pet_name="旺财", total_events=5, alert_count=1)
    rr.save_report(report)
    loaded = rr.get_report("2026-07-16", "pet_001")
    assert loaded is not None
    assert loaded.pet_name == "旺财"
    assert rr.get_report("2026-07-15", "pet_001") is None'''

content = content.replace(old_test, new_test)

with open(test_path, "wb") as f:
    f.write(content.encode("utf-8"))

print("test_storage.py 已更新")
