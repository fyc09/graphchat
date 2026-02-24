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
        root_content, knowledge_parts = self._split_marked_sections(content)
        center = self.repo.create_node(
            session_id=session.id,
            title=topic,
            content=root_content,
            x=0.0,
            y=0.0,
            width=400.0,
            node_type="core",
        )
        nodes: list[Node] = [center]
        edges: list[Edge] = []
        for idx, part in enumerate(knowledge_parts):
            kn = self.repo.create_node(
                session_id=session.id,
                title=part["title"][:60] or f"Knowledge {idx + 1}",
                content=part["content"],
                x=300.0 + idx * 80.0,
                y=60.0 + idx * 120.0,
                width=400.0,
                node_type="knowledge",
            )
            nodes.append(kn)
            edges.append(
                self.repo.create_edge(
                    session_id=session.id,
                    source_node_id=center.id,
                    target_node_id=kn.id,
                    source_section_key=None,
                    edge_type="direct",
                )
            )
        return session, nodes, edges

    def init_session_stream(self, topic: str) -> Generator[dict[str, Any], None, tuple[SessionOut, list[Node], list[Edge]]]:
        session = self.repo.create_session(topic)
        center = self.repo.create_node(
            session_id=session.id,
            title=topic,
            content="",
            x=0.0,
            y=0.0,
            width=400.0,
            node_type="core",
        )
        yield {"type": "start", "nodes": [center], "edges": [], "root_node_id": center.id}
        system_prompt, user_prompt = self._init_prompts(topic)
        knowledge_nodes: list[Node] = []
        knowledge_edges: list[Edge] = []
        knowledge_order: list[str] = []
        knowledge_bodies: dict[str, list[str]] = {}
        root_parts: list[str] = []
        pending = ""
        current_target_node_id = center.id

        def emit_token(node_id: str, text: str) -> dict[str, Any] | None:
            if not text:
                return None
            if node_id == center.id:
                root_parts.append(text)
            else:
                buf = knowledge_bodies.get(node_id)
                if buf is None:
                    return None
                buf.append(text)
            return {"type": "token", "node_id": node_id, "content": text}

        def handle_line(line_text: str) -> tuple[list[dict[str, Any]], str]:
            events: list[dict[str, Any]] = []
            next_target = current_target_node_id
            line_no_nl = line_text[:-1] if line_text.endswith("\n") else line_text
            stripped = line_no_nl.strip()
            if stripped.startswith("## "):
                heading = stripped[3:].strip()
                if heading.upper().startswith("[KNOWLEDGE]"):
                    ktitle = heading[len("[KNOWLEDGE]") :].strip() or f"Knowledge {len(knowledge_nodes) + 1}"
                    kn = self.repo.create_node(
                        session_id=session.id,
                        title=ktitle[:60],
                        content="",
                        x=center.x + center.width + 180.0 + len(knowledge_nodes) * 22.0,
                        y=center.y + len(knowledge_nodes) * 220.0,
                        width=400.0,
                        node_type="knowledge",
                    )
                    edge = self.repo.create_edge(
                        session_id=session.id,
                        source_node_id=center.id,
                        target_node_id=kn.id,
                        source_section_key=None,
                        edge_type="direct",
                    )
                    knowledge_nodes.append(kn)
                    knowledge_edges.append(edge)
                    knowledge_order.append(kn.id)
                    knowledge_bodies[kn.id] = []
                    print(f"[DEBUG] init knowledge heading detected: node_id={kn.id}, title={ktitle}")
                    events.append({"type": "knowledge_start", "node": kn, "edge": edge})
                    next_target = kn.id
                    token_evt = emit_token(kn.id, f"## {ktitle}\n")
                    if token_evt is not None:
                        events.append(token_evt)
                    return events, next_target
                next_target = center.id
            token_evt = emit_token(next_target, line_text)
            if token_evt is not None:
                events.append(token_evt)
            return events, next_target

        for chunk in self.llm.stream_text_completion(system_prompt, user_prompt):
            pending += chunk
            while True:
                idx = pending.find("\n")
                if idx < 0:
                    break
                full_line = pending[: idx + 1]
                pending = pending[idx + 1 :]
                line_events, current_target_node_id = handle_line(full_line)
                for evt in line_events:
                    yield evt

        if pending:
            final_line_events, current_target_node_id = handle_line(pending)
            for evt in final_line_events:
                yield evt

        root_content = "".join(root_parts).strip()
        if not root_content:
            raise ValueError("LLM returned empty content for initial topic description.")
        self.repo.update_node_content(
            session_id=session.id,
            node_id=center.id,
            title=center.title,
            content=root_content,
        )
        center.content = root_content
        for kn_id in knowledge_order:
            parts = knowledge_bodies.get(kn_id, [])
            if not parts:
                continue
            kn = next((n for n in knowledge_nodes if n.id == kn_id), None)
            if kn is None:
                continue
            content_text = "".join(parts).strip()
            self.repo.update_node_content(
                session_id=session.id,
                node_id=kn.id,
                title=kn.title,
                content=content_text,
            )
            kn.content = content_text
        return session, [center, *knowledge_nodes], knowledge_edges

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
            "When formulas are useful, prefer LaTeX math notation ($...$ or $$...$$). "
            "If a section should become a knowledge-point node, mark its heading as '## [KNOWLEDGE] Title'. "
            "Unmarked sections will be merged into the root node."
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
            "Each node has title, content, node_type. "
            "Each edge has source_ref, target_ref. "
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
                x=180.0 + 80.0 * idx,
                y=-120.0 + 120.0 * idx,
                width=400.0,
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
                source_section_key=None,
                edge_type="direct",
            )
            new_edges.append(edge)

        counter = raw.get("counterexample")
        counter_node = None
        if isinstance(counter, dict):
            counter_node = self.repo.create_node(
                session_id=session_id,
                title=str(counter.get("title", "Counterexample")),
                content=str(counter.get("content", "")),
                x=220.0,
                y=-160.0,
                width=400.0,
                node_type="counterexample",
            )
            if selected_nodes:
                new_edges.append(
                    self.repo.create_edge(
                        session_id=session_id,
                        source_node_id=counter_node.id,
                        target_node_id=selected_nodes[0].id,
                        source_section_key=None,
                        edge_type="direct",
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
            "The first non-empty line MUST be '[QTITLE] <noun phrase>' for the question node title. "
            "The noun phrase should be concise and concept-like (for example: 'Conservation Laws'). "
            "Answer in Markdown with '## Title' sections. "
            "Each section may include 1-3 short paragraphs and examples. "
            "When formulas are useful, prefer LaTeX math notation ($...$ or $$...$$). "
            "Sections that should become separate knowledge-point nodes must use heading prefix: '## [KNOWLEDGE] '. "
            "Keep other sections unmarked; they belong to the answer node. "
            "Do not return JSON."
        )
        user_prompt = (
            f"User question: {question}\n"
            f"Selected nodes:\n{node_desc}\n"
            f"Selected sections:\n{section_desc}\n"
            f"Reference materials:\n{material_context}"
        )
        question_title = (question.strip()[:16] or "Question").strip()

        question_node = self.repo.create_node(
            session_id=session_id,
            title=question_title,
            content=question.strip(),
            x=180.0,
            y=-80.0,
            width=400.0,
            node_type="question",
        )
        answer_node = self.repo.create_node(
            session_id=session_id,
            title="Answer",
            content="",
            x=520.0,
            y=-80.0,
            width=400.0,
            node_type="answer",
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
        for src_id, src_section_key in edge_specs:
            edges.append(
                self.repo.create_edge(
                    session_id=session_id,
                    source_node_id=src_id,
                    target_node_id=question_node.id,
                    source_section_key=src_section_key,
                    edge_type="direct",
                )
            )
        edges.append(
            self.repo.create_edge(
                session_id=session_id,
                source_node_id=question_node.id,
                target_node_id=answer_node.id,
                source_section_key=None,
                edge_type="direct",
            )
        )

        yield {
            "type": "start",
            "nodes": [question_node, answer_node],
            "question_node_id": question_node.id,
            "answer_node_id": answer_node.id,
            "edges": edges,
        }

        knowledge_nodes: list[Node] = []
        knowledge_edges: list[Edge] = []
        knowledge_order: list[str] = []
        knowledge_bodies: dict[str, list[str]] = {}
        answer_parts: list[str] = []
        pending = ""
        current_target_node_id = answer_node.id
        question_title_resolved = False

        def emit_token(node_id: str, text: str) -> dict[str, Any] | None:
            if not text:
                return None
            if node_id == answer_node.id:
                answer_parts.append(text)
            else:
                buf = knowledge_bodies.get(node_id)
                if buf is None:
                    return None
                buf.append(text)
            return {"type": "token", "node_id": node_id, "content": text}

        def handle_line(line_text: str) -> tuple[list[dict[str, Any]], str]:
            nonlocal question_title_resolved
            events: list[dict[str, Any]] = []
            next_target = current_target_node_id
            line_no_nl = line_text[:-1] if line_text.endswith("\n") else line_text
            stripped = line_no_nl.strip()
            if not question_title_resolved and stripped:
                if stripped.upper().startswith("[QTITLE]"):
                    new_title = stripped[len("[QTITLE]") :].strip() or question_title
                    question_node.title = new_title[:24]
                    self.repo.update_node_content(
                        session_id=session_id,
                        node_id=question_node.id,
                        title=question_node.title,
                        content=question_node.content,
                    )
                    question_title_resolved = True
                    events.append({"type": "question_title", "node_id": question_node.id, "title": question_node.title})
                    return events, next_target
                question_title_resolved = True
            if stripped.startswith("## "):
                heading = stripped[3:].strip()
                if heading.upper().startswith("[KNOWLEDGE]"):
                    ktitle = heading[len("[KNOWLEDGE]") :].strip() or f"Knowledge {len(knowledge_nodes) + 1}"
                    kn = self.repo.create_node(
                        session_id=session_id,
                        title=ktitle[:60],
                        content="",
                        x=answer_node.x + len(knowledge_nodes) * 22.0,
                        y=answer_node.y + 240.0 + len(knowledge_nodes) * 220.0,
                        width=400.0,
                        node_type="knowledge",
                    )
                    edge = self.repo.create_edge(
                        session_id=session_id,
                        source_node_id=question_node.id,
                        target_node_id=kn.id,
                        source_section_key=None,
                        edge_type="direct",
                    )
                    knowledge_nodes.append(kn)
                    knowledge_edges.append(edge)
                    knowledge_order.append(kn.id)
                    knowledge_bodies[kn.id] = []
                    print(f"[DEBUG] knowledge heading detected: node_id={kn.id}, title={ktitle}")
                    events.append({"type": "knowledge_start", "node": kn, "edge": edge})
                    next_target = kn.id
                    token_evt = emit_token(kn.id, f"## {ktitle}\n")
                    if token_evt is not None:
                        events.append(token_evt)
                    return events, next_target
                next_target = answer_node.id
            token_evt = emit_token(next_target, line_text)
            if token_evt is not None:
                events.append(token_evt)
            return events, next_target

        for chunk in self.llm.stream_text_completion(system_prompt, user_prompt):
            pending += chunk
            while True:
                idx = pending.find("\n")
                if idx < 0:
                    break
                full_line = pending[: idx + 1]
                pending = pending[idx + 1 :]
                line_events, current_target_node_id = handle_line(full_line)
                for evt in line_events:
                    yield evt

        if pending:
            final_line_events, current_target_node_id = handle_line(pending)
            for evt in final_line_events:
                yield evt

        answer_content = "".join(answer_parts).strip()
        title = self._guess_title(answer_content, question)
        self.repo.update_node_content(
            session_id=session_id, node_id=answer_node.id, title=title, content=answer_content
        )
        answer_node.title = title
        answer_node.content = answer_content

        for kn_id in knowledge_order:
            parts = knowledge_bodies.get(kn_id, [])
            if not parts:
                continue
            kn = next((n for n in knowledge_nodes if n.id == kn_id), None)
            if kn is None:
                continue
            content_text = "".join(parts).strip()
            self.repo.update_node_content(
                session_id=session_id,
                node_id=kn.id,
                title=kn.title,
                content=content_text,
            )
            kn.content = content_text
        all_nodes = [question_node, answer_node, *knowledge_nodes]
        all_edges = [*edges, *knowledge_edges]
        return AskOut(new_nodes=all_nodes, new_edges=all_edges, redirect_hint=None, counterexample=None)

    @staticmethod
    def _safe_node_type(value: object) -> str:
        allowed = {"core", "normal", "counterexample", "skeleton", "question", "answer", "knowledge"}
        text = str(value)
        return text if text in allowed else "normal"

    @staticmethod
    def _guess_title(content: str, fallback: str) -> str:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("## "):
                return line[3:].strip()[:40] or fallback[:40]
        return fallback[:40] or "Answer"

    def _split_marked_sections(self, content: str) -> tuple[str, list[dict[str, str]]]:
        lines = content.splitlines()
        sections: list[dict[str, str]] = []
        current_title: str | None = None
        current_body: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if current_title is not None:
                    sections.append({"title": current_title, "content": "\n".join(current_body).strip()})
                current_title = stripped[3:].strip()
                current_body = []
            else:
                current_body.append(line)
        if current_title is not None:
            sections.append({"title": current_title, "content": "\n".join(current_body).strip()})

        root_sections: list[str] = []
        knowledge_parts: list[dict[str, str]] = []
        for sec in sections:
            title = sec["title"]
            body = sec["content"].strip()
            if not body:
                continue
            if title.upper().startswith("[KNOWLEDGE]"):
                ktitle = title[len("[KNOWLEDGE]") :].strip() or "Knowledge"
                knowledge_parts.append({"title": ktitle, "content": f"## {ktitle}\n{body}".strip()})
            else:
                root_sections.append(f"## {title}\n{body}".strip())
        root_content = "\n\n".join(root_sections).strip()
        if not root_content:
            root_content = content.strip()
        return root_content, knowledge_parts[:6]
