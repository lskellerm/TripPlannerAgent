"""TripPlannerAgent backend package.

Eagerly imports ORM models so that SQLAlchemy table metadata is
registered before ``Base.metadata.create_all`` runs in the lifespan.
"""

from src.models import Base  # noqa: F401 — eager registration

__all__: list[str] = ["Base"]
