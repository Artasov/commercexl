from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from commercexl.models import Currency
from commercexl.money import Money

CurrencyValue = str | Currency
MinTopUpAmountRule = Decimal | Callable[[], Decimal]
CreditsConverterRule = Decimal | Callable[[Decimal], Decimal]


class BaseConfig:
    """Coarse allowlist валют и provider systems для commerce."""

    PAYMENT_SYSTEMS: dict[str, tuple[str, ...]] = {
        "RUB": ("handmade", "balance"),
        "USD": ("handmade", "balance"),
    }
    MIN_TOP_UP_AMOUNTS = {
        "RUB": Decimal("50"),
        "USD": Decimal("1"),
    }
    CREDITS_CONVERTERS = {
        "RUB": Decimal("110"),
        "USD": Decimal("10000"),
    }
    MAX_TOP_UP_AMOUNT = Decimal("1000000")

    @classmethod
    def normalize_currency(cls, currency: CurrencyValue) -> str:
        if isinstance(currency, Currency):
            return currency.value
        if not isinstance(currency, str):
            raise TypeError("Currency code must be a string.")
        normalized_currency = currency.strip().upper()
        if not normalized_currency:
            raise TypeError("Currency code cannot be empty.")
        if len(normalized_currency) > Money.currency_code_length:
            raise TypeError(f"Currency code cannot exceed {Money.currency_code_length} characters.")
        return normalized_currency

    @staticmethod
    def normalize_payment_system(payment_system: str) -> str:
        if not isinstance(payment_system, str):
            raise TypeError("Payment system must be a string.")
        normalized_system = payment_system.strip().lower()
        if not normalized_system:
            raise TypeError("Payment system cannot be empty.")
        if len(normalized_system) > 50:
            raise TypeError("Payment system cannot exceed 50 characters.")
        return normalized_system

    @classmethod
    def get_currency_codes(cls) -> tuple[str, ...]:
        return tuple(dict.fromkeys(cls.normalize_currency(currency) for currency in cls.PAYMENT_SYSTEMS))

    @classmethod
    def get_payment_systems_map(cls) -> dict[str, tuple[str, ...]]:
        return {
            cls.normalize_currency(currency): tuple(
                cls.normalize_payment_system(system)
                for system in payment_systems
            )
            for currency, payment_systems in cls.PAYMENT_SYSTEMS.items()
        }

    @classmethod
    def get_min_top_up_amounts_map(cls) -> dict[str, MinTopUpAmountRule]:
        return {cls.normalize_currency(currency): rule for currency, rule in cls.MIN_TOP_UP_AMOUNTS.items()}

    @classmethod
    def get_credits_converters_map(cls) -> dict[str, CreditsConverterRule]:
        return {cls.normalize_currency(currency): rule for currency, rule in cls.CREDITS_CONVERTERS.items()}

    @classmethod
    def validate(cls) -> None:
        currencies = cls.get_currency_codes()
        if not currencies:
            raise TypeError(f"{cls.__name__}.PAYMENT_SYSTEMS must contain at least one currency.")

        payment_systems = cls.get_payment_systems_map()
        min_top_up_amounts = cls.get_min_top_up_amounts_map()
        credits_converters = cls.get_credits_converters_map()

        for currency in currencies:
            if not payment_systems[currency]:
                raise TypeError(f"{cls.__name__}.PAYMENT_SYSTEMS[{currency}] must contain a payment system.")
            if "balance" in payment_systems[currency] and currency not in min_top_up_amounts:
                raise TypeError(
                    f"{cls.__name__}.MIN_TOP_UP_AMOUNTS must contain {currency} because balance is enabled.",
                )
            if "balance" in payment_systems[currency] and currency not in credits_converters:
                raise TypeError(
                    f"{cls.__name__}.CREDITS_CONVERTERS must contain {currency} because balance is enabled.",
                )

    @classmethod
    def get_min_top_up_amount(cls, currency: CurrencyValue) -> Decimal:
        rule: MinTopUpAmountRule = cls.get_min_top_up_amounts_map().get(
            cls.normalize_currency(currency),
            Decimal("1"),
        )
        value = rule() if callable(rule) else rule
        return Decimal(value)

    @classmethod
    def calc_credits(cls, currency: CurrencyValue, amount: Decimal) -> Decimal:
        converter = cls.get_credits_converters_map().get(cls.normalize_currency(currency))
        if converter is None:
            raise KeyError(cls.normalize_currency(currency))
        value = converter(amount) if callable(converter) else Decimal(converter) * amount
        return Decimal(value).quantize(Decimal("0.000001"))
