from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class StartOrder(StrictModel):
    customer_id: str=Field(min_length=1,max_length=30)
    mode: Literal['live','demo']='live'
    request_id: str=Field(min_length=8,max_length=100)

class Turn(StrictModel):
    text: str=Field(min_length=1,max_length=2000)
    request_id: str=Field(min_length=8,max_length=100)
    revision: int=Field(ge=0)

class Item(StrictModel):
    product_id: str=Field(min_length=1,max_length=40)
    quantity: int=Field(ge=0,le=10000,strict=True)

class ItemUpdate(StrictModel):
    items: list[Item]=Field(min_length=1,max_length=30)
    delivery_date: str | None=None

class Confirm(StrictModel):
    revision: int=Field(ge=0)
    explicit_confirmation: Literal[True]

class Speech(StrictModel):
    text: str=Field(min_length=1,max_length=2400)
    language: Literal['hi-IN','en-IN','ta-IN','bn-IN']='hi-IN'

class PhoneTurn(Turn):
    interaction_id: str=Field(min_length=1,max_length=100)
    phone_number: str=Field(pattern=r'^\+[1-9]\d{7,14}$')
