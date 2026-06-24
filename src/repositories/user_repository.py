from sqlalchemy.orm import Session
from src.models.database_models import users

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        return self.db.query(users).all()

    def get_by_id(self, user_id: int):
        return self.db.query(users).filter(users.id == user_id).first()

    def create(self, user_data: dict):
        new_user = users(**user_data)
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        return new_user

    def delete(self, user_id: int):
        user = self.get_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False
    
    def get_by_email(self, email: str):
        return self.db.query(users).filter(users.email == email).first()