from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

db_client = MongoClient("mongodb://localhost:27017/")