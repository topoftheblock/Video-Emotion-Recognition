"""Cross-video person identity."""

from fastapi import APIRouter

from ..queries import persons

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.get("/global")
def list_global_persons():
    """Every person cluster that spans more than one video."""
    return persons.list_global_clusters()
