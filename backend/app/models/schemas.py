from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
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
    secondary_phone: str = ""
    company: str = ""
    status: ContactStatus = ContactStatus.new
    notes: str = ""


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[ContactStatus] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    name: str
    phone: str
    secondary_phone: str = ""
    company: str
    status: ContactStatus
    notes: str
    last_called: Optional[datetime] = None
    assigned_to: Optional[str] = None
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
    user_id: Optional[str] = None
    created_at: datetime


class EnrichmentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ClientResponse(BaseModel):
    id: str
    name: str
    company: str = ""
    project: str = ""
    phone: str
    contact_id: Optional[str] = None
    domain: Optional[str] = None
    related_domains: list[str] = []
    matched_project_ids: list[str] = []
    enrichment_status: EnrichmentStatus = EnrichmentStatus.pending
    source_file: str = ""
    created_at: datetime


class ClientUploadRowError(BaseModel):
    row: int
    message: str


class ClientUploadResult(BaseModel):
    total_rows: int
    imported: int
    updated: int
    skipped: int
    errors: list[ClientUploadRowError] = []


class ProcessingStatus(str, Enum):
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ProjectResponse(BaseModel):
    id: str
    name: str
    file_name: str
    file_type: str
    file_size: int = 0
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime


class UserRole(str, Enum):
    admin = "admin"
    sales = "sales"


class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: UserRole = UserRole.sales


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class AssignedNumberSummary(BaseModel):
    id: str
    phone_number: str
    label: str = ""


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    is_active: bool
    assigned_numbers: list[AssignedNumberSummary] = []
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TwilioNumberCreate(BaseModel):
    phone_number: str
    label: str = ""


class TwilioNumberUpdate(BaseModel):
    label: Optional[str] = None
    is_active: Optional[bool] = None


class TwilioNumberAssign(BaseModel):
    user_id: str
    action: Literal["add", "remove"] = "add"


class AssignedUserSummary(BaseModel):
    id: str
    name: str


class TwilioNumberResponse(BaseModel):
    id: str
    phone_number: str
    label: str = ""
    is_active: bool
    assigned_users: list[AssignedUserSummary] = []
    created_at: datetime
