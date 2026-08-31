from pydantic import BaseModel, ConfigDict, Field


class CommerceUserActorDTO(BaseModel):
    """Auth-neutral actor, собранный host-приложением после аутентификации."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    permissions: frozenset[str] = Field(default_factory=frozenset)

    def has_permission(self, permission: str) -> bool:
        """Проверяет permission, переданное auth adapter-ом."""
        return permission in self.permissions
