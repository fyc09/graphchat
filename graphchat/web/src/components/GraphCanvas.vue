<template>
  <div
    class="canvas"
    :class="{ interacting: isInteracting }"
    ref="canvasRef"
    @dblclick="onCanvasDblClick"
    @pointerdown="onCanvasPointerDown"
    @wheel.prevent="onWheel"
  >
    <svg class="edges" :width="canvasSize.w" :height="canvasSize.h" :viewBox="`0 0 ${canvasSize.w} ${canvasSize.h}`" preserveAspectRatio="none">
      <path
        v-for="edge in edges"
        :key="`${edge.id}-${edgeRenderTick}`"
        :d="edgePath(edge)"
        :stroke="edgeColor(edge.edge_type)"
        :stroke-width="1 + edge.strength * 2"
        :stroke-dasharray="edge.edge_type === 'counter' ? '6 4' : ''"
        fill="none"
        @click.stop="$emit('edge-click', edge.question)"
      />
      <path
        v-for="edge in draftEdges"
        :key="`${edge.id}-${edgeRenderTick}`"
        :d="edgePath(edge)"
        stroke="#64748b"
        stroke-width="1.5"
        stroke-dasharray="5 4"
        fill="none"
      />
    </svg>

    <div
      v-for="node in nodes"
      :key="node.id"
      class="node"
      :class="[{ selected: selectedIds.includes(node.id) }, `node-${node.node_type}`]"
      :style="nodeStyle(node)"
    >
      <div class="title-row" :data-node-title-id="node.id" @pointerdown.stop="startNodeDrag($event, node.id)">
        <div class="check-inline" @click.stop>
          <input type="checkbox" :checked="selectedIds.includes(node.id)" @change="$emit('toggle-select', node.id)" />
          <span class="title">{{ node.title }}</span>
        </div>
      </div>
      <div class="content">
        <template v-if="sections(node.content).length > 0">
          <details v-for="(s, i) in sections(node.content)" :key="`${node.id}-${i}`" open>
            <summary class="summary-row" :data-section-key="sectionKey(node.id, i)">
              <input
                type="checkbox"
                :checked="selectedSectionKeys.includes(sectionKey(node.id, i))"
                @click.stop
                @change="$emit('toggle-section', { nodeId: node.id, title: s.title, body: s.body, key: sectionKey(node.id, i) })"
              />
              <span class="section-title" :class="{ 'section-selected': selectedSectionKeys.includes(sectionKey(node.id, i)) }">
                {{ s.title }}
              </span>
            </summary>
            <div :key="sectionBodyKey(node, i, s.body)" class="section-body markdown-body" v-html="renderMarkdown(s.body)"></div>
          </details>
        </template>
        <template v-else>
          <div :key="nodeBodyKey(node)" class="section-body markdown-body" v-html="renderMarkdown(node.content)"></div>
        </template>
      </div>
      <div class="resize-edge" @pointerdown.stop="startResize($event, node.id)" />
    </div>

    <div v-if="draftQuestion" class="node node-draft" :style="draftStyle">
      <div class="title-row title-row-solid" data-node-title-id="draft-question" @pointerdown.stop="startDraftDrag">
        <span class="title">Question Node</span>
      </div>
      <textarea
        class="draft-input"
        :value="draftQuestion.text"
        rows="4"
        placeholder="Type your question..."
        @click.stop
        @input="$emit('draft-change', ($event.target as HTMLTextAreaElement).value)"
      />
      <div class="draft-actions">
        <button @click.stop="$emit('draft-submit')">Submit</button>
        <button class="ghost" @click.stop="$emit('draft-cancel')">Cancel</button>
      </div>
    </div>

    <div v-if="showInitNode" class="node node-init" :style="initStyle">
      <div class="title-row title-row-solid" @pointerdown.stop="startInitDrag">
        <span class="title">Initialize Topic</span>
      </div>
      <input
        :value="initTopic"
        class="draft-input"
        placeholder="Enter topic..."
        @click.stop
        @input="$emit('init-topic-change', ($event.target as HTMLInputElement).value)"
      />
      <div class="draft-actions">
        <button @click.stop="$emit('init-submit')">Start</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, onUpdated, ref } from "vue";
