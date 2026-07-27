from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from app.database import contacts_collection
from app.models.schemas import ContactCreate, ContactUpdate, ContactResponse

router = APIRouter(prefix="/contacts", tags=["contacts"])


def serialize_contact(doc) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc["name"],
        "phone": doc["phone"],
        "secondary_phone": doc.get("secondary_phone", ""),
        "company": doc.get("company", ""),
        "status": doc.get("status", "new"),
        "notes": doc.get("notes", ""),
        "last_called": doc.get("last_called"),
        "created_at": doc.get("created_at", datetime.utcnow()),
    }


@router.get("/", response_model=list[ContactResponse])
async def get_contacts():
    contacts = []
    async for doc in contacts_collection.find().sort("created_at", -1):
        contacts.append(serialize_contact(doc))
    return contacts


@router.post("/", response_model=ContactResponse)
async def create_contact(contact: ContactCreate):
    doc = {
        **contact.model_dump(),
        "last_called": None,
        "created_at": datetime.utcnow(),
    }
    result = await contacts_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_contact(doc)


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(contact_id: str, contact: ContactUpdate):
    update_data = {k: v for k, v in contact.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await contacts_collection.find_one_and_update(
        {"_id": ObjectId(contact_id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Contact not found")
    return serialize_contact(result)


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str):
    result = await contacts_collection.delete_one({"_id": ObjectId(contact_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"message": "Contact deleted"}
