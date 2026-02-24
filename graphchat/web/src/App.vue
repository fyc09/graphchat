<template>
  <div class="layout">
    <aside class="panel">
      <h1>GraphChat</h1>
      <div class="section">
        <label>Session</label>
        <select v-model="sessionId" @change="onSwitchSession">
          <option value="">Select session</option>
          <option v-for="s in sessions" :key="s.id" :value="s.id">{{ s.topic }} ({{ s.created_at.slice(0, 19) }})</option>
        </select>
        <button @click="onNewSession">New Session</button>
      </div>
      <div class="section">
        <label>Upload Reference (txt/md)</label>
        <input type="file" @change="onFileChange" />
      </div>
      <div class="section">
        <button :disabled="!sessionId || isLoading" @click="onReview">Review</button>
        <button :disabled="!sessionId || isLoading" @click="onGenerateQuiz">Quiz</button>
      </div>
      <div v-if="review" class="section result">
        <h3>Review</h3>
        <p>{{ review.summary }}</p>
      </div>
      <div v-if="edgeQuestion" class="section result">
        <h3>Edge Question</h3>
        <p>{{ edgeQuestion }}</p>
      </div>
      <div v-if="redirectHint" class="section result">
        <h3>Redirect</h3>
        <p>{{ redirectHint }}</p>
      </div>
      <div v-if="quizItems.length > 0" class="section result">
        <h3>Quiz</h3>
        <div v-for="q in quizItems" :key="q.quiz_id" class="quiz-item">
          <p>{{ q.question }}</p>
          <input v-model="quizAnswerMap[q.quiz_id]" placeholder="Your answer" />
          <button @click="onGrade(q.quiz_id)">Grade</button>
        </div>
      </div>
      <div v-if="errorText" class="section error">{{ errorText }}</div>
    </aside>
    <main class="graph-wrap">
      <GraphCanvas
        :nodes="graph.nodes"
        :edges="graph.edges"
        :selected-ids="selectedNodeIds"
        :selected-section-keys="selectedSectionKeys"
        :draft-question="draftQuestion"
        :show-init-node="graph.nodes.length === 0 && !draftQuestion"
        :init-topic="initTopic"
        :init-node-position="initNodePosition"
        @toggle-select="toggleSelect"
        @toggle-section="toggleSection"
        @move-end="onMoveEnd"
        @resize-end="onResizeEnd"
        @edge-click="onEdgeClick"
        @clear-select="clearSelections"
        @canvas-dblclick="onCanvasDblClick"
        @draft-change="onDraftChange"
        @draft-move="onDraftMove"
        @draft-submit="onDraftSubmit"
        @draft-cancel="onDraftCancel"
        @init-topic-change="onInitTopicChange"
        @init-node-move="onInitNodeMove"
        @init-submit="onInitSession"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import GraphCanvas from "./components/GraphCanvas.vue";
import {
  askQuestionStream,
  generateQuiz,
  generateReview,
  getGraph,
  gradeQuiz,
  initSessionStream,
  listSessions,
  updateNodePosition,
  uploadMaterial
} from "./api";
import type { EdgeItem, NodeItem, SelectedSection, Session } from "./types";

type DraftQuestion = { x: number; y: number; text: string };

const initTopic = ref("");
const sessionId = ref("");
const sessions = ref<Session[]>([]);
const selectedNodeIds = ref<string[]>([]);
const selectedSections = ref<SelectedSection[]>([]);
const selectedSectionKeys = ref<string[]>([]);
const draftQuestion = ref<DraftQuestion | null>(null);
const initNodePosition = ref<{ x: number; y: number }>({ x: 0, y: 0 });
const edgeQuestion = ref("");
const redirectHint = ref("");
const errorText = ref("");
const isLoading = ref(false);
const review = ref<{ summary: string; gaps: string[]; actions: string[] } | null>(null);
const quizItems = ref<{ quiz_id: string; question: string; answer: string; related_node_id: string; difficulty: string }[]>(
  []
);
const quizAnswerMap = reactive<Record<string, string>>({});
const graph = reactive<{ nodes: NodeItem[]; edges: EdgeItem[] }>({ nodes: [], edges: [] });

onMounted(async () => {
  await refreshSessions();
});