import DOMPurify from "dompurify";
import MarkdownIt from "markdown-it";
import type { EdgeItem, NodeItem } from "../types";
import { ensureMathJax } from "../mathjax";

type DraftQuestion = { x: number; y: number; text: string };
type RenderEdge = Pick<EdgeItem, "id" | "source_node_id" | "target_node_id" | "source_section_key" | "strength" | "edge_type">;

const props = withDefaults(
  defineProps<{
    nodes: NodeItem[];
    edges: EdgeItem[];
    selectedIds: string[];
    selectedSectionKeys: string[];
    draftQuestion?: DraftQuestion | null;
    showInitNode?: boolean;
    initTopic?: string;
    initNodePosition?: { x: number; y: number };
  }>(),
  {
    draftQuestion: null,
    showInitNode: false,
    initTopic: "",
    initNodePosition: () => ({ x: 0, y: 0 })
  }
);

const emit = defineEmits<{
  (e: "move-end", payload: { nodeId: string; x: number; y: number }): void;
  (e: "resize-end", payload: { nodeId: string; width: number }): void;
  (e: "toggle-select", nodeId: string): void;
  (e: "toggle-section", payload: { nodeId: string; title: string; body: string; key: string }): void;
  (e: "edge-click", question: string): void;
  (e: "clear-select"): void;
  (e: "canvas-dblclick", payload: { x: number; y: number }): void;
  (e: "draft-change", value: string): void;
  (e: "draft-move", payload: { x: number; y: number }): void;
  (e: "draft-submit"): void;
  (e: "draft-cancel"): void;
  (e: "init-topic-change", value: string): void;
  (e: "init-node-move", payload: { x: number; y: number }): void;
  (e: "init-submit"): void;
}>();

const canvasRef = ref<HTMLDivElement | null>(null);
const canvasSize = ref({ w: 1, h: 1 });
const draggingNodeId = ref<string | null>(null);
const dragMode = ref<"node" | "draft" | "init" | null>(null);
const resizingNodeId = ref<string | null>(null);
const panDragging = ref(false);
const isInteracting = ref(false);
const dragOffset = ref({ x: 0, y: 0 });
const resizeStart = ref({ x: 0, width: 0 });
const panStart = ref({ x: 0, y: 0, panX: 480, panY: 320 });

const scale = ref(1);
const panX = ref(480);
const panY = ref(320);

const zCounter = ref(10);
const nodeZ = ref<Record<string, number>>({});
const nodeWidth = ref<Record<string, number>>({});
const edgeRenderTick = ref(0);
const contentRenderTick = ref(0);
let canvasObserver: ResizeObserver | null = null;
let rerenderRaf: number | null = null;
let mathRaf: number | null = null;

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
});

const draftStyle = computed(() => {
  if (!props.draftQuestion) return {};
  return {
    transform: `translate(${worldToScreenX(props.draftQuestion.x)}px, ${worldToScreenY(props.draftQuestion.y)}px) scale(${scale.value})`,
    width: "260px",
    zIndex: 9999
  };
});

const initStyle = computed(() => ({
  transform: `translate(${worldToScreenX(props.initNodePosition.x)}px, ${worldToScreenY(props.initNodePosition.y)}px) scale(${scale.value})`,
  width: "280px",
  zIndex: 9998
}));

const draftEdges = computed<RenderEdge[]>(() => {
  if (!props.draftQuestion) return [];
  const out: RenderEdge[] = [];
  for (const nodeId of props.selectedIds) {
    out.push({
      id: `draft-node-${nodeId}`,
      source_node_id: nodeId,
      source_section_key: null,
      target_node_id: "draft-question",
      strength: 0.4,
      edge_type: "redirect"
    });
  }
  for (const key of props.selectedSectionKeys) {
    const nodeId = key.split("::")[0] || "";
    if (!nodeId) continue;
    out.push({
      id: `draft-sec-${key}`,
      source_node_id: nodeId,
      source_section_key: key,
      target_node_id: "draft-question",
      strength: 0.4,
      edge_type: "redirect"
    });
  }
  return out;
});

