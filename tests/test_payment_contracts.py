from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from commercexl import (
    __version__,
    AbstractPaymentService,
    CheckoutAction,
    CommerceBase,
    Money,
    PaymentCreateContext,
    PaymentCreateResult,
    PaymentOption,
    PaymentProviderRegistration,
    PaymentState,
    PaymentVerificationResult,
)
from commercexl.dto import ProductPriceDTO
from commercexl.models import OrderORM, PaymentORM
from commercexl.payment import PaymentStateMachine
from commercexl.schemas import CreateOrderRequest, CreatePaymentAttemptRequest
from commercexl.services.idempotency import Idempotency


def test_public_provider_contract_imports_are_stable():
    assert __version__ == "0.3.1"
    assert CommerceBase is not None
    assert AbstractPaymentService is not None
    assert PaymentCreateContext is not None
    assert PaymentCreateResult is not None
    assert PaymentOption is not None
    assert PaymentVerificationResult is not None
    assert PaymentProviderRegistration is not None


def test_money_contract_accepts_decimal_string_and_never_serializes_float():
    price = ProductPriceDTO(
        id=1,
        product=2,
        currency="USD",
        amount=Decimal("123.450000"),
    )

    assert price.model_dump(mode="json")["amount"] == "123.45"
    assert Money.parse("0.000001") == Decimal("0.000001")
    with pytest.raises(ValueError, match="decimal string"):
        Money.parse(0.1)
    with pytest.raises(ValueError, match="at most 6"):
        Money.parse("0.0000001")


def test_idempotency_key_rejects_non_string_values():
    with pytest.raises(ValueError, match="must be a string"):
        Idempotency.normalize_key(None)  # type: ignore[arg-type]


def test_http_money_input_rejects_json_number():
    accepted = CreateOrderRequest.model_validate({"product": 1, "currency": "USD", "requested_amount": "10.25"})
    assert accepted.requested_amount == Decimal("10.25")

    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate({"product": 1, "currency": "USD", "requested_amount": 10.25})


def test_order_request_requires_unambiguous_product_selection():
    with pytest.raises(ValidationError, match="Exactly one"):
        CreateOrderRequest.model_validate({"currency": "USD"})
    with pytest.raises(ValidationError, match="Exactly one"):
        CreateOrderRequest.model_validate({"product": 1, "products": [{"product": 2}], "currency": "USD"})


def test_payment_attempt_request_accepts_only_published_option_id():
    accepted = CreatePaymentAttemptRequest.model_validate({"payment_option_id": "solana:usdc"})
    assert accepted.payment_option_id == "solana:usdc"

    with pytest.raises(ValidationError):
        CreatePaymentAttemptRequest.model_validate({
            "payment_option_id": "solana:usdc",
            "amount": "1",
            "currency": "USD",
            "payment_system": "solana",
        })


def test_checkout_action_validates_known_shapes_and_aware_expiry():
    action = CheckoutAction(
        kind="transaction_request",
        uri="solana:https://commerce.example.com/transaction/capability",
        expires_at=datetime.now(UTC),
    )
    assert action.kind == "transaction_request"

    with pytest.raises(ValidationError):
        CheckoutAction(kind="transaction_request")
    with pytest.raises(ValidationError):
        CheckoutAction(kind="solana_transaction_request")
    with pytest.raises(ValidationError):
        CheckoutAction(kind="manual")
    with pytest.raises(ValidationError):
        CheckoutAction(kind="completed", uri="https://commerce.example.com")
    with pytest.raises(ValidationError):
        CheckoutAction(kind="wallet", uri="solana:abc", expires_at=datetime.now())


def test_verification_requires_unique_evidence_for_paid_result():
    with pytest.raises(ValidationError, match="requires an evidence key"):
        PaymentVerificationResult(state=PaymentState.PAID)

    result = PaymentVerificationResult(
        state=PaymentState.PAID,
        evidence_key="signature:instruction-index",
        evidence={"signature": "safe-digest"},
    )
    assert result.evidence_key == "signature:instruction-index"


def test_payment_state_terminal_and_active_slot_contract_is_coherent():
    assert PaymentState.FAILED.is_terminal
    assert PaymentState.REFUNDED.is_terminal
    assert not PaymentState.PAID.is_terminal
    assert PaymentStateMachine.can_transition(PaymentState.PAID, PaymentState.REFUND_PENDING)
    assert not PaymentStateMachine.can_transition(PaymentState.PAID, PaymentState.REVIEW)
    assert not PaymentStateMachine.can_transition(PaymentState.FAILED, PaymentState.REVIEW)

    for state in PaymentState:
        assert state.occupies_active_slot is not state.is_terminal


def test_provisional_confirmation_can_expire_before_final_settlement():
    assert PaymentStateMachine.can_transition(PaymentState.CONFIRMED, PaymentState.EXPIRED)
    assert not PaymentStateMachine.can_transition(PaymentState.CONFIRMED, PaymentState.CANCELLED)


def test_canonical_models_have_no_legacy_flags_or_persisted_checkout_capability():
    for legacy_name in ("is_created", "is_paid", "is_cancelled", "is_refunded", "is_executed"):
        assert not hasattr(OrderORM, legacy_name)
    for secret_name in ("action_uri", "action_payload", "payment_url"):
        assert not hasattr(PaymentORM, secret_name)
