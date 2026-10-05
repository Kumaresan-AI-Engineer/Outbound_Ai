import asyncio
from datetime import datetime

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from twilio.base.exceptions import TwilioRestException

from app.core.security import require_role
from app.core.timezone import get_request_timezone, to_tz
from app.models.schemas import (
    TwilioNumberAssign,
    TwilioNumberCreate,
    TwilioNumberResponse,
    TwilioNumberUpdate,
)
from app.repositories.twilio_numbers_repo import twilio_numbers_repo
from app.repositories.users_repo import users_repo
from app.services.twilio_service import is_valid_caller_id

router = APIRouter(
    prefix="/twilio-numbers", tags=["twilio-numbers"], dependencies=[Depends(require_role("admin"))]
)


async def serialize_number(doc: dict, tz_name: str = "UTC") -> dict:
    number_id = str(doc["_id"])
    assigned_users = []
    async for user in users_repo.find({"assigned_number_ids": number_id}):
        assigned_users.append({"id": str(user["_id"]), "name": user.get("name", "")})
    return {
        "id": number_id,
        "phone_number": doc.get("phone_number", ""),
        "label": doc.get("label", ""),
        "is_active": doc.get("is_active", True),
        "assigned_users": assigned_users,
        "created_at": to_tz(doc.get("created_at", datetime.utcnow()), tz_name),
    }


@router.get("/", response_model=list[TwilioNumberResponse])
async def list_numbers(tz_name: str = Depends(get_request_timezone)):
    numbers = []
    async for doc in twilio_numbers_repo.find().sort("created_at", -1):
        numbers.append(await serialize_number(doc, tz_name))
    return numbers


@router.post("/", response_model=TwilioNumberResponse)
async def create_number(payload: TwilioNumberCreate, tz_name: str = Depends(get_request_timezone)):
    phone_number = payload.phone_number.strip()
    if await twilio_numbers_repo.find_one({"phone_number": phone_number}):
        raise HTTPException(status_code=400, detail="This number is already in the pool")

    try:
        # Twilio's REST client is synchronous - run it off the event loop so
        # one slow Twilio API call doesn't stall every other request.
        is_valid, reason = await asyncio.to_thread(is_valid_caller_id, phone_number)
    except TwilioRestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not verify this number with Twilio right now ({e.msg or e}). Try again shortly.",
        ) from e
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    doc = {
        "phone_number": phone_number,
        "label": payload.label,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    result = await twilio_numbers_repo.insert_one(doc)
    doc["_id"] = result.inserted_id
    return await serialize_number(doc, tz_name)


@router.put("/{number_id}", response_model=TwilioNumberResponse)
async def update_number(
    number_id: str, payload: TwilioNumberUpdate, tz_name: str = Depends(get_request_timezone)
):
    if not ObjectId.is_valid(number_id):
        raise HTTPException(status_code=404, detail="Number not found")

    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await twilio_numbers_repo.find_one_and_update(
        {"_id": ObjectId(number_id)}, {"$set": update_data}, return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Number not found")
    return await serialize_number(result, tz_name)


@router.post("/{number_id}/assign", response_model=TwilioNumberResponse)
async def assign_number(
    number_id: str, payload: TwilioNumberAssign, tz_name: str = Depends(get_request_timezone)
):
    if not ObjectId.is_valid(number_id):
        raise HTTPException(status_code=404, detail="Number not found")
    if not ObjectId.is_valid(payload.user_id):
        raise HTTPException(status_code=404, detail="User not found")

    number = await twilio_numbers_repo.find_one({"_id": ObjectId(number_id)})
    if not number:
        raise HTTPException(status_code=404, detail="Number not found")
    user = await users_repo.find_one({"_id": ObjectId(payload.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_op = "$addToSet" if payload.action == "add" else "$pull"
    await users_repo.update_one(
        {"_id": ObjectId(payload.user_id)}, {update_op: {"assigned_number_ids": number_id}}
    )
    return await serialize_number(number, tz_name)


@router.delete("/{number_id}")
async def delete_number(number_id: str):
    if not ObjectId.is_valid(number_id):
        raise HTTPException(status_code=404, detail="Number not found")
    result = await twilio_numbers_repo.delete_one({"_id": ObjectId(number_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Number not found")
    await users_repo.update_many(
        {"assigned_number_ids": number_id}, {"$pull": {"assigned_number_ids": number_id}}
    )
    return {"message": "Number deleted"}