onMounted(() => {
  updateCanvasSize();
  if (canvasRef.value) {
    canvasObserver = new ResizeObserver(() => updateCanvasSize());
    canvasObserver.observe(canvasRef.value);
  }
  void ensureMathJax().then(() => scheduleMathTypeset());
});

onUpdated(() => {
  scheduleMathTypeset();
});

onBeforeUnmount(() => {
  canvasObserver?.disconnect();
  if (rerenderRaf !== null) {
    window.cancelAnimationFrame(rerenderRaf);
    rerenderRaf = null;
  }
  if (mathRaf !== null) {
    window.cancelAnimationFrame(mathRaf);
    mathRaf = null;
  }
});

function worldToScreenX(x: number): number {
  return x * scale.value + panX.value;
}

function worldToScreenY(y: number): number {
  return y * scale.value + panY.value;
}

function screenToWorld(x: number, y: number): { x: number; y: number } {
  return {
    x: (x - panX.value) / scale.value,
    y: (y - panY.value) / scale.value
  };
}

function screenPos(nodeId: string): { x: number; y: number } {
  const n = props.nodes.find((it) => it.id === nodeId);
  return n ? { x: worldToScreenX(n.x), y: worldToScreenY(n.y) } : { x: 0, y: 0 };
}

function edgeColor(edgeType: EdgeItem["edge_type"]): string {
  if (edgeType === "counter") return "#d94141";
  if (edgeType === "redirect") return "#8f8f8f";
  if (edgeType === "bridge") return "#156f63";
  return "#2563eb";
}

function edgePath(edge: RenderEdge): string {
  const src = sourceAnchor(edge);
  const dst = targetAnchor(edge);
  const dx = Math.max(40, Math.abs(dst.x - src.x) * 0.35);
  const c1x = src.x + dx;
  const c1y = src.y;
  const c2x = dst.x - dx;
  const c2y = dst.y;
  return `M ${src.x},${src.y} C ${c1x},${c1y} ${c2x},${c2y} ${dst.x},${dst.y}`;
}

function edgeAnchorByElement(selector: string, side: "left" | "right"): { x: number; y: number } | null {
  const canvas = canvasRef.value;
  if (!canvas) return null;
  const el = canvas.querySelector(selector) as HTMLElement | null;
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  const root = canvas.getBoundingClientRect();
  return {
    x: (side === "left" ? rect.left : rect.right) - root.left,
    y: rect.top - root.top + rect.height / 2
  };
}

function sourceAnchor(edge: RenderEdge): { x: number; y: number } {
  if (edge.source_section_key) {
    const canvas = canvasRef.value;
    if (canvas) {
      const el = canvas.querySelector(`[data-section-key="${edge.source_section_key}"]`) as HTMLElement | null;
      if (el) {
        const root = canvas.getBoundingClientRect();
        const y = el.getBoundingClientRect().top - root.top + el.getBoundingClientRect().height / 2;
        const nodeEl = el.closest(".node") as HTMLElement | null;
        if (nodeEl) {
          const nr = nodeEl.getBoundingClientRect();
          return { x: nr.right - root.left, y };
        }
      }
    }
  }
  const p = edgeAnchorByElement(`[data-node-title-id="${edge.source_node_id}"]`, "right");
  if (p) return p;
  const n = props.nodes.find((it) => it.id === edge.source_node_id);
  if (!n) return { x: 0, y: 0 };
  return { x: worldToScreenX(n.x) + widthOf(n) * scale.value, y: worldToScreenY(n.y) + 18 * scale.value };
}

function targetAnchor(edge: RenderEdge): { x: number; y: number } {
  const p = edgeAnchorByElement(`[data-node-title-id="${edge.target_node_id}"]`, "left");
  if (p) return p;
  const n = props.nodes.find((it) => it.id === edge.target_node_id);
  if (!n) return { x: 0, y: 0 };
  return { x: worldToScreenX(n.x), y: worldToScreenY(n.y) + 18 * scale.value };
}

