import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.repositories.search import SearchRepository
from app.schemas.search import SearchResultItem


class SearchService:
    DEFAULT_LIMIT = 20
    OWNER_LIMIT = 10
    PATIENT_LIMIT = 10

    def __init__(self, db: Session) -> None:
        self.search_repository = SearchRepository(db)

    def search(self, tenant_id: uuid.UUID, query: str) -> tuple[list[SearchResultItem], str]:
        trimmed_query = query.strip()
        if not trimmed_query:
            raise AppError(
                400,
                "empty_search_query",
                "Query parameter q must not be empty",
            )

        owner_results = self.search_repository.search_owners(
            tenant_id, trimmed_query, self.OWNER_LIMIT
        )
        patient_results = self.search_repository.search_patients(
            tenant_id, trimmed_query, self.PATIENT_LIMIT
        )

        items: list[SearchResultItem] = []

        for owner in owner_results:
            items.append(
                SearchResultItem(
                    type="owner",
                    id=owner.id,
                    title=owner.full_name,
                    subtitle=owner.phone,
                    owner_id=None,
                    patient_id=None,
                )
            )

        for patient, owner_name in patient_results:
            items.append(
                SearchResultItem(
                    type="patient",
                    id=patient.id,
                    title=patient.name,
                    subtitle=f"{patient.species} • Owner: {owner_name}",
                    owner_id=patient.owner_id,
                    patient_id=patient.id,
                )
            )

        return items[: self.DEFAULT_LIMIT], trimmed_query
