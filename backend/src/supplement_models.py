from sqlalchemy import String,Integer,Text,ForeignKey,CheckConstraint,Index,text
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class SupplementaryDebrief(Base):
    __tablename__='supplementary_debriefs'
    __table_args__=(
        CheckConstraint("state in ('open','archived')"),
        CheckConstraint('version_no > 0'),
        # 同一份原交接至多保留一份开启中的补充单：重复开启返回原单，重试不重复建单
        Index('one_open_supplement_per_debrief','debrief_id',unique=True,
              postgresql_where=text("state = 'open'"),sqlite_where=text("state = 'open'")),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    debrief_id:Mapped[int]=mapped_column(ForeignKey('show_debriefs.id'))
    version_no:Mapped[int]=mapped_column(Integer)
    prev_id:Mapped[int|None]=mapped_column(ForeignKey('supplementary_debriefs.id'),nullable=True)
    reason:Mapped[str]=mapped_column(Text)
    supplement_note:Mapped[str]=mapped_column(Text,default='')
    state:Mapped[str]=mapped_column(String(20),default='open')
    opened_by:Mapped[str]=mapped_column(String(100))
    opened_at:Mapped[str]=mapped_column(String(40))
    archived_by:Mapped[str|None]=mapped_column(String(100),nullable=True)
    archived_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
