from datetime import datetime,timezone
from sqlalchemy import select
from fastapi import HTTPException
from .debrief_models import ShowDebrief
from .supplement_models import SupplementaryDebrief
from .incident_models import HouseIncident
from .staff_service import locked
from .services import pack,audit

def now():return datetime.now(timezone.utc).isoformat()

def chain(s,debrief_id):
    return s.scalars(select(SupplementaryDebrief)
                     .where(SupplementaryDebrief.debrief_id==debrief_id)
                     .order_by(SupplementaryDebrief.version_no)).all()

def open_one(s,debrief_id):
    """同场唯一的开启中补充单；不存在返回 None。"""
    return s.scalar(select(SupplementaryDebrief)
                    .where(SupplementaryDebrief.debrief_id==debrief_id,
                           SupplementaryDebrief.state=='open'))

def review_state(s,debrief_id):
    """场次复核标记：存在开启中的补充单即为待复核。"""
    return 'pending_review' if open_one(s,debrief_id) else 'clear'

def debrief_view(s,x):
    rows=chain(s,x.id)
    current=open_one(s,x.id)
    return pack(x)|{
        'supplement_state':review_state(s,x.id),
        'supplement_count':len(rows),
        'open_supplement_id':current.id if current else None,
        'supplement_chain':[pack(v) for v in rows],
    }

def open_supplement(s,id,d,u):
    # 先锁原交接行：与事件补报、补充归档共用同一把锁，串行化同场并发
    base=locked(s,ShowDebrief,id)
    if base.state!='archived':raise HTTPException(409,'只有已归档交接可以开启补充交接；草稿请直接修订原单')
    existing=open_one(s,base.id)
    if existing:
        # 同场仅一份补充待办：重复开启/失败重试返回原单，不重复建单
        audit(s,u,f'查看本场补充交接原单 #{existing.id}（重复开启）')
        return pack(existing)
    prior=s.scalar(select(SupplementaryDebrief)
                   .where(SupplementaryDebrief.debrief_id==base.id)
                   .order_by(SupplementaryDebrief.version_no.desc()))
    version_no=(prior.version_no if prior else 0)+1
    x=SupplementaryDebrief(debrief_id=base.id,version_no=version_no,
                           prev_id=prior.id if prior else None,
                           reason=d.reason.strip(),state='open',
                           opened_by=u.email,opened_at=now())
    s.add(x);s.flush()
    audit(s,u,f'经理开启补充交接 场次#{base.performance_id} 第{version_no}版（基于交接#{base.id}）')
    return pack(x)

def ensure_open_for_incident(s,base,u):
    """补报事件调用：调用方须已锁定原交接 base。
    有开启中的补充单则复用；若上一版刚被归档，则续开下一版承接新险情，避免漏报。"""
    existing=open_one(s,base.id)
    if existing:return existing
    prior=s.scalar(select(SupplementaryDebrief)
                   .where(SupplementaryDebrief.debrief_id==base.id)
                   .order_by(SupplementaryDebrief.version_no.desc()))
    if not prior:
        raise HTTPException(409,'本场交接已归档且无补充交接；请经理凭原因开启本场补充交接后再补报事件')
    version_no=prior.version_no+1
    x=SupplementaryDebrief(debrief_id=base.id,version_no=version_no,prev_id=prior.id,
                           reason=f'补报触发续开：{u.email} 在第{prior.version_no}版归档后登记新险情，待经理补填原因并复核',
                           state='open',opened_by=u.email,opened_at=now())
    s.add(x);s.flush()
    audit(s,u,f'补报事件自动续开补充交接 第{version_no}版（承接第{prior.version_no}版，待经理复核）')
    return x

def revise_supplement(s,id,d,u):
    preview=s.get(SupplementaryDebrief,id)
    if not preview:raise HTTPException(404,'补充交接单不存在')
    base=locked(s,ShowDebrief,preview.debrief_id)  # 保持“原交接→补充单”锁序
    x=locked(s,SupplementaryDebrief,id)
    if x.state!='open':raise HTTPException(409,'补充交接已重新归档，不能再改写')
    note=d.supplement_note.strip()
    if note and len(note)<8:raise HTTPException(409,'补充修订说明至少8字；如无补充可留空')
    x.supplement_note=note
    audit(s,u,f'领班修订补充交接 #{id}（第{x.version_no}版）')
    return pack(x)

def archive_supplement(s,id,u):
    preview=s.get(SupplementaryDebrief,id)
    if not preview:raise HTTPException(404,'补充交接单不存在')
    base=locked(s,ShowDebrief,preview.debrief_id)
    x=locked(s,SupplementaryDebrief,id)
    if x.state!='open':raise HTTPException(409,'这份补充交接已经归档，不能重复签署')
    # 高风险事件全部经理关闭后才能重新归档；锁内复查避免补报/关闭与归档竞态
    if s.scalar(select(HouseIncident.id).where(HouseIncident.performance_id==base.performance_id,
                                               HouseIncident.severity=='high',
                                               HouseIncident.state!='closed')):
        raise HTTPException(409,'高风险现场事件尚未全部经理关闭，不能重新归档')
    x.state='archived';x.archived_by=u.email;x.archived_at=now()
    audit(s,u,f'经理重新归档补充交接 #{id}（第{x.version_no}版，关联上一版#{x.prev_id or base.id}）')
    return pack(x)
