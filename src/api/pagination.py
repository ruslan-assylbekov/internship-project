"""Query parameters shared by every list endpoint.

A dependency rather than repeated ``skip``/``limit`` arguments, so the bounds
are declared once. The cap matters: without ``limit`` these endpoints returned
every row, which is fine for a seeded dev database and not for a real one.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Query

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


@dataclass
class Pagination:
    skip: Annotated[int, Query(ge=0, description="Rows to skip.")] = 0
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_PAGE_SIZE, description="Rows to return."),
    ] = DEFAULT_PAGE_SIZE
