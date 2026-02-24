from __future__ import annotations

from collections.abc import Generator
from typing import Any

from ..llm_client import LlmClient
from ..models import AskOut, Edge, Node, SessionOut
from ..repository import Repository


class GraphService:
    def __init__(self, repo: Repository, llm: LlmClient) -> None:
        self.repo = repo
        self.llm = llm

    def init_session(self, topic: str) -> tuple[SessionOut, list[Node], list[Edge]]:
        session = self.repo.create_session(topic)
        content = self._generate_topic_description(topic)
        center = self.repo.create_node(
            session_id=session.id,
            title=topic,
            content=content,
            mastery=0.2,
            importance=1.0,
            x=0.0,
            y=0.0,
            width=320.0,
            node_type="core",
        )
        return session, [center], []

    def init_session_stream(self, topic: str) -> Generator[str, None, tuple[SessionOut, list[Node], list[Edge]]]:
        session = self.repo.create_session(topic)
        system_prompt, user_prompt = self._init_prompts(topic)
        content = ""
        for chunk in self.llm.stream_text_completion(system_prompt, user_prompt):
            content += chunk
            yield chunk
        content = content.strip()
        if not content:
            raise ValueError("LLM returned empty content for initial topic description.")
        center = self.repo.create_node(
            session_id=session.id,
            title=topic,
            content=content,
            mastery=0.2,
            importance=1.0,
            x=0.0,
            y=0.0,
            width=320.0,
            node_type="core",
        )
        return session, [center], []

    def _generate_topic_description(self, topic: str) -> str:
        system_prompt, user_prompt = self._init_prompts(topic)
        system_prompt = (
            "You are a learning content generator. "
            "Return JSON with a single field: content. "
            f"{system_prompt}"
        )
        raw = self.llm.json_completion(system_prompt, user_prompt)
        content = str(raw.get("content", "")).strip()
        if not content:
            raise ValueError("LLM returned empty content for initial topic description.")
        return content

    @staticmethod
    def _init_prompts(topic: str) -> tuple[str, str]:
        system_prompt = (
            "The content must be organized as Markdown sections using '## Title'. "
            "Provide 3-6 sections, and each section can contain 1-3 short paragraphs and examples. "
            "When formulas are useful, prefer LaTeX math notation ($...$ or $$...$$)."
        )
        user_prompt = f"Topic: {topic}\nGenerate a complete introductory explanation."
        return system_prompt, user_prompt

    def ask(
        self,
        session_id: str,
        question: str,
        node_ids: list[str],
        selected_sections: list[dict[str, Any]] | None = None,
    ) -> AskOut:
        selected_sections = selected_sections or []
        selected_nodes = self.repo.get_nodes_by_ids(session_id, node_ids)
        section_node_ids = [str(s.get("node_id", "")) for s in selected_sections if s.get("node_id")]
        section_nodes = self.repo.get_nodes_by_ids(session_id, section_node_ids)
        context_nodes = {n.id: n for n in selected_nodes}
        context_nodes.update({n.id: n for n in section_nodes})
        node_desc = "\n".join([f"- {n.title}: {n.content}" for n in context_nodes.values()])
        section_desc = "\n".join(
            [f"- ({s.get('node_id')}) {s.get('title')}: {s.get('body')}" for s in selected_sections]
        )
        graph_nodes = self.repo.list_nodes(session_id)
        graph_edges = self.repo.list_edges(session_id)
        material_context = self.repo.get_material_context(session_id)

        system_prompt = (
            "You are a knowledge graph tutor. Return JSON with fields: "
            "nodes, edges, redirect_hint, counterexample. "
            "Each node has title, content, importance, mastery, node_type. "
            "Each edge has source_ref, target_ref, question, strength, edge_type. "
            "Node content must be sectioned Markdown using '## Title' headings. "
            "When formulas are useful, prefer LaTeX math notation ($...$ or $$...$$). "
            "source_ref/target_ref can reference selected:N or new:N."
        )
        user_prompt = (
            f"User question: {question}\n"
            f"Selected nodes:\n{node_desc}\n"
            f"Selected sections:\n{section_desc}\n"
            f"Graph stats: nodes={len(graph_nodes)}, edges={len(graph_edges)}\n"
            f"Reference materials:\n{material_context}"
        )
        raw = self.llm.json_completion(system_prompt, user_prompt)
        new_nodes_raw = raw.get("nodes", [])
        new_edges_raw = raw.get("edges", [])

        new_nodes: list[Node] = []
        for idx, item in enumerate(new_nodes_raw):
            nn = self.repo.create_node(
                session_id=session_id,
                title=str(item.get("title", "Untitled Node")),
                content=str(item.get("content", "")),
                mastery=self._clamp(item.get("mastery", 0.3), 0.0, 1.0, 0.3),
                importance=self._clamp(item.get("importance", 0.6), 0.0, 1.0, 0.6),
                x=180.0 + 80.0 * idx,
                y=-120.0 + 120.0 * idx,
                width=242.0,
                node_type=self._safe_node_type(item.get("node_type", "normal")),
            )
            new_nodes.append(nn)

        id_ref = {f"selected:{i}": n.id for i, n in enumerate(selected_nodes)}
        id_ref.update({f"new:{i}": n.id for i, n in enumerate(new_nodes)})

        new_edges: list[Edge] = []
        for item in new_edges_raw:
            source_id = id_ref.get(str(item.get("source_ref", "")))
            target_id = id_ref.get(str(item.get("target_ref", "")))
            if not source_id or not target_id:
                continue
            edge = self.repo.create_edge(
                session_id=session_id,
                source_node_id=source_id,
                target_node_id=target_id,
                question=str(item.get("question", "How are these connected?")),
                source_section_key=None,
                strength=self._clamp(item.get("strength", 0.6), 0.0, 1.0, 0.6),
                edge_type=self._safe_edge_type(item.get("edge_type", "normal")),
            )
            new_edges.append(edge)

        counter = raw.get("counterexample")
        counter_node = None
        if isinstance(counter, dict):
            counter_node = self.repo.create_node(
                session_id=session_id,
                title=str(counter.get("title", "Counterexample")),
                content=str(counter.get("content", "")),
                mastery=0.2,
                importance=0.6,
                x=220.0,
                y=-160.0,
                width=242.0,
                node_type="counterexample",
            )
            if selected_nodes:
                new_edges.append(
                    self.repo.create_edge(
                        session_id=session_id,
                        source_node_id=counter_node.id,
                        target_node_id=selected_nodes[0].id,
                        question=str(counter.get("question", "Would this still hold if conditions change?")),
                        source_section_key=None,
                        strength=0.7,
                        edge_type="counter",
                    )
                )

        return AskOut(
            new_nodes=new_nodes,
            new_edges=new_edges,
            redirect_hint=raw.get("redirect_hint"),
            counterexample=counter_node,
        )

    def ask_stream(
        self,
        session_id: str,
        question: str,
        node_ids: list[str],
        selected_sections: list[dict[str, Any]] | None = None,
    ) -> Generator[dict[str, Any], None, AskOut]:
        selected_sections = selected_sections or []
        selected_nodes = self.repo.get_nodes_by_ids(session_id, node_ids)
        section_node_ids = [str(s.get("node_id", "")) for s in selected_sections if s.get("node_id")]
        section_nodes = self.repo.get_nodes_by_ids(session_id, section_node_ids)
        context_nodes = {n.id: n for n in selected_nodes}
        context_nodes.update({n.id: n for n in section_nodes})
        node_desc = "\n".join([f"- {n.title}: {n.content}" for n in context_nodes.values()])
        section_desc = "\n".join(
            [f"- ({s.get('node_id')}) {s.get('title')}: {s.get('body')}" for s in selected_sections]
        )
        material_context = self.repo.get_material_context(session_id)

        system_prompt = (
            "You are a knowledge graph tutor. "
            "Answer in Markdown with '## Title' sections. "
            "Each section may include 1-3 short paragraphs and examples. "
            "When formulas are useful, prefer LaTeX math notation ($...$ or $$...$$). "
            "Do not return JSON."
        )
        user_prompt = (
            f"User question: {question}\n"
            f"Selected nodes:\n{node_desc}\n"
            f"Selected sections:\n{section_desc}\n"
            f"Reference materials:\n{material_context}"
        )

        question_node = self.repo.create_node(
            session_id=session_id,
            title="Question",
            content=question.strip(),
            mastery=0.3,
            importance=0.7,
            x=180.0,
            y=-80.0,
            width=242.0,
            node_type="question",
        )
        answer_node = self.repo.create_node(
            session_id=session_id,
            title="Answer",
            content="",
            mastery=0.3,
            importance=0.7,
            x=520.0,
            y=-80.0,
            width=242.0,
            node_type="normal",
        )

        edge_specs: list[tuple[str, str | None]] = []
        seen: set[tuple[str, str | None]] = set()
        for src in selected_nodes:
            key = (src.id, None)
            if key not in seen:
                seen.add(key)
                edge_specs.append(key)
        for sec in selected_sections:
            src_id = str(sec.get("node_id", ""))
            sec_key = sec.get("key")
            if not src_id:
                continue
            key = (src_id, str(sec_key) if sec_key else None)
            if key not in seen:
                seen.add(key)
                edge_specs.append(key)

        edges: list[Edge] = []
        edge_type = "bridge" if len(edge_specs) > 1 else "normal"
        for src_id, src_section_key in edge_specs:
            edges.append(
                self.repo.create_edge(
                    session_id=session_id,
                    source_node_id=src_id,
                    target_node_id=question_node.id,
                    question=question,
                    source_section_key=src_section_key,
                    strength=0.65,
                    edge_type=edge_type,
                )
            )
        edges.append(
            self.repo.create_edge(
                session_id=session_id,
                source_node_id=question_node.id,
                target_node_id=answer_node.id,
                question=question,
                source_section_key=None,
                strength=0.75,
                edge_type="normal",
            )
        )

        yield {
            "type": "start",
            "nodes": [question_node, answer_node],
            "question_node_id": question_node.id,
            "answer_node_id": answer_node.id,
            "edges": edges,
        }

        content = ""
        for chunk in self.llm.stream_text_completion(system_prompt, user_prompt):
            content += chunk
            yield {"type": "token", "content": chunk}

        title = self._guess_title(content, question)
        final_content = content.strip()
        self.repo.update_node_content(
            session_id=session_id, node_id=answer_node.id, title=title, content=final_content
        )
        answer_node.title = title
        answer_node.content = final_content
        return AskOut(new_nodes=[question_node, answer_node], new_edges=edges, redirect_hint=None, counterexample=None)

    @staticmethod
    def _clamp(value: object, min_v: float, max_v: float, fallback: float) -> float:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return fallback
        if num < min_v:
            return min_v
        if num > max_v:
            return max_v
        return num

    @staticmethod
    def _safe_node_type(value: object) -> str:
        allowed = {"core", "normal", "counterexample", "skeleton", "question"}
        text = str(value)
        return text if text in allowed else "normal"

    @staticmethod
    def _safe_edge_type(value: object) -> str:
        allowed = {"normal", "bridge", "counter", "redirect"}
        text = str(value)
        return text if text in allowed else "normal"

    @staticmethod
    def _guess_title(content: str, fallback: str) -> str:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("## "):
                return line[3:].strip()[:40] or fallback[:40]
        return fallback[:40] or "Answer"
