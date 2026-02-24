from __future__ import annotations

from ..llm_client import LlmClient
from ..models import QuizGenerateOut, QuizGradeOut, QuizItem
from ..repository import Repository


class QuizService:
    def __init__(self, repo: Repository, llm: LlmClient) -> None:
        self.repo = repo
        self.llm = llm

    def generate(self, session_id: str, count: int) -> QuizGenerateOut:
        nodes = self.repo.list_nodes(session_id)
        system_prompt = (
            "你是学习测验生成器，返回JSON对象：items数组，每项含question,answer,related_node_title,difficulty。"
        )
        user_prompt = (
            f"请基于以下图谱生成{count}道题：\n"
            + "\n".join([f"- {n.title}: {n.content}" for n in nodes if n.node_type != "skeleton"])
        )
        raw = self.llm.json_completion(system_prompt, user_prompt)
        items = raw.get("items", [])
        node_map = {n.title: n.id for n in nodes}
        out: list[QuizItem] = []
        for i, item in enumerate(items[:count]):
            related_node_id = node_map.get(str(item.get("related_node_title", "")))
            if not related_node_id and nodes:
                related_node_id = nodes[min(i, len(nodes) - 1)].id
            if not related_node_id:
                continue
            quiz_item = self.repo.create_quiz_item(
                session_id=session_id,
                question=str(item.get("question", "请解释该节点的作用。")),
                answer=str(item.get("answer", "略")),
                related_node_id=related_node_id,
                difficulty=str(item.get("difficulty", "medium")),
            )
            out.append(quiz_item)
        return QuizGenerateOut(items=out)

    def grade(self, session_id: str, quiz_id: str, user_answer: str) -> QuizGradeOut:
        row = self.repo.get_quiz_item(session_id, quiz_id)
        if not row:
            raise ValueError("Quiz item not found.")
        reference_answer = str(row["answer"])
        system_prompt = (
            "你是评测器，比较参考答案与用户答案。返回JSON对象：correct(布尔),feedback(字符串),score(0到1小数)。"
        )
        user_prompt = f"参考答案：{reference_answer}\n用户答案：{user_answer}"
        raw = self.llm.json_completion(system_prompt, user_prompt)
        correct = bool(raw.get("correct", False))
        score = float(raw.get("score", 0.0))
        delta = 0.05 if correct else -0.15
        feedback = str(raw.get("feedback", "请补充关键因果关系。"))
        node_id = str(row["related_node_id"])
        nodes = self.repo.get_nodes_by_ids(session_id, [node_id])
        if nodes:
            updated = min(1.0, max(0.0, nodes[0].mastery + delta * (0.5 + score / 2)))
            self.repo.update_node_mastery(session_id, node_id, updated)
        return QuizGradeOut(correct=correct, feedback=feedback, mastery_delta=delta)
