"""Every agent output is validated against these schemas."""
from typing import Literal

from pydantic import BaseModel, Field


class Note(BaseModel):
    kind: Literal["requirement", "change", "constraint", "decision", "open_question", "out_of_scope_hint"]
    text: str
    quote: str = Field(description="Exact words from the transcript that support this note")
    speaker: str = ""


class Notes(BaseModel):
    notes: list[Note]


class ScopeItem(BaseModel):
    id: str = Field(description="Stable id like S1, S2. Reuse existing ids when updating a baseline.")
    title: str
    description: str = Field(description="Precise, testable description a developer can build from")
    acceptance_criteria: list[str]
    assumptions: list[str] = []
    evidence: str = Field(description="Quote from the client that justifies this item")
    status: Literal["new", "unchanged", "changed", "removed"] = "new"
    change_summary: str = ""


class Scope(BaseModel):
    items: list[ScopeItem]
    questions_for_client: list[str] = Field(description="What a senior consultant would still ask")


class Fit(BaseModel):
    item_id: str
    solution: Literal["existing_setting", "partial_setting", "custom_dev"]
    how: str = Field(description="Menu path / setting name if a setting helps, else why custom work is needed")
    sources: list[str] = []


class EstTask(BaseModel):
    scope_item_id: str
    title: str
    role: Literal["frontend", "backend", "design", "qa", "pm", "config"]
    hours_low: float
    hours_high: float
    risk: Literal["low", "medium", "high"]
    notes: str = ""


class Estimate(BaseModel):
    tasks: list[EstTask]


class Review(BaseModel):
    ok: bool
    issues: list[str]
