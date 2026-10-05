"""Thin base wrapping a single Motor collection.

Repositories are the only modules allowed to import collection objects from
app.database - everything downstream (routers, domain services, AI agents)
asks a repository for data instead of touching Motor directly. This is what
lets a service be unit-tested against a fake repository instead of a live
MongoDB connection.

Pass-through methods mirror Motor's own collection API 1:1 (same filter/
update dict shapes, same cursor chaining like `.sort()`/`.limit()`) so
existing call sites move over by swapping the collection object for the
repository, not by learning a new query DSL. Named convenience methods
(`get_by_id`, `update_fields`, `delete_by_id`) exist for the handful of
patterns repeated identically across every collection.
"""

from bson import ObjectId


class MongoRepository:
    def __init__(self, collection):
        self._collection = collection

    def find_one(self, filter_: dict | None = None, **kwargs):
        return self._collection.find_one(filter_ or {}, **kwargs)

    def find(self, filter_: dict | None = None, **kwargs):
        return self._collection.find(filter_ or {}, **kwargs)

    def insert_one(self, document: dict):
        return self._collection.insert_one(document)

    def update_one(self, filter_: dict, update: dict, **kwargs):
        return self._collection.update_one(filter_, update, **kwargs)

    def update_many(self, filter_: dict, update: dict, **kwargs):
        return self._collection.update_many(filter_, update, **kwargs)

    def delete_one(self, filter_: dict):
        return self._collection.delete_one(filter_)

    def find_one_and_update(self, filter_: dict, update: dict, **kwargs):
        return self._collection.find_one_and_update(filter_, update, **kwargs)

    def find_one_and_delete(self, filter_: dict):
        return self._collection.find_one_and_delete(filter_)

    def count_documents(self, filter_: dict):
        return self._collection.count_documents(filter_)

    def aggregate(self, pipeline: list):
        return self._collection.aggregate(pipeline)

    def distinct(self, field: str, filter_: dict | None = None):
        return self._collection.distinct(field, filter_ or {})

    def create_index(self, *args, **kwargs):
        return self._collection.create_index(*args, **kwargs)

    async def get_by_id(self, doc_id: str) -> dict | None:
        if not ObjectId.is_valid(doc_id):
            return None
        return await self.find_one({"_id": ObjectId(doc_id)})

    async def update_fields(self, doc_id: str, fields: dict) -> None:
        await self.update_one({"_id": ObjectId(doc_id)}, {"$set": fields})

    async def delete_by_id(self, doc_id: str):
        return await self.delete_one({"_id": ObjectId(doc_id)})
