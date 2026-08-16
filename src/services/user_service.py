from src.core.security import hash_password, verify_password
from src.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_all_users(self, skip: int = 0, limit: int = 50):
        return self.repository.get_all(skip=skip, limit=limit)

    def get_user_by_id(self, user_id: int):
        return self.repository.get_by_id(user_id)

    def get_user_by_email(self, email: str):
        return self.repository.get_by_email(email)

    def create_user(self, user_data: dict):
        stored = dict(user_data)
        if "password" in stored:
            stored["password"] = hash_password(stored["password"])
        return self.repository.create(stored)

    def delete_user(self, user_id: int):
        return self.repository.delete(user_id)

    def authenticate(self, email: str, password: str):
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.password):
            return None
        return user
