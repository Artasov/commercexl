from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from commercexl.services.base_config import BaseConfig


class Credits:
    @classmethod
    def to_credits(cls, config: type[BaseConfig], currency: str, amount: Decimal) -> Decimal:
        try:
            return config.calc_credits(currency, amount)
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Currency rate not configured.",
            ) from exc

    @classmethod
    def get_currency_rates(cls, config: type[BaseConfig]) -> dict[str, str]:
        rates: dict[str, str] = {}
        for currency in config.get_credits_converters_map():
            rates[currency] = str(cls.to_credits(config, currency, Decimal("1")))
        return rates


