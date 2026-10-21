from pydantic import BaseModel

class User(BaseModel):
    """Representa los datos de un usuario."""
    id: int
    username: str
    email: str





#.\mongod --dbpath "D:\mongodb_9.0.4\Data\"