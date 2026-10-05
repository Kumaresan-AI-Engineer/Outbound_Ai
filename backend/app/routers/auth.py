from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.core.timezone import get_request_timezone, to_tz
from app.models.schemas import LoginRequest, TokenResponse, UserResponse
from app.repositories.twilio_numbers_repo import twilio_numbers_repo
from app.repositories.users_repo import users_repo

router = APIRouter(prefix="/auth", tags=["auth"])


async def serialize_user(doc: dict, tz_name: str = "UTC") -> dict:
    number_ids = [n for n in doc.get("assigned_number_ids", []) if ObjectId.is_valid(n)]
    assigned_numbers = []
    if number_ids:
        async for number in twilio_numbers_repo.find({"_id": {"$in": [ObjectId(n) for n in number_ids]}}):
            assigned_numbers.append(
                {
                    "id": str(number["_id"]),
                    "phone_number": number.get("phone_number", ""),
                    "label": number.get("label", ""),
                }
            )
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "email": doc.get("email", ""),
        "role": doc.get("role", "sales"),
        "is_active": doc.get("is_active", True),
        "assigned_numbers": assigned_numbers,
        "created_at": to_tz(doc.get("created_at", datetime.utcnow()), tz_name),
    }


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, tz_name: str = Depends(get_request_timezone)):
    user = await users_repo.get_by_email(req.email.lower().strip())
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    token = create_access_token(user)
    return {"access_token": token, "user": await serialize_user(user, tz_name)}


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: dict = Depends(get_current_user), tz_name: str = Depends(get_request_timezone)
):
    return await serialize_user(current_user, tz_name)
