from enum import Enum


class Role(str, Enum):
    SUPERADMIN = "superadmin"
    MEDICO_VETERINARIO = "medico_veterinario"
    CONTADOR = "contador"


ALL_ROLES: tuple[str, ...] = tuple(role.value for role in Role)

DEFAULT_ROLE: str = Role.MEDICO_VETERINARIO.value
