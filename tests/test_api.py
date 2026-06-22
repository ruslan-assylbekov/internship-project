from fastapi.testclient import TestClient
from core.backend.main import app
from core.schemas.user_schemas import BookCreate

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == 200

def test_weather_get():
    response = client.get("/weather/Astana/1")
    assert response.status_code == 200

def test_user_get():
    response = client.get("/users/1")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == 1
    assert data["email"] == "qwewqewqe@mail.ru"
    assert data["firstname"] == "RUSLAN"
    assert data["lastname"] == "ASSYLBEKOV"
    assert data["created"] is not None

def test_book_post():
    book = BookCreate(title="testbook", author="testbook_Author", year=2000)
    response = client.post("/books", json=book.model_dump())
    assert response.status_code == 200

def test_book_post_missingfield():
    book = {"title": "testbook", "author": "testbook_Author"}  # no year
    response = client.post("/books", json=book)
    assert response.status_code == 422

def test_book_post_wrongtype():
    book = {"title": "testbook", "author": "testbook_Author", "year": "sixseven"}
    response = client.post("/books/", json=book)
    assert response.status_code == 422


