from pydantic import BaseModel


class CommerceUserActorDTO(BaseModel):
    """Минимальные данные пользователя, которые реально нужны commerce-сервисам."""

    id: int


