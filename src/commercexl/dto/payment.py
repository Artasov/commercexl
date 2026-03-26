from __future__ import annotations

from typing import Any

from pydantic import BaseModel, RootModel


class PaymentDTO(BaseModel):
    id: int
    amount: float
    currency: str
    payment_url: str | None = None
    created_at: str
    extras: dict[str, Any] | None = None


class PaymentTypesDTO(RootModel[dict[str, list[str]]]):
    """РЎР»РѕРІР°СЂСЊ РІРёРґР° `РІР°Р»СЋС‚Р° -> СЃРїРёСЃРѕРє СЂР°Р·СЂРµС€С‘РЅРЅС‹С… РїР»Р°С‚С‘Р¶РЅС‹С… СЃРёСЃС‚РµРј`."""
    pass


