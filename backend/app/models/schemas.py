from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime
from enum import Enum


class ContactStatus(str, Enum):
    new = "new"
    called = "called"
    follow_up = "follow_up"
    closed = "closed"


class ContactCreate(BaseModel):
    name: str
    phone: str
    company: str = ""
    status: ContactStatus = ContactStatus.new
    notes: str = ""


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[ContactStatus] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    name: str
    phone: str
    company: str
    status: ContactStatus
    notes: str
    last_called: Optional[datetime] = None
    created_at: datetime


class CallInitiateRequest(BaseModel):
    contact_id: str
    phone: str


class CallLogResponse(BaseModel):
    id: str
    contact_id: str
    contact_name: str
    phone: str
    status: str
    duration: int = 0
    transcript: str = ""
    suggestions: list[Any] = []
    analysis: Optional[dict] = None
    created_at: datetime
