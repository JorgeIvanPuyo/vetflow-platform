from collections.abc import Iterable, Mapping
from typing import Any


def tenant_scoped_relation_values(
    value: Any,
    fields: Iterable[str],
    relations: Mapping[str, str],
) -> Any:
    """Project optional ORM FKs from owned relations without changing stored FKs.

    Scoped SQL loaders can return None while the original scalar FK remains set.
    Check ownership as well, for serialization after writes or identity-map reuse.
    Explicit DTO dictionaries have already crossed the ORM projection boundary.
    """
    if isinstance(value, Mapping):
        return value
    result = {field: getattr(value, field) for field in fields if hasattr(value, field)}
    for field, relationship in relations.items():
        related = getattr(value, relationship)
        result[field] = (
            related.id
            if related is not None and related.tenant_id == value.tenant_id
            else None
        )
    return result