async function refreshSessions(): Promise<void> {
  try {
    sessions.value = await listSessions(100);
  } catch {
    // ignore
  }
}

async function onSwitchSession(): Promise<void> {
  if (!sessionId.value) return;
  try {
    isLoading.value = true;
    errorText.value = "";
    const data = await getGraph(sessionId.value);
    graph.nodes = data.nodes;
    graph.edges = data.edges;
    clearSelections();
  } catch (err) {
    errorText.value = String(err);
  } finally {
    isLoading.value = false;
  }
}

function onNewSession(): void {
  sessionId.value = "";
  graph.nodes = [];
  graph.edges = [];
  draftQuestion.value = null;
  initTopic.value = "";
  initNodePosition.value = { x: 0, y: 0 };
  clearSelections();
}

async function onInitSession(): Promise<void> {
  if (!initTopic.value.trim()) {
    errorText.value = "Topic is required.";
    return;
  }
  try {
    isLoading.value = true;
    errorText.value = "";
    const topic = initTopic.value.trim();
    const tempId = `temp-init-${Date.now()}`;
    const tempNode: NodeItem = {
      id: tempId,
      session_id: "",
      title: topic,
      content: "",
      mastery: 0.2,
      importance: 1.0,
      x: initNodePosition.value.x,
      y: initNodePosition.value.y,
      width: 320,
      node_type: "core",
      created_at: new Date().toISOString()
    };
    graph.nodes = [tempNode];
    const data = await initSessionStream(topic, (chunk) => {
      const n = graph.nodes.find((it) => it.id === tempId);
      if (n) n.content += chunk;
    });
    sessionId.value = data.session.id;
    graph.nodes = data.nodes;
    graph.edges = data.edges;
    clearSelections();
    initTopic.value = "";
    await refreshSessions();
  } catch (err) {
    errorText.value = String(err);
  } finally {
    isLoading.value = false;
  }
}

function onCanvasDblClick(payload: { x: number; y: number }): void {
  if (!sessionId.value) return;
  draftQuestion.value = { x: payload.x, y: payload.y, text: "" };
}

function onDraftChange(value: string): void {
  if (!draftQuestion.value) return;
  draftQuestion.value = { ...draftQuestion.value, text: value };
}

function onDraftCancel(): void {
  draftQuestion.value = null;
}

function onDraftMove(payload: { x: number; y: number }): void {
  if (!draftQuestion.value) return;
  draftQuestion.value = { ...draftQuestion.value, x: payload.x, y: payload.y };
}

function onInitTopicChange(value: string): void {
  initTopic.value = value;
}

function onInitNodeMove(payload: { x: number; y: number }): void {
  initNodePosition.value = payload;
}

async function onDraftSubmit(): Promise<void> {
  if (!draftQuestion.value || !sessionId.value) return;
  const q = draftQuestion.value;
  if (!q.text.trim()) {
    errorText.value = "Question is required.";
    return;
  }
  try {
    isLoading.value = true;
    errorText.value = "";
    const selectedNodeIdsSnapshot = [...selectedNodeIds.value];
    const selectedSectionsSnapshot = selectedSections.value.map((s) => ({ ...s }));
    draftQuestion.value = null;
    clearSelections();
    let liveNodeId = "";

    const data = await askQuestionStream(
      sessionId.value,
      q.text.trim(),
      selectedNodeIdsSnapshot,
      selectedSectionsSnapshot,
      {
        onStart: ({ nodes, edges, questionNodeId: qid, answerNodeId: aid }) => {
          const cloned = nodes.map((n) => ({ ...n }));
          const qNode = cloned.find((n) => n.id === qid) ?? cloned[0];
          const aNode = cloned.find((n) => n.id === aid) ?? cloned[cloned.length - 1];
          if (qNode) {
            qNode.x = q.x;
            qNode.y = q.y;
          }
          if (aNode) {
            aNode.x = q.x + (qNode?.width ?? 242) + 180;
            aNode.y = q.y;
            liveNodeId = aNode.id;
          }
          graph.nodes = [...graph.nodes, ...cloned];
          graph.edges = [...graph.edges, ...edges];
          if (sessionId.value) {
            if (qNode) void updateNodePosition(sessionId.value, qNode.id, qNode.x, qNode.y, qNode.width);
            if (aNode) void updateNodePosition(sessionId.value, aNode.id, aNode.x, aNode.y, aNode.width);
          }
        },
        onToken: (chunk) => {
          if (!liveNodeId) return;
          const n = graph.nodes.find((it) => it.id === liveNodeId);
          if (n) n.content += chunk;
        }
      }
    );
    if (data.new_nodes.length > 0) {
      for (const node of data.new_nodes) {
        const idx = graph.nodes.findIndex((n) => n.id === node.id);
        if (idx < 0) continue;
        const prev = graph.nodes[idx];
        const next = { ...node, x: prev.x, y: prev.y, width: prev.width };
        graph.nodes[idx] = next;
        await updateNodePosition(sessionId.value, next.id, next.x, next.y, next.width);
      }
      redirectHint.value = data.redirect_hint ?? "";
    }
  } catch (err) {
    errorText.value = String(err);
  } finally {
    isLoading.value = false;
  }
}

