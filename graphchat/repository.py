from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import Edge, Node, QuizItem, SessionOut


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create_session(self, topic: str) -> SessionOut:
        sid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            "INSERT INTO sessions(id, topic, created_at) VALUES(?, ?, ?)",
            (sid, topic, created_at),
        )
        self.conn.commit()
        return SessionOut(id=sid, topic=topic, created_at=created_at)

    def list_sessions(self, limit: int = 50) -> list[SessionOut]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [SessionOut(**dict(r)) for r in rows]

    def list_nodes(self, session_id: str) -> list[Node]:
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        ).fetchall()
        out: list[Node] = []
        for r in rows:
            data = dict(r)
            if data.get("width") is None or float(data.get("width", 0) or 0) <= 0:
                data["width"] = 260.0
            out.append(Node(**data))
        return out

    def list_edges(self, session_id: str) -> list[Edge]:
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE session_id = ? ORDER BY created_at ASC", (session_id,)
        ).fetchall()
        return [Edge(**dict(r)) for r in rows]

    def create_node(
        self,
        session_id: str,
        title: str,
        content: str,
        mastery: float,
        importance: float,
        x: float,
        y: float,
        width: float,
        node_type: str,
    ) -> Node:
        nid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            """
            INSERT INTO nodes(id, session_id, title, content, mastery, importance, x, y, width, node_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (nid, session_id, title, content, mastery, importance, x, y, width, node_type, created_at),
        )
        self.conn.commit()
        return Node(
            id=nid,
            session_id=session_id,
            title=title,
            content=content,
            mastery=mastery,
            importance=importance,
            x=x,
            y=y,
            width=width,
            node_type=node_type,  # type: ignore[arg-type]
            created_at=created_at,
        )

    def create_edge(
        self,
        session_id: str,
        source_node_id: str,
        target_node_id: str,
        question: str,
        source_section_key: str | None,
        strength: float,
        edge_type: str,
    ) -> Edge:
        eid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            """
            INSERT INTO edges(id, session_id, source_node_id, target_node_id, question, source_section_key, strength, edge_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (eid, session_id, source_node_id, target_node_id, question, source_section_key, strength, edge_type, created_at),
        )
        self.conn.commit()
        return Edge(
            id=eid,
            session_id=session_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            question=question,
            source_section_key=source_section_key,
            strength=strength,
            edge_type=edge_type,  # type: ignore[arg-type]
            created_at=created_at,
        )

    def get_nodes_by_ids(self, session_id: str, node_ids: list[str]) -> list[Node]:
        if not node_ids:
            return []
        placeholders = ",".join("?" for _ in node_ids)
        rows = self.conn.execute(
            f"SELECT * FROM nodes WHERE session_id = ? AND id IN ({placeholders})",
            (session_id, *node_ids),
        ).fetchall()
        out: list[Node] = []
        for r in rows:
            data = dict(r)
            if data.get("width") is None or float(data.get("width", 0) or 0) <= 0:
                data["width"] = 260.0
            out.append(Node(**data))
        return out

    def update_node_position(self, session_id: str, node_id: str, x: float, y: float, width: float | None = None) -> None:
        if width is None:
            self.conn.execute(
                "UPDATE nodes SET x = ?, y = ? WHERE session_id = ? AND id = ?",
                (x, y, session_id, node_id),
            )
        else:
            self.conn.execute(
                "UPDATE nodes SET x = ?, y = ?, width = ? WHERE session_id = ? AND id = ?",
                (x, y, width, session_id, node_id),
            )
        self.conn.commit()

    def update_node_mastery(self, session_id: str, node_id: str, mastery: float) -> None:
        self.conn.execute(
            "UPDATE nodes SET mastery = ? WHERE session_id = ? AND id = ?",
            (mastery, session_id, node_id),
        )
        self.conn.commit()

    def update_node_content(self, session_id: str, node_id: str, title: str, content: str) -> None:
        self.conn.execute(
            "UPDATE nodes SET title = ?, content = ? WHERE session_id = ? AND id = ?",
            (title, content, session_id, node_id),
        )
        self.conn.commit()

    def add_material(self, session_id: str, filename: str, mime_type: str, content_text: str) -> str:
        mid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            "INSERT INTO materials(id, session_id, filename, mime_type, content_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, session_id, filename, mime_type, content_text, created_at),
        )
        self.conn.commit()
        return mid

    def get_material_context(self, session_id: str, max_chars: int = 4000) -> str:
        rows = self.conn.execute(
            "SELECT filename, content_text FROM materials WHERE session_id = ? ORDER BY created_at DESC LIMIT 5",
            (session_id,),
        ).fetchall()
        pieces: list[str] = []
        for r in rows:
            pieces.append(f"[{r['filename']}]\n{r['content_text']}")
        ctx = "\n\n".join(pieces)
        return ctx[:max_chars]

    def save_review(self, session_id: str, summary: str, gaps: list[str], actions: list[str]) -> None:
        rid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            "INSERT INTO reviews(id, session_id, summary, gaps_json, actions_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (rid, session_id, summary, json.dumps(gaps), json.dumps(actions), created_at),
        )
        self.conn.commit()

    def create_quiz_item(
        self,
        session_id: str,
        question: str,
        answer: str,
        related_node_id: str,
        difficulty: str,
    ) -> QuizItem:
        qid = str(uuid.uuid4())
        created_at = _now_iso()
        self.conn.execute(
            "INSERT INTO quizzes(id, session_id, question, answer, related_node_id, difficulty, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (qid, session_id, question, answer, related_node_id, difficulty, created_at),
        )
        self.conn.commit()
        return QuizItem(
            quiz_id=qid,
            question=question,
            answer=answer,
            related_node_id=related_node_id,
            difficulty=difficulty,
        )

    def get_quiz_item(self, session_id: str, quiz_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM quizzes WHERE session_id = ? AND id = ?",
            (session_id, quiz_id),
        ).fetchone()
        return dict(row) if row else None
