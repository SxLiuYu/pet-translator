import sys, os
sys.path.insert(0, os.path.join('server'))
from storage.schema import Pet, Event, DailyReport
from storage.repository import PetRepository, EventRepository, ReportRepository
import tempfile
from storage import repository as repo

p = Pet(id='p1', name='旺财', species='狗')
assert p.id == 'p1'
e = Event(id='e1', pet_id='p1', behavior='吠叫', confidence=0.9, evidence_paths={'snapshot':'a.jpg'})
assert e.evidence_paths == {'snapshot':'a.jpg'}
print('schema ok')
with tempfile.TemporaryDirectory() as td:
    repo.STORAGE_DIR = td
    pr = PetRepository()
    er = EventRepository()
    rr = ReportRepository()
    pr.create(Pet(id='pet_1', name='旺财', species='狗'))
    pr.create(Pet(id='pet_2', name='咪咪', species='猫'))
    assert pr.get_by_id('pet_1').name == '旺财'
    pr.update('pet_1', {'name':'旺财2'})
    assert pr.get_by_id('pet_1').name == '旺财2'
    ev = Event(id='evt_1', pet_id='pet_2', behavior='喵叫', confidence=0.8)
    er.add(ev)
    events, total = er.get_by_pet('pet_2', limit=10)
    assert total == 1 and events[0].behavior == '喵叫'
    er.update_feedback('evt_1', 'useful')
    assert er.get_by_id('evt_1').feedback == 'useful'
    rpt = DailyReport(date='2026-07-16', pet_id='pet_2', pet_name='咪咪', total_events=1)
    rr.save_report(rpt)
    assert rr.get_report('2026-07-16', 'pet_2') is not None
print('repository ok')
