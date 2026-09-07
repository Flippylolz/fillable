"""Persisted editor review, distinct from asynchronous detection proposals."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.fields.schema import Identity, StrictModel
from app.fields.validation import MODEL_TEXT

Property = Annotated[str, Field(max_length=MODEL_TEXT)]


class WorkingSpan(StrictModel):
    kind: Literal["span"]
    start: int = Field(alias="from", strict=True, ge=0, le=2 * MODEL_TEXT + 200000)
    end: int = Field(alias="to", strict=True, ge=0, le=2 * MODEL_TEXT + 200000)
    text: str = Field(max_length=65536)


class WorkingControl(StrictModel):
    kind: Literal["control"]
    id: Identity


class WorkingItem(StrictModel):
    id: Identity
    occurrence_id: Identity = Field(alias="occurrenceId")
    reason: Literal[
        "native_control", "placeholder", "blank_line", "blank_cell", "manual"
    ]
    source_key: Property | None = Field(alias="sourceKey")
    context: str = Field(max_length=1024)
    label: Property
    key: Property
    type: Literal["text"]
    decision: Literal["proposed", "accepted", "dismissed"]
    missing: bool = Field(strict=True)
    location: Annotated[WorkingSpan | WorkingControl, Field(discriminator="kind")]

    @model_validator(mode="after")
    def shape(self):
        control = isinstance(self.location, WorkingControl)
        if control != (self.decision == "accepted"):
            raise ValueError("invalid_working_decision")
        if not control and self.reason in {"native_control", "manual"}:
            raise ValueError("invalid_working_origin")
        return self


class WorkingReview(StrictModel):
    source_version: UUID | None = Field(alias="sourceVersion")
    items: list[WorkingItem] = Field(max_length=2000)

    @model_validator(mode="after")
    def identities(self):
        if len({item.id for item in self.items}) != len(self.items) or len(
            {item.occurrence_id for item in self.items}
        ) != len(self.items):
            raise ValueError("duplicate_working_identity")
        if self.source_version is None and any(
            item.reason not in {"native_control", "manual"} for item in self.items
        ):
            raise ValueError("unbound_working_origin")
        return self
