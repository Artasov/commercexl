from __future__ import annotations

from decimal import Decimal

import pytest

from commercexl import BaseConfig


def test_base_config_accepts_string_currency_keys():
    class DynamicConfig(BaseConfig):
        PAYMENT_SYSTEMS = {"BTC": ("handmade",)}
        MIN_TOP_UP_AMOUNTS = {"BTC": Decimal("0.001")}
        CREDITS_CONVERTERS = {"BTC": lambda amount: amount * Decimal("500000")}

    DynamicConfig.validate()

    assert DynamicConfig.get_currency_codes() == ("BTC",)
    assert DynamicConfig.get_min_top_up_amount("btc") == Decimal("0.001")
    assert DynamicConfig.calc_credits("btc", Decimal("2")) == Decimal("1000000.000000")


def test_base_config_requires_at_least_one_currency():
    class EmptyConfig(BaseConfig):
        PAYMENT_SYSTEMS = {}
        MIN_TOP_UP_AMOUNTS = {}
        CREDITS_CONVERTERS = {}

    with pytest.raises(TypeError) as exc_info:
        EmptyConfig.validate()

    assert str(exc_info.value) == "EmptyConfig.PAYMENT_SYSTEMS must contain at least one currency."
