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
      <div v-if="hiddenRootIds.length > 0" class="section">
        <button @click="resetHiddenNodes">Show Hidden Nodes ({{ hiddenRootIds.length }})</button>
      </div>
      <div v-if="redirectHint" class="section result">
        <h3>Redirect</h3>
        <p>{{ redirectHint }}</p>
      </div>
      <div v-if="errorText" class="section error">{{ errorText }}</div>
    </aside>
    <main class="graph-wrap">
      <GraphCanvas
        :nodes="visibleNodes"
        :edges="visibleEdges"
        :child-controls="childControls"
        :selected-ids="visibleSelectedNodeIds"
        :selected-section-keys="visibleSelectedSectionKeys"
        :draft-question="draftQuestion"
        :show-init-node="graph.nodes.length === 0 && !draftQuestion"
        :init-topic="initTopic"
        :init-node-position="initNodePosition"
        @toggle-select="toggleSelect"
        @toggle-section="toggleSection"
        @move-end="onMoveEnd"
        @resize-end="onResizeEnd"
        @clear-select="clearSelections"
        @canvas-dblclick="onCanvasDblClick"
        @draft-change="onDraftChange"
        @draft-move="onDraftMove"
        @draft-submit="onDraftSubmit"
        @draft-cancel="onDraftCancel"
        @init-topic-change="onInitTopicChange"
        @init-node-move="onInitNodeMove"
        @init-submit="onInitSession"
        @delete-node="onDeleteNode"
        @hide-node="onHideNode"
        @toggle-child-hidden="onToggleChildHidden"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import GraphCanvas from "./components/GraphCanvas.vue";
import {
  askQuestionStream,
  getGraph,
  initSessionStream,
  listSessions,
  softDeleteNode,
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
const redirectHint = ref("");
const errorText = ref("");
const isLoading = ref(false);
const hiddenRootIds = ref<string[]>([]);
const graph = reactive<{ nodes: NodeItem[]; edges: EdgeItem[] }>({ nodes: [], edges: [] });

const hiddenNodeIdSet = computed<Set<string>>(() => {
  if (hiddenRootIds.value.length === 0) return new Set<string>();
  const nodeIds = new Set(graph.nodes.map((node) => node.id));
  const childrenByNode = new Map<string, string[]>();
  for (const edge of graph.edges) {
    if (!childrenByNode.has(edge.source_node_id)) childrenByNode.set(edge.source_node_id, []);
    childrenByNode.get(edge.source_node_id)?.push(edge.target_node_id);
  }
  const out = new Set<string>();
  const queue = hiddenRootIds.value.filter((nodeId) => nodeIds.has(nodeId));
  while (queue.length > 0) {
    const nodeId = queue.shift() as string;
    if (out.has(nodeId)) continue;
    out.add(nodeId);
    for (const nextId of childrenByNode.get(nodeId) ?? []) {
      if (!out.has(nextId)) queue.push(nextId);
    }
  }
  return out;
});

const visibleNodes = computed<NodeItem[]>(() =>
  graph.nodes.filter((node) => !hiddenNodeIdSet.value.has(node.id))
);

const visibleEdges = computed<EdgeItem[]>(() =>
  graph.edges.filter(
    (edge) => !hiddenNodeIdSet.value.has(edge.source_node_id) && !hiddenNodeIdSet.value.has(edge.target_node_id)
  )
);

const visibleNodeIdSet = computed<Set<string>>(() => new Set(visibleNodes.value.map((node) => node.id)));

const visibleSelectedNodeIds = computed<string[]>(() =>
  selectedNodeIds.value.filter((nodeId) => visibleNodeIdSet.value.has(nodeId))
);

const visibleSelectedSectionKeys = computed<string[]>(() =>
  selectedSectionKeys.value.filter((key) => visibleNodeIdSet.value.has(key.split("::")[0] || ""))
);

const childControls = computed<
  Array<{
    parentNodeId: string;
    children: Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }>;
  }>
