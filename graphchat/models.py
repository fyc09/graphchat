from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeType = Literal["core", "normal", "counterexample", "skeleton", "question"]
EdgeType = Literal["normal", "bridge", "counter", "redirect"]


class SessionOut(BaseModel):
    id: str
    topic: str
    created_at: str


class Node(BaseModel):
    id: str
    session_id: str
    title: str
    content: str
    mastery: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    x: float
    y: float
    width: float = Field(gt=80.0, le=1200.0, default=260.0)
    node_type: NodeType
    created_at: str


class Edge(BaseModel):
    id: str
    session_id: str
    source_node_id: str
    target_node_id: str
    question: str
    source_section_key: str | None = None
    strength: float = Field(ge=0.0, le=1.0)
    edge_type: EdgeType
    created_at: str


class InitSessionIn(BaseModel):
    topic: str = Field(min_length=1, max_length=120)


class InitSessionOut(BaseModel):
    session: SessionOut
    nodes: list[Node]
    edges: list[Edge]


class GraphOut(BaseModel):
    nodes: list[Node]
    edges: list[Edge]


class SelectedSection(BaseModel):
    node_id: str
    title: str
    body: str
    key: str | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    node_ids: list[str] = Field(default_factory=list)
    selected_sections: list[SelectedSection] = Field(default_factory=list)


class AskOut(BaseModel):
    new_nodes: list[Node]
    new_edges: list[Edge]
    redirect_hint: str | None = None
    counterexample: Node | None = None


class UpdatePositionIn(BaseModel):
    x: float
    y: float
    width: float | None = Field(default=None, gt=80.0, le=1200.0)


class UpdateMasteryIn(BaseModel):
    mastery: float = Field(ge=0.0, le=1.0)


class ReviewOut(BaseModel):
    summary: str
    gaps: list[str]
    actions: list[str]


class QuizGenerateIn(BaseModel):
    count: int = Field(default=3, ge=1, le=10)


class QuizItem(BaseModel):
    quiz_id: str
    question: str
    answer: str
    related_node_id: str
    difficulty: str


class QuizGenerateOut(BaseModel):
    items: list[QuizItem]


class QuizGradeIn(BaseModel):
    quiz_id: str
    user_answer: str = Field(min_length=1, max_length=1200)


class QuizGradeOut(BaseModel):
    correct: bool
    feedback: str
    mastery_delta: float