function toggleSelect(nodeId: string): void {
  const exists = selectedNodeIds.value.includes(nodeId);
  selectedNodeIds.value = exists
    ? selectedNodeIds.value.filter((id) => id !== nodeId)
    : [...selectedNodeIds.value, nodeId];
}

function toggleSection(payload: { nodeId: string; title: string; body: string; key: string }): void {
  const exists = selectedSectionKeys.value.includes(payload.key);
  if (exists) {
    selectedSectionKeys.value = selectedSectionKeys.value.filter((k) => k !== payload.key);
    selectedSections.value = selectedSections.value.filter((s) => s.key !== payload.key);
    return;
  }
  selectedSectionKeys.value = [...selectedSectionKeys.value, payload.key];
  selectedSections.value = [
    ...selectedSections.value,
    { node_id: payload.nodeId, title: payload.title, body: payload.body, key: payload.key }
  ];
}

function clearSelections(): void {
  selectedNodeIds.value = [];
  selectedSections.value = [];
  selectedSectionKeys.value = [];
}

async function onMoveEnd(payload: { nodeId: string; x: number; y: number }): Promise<void> {
  if (!sessionId.value) return;
  try {
    const n = graph.nodes.find((it) => it.id === payload.nodeId);
    await updateNodePosition(sessionId.value, payload.nodeId, payload.x, payload.y, n?.width);
  } catch (err) {
    errorText.value = String(err);
  }
}

async function onResizeEnd(payload: { nodeId: string; width: number }): Promise<void> {
  if (!sessionId.value) return;
  try {
    const n = graph.nodes.find((it) => it.id === payload.nodeId);
    if (!n) return;
    await updateNodePosition(sessionId.value, payload.nodeId, n.x, n.y, payload.width);
  } catch (err) {
    errorText.value = String(err);
  }
}

function onEdgeClick(questionText: string): void {
  edgeQuestion.value = questionText;
}

async function onFileChange(event: Event): Promise<void> {
  if (!sessionId.value) return;
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  try {
    errorText.value = "";
    await uploadMaterial(sessionId.value, file);
  } catch (err) {
    errorText.value = String(err);
  } finally {
    target.value = "";
  }
}

async function onReview(): Promise<void> {
  if (!sessionId.value) return;
  try {
    errorText.value = "";
    review.value = await generateReview(sessionId.value);
  } catch (err) {
    errorText.value = String(err);
  }
}

async function onGenerateQuiz(): Promise<void> {
  if (!sessionId.value) return;
  try {
    errorText.value = "";
    const data = await generateQuiz(sessionId.value, 3);
    quizItems.value = data.items;
    for (const item of data.items) quizAnswerMap[item.quiz_id] = "";
  } catch (err) {
    errorText.value = String(err);
  }
}

async function onGrade(quizId: string): Promise<void> {
  if (!sessionId.value) return;
  try {
    errorText.value = "";
    await gradeQuiz(sessionId.value, quizId, quizAnswerMap[quizId] || "");
    const latest = await getGraph(sessionId.value);
    graph.nodes = latest.nodes;
    graph.edges = latest.edges;
  } catch (err) {
    errorText.value = String(err);
  }
}
</script>
