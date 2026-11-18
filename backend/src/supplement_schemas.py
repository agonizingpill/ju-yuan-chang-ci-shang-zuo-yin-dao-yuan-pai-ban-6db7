from pydantic import BaseModel,Field
class SupplementOpenInput(BaseModel):
    reason:str=Field(min_length=8,max_length=1000)
class SupplementReviseInput(BaseModel):
    supplement_note:str=Field(default='',max_length=2000)
