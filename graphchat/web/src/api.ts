import type { EdgeItem, GraphData, NodeItem, SelectedSection, Session } from "./types";

const API_BASE = "";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function initSession(topic: string): Promise<{ session: Session; nodes: NodeItem[]; edges: EdgeItem[] }> {
  return http("/api/sessions/init", {
    method: "POST",
    body: JSON.stringify({ topic })
  });
}

export async function initSessionStream(
  topic: string,
  onToken: (chunk: string) => void
): Promise<{ session: Session; nodes: NodeItem[]; edges: EdgeItem[] }> {
  const res = await fetch(`${API_BASE}/api/sessions/init/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic })
  });
  if (!res.ok || !res.body) {
    throw new Error(await res.text());
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: { session: Session; nodes: NodeItem[]; edges: EdgeItem[] } | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      for (const line of evt.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "token") onToken(String(payload.content ?? ""));
        if (payload.type === "done") result = payload.result;
        if (payload.type === "error") throw new Error(String(payload.message ?? "Stream error"));
      }
    }
  }
  if (!result) throw new Error("No stream result.");
  return result;
}

export async function listSessions(limit = 50): Promise<Session[]> {
  return http(`/api/sessions?limit=${limit}`);
}

export async function getGraph(sessionId: string): Promise<GraphData> {
  return http(`/api/sessions/${sessionId}/graph`);
}

export async function askQuestion(
  sessionId: string,
  question: string,
  nodeIds: string[],
  selectedSections: SelectedSection[]
): Promise<{ new_nodes: NodeItem[]; new_edges: EdgeItem[]; redirect_hint?: string | null }> {
  return http(`/api/sessions/${sessionId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question, node_ids: nodeIds, selected_sections: selectedSections })
  });
}

export async function askQuestionStream(
  sessionId: string,
  question: string,
  nodeIds: string[],
  selectedSections: SelectedSection[],
  handlers: {
    onStart?: (payload: {
      nodes: NodeItem[];
      edges: EdgeItem[];
      questionNodeId?: string;
      answerNodeId?: string;
    }) => void;
    onToken: (chunk: string) => void;
  }
): Promise<{ new_nodes: NodeItem[]; new_edges: EdgeItem[]; redirect_hint?: string | null }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, node_ids: nodeIds, selected_sections: selectedSections })
  });
  if (!res.ok || !res.body) {
    throw new Error(await res.text());
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: { new_nodes: NodeItem[]; new_edges: EdgeItem[]; redirect_hint?: string | null } | null = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      for (const line of evt.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "start" && handlers.onStart) {
          handlers.onStart({
            nodes: (payload.nodes ?? []) as NodeItem[],
            edges: (payload.edges ?? []) as EdgeItem[],
            questionNodeId: payload.question_node_id as string | undefined,
            answerNodeId: payload.answer_node_id as string | undefined
          });
        }
        if (payload.type === "token") handlers.onToken(String(payload.content ?? ""));
        if (payload.type === "done") result = payload.result;
        if (payload.type === "error") throw new Error(String(payload.message ?? "Stream error"));
      }
    }
  }
  if (!result) throw new Error("No stream result.");
  return result;
}

export async function updateNodePosition(
  sessionId: string,
  nodeId: string,
  x: number,
  y: number,
  width?: number
): Promise<void> {
  await http(`/api/sessions/${sessionId}/nodes/${nodeId}/position`, {
    method: "PATCH",
    body: JSON.stringify({ x, y, width })
  });
}

export async function uploadMaterial(sessionId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/materials`, {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
}

export async function generateReview(sessionId: string): Promise<{ summary: string; gaps: string[]; actions: string[] }> {
  return http(`/api/sessions/${sessionId}/review`, { method: "POST" });
}

export async function generateQuiz(
  sessionId: string,
  count = 3
): Promise<{ items: { quiz_id: string; question: string; answer: string; related_node_id: string; difficulty: string }[] }> {
  return http(`/api/sessions/${sessionId}/quiz/generate`, {
    method: "POST",
    body: JSON.stringify({ count })
  });
}

export async function gradeQuiz(
  sessionId: string,
  quizId: string,
  userAnswer: string
): Promise<{ correct: boolean; feedback: string; mastery_delta: number }> {
  return http(`/api/sessions/${sessionId}/quiz/grade`, {
    method: "POST",
    body: JSON.stringify({ quiz_id: quizId, user_answer: userAnswer })
  });
}
