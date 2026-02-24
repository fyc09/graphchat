from __future__ import annotations

from ..llm_client import LlmClient
from ..models import ReviewOut
from ..repository import Repository


class ReviewService:
    def __init__(self, repo: Repository, llm: LlmClient) -> None:
        self.repo = repo
        self.llm = llm

    def generate_review(self, session_id: str) -> ReviewOut:
        nodes = self.repo.list_nodes(session_id)
        edges = self.repo.list_edges(session_id)
        system_prompt = (
            "你是学习图谱评估器，返回JSON对象：summary(字符串),gaps(字符串数组),actions(字符串数组)。"
        )
        user_prompt = (
            f"节点:\n" + "\n".join([f"- {n.title}: mastery={n.mastery}" for n in nodes]) + "\n"
            f"连线:\n" + "\n".join([f"- {e.question}" for e in edges])
        )
        raw = self.llm.json_completion(system_prompt, user_prompt)
        summary = str(raw.get("summary", "当前图谱仍需补足因果链与关键概念覆盖。"))
        gaps = [str(x) for x in raw.get("gaps", ["关键因果链不足"])]
        actions = [str(x) for x in raw.get("actions", ["优先补充核心概念到关键机制的推导问题"])]
        self.repo.save_review(session_id, summary, gaps, actions)
        return ReviewOut(summary=summary, gaps=gaps, actions=actions)
