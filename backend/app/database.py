from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

contacts_collection = db["contacts"]
call_logs_collection = db["call_logs"]
clients_collection = db["clients"]
projects_collection = db["projects"]
users_collection = db["users"]
twilio_numbers_collection = db["twilio_numbers"]


async def ensure_indexes():
    """Create indexes for the new collections. Called once on app startup."""
    await clients_collection.create_index("phone")
    await clients_collection.create_index("domain")
    await clients_collection.create_index("contact_id")
    await clients_collection.create_index([("created_at", -1)])
    await projects_collection.create_index("processing_status")
    await projects_collection.create_index("metadata.domain")
    await projects_collection.create_index([("created_at", -1)])
    await users_collection.create_index("email", unique=True)
    await users_collection.create_index("assigned_number_ids")
    await twilio_numbers_collection.create_index("phone_number", unique=True)
