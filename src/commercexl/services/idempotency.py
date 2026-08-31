from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from commercexl.money import Money


class Idempotency:
    """Нормализует ключ и строит стабильный fingerprint операции."""

    max_key_length = 200

    @classmethod
    def normalize_key(cls, value: str) -> str:
        """Проверяет обязательный непробельный idempotency key."""
        if not isinstance(value, str):
            raise ValueError("Idempotency key must be a string.")
        key = value.strip()
        if not key:
            raise ValueError("Idempotency key is required.")
        if len(key) > cls.max_key_length:
            raise ValueError(f"Idempotency key cannot exceed {cls.max_key_length} characters.")
        return key

    @classmethod
    def fingerprint(cls, payload: Any) -> str:
        """Хеширует canonical JSON без хранения чувствительного request payload."""
        canonical = json.dumps(
            cls.normalize_value(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def normalize_value(cls, value: Any) -> Any:
        """Преобразует поддерживаемые типы в детерминированное JSON-значение."""
        if isinstance(value, BaseModel):
            return cls.normalize_value(value.model_dump(mode="python"))
        if isinstance(value, dict):
            return {str(key): cls.normalize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.normalize_value(item) for item in value]
        if isinstance(value, Decimal):
            return Money.serialize(value)
        if isinstance(value, (UUID, Enum)):
            return str(value.value if isinstance(value, Enum) else value)
        if value is None or isinstance(value, (str, int, bool)):
            return value
        raise TypeError(f"Unsupported idempotency payload type: {type(value).__name__}.")
