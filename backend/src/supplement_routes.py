from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,writers,admin
from .debrief_models import ShowDebrief
from .supplement_models import SupplementaryDebrief
from .supplement_schemas import SupplementOpenInput,SupplementReviseInput
from .services import pack
from . import supplement_service as supp
router=APIRouter()
@router.get('/supplementary-debriefs')
def list_supplements(s=Depends(db_session),u=Depends(current)):
    return [pack(x) for x in s.scalars(select(SupplementaryDebrief).order_by(SupplementaryDebrief.id.desc()))]
@router.get('/show-debriefs/{id}/supplements')
def supplements_of_debrief(id:int,s=Depends(db_session),u=Depends(current)):
    d=s.get(ShowDebrief,id)
    if not d:return []
    return [pack(x) for x in supp.chain(s,id)]
@router.post('/show-debriefs/{id}/supplements')
def open_supplement(id:int,d:SupplementOpenInput,s=Depends(db_session),u=Depends(admin)):
    x=supp.open_supplement(s,id,d,u);s.commit();return x
@router.put('/supplementary-debriefs/{id}')
def revise_supplement(id:int,d:SupplementReviseInput,s=Depends(db_session),u=Depends(writers)):
    x=supp.revise_supplement(s,id,d,u);s.commit();return x
@router.post('/supplementary-debriefs/{id}/archive')
def archive_supplement(id:int,s=Depends(db_session),u=Depends(admin)):
    x=supp.archive_supplement(s,id,u);s.commit();return x
