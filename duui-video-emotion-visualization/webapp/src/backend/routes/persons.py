"""The people who have been linked across videos."""

from typing import Any

from fastapi import APIRouter

from ..queries import persons

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("/global")
def list_global_persons() -> list[dict[str, Any]]:
    """List every global person, with the people making it up."""
    return persons.list_global_clusters()
