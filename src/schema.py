from pydantic import BaseModel, Field, field_validator
from typing import Optional
import time

class Event(BaseModel):
    sensor_id: str = Field(min_length=1)
    ts: float = Field(description="Unix timestamp seconds")
    value: float
    temperature: Optional[float] = None
    status: Optional[str] = Field(default="OK")

    @field_validator("ts")
    @classmethod
    def ts_reasonable(cls, v: float) -> float:
        # Basic sanity: within +/- 1 day of now
        now = time.time()
        if v < now - 86400 or v > now + 86400:
            raise ValueError("timestamp out of acceptable window")
        return v

    @field_validator("status")
    @classmethod
    def status_ok(cls, v: str) -> str:
        allowed = {"OK", "WARN", "FAIL"}
        if v is not None and v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v
