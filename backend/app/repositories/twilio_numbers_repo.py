from app.database import twilio_numbers_collection
from app.repositories.base import MongoRepository


class TwilioNumbersRepository(MongoRepository):
    pass


twilio_numbers_repo = TwilioNumbersRepository(twilio_numbers_collection)
