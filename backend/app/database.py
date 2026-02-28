from motor.motor_asyncio import AsyncIOMotorClient
from app.config import get_settings

settings = get_settings()

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.mongo_db_name]

contacts_collection = db["contacts"]
call_logs_collection = db["call_logs"]
