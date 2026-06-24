from src.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_all_users(self):
        return self.repository.get_all()

    def get_user_by_id(self, user_id: int):
        return self.repository.get_by_id(user_id)

    def create_user(self, user_data: dict):
        return self.repository.create(user_data)

    def delete_user(self, user_id: int):
        return self.repository.delete(user_id)
