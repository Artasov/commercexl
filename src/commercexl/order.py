from enum import StrEnum


class OrderState(StrEnum):
    """Канонические состояния коммерческого заказа."""

    CREATED = "created"
    READY_FOR_PAYMENT = "ready_for_payment"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class OrderItemState(StrEnum):
    """Канонические состояния позиции заказа."""

    CREATED = "created"
    READY = "ready"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