function nodeStyle(node: NodeItem): Record<string, string | number> {
  const width = `${widthOf(node)}px`;
  const bg = `hsl(${Math.floor(node.mastery * 120)}, 65%, 90%)`;
  const z = nodeZ.value[node.id] ?? 1;
  return {
    transform: `translate(${worldToScreenX(node.x)}px, ${worldToScreenY(node.y)}px) scale(${scale.value})`,
    width,
    background: bg,
    zIndex: z
  };
}

function widthOf(node: NodeItem): number {
  return nodeWidth.value[node.id] ?? node.width ?? (200 + node.importance * 70);
}

function sections(content: string): Array<{ title: string; body: string }> {
  const lines = content.split(/\r?\n/);
  const out: Array<{ title: string; body: string }> = [];
  let current: { title: string; body: string[] } | null = null;
  for (const line of lines) {
    const m = line.match(/^##\s+(.+)\s*$/);
    if (m) {
      if (current) out.push({ title: current.title, body: cleanSectionBody(current.body.join("\n")) });
      current = { title: m[1], body: [] };
      continue;
    }
    if (current) current.body.push(line);
  }
  if (current) out.push({ title: current.title, body: cleanSectionBody(current.body.join("\n")) });
  return out.filter((x) => x.title || x.body);
}

function cleanSectionBody(text: string): string {
  const lines = text.split(/\r?\n/);
  const isDivider = (s: string): boolean => /^(\s*)(-{3,}|\*{3,}|_{3,})(\s*)$/.test(s);
  while (lines.length > 0 && isDivider(lines[0] || "")) lines.shift();
  while (lines.length > 0 && isDivider(lines[lines.length - 1] || "")) lines.pop();
  return lines.join("\n").trim();
}

function normalizeMathDelimiters(text: string): string {
  let out = text;
  // Only fix explicit malformed forms like `$ $...$ $` / `$$ $$...$$ $$`.
  // Leave valid formulas untouched to avoid introducing parser regressions.
  let prev = "";
  while (prev !== out) {
    prev = out;
    out = out.replace(/(^|[^\\])\$\s+\$([\s\S]*?)\$\s+\$/g, (_m, prefix, body) => {
      return `${prefix}$${String(body).trim()}$`;
    });
    out = out.replace(/(^|[^\\])\$\$\s+\$\$([\s\S]*?)\$\$\s+\$\$/g, (_m, prefix, body) => {
      return `${prefix}$$${String(body).trim()}$$`;
    });
  }
  console.log("Normalized math delimiters:", { before: text, after: out });
  return out;
}

function protectMathSegments(text: string): { content: string; segments: string[] } {
  const segments: string[] = [];
  const content = text.replace(/(\\)?\$\$([\s\S]+?)\$\$|(\\)?\$([^\n$]+?)\$/g, (m, esc1, _b1, esc2) => {
    if (esc1 || esc2) return m;
    const token = `@@MATH_SEG_${segments.length}@@`;
    segments.push(m);
    return token;
  });
  return { content, segments };
}

function restoreMathSegments(html: string, segments: string[]): string {
  return html.replace(/@@MATH_SEG_(\d+)@@/g, (m, idxText) => {
    const idx = Number(idxText);
    if (!Number.isFinite(idx) || idx < 0 || idx >= segments.length) return m;
    return segments[idx] ?? m;
  });
}

function renderMarkdown(text: string): string {
  const normalized = normalizeMathDelimiters(cleanSectionBody(text || ""));
  const protectedMath = protectMathSegments(normalized);
  const raw = md.render(protectedMath.content);
  const restored = restoreMathSegments(raw, protectedMath.segments);
  return DOMPurify.sanitize(restored);
}

function sectionBodyKey(node: NodeItem, idx: number, body: string): string {
  return `${node.id}:${idx}:${Math.round(widthOf(node))}:${contentRenderTick.value}:${body.length}`;
}

function nodeBodyKey(node: NodeItem): string {
  return `${node.id}:${Math.round(widthOf(node))}:${contentRenderTick.value}:${node.content.length}`;
}

function sectionKey(nodeId: string, idx: number): string {
  return `${nodeId}::${idx}`;
}

function bringToFront(nodeId: string): void {
  zCounter.value += 1;
  nodeZ.value[nodeId] = zCounter.value;
}

function updateCanvasSize(): void {
  const el = canvasRef.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  canvasSize.value = { w: Math.max(1, Math.floor(rect.width)), h: Math.max(1, Math.floor(rect.height)) };
  scheduleCanvasRerender();
}

function scheduleCanvasRerender(): void {
  if (rerenderRaf !== null) return;
  rerenderRaf = window.requestAnimationFrame(() => {
    rerenderRaf = null;
    edgeRenderTick.value += 1;
  });
}

function scheduleMathTypeset(): void {
  if (mathRaf !== null) return;
  mathRaf = window.requestAnimationFrame(async () => {
    mathRaf = null;
    await nextTick();
    const root = canvasRef.value;
    const mj = window.MathJax;
    if (!root || !mj?.typesetPromise) return;
    const elements = Array.from(root.querySelectorAll(".markdown-body"));
    if (elements.length === 0) return;
    try {
      mj.typesetClear?.(elements);
      await mj.typesetPromise(elements);
    } catch {
      // ignore transient MathJax parse/runtime errors during streaming updates
    }
  });
}

function startNodeDrag(event: PointerEvent, nodeId: string): void {
  event.preventDefault();
  const node = props.nodes.find((n) => n.id === nodeId);
  const canvas = canvasRef.value;
  if (!node || !canvas) return;
  isInteracting.value = true;
  dragMode.value = "node";
  draggingNodeId.value = nodeId;
  bringToFront(nodeId);
  const rect = canvas.getBoundingClientRect();
  const sx = event.clientX - rect.left;
  const sy = event.clientY - rect.top;
  dragOffset.value = {
    x: sx - worldToScreenX(node.x),
    y: sy - worldToScreenY(node.y)
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopPointerAction, { once: true });
}

function startResize(event: PointerEvent, nodeId: string): void {
  event.preventDefault();
  const node = props.nodes.find((n) => n.id === nodeId);
  if (!node) return;
  isInteracting.value = true;
  resizingNodeId.value = nodeId;
  bringToFront(nodeId);
  resizeStart.value = {
    x: event.clientX,
    width: widthOf(node)
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopPointerAction, { once: true });
}

function startDraftDrag(event: PointerEvent): void {
  event.preventDefault();
  const q = props.draftQuestion;
  const canvas = canvasRef.value;
  if (!q || !canvas) return;
  isInteracting.value = true;
  dragMode.value = "draft";
  const rect = canvas.getBoundingClientRect();
  const sx = event.clientX - rect.left;
  const sy = event.clientY - rect.top;
  dragOffset.value = {
    x: sx - worldToScreenX(q.x),
    y: sy - worldToScreenY(q.y)
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopPointerAction, { once: true });
}

function startInitDrag(event: PointerEvent): void {
  event.preventDefault();
  const canvas = canvasRef.value;
  if (!canvas) return;
  isInteracting.value = true;
  dragMode.value = "init";
  const rect = canvas.getBoundingClientRect();
  const sx = event.clientX - rect.left;
  const sy = event.clientY - rect.top;
  dragOffset.value = {
    x: sx - worldToScreenX(props.initNodePosition.x),
    y: sy - worldToScreenY(props.initNodePosition.y)
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopPointerAction, { once: true });
}

function onCanvasPointerDown(event: PointerEvent): void {
  const target = event.target as HTMLElement;
  if (target.closest(".node")) return;
  event.preventDefault();
  const canvas = canvasRef.value;
  if (!canvas) return;
  isInteracting.value = true;
  panDragging.value = true;
  panStart.value = {
    x: event.clientX,
    y: event.clientY,
    panX: panX.value,
    panY: panY.value
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopPointerAction, { once: true });
}

function onPointerMove(event: PointerEvent): void {
  if (resizingNodeId.value || dragMode.value || panDragging.value) {
    event.preventDefault();
  }
  if (resizingNodeId.value) {
    const id = resizingNodeId.value;
    const delta = (event.clientX - resizeStart.value.x) / scale.value;
    const next = Math.max(180, Math.min(640, resizeStart.value.width + delta));
    nodeWidth.value[id] = next;
    const node = props.nodes.find((n) => n.id === id);
    if (node) node.width = next;
    contentRenderTick.value += 1;
    scheduleCanvasRerender();
    scheduleMathTypeset();
    return;
  }
  if (dragMode.value === "node" && draggingNodeId.value && canvasRef.value) {
    const node = props.nodes.find((n) => n.id === draggingNodeId.value);
    if (!node) return;
    const rect = canvasRef.value.getBoundingClientRect();
    const sx = event.clientX - rect.left;
    const sy = event.clientY - rect.top;
    node.x = (sx - dragOffset.value.x - panX.value) / scale.value;
    node.y = (sy - dragOffset.value.y - panY.value) / scale.value;
    scheduleCanvasRerender();
    return;
  }
  if (dragMode.value === "draft" && canvasRef.value && props.draftQuestion) {
    const rect = canvasRef.value.getBoundingClientRect();
    const sx = event.clientX - rect.left;
    const sy = event.clientY - rect.top;
    emit("draft-move", {
      x: (sx - dragOffset.value.x - panX.value) / scale.value,
      y: (sy - dragOffset.value.y - panY.value) / scale.value
    });
    scheduleCanvasRerender();
    return;
  }
  if (dragMode.value === "init" && canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect();
    const sx = event.clientX - rect.left;
    const sy = event.clientY - rect.top;
    emit("init-node-move", {
      x: (sx - dragOffset.value.x - panX.value) / scale.value,
      y: (sy - dragOffset.value.y - panY.value) / scale.value
    });
    scheduleCanvasRerender();
    return;
  }
  if (panDragging.value) {
    panX.value = panStart.value.panX + (event.clientX - panStart.value.x);
    panY.value = panStart.value.panY + (event.clientY - panStart.value.y);
    scheduleCanvasRerender();
  }
}

function stopPointerAction(): void {
  if (resizingNodeId.value) {
    const node = props.nodes.find((n) => n.id === resizingNodeId.value);
    if (node) emit("resize-end", { nodeId: node.id, width: widthOf(node) });
    contentRenderTick.value += 1;
    scheduleMathTypeset();
  }
  resizingNodeId.value = null;
  if (dragMode.value === "node" && draggingNodeId.value) {
    const node = props.nodes.find((n) => n.id === draggingNodeId.value);
    if (node) emit("move-end", { nodeId: node.id, x: node.x, y: node.y });
  }
  dragMode.value = null;
  draggingNodeId.value = null;
  panDragging.value = false;
  isInteracting.value = false;
  scheduleCanvasRerender();
  window.removeEventListener("pointermove", onPointerMove);
}

function onWheel(event: WheelEvent): void {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const sx = event.clientX - rect.left;
  const sy = event.clientY - rect.top;
  const wx = (sx - panX.value) / scale.value;
  const wy = (sy - panY.value) / scale.value;

  const factor = event.deltaY < 0 ? 1.1 : 0.9;
  const nextScale = Math.max(0.35, Math.min(2.5, scale.value * factor));
  scale.value = nextScale;
  panX.value = sx - wx * nextScale;
  panY.value = sy - wy * nextScale;
  scheduleCanvasRerender();
}

function onCanvasDblClick(event: MouseEvent): void {
  const target = event.target as HTMLElement;
  if (target.closest(".node")) return;
  if (!canvasRef.value) return;
  const rect = canvasRef.value.getBoundingClientRect();
  const sx = event.clientX - rect.left;
  const sy = event.clientY - rect.top;
  const world = screenToWorld(sx, sy);
  emit("canvas-dblclick", world);
}
</script>
