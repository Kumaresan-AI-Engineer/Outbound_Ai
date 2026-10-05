from app.database import call_logs_collection
from app.repositories.base import MongoRepository


class CallLogsRepository(MongoRepository):
    pass


call_logs_repo = CallLogsRepository(call_logs_collection)
