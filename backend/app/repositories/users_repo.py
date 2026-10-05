from app.database import users_collection
from app.repositories.base import MongoRepository


class UsersRepository(MongoRepository):
    async def get_by_email(self, email: str) -> dict | None:
        return await self.find_one({"email": email})


users_repo = UsersRepository(users_collection)
