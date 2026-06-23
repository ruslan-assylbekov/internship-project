from fastapi.testclient import TestClient
from core.backend.main import app
from core.schemas.user_schemas import BookCreate

client = TestClient(app)

def test_weather_get():
    response = client.get("/weather/Astana")
    assert response.status_code == 200

def test_user_get():
    response = client.get("/users/1")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == 1
    assert data["firstname"] == "RUSLAN"

def test_book_get():
    response = client.get("/books/1")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == 1
    assert data["title"] == "testbook"

def test_book_post_missingfield():
    book = {"title": "testbook", "author": "testbook_Author"}  # no year
    response = client.post("/books", json=book)
    assert response.status_code == 422

def test_book_post_wrongtype():
    book = {"title": "testbook", "author": "testbook_Author", "year": "sixseven"}
    response = client.post("/books/", json=book)
    assert response.status_code == 422
