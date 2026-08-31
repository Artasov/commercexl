from pydantic import BaseModel, ConfigDict, Field


class CreatePaymentAttemptRequest(BaseModel):
    """Выбирает только opaque server-published payment option."""

    model_config = ConfigDict(extra="forbid")

    payment_option_id: str = Field(min_length=1, max_length=200)
