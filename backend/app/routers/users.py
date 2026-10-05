from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user, hash_password, require_role
from app.core.timezone import get_request_timezone
from app.models.schemas import UserCreate, UserResponse, UserUpdate
from app.repositories.users_repo import users_repo
from app.routers.auth import serialize_user

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_role("admin"))])


@router.get("/", response_model=list[UserResponse])
async def list_users(tz_name: str = Depends(get_request_timezone)):
    users = []
    async for doc in users_repo.find().sort("created_at", -1):
        users.append(await serialize_user(doc, tz_name))
    return users


@router.post("/", response_model=UserResponse)
async def create_user(payload: UserCreate, tz_name: str = Depends(get_request_timezone)):
    email = payload.email.lower().strip()
    if await users_repo.get_by_email(email):
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    doc = {
        "name": payload.name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": payload.role.value,
        "is_active": True,
        "assigned_number_ids": [],
        "created_at": datetime.utcnow(),
    }
    result = await users_repo.insert_one(doc)
    doc["_id"] = result.inserted_id
    return await serialize_user(doc, tz_name)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
    tz_name: str = Depends(get_request_timezone),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name
    if payload.email is not None:
        email = payload.email.lower().strip()
        existing = await users_repo.find_one({"email": email, "_id": {"$ne": ObjectId(user_id)}})
        if existing:
            raise HTTPException(status_code=400, detail="A user with this email already exists")
        update_data["email"] = email
    if payload.password is not None:
        update_data["password_hash"] = hash_password(payload.password)
    if payload.role is not None:
        update_data["role"] = payload.role.value
    if payload.is_active is not None:
        if user_id == str(current_user["_id"]) and not payload.is_active:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        update_data["is_active"] = payload.is_active

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await users_repo.find_one_and_update(
        {"_id": ObjectId(user_id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return await serialize_user(result, tz_name)


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    result = await users_repo.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}
