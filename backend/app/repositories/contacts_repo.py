from app.database import contacts_collection
from app.repositories.base import MongoRepository


class ContactsRepository(MongoRepository):
    pass


contacts_repo = ContactsRepository(contacts_collection)
