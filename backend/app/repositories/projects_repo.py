from app.database import projects_collection
from app.repositories.base import MongoRepository


class ProjectsRepository(MongoRepository):
    pass


projects_repo = ProjectsRepository(projects_collection)
