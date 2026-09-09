"""Version-bound text-field proposals; all labels and values remain user data."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identity = Annotated[str, Field(min_length=1, max_length=1024)]
Offset = Annotated[int, Field(strict=True, ge=0, le=50 * 1024 * 1024)]
FieldType = Literal["text", "number", "date"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ControlAnchor(StrictModel):
    kind: Literal["control"]
    part: Identity
    paragraph_id: Identity
    control_id: Identity


class SpanAnchor(StrictModel):
    kind: Literal["span"]
    part: Identity
    paragraph_id: Identity
    start: Offset
    end: Offset

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("invalid_field_range")
        return self


Anchor = Annotated[ControlAnchor | SpanAnchor, Field(discriminator="kind")]


class Occurrence(StrictModel):
    id: Identity
    anchor: Anchor
    value: str = Field(max_length=65536)


class TextField(StrictModel):
    id: Identity
    type: FieldType = "text"
    label: str = Field(max_length=512)
    occurrence_ids: list[Identity] = Field(min_length=1, max_length=2000)


class Candidate(StrictModel):
    id: Identity
    occurrence_id: Identity
    label: str = Field(max_length=512)
    source_key: str | None = Field(default=None, max_length=512)
    reason: Literal[
        "native_control", "placeholder", "blank_line", "blank_cell", "manual"
    ]
    context: str = Field(max_length=1024)
    # Proposed fill-time kind; absent in payloads saved before typed proposals.
    type: FieldType = "text"


class ReviewDecision(StrictModel):
    candidate_id: Identity
    status: Literal["accepted", "dismissed"]
    field_id: Identity | None = None

    @model_validator(mode="after")
    def assigned(self):
        if (self.status == "accepted") != (self.field_id is not None):
            raise ValueError("invalid_review_assignment")
        return self


class FieldSnapshot(StrictModel):
    schema_version: int = Field(default=1, strict=True, ge=1, le=1)
    source_version_id: UUID
    fields: list[TextField] = Field(default_factory=list, max_length=2000)
    occurrences: list[Occurrence] = Field(default_factory=list, max_length=2000)
    candidates: list[Candidate] = Field(default_factory=list, max_length=2000)
    decisions: list[ReviewDecision] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def references(self):
        for items in (self.fields, self.occurrences, self.candidates):
            if len({item.id for item in items}) != len(items):
                raise ValueError("duplicate_field_identity")
        occurrences = {item.id for item in self.occurrences}
        fields = {item.id: item for item in self.fields}
        candidates = {item.id: item for item in self.candidates}
        assigned = [
            identity for field in self.fields for identity in field.occurrence_ids
        ]
        if len(set(assigned)) != len(assigned) or not set(assigned) <= occurrences:
            raise ValueError("invalid_field_occurrences")
        proposed = [candidate.occurrence_id for candidate in self.candidates]
        if len(set(proposed)) != len(proposed) or not set(proposed) <= occurrences:
            raise ValueError("invalid_candidate_occurrence")
        anchors = {item.id: item.anchor for item in self.occurrences}
        for candidate in self.candidates:
            anchor = anchors[candidate.occurrence_id]
            if (
                candidate.reason == "native_control"
                and not isinstance(anchor, ControlAnchor)
            ) or (
                candidate.reason in {"placeholder", "blank_line", "blank_cell"}
                and not isinstance(anchor, SpanAnchor)
            ):
                raise ValueError("invalid_candidate_anchor")
        if len({item.candidate_id for item in self.decisions}) != len(self.decisions):
            raise ValueError("duplicate_review_decision")
        for decision in self.decisions:
            reviewed = candidates.get(decision.candidate_id)
            if reviewed is None:
                raise ValueError("unknown_review_candidate")
            if decision.status == "accepted":
                field = fields.get(decision.field_id) if decision.field_id else None
                if field is None or reviewed.occurrence_id not in field.occurrence_ids:
                    raise ValueError("invalid_review_field")
            elif reviewed.occurrence_id in assigned:
                raise ValueError("dismissed_field_occurrence")
        return self
