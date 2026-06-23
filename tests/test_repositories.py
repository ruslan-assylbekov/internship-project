from core.repositories.user_repository import UserRepository


def test_create_user_repo(db_session):
    repo = UserRepository(db_session)
    user_data = {"email": "jonathan@mail.com", "password": "pass", "firstname": "Ruslan", "lastname": "Assylbekov"}

    new_user = repo.create(user_data)

    assert new_user.id is not None
    assert new_user.firstname == "Ruslan"
    assert new_user.created is not None


def test_get_user_by_id(db_session):
    repo = UserRepository(db_session)
    user = repo.create({"email": "jonathan@mail.com", "password": "pass", "firstname": "Ruslan", "lastname": "Assylbekov"})

    found_user = repo.get_by_id(user.id)
    assert found_user.firstname == "Ruslan"

