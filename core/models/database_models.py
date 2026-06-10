import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

Base = declarative_base() # base for database models

class users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String)
    password = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    created = Column(DateTime, default=datetime.datetime.utcnow)

class books(Base):
    __tablename__ = 'books'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    author = Column(String)
    year = Column(Integer, default = 0)
    status = Column(String, default = "Available")
    user_id = Column(Integer, ForeignKey('users.id'))
    created = Column(DateTime, default=datetime.datetime.utcnow)

class borrowings(Base):
    __tablename__ = 'borrowings'
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    borrow_date = Column(DateTime, default=datetime.datetime.utcnow)
    return_date = Column(DateTime)

