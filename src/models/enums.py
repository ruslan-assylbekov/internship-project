"""Allowed values for the ``status`` columns.

``StrEnum`` members are strings, so these double as request/response types in
the Pydantic schemas (FastAPI renders them as an OpenAPI enum) and as the
values written to the ``String`` columns. Assignments to model attributes use
``.value`` -- psycopg2 adapts ``str`` but not necessarily a ``str`` subclass.
"""

from enum import StrEnum


class BookStatus(StrEnum):
    AVAILABLE = "Available"
    BORROWED = "Borrowed"
    RESERVED = "Reserved"
    LOST = "Lost"


class BorrowingStatus(StrEnum):
    ACTIVE = "Active"
    RESERVED = "Reserved"
    RETURNED = "Returned"
    LOST = "Lost"

    @classmethod
    def open_states(cls) -> tuple[BorrowingStatus, ...]:
        """States that still tie up a book."""
        return (cls.ACTIVE, cls.RESERVED)
