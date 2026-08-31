from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from commercexl.dto.actor import CommerceUserActorDTO

if TYPE_CHECKING:
    from commercexl.models import OrderORM, PaymentORM


class PaymentState(StrEnum):
    """Канонические состояния одной попытки оплаты."""

    CREATED = "created"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    OBSERVED = "observed"
    CONFIRMED = "confirmed"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REVIEW = "review"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"

    @property
    def is_terminal(self) -> bool:
        """Показывает, что state не имеет исходящих lifecycle-переходов."""
        return self in {
            self.EXPIRED,
            self.CANCELLED,
            self.FAILED,
            self.REFUNDED,
        }

    @property
    def occupies_active_slot(self) -> bool:
        """Удерживает единственный lifecycle slot заказа до terminal state."""
        return not self.is_terminal

    @property
    def accepts_checkout_action(self) -> bool:
        """Разрешает provider-у выпустить новое пользовательское checkout action."""
        return self in {
            self.CREATED,
            self.REQUIRES_ACTION,
            self.PROCESSING,
            self.OBSERVED,
            self.CONFIRMED,
        }


class PaymentStateMachine:
    """Проверяет допустимые переходы provider-neutral payment lifecycle."""

    transitions = {
        PaymentState.CREATED: {
            PaymentState.REQUIRES_ACTION,
            PaymentState.PROCESSING,
            PaymentState.PAID,
            PaymentState.CANCELLED,
            PaymentState.FAILED,
            PaymentState.REVIEW,
        },
        PaymentState.REQUIRES_ACTION: {
            PaymentState.PROCESSING,
            PaymentState.OBSERVED,
            PaymentState.CONFIRMED,
            PaymentState.PAID,
            PaymentState.EXPIRED,
            PaymentState.CANCELLED,
            PaymentState.FAILED,
            PaymentState.REVIEW,
        },
        PaymentState.PROCESSING: {
            PaymentState.OBSERVED,
            PaymentState.CONFIRMED,
            PaymentState.PAID,
            PaymentState.EXPIRED,
            PaymentState.CANCELLED,
            PaymentState.FAILED,
            PaymentState.REVIEW,
        },
        PaymentState.OBSERVED: {
            PaymentState.CONFIRMED,
            PaymentState.PAID,
            PaymentState.EXPIRED,
            PaymentState.FAILED,
            PaymentState.REVIEW,
        },
        PaymentState.CONFIRMED: {
            PaymentState.PAID,
            PaymentState.FAILED,
            PaymentState.REVIEW,
        },
        PaymentState.PAID: {
            PaymentState.REFUND_PENDING,
            PaymentState.REFUNDED,
        },
        PaymentState.REFUND_PENDING: {
            PaymentState.REFUNDED,
            PaymentState.PAID,
        },
        PaymentState.REVIEW: {
            PaymentState.OBSERVED,
            PaymentState.CONFIRMED,
            PaymentState.PAID,
            PaymentState.FAILED,
            PaymentState.CANCELLED,
            PaymentState.EXPIRED,
        },
    }

    @classmethod
    def can_transition(cls, current: PaymentState, target: PaymentState) -> bool:
        """Разрешает идемпотентный повтор либо явно описанный переход."""
        return current == target or target in cls.transitions.get(current, set())


class CheckoutAction(BaseModel):
    """Расширяемое действие, которое checkout должен показать пользователю."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str = Field(min_length=1, max_length=50)
    uri: str | None = Field(default=None, max_length=4000, repr=False)
    expires_at: datetime | None = None
    payload: dict[str, JsonValue] = Field(default_factory=dict, repr=False)

    @field_validator("kind", mode="before")
    @classmethod
    def normalize_kind(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Checkout action kind is required.")
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_action(self) -> CheckoutAction:
        """Проверяет известные action kinds без provider-specific union в core."""
        if self.expires_at is not None and self.expires_at.utcoffset() is None:
            raise ValueError("Checkout action expiry must be timezone-aware.")
        if self.kind == "completed":
            if self.uri is not None or self.expires_at is not None:
                raise ValueError("Completed checkout action cannot contain URI or expiry.")
            return self
        if self.kind == "processing" and self.uri is not None:
            raise ValueError("Processing checkout action cannot contain URI.")
        if self.kind == "manual" and self.uri is None and not self.payload:
            raise ValueError("Manual checkout action requires URI or payload instructions.")
        if self.kind not in {"manual", "processing"} and self.uri is None:
            raise ValueError(f"Checkout action '{self.kind}' requires a URI.")
        if self.kind == "redirect" and self.uri is not None and not self.uri.startswith(("https://", "http://")):
            raise ValueError("Redirect checkout action requires an HTTP URL.")
        return self


class PaymentOption(BaseModel):
    """Опубликованный provider-neutral вариант оплаты конкретного заказа."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    action_kind: str = Field(min_length=1, max_length=50)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("id", "label", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Payment option text fields cannot be empty.")
        return value.strip()

    @field_validator("action_kind", mode="before")
    @classmethod
    def normalize_action_kind(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Payment option action kind is required.")
        return value.strip().lower()


class PaymentOptionDTO(PaymentOption):
    """Публичный вариант оплаты с проверенной identity провайдера."""

    payment_system: str
    provider_kind: str


class PaymentVerificationResult(BaseModel):
    """Результат проверки, отмены или возврата, применяемый только core runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: PaymentState
    evidence_key: str | None = Field(default=None, min_length=1, max_length=255)
    reason_code: str | None = Field(default=None, max_length=100)
    evidence: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_state(self) -> PaymentVerificationResult:
        """Не позволяет провайдеру вернуть внутреннее начальное состояние."""
        if self.state == PaymentState.CREATED:
            raise ValueError("Verification result cannot target the created state.")
        if self.state in {
            PaymentState.OBSERVED,
            PaymentState.CONFIRMED,
            PaymentState.PAID,
            PaymentState.REFUNDED,
        } and self.evidence_key is None:
            raise ValueError(f"{self.state.value} verification requires an evidence key.")
        return self


@dataclass(frozen=True)
class PaymentCreateContext:
    """Передаёт провайдеру только server-validated checkout data."""

    actor: CommerceUserActorDTO
    order: OrderORM
    payment: PaymentORM
    option: PaymentOptionDTO
    public_base_url: str | None
    idempotency_key: str


@dataclass(frozen=True)
class PaymentCreateResult:
    """Возвращает canonical checkout action и необязательный синхронный verdict."""

    action: CheckoutAction
    verification: PaymentVerificationResult | None = None