>(() => {
  const hiddenSet = hiddenNodeIdSet.value;
  const edgesBySource = new Map<string, string[]>();
  for (const edge of graph.edges) {
    if (!edgesBySource.has(edge.source_node_id)) edgesBySource.set(edge.source_node_id, []);
    edgesBySource.get(edge.source_node_id)?.push(edge.target_node_id);
  }
  const nodeById = new Map(graph.nodes.map((node) => [node.id, node]));
  const out: Array<{
    parentNodeId: string;
    children: Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }>;
  }> = [];
  for (const node of visibleNodes.value) {
    const targetIds = Array.from(new Set(edgesBySource.get(node.id) ?? []));
    if (targetIds.length === 0) continue;
    const children = targetIds
      .map((id) => {
        const child = nodeById.get(id);
        if (!child) return null;
        return {
          id,
          title: child.title,
          node_type: child.node_type,
          hidden: hiddenSet.has(id)
        };
      })
      .filter((item): item is { id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean } => !!item);
    if (children.length === 0) continue;
    out.push({
      parentNodeId: node.id,
      children
    });
  }
  return out;
});

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
    hiddenRootIds.value = [];
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
  hiddenRootIds.value = [];
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
    let liveRootNodeId = "";
    let knowledgeSpawnIndex = 0;
    const data = await initSessionStream(topic, {
      onStart: ({ nodes, edges, rootNodeId }) => {
        const cloned = nodes.map((n) => ({ ...n }));
        const rootNode = cloned.find((n) => n.id === rootNodeId) ?? cloned[0];
        if (rootNode) {
          rootNode.x = initNodePosition.value.x;
          rootNode.y = initNodePosition.value.y;
          liveRootNodeId = rootNode.id;
        }
        graph.nodes = cloned;
        graph.edges = [...edges];
      },
      onKnowledgeStart: ({ node, edge }) => {
        const rootNode = liveRootNodeId ? graph.nodes.find((n) => n.id === liveRootNodeId) : null;
        const placedNode = { ...node };
        if (rootNode) {
          placedNode.x = rootNode.x + (rootNode.width || 400) + 180 + knowledgeSpawnIndex * 22;
          placedNode.y = rootNode.y + knowledgeSpawnIndex * 220;
        }
        knowledgeSpawnIndex += 1;
        if (!graph.nodes.some((n) => n.id === node.id)) {
          graph.nodes = [...graph.nodes, placedNode];
        }
        if (edge && !graph.edges.some((e) => e.id === edge.id)) {
          graph.edges = [...graph.edges, edge];
        }
      },
      onToken: (chunk, nodeId) => {
        const targetId = nodeId || liveRootNodeId;
        if (!targetId) return;
        const n = graph.nodes.find((it) => it.id === targetId);
        if (n) n.content += chunk;
      }
    });
    sessionId.value = data.session.id;
    if (data.nodes.length > 0) {
      for (const node of data.nodes) {
        const idx = graph.nodes.findIndex((n) => n.id === node.id);
        if (idx < 0) {
          graph.nodes = [...graph.nodes, node];
          await updateNodePosition(sessionId.value, node.id, node.x, node.y, node.width);
        } else {
          const prev = graph.nodes[idx];
          const next = { ...node, x: prev.x, y: prev.y, width: prev.width };
          graph.nodes[idx] = next;
          await updateNodePosition(sessionId.value, next.id, next.x, next.y, next.width);
        }
      }
      const edgeIds = new Set(graph.edges.map((e) => e.id));
      const edgesToAdd = data.edges.filter((e) => !edgeIds.has(e.id));
      if (edgesToAdd.length > 0) graph.edges = [...graph.edges, ...edgesToAdd];
    }
    clearSelections();
    hiddenRootIds.value = [];
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
    let liveQuestionNodeId = "";
    let knowledgeSpawnIndex = 0;

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
            liveQuestionNodeId = qNode.id;
          }
          if (aNode) {
            aNode.x = q.x + (qNode?.width ?? 400) + 180;
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
        onKnowledgeStart: ({ node, edge }) => {
          const answerNode = liveNodeId ? graph.nodes.find((n) => n.id === liveNodeId) : null;
          const questionNode = liveQuestionNodeId ? graph.nodes.find((n) => n.id === liveQuestionNodeId) : null;
          const placedNode = { ...node };
          if (answerNode) {
            placedNode.x = answerNode.x + knowledgeSpawnIndex * 22;
            placedNode.y = answerNode.y + 240 + knowledgeSpawnIndex * 220;
          } else if (questionNode) {
            placedNode.x = questionNode.x + (questionNode.width || 400) + 180 + knowledgeSpawnIndex * 22;
            placedNode.y = questionNode.y + 240 + knowledgeSpawnIndex * 220;
          }
          knowledgeSpawnIndex += 1;
          if (!graph.nodes.some((n) => n.id === node.id)) {
            graph.nodes = [...graph.nodes, placedNode];
            if (sessionId.value) {
              void updateNodePosition(sessionId.value, placedNode.id, placedNode.x, placedNode.y, placedNode.width);
            }
          }
          if (edge && !graph.edges.some((e) => e.id === edge.id)) {
            graph.edges = [...graph.edges, edge];
          }
        },
        onQuestionTitle: ({ nodeId, title }) => {
          if (!nodeId || !title) return;
          const n = graph.nodes.find((it) => it.id === nodeId);
          if (n) n.title = title;
        },
        onToken: (chunk, nodeId) => {
          const targetId = nodeId || liveNodeId;
          if (!targetId) return;
          const n = graph.nodes.find((it) => it.id === targetId);
          if (n) n.content += chunk;
        }
      }
    );
    if (data.new_nodes.length > 0) {
      for (const node of data.new_nodes) {
        const idx = graph.nodes.findIndex((n) => n.id === node.id);
        if (idx < 0) {
          graph.nodes = [...graph.nodes, node];
          await updateNodePosition(sessionId.value, node.id, node.x, node.y, node.width);
        } else {
          const prev = graph.nodes[idx];
          const next = { ...node, x: prev.x, y: prev.y, width: prev.width };
          graph.nodes[idx] = next;
          await updateNodePosition(sessionId.value, next.id, next.x, next.y, next.width);
        }
      }
      const edgeIds = new Set(graph.edges.map((e) => e.id));
      const edgesToAdd = data.new_edges.filter((e) => !edgeIds.has(e.id));
      if (edgesToAdd.length > 0) graph.edges = [...graph.edges, ...edgesToAdd];
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

function resetHiddenNodes(): void {
  hiddenRootIds.value = [];
}

function onHideNode(nodeId: string): void {
  if (!hiddenRootIds.value.includes(nodeId)) {
    hiddenRootIds.value = [...hiddenRootIds.value, nodeId];
  }
  clearSelections();
}

function onRestoreHiddenNode(nodeId: string): void {
  if (!nodeId) return;
  if (hiddenRootIds.value.includes(nodeId)) {
    hiddenRootIds.value = hiddenRootIds.value.filter((id) => id !== nodeId);
    return;
  }
  const edgesBySource = new Map<string, string[]>();
  for (const edge of graph.edges) {
    if (!edgesBySource.has(edge.source_node_id)) edgesBySource.set(edge.source_node_id, []);
    edgesBySource.get(edge.source_node_id)?.push(edge.target_node_id);
  }
  const rootsToShow = new Set<string>();
  for (const rootId of hiddenRootIds.value) {
    const queue = [rootId];
    const visited = new Set<string>();
    while (queue.length > 0) {
      const nextId = queue.shift() as string;
      if (visited.has(nextId)) continue;
      visited.add(nextId);
      if (nextId === nodeId) {
        rootsToShow.add(rootId);
        break;
      }
      for (const childId of edgesBySource.get(nextId) ?? []) {
        if (!visited.has(childId)) queue.push(childId);
      }
    }
  }
  if (rootsToShow.size === 0) return;
  hiddenRootIds.value = hiddenRootIds.value.filter((id) => !rootsToShow.has(id));
}

function onToggleChildHidden(payload: { childNodeId: string; hidden: boolean }): void {
  if (!payload.childNodeId) return;
  if (payload.hidden) {
    if (!hiddenRootIds.value.includes(payload.childNodeId)) {
      hiddenRootIds.value = [...hiddenRootIds.value, payload.childNodeId];
    }
    return;
  }
  onRestoreHiddenNode(payload.childNodeId);
}

async function onDeleteNode(nodeId: string): Promise<void> {
  if (!sessionId.value) return;
  try {
    errorText.value = "";
    await softDeleteNode(sessionId.value, nodeId);
    const deleted = new Set<string>([nodeId]);
    graph.nodes = graph.nodes.filter((node) => !deleted.has(node.id));
    graph.edges = graph.edges.filter(
      (edge) => !deleted.has(edge.source_node_id) && !deleted.has(edge.target_node_id)
    );
    hiddenRootIds.value = hiddenRootIds.value.filter((id) => id !== nodeId);
    selectedNodeIds.value = selectedNodeIds.value.filter((id) => id !== nodeId);
    selectedSections.value = selectedSections.value.filter((s) => s.node_id !== nodeId);
    selectedSectionKeys.value = selectedSectionKeys.value.filter((key) => (key.split("::")[0] || "") !== nodeId);
  } catch (err) {
    errorText.value = String(err);
  }
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

</script>
