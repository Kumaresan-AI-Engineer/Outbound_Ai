from app.database import clients_collection
from app.repositories.base import MongoRepository


class ClientsRepository(MongoRepository):
    pass


clients_repo = ClientsRepository(clients_collection)
