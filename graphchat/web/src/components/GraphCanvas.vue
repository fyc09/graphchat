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
        stroke-width="2"
        fill="none"
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
      :class="[{ selected: selectedIds.includes(node.id), 'node-collapsed': isNodeCollapsed(node.id) }, `node-${node.node_type}`]"
      :style="nodeStyle(node)"
      @pointerdown.capture="onNodePointerDown(node.id)"
    >
      <div class="title-row" :data-node-title-id="node.id" @pointerdown.stop="startNodeDrag($event, node.id)">
        <div class="title-main">
          <button
            class="node-collapse-btn"
            type="button"
            :aria-label="isNodeCollapsed(node.id) ? 'Expand node' : 'Collapse node'"
            @pointerdown.stop
            @click.stop="toggleNodeCollapsed(node.id)"
          >
            <svg viewBox="0 0 10 10" width="10" height="10" :class="{ collapsed: isNodeCollapsed(node.id) }">
              <path d="M2 1.5 L8 5 L2 8.5 Z" fill="currentColor" />
            </svg>
          </button>
          <div class="check-inline" @click.stop>
            <input type="checkbox" :checked="selectedIds.includes(node.id)" @change="$emit('toggle-select', node.id)" />
            <span
              class="title markdown-inline"
              :data-math-node-id="node.id"
              :data-math-section-key="'title'"
              v-html="renderInlineMarkdown(node.title)"
            ></span>
          </div>
        </div>
        <div class="node-actions" @pointerdown.stop @click.stop>
          <button
            class="node-action-btn danger"
            type="button"
            title="Delete node"
            aria-label="Delete node"
            @click.stop="$emit('delete-node', node.id)"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
              <path
                d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v8h-2V9zm4 0h2v8h-2V9zM7 9h2v8H7V9zm-1 12h12l1-12H5l1 12z"
                fill="currentColor"
              />
            </svg>
          </button>
          <button
            class="node-action-btn"
            type="button"
            title="Hide subtree"
            aria-label="Hide subtree"
            @click.stop="$emit('hide-node', node.id)"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
              <path
                d="M12 5c5.5 0 9.5 4.7 10.7 6.4.4.5.4 1.2 0 1.7C21.5 14.8 17.5 19.5 12 19.5S2.5 14.8 1.3 13.1a1.4 1.4 0 010-1.7C2.5 9.7 6.5 5 12 5zm0 2C7.8 7 4.5 10.5 3.3 12c1.2 1.5 4.5 5 8.7 5s7.5-3.5 8.7-5C19.5 10.5 16.2 7 12 7zm0 2.5A2.5 2.5 0 1112 14a2.5 2.5 0 010-5z"
                fill="currentColor"
              />
            </svg>
          </button>
          <button
            class="node-action-btn"
            type="button"
            title="Manage child visibility"
            aria-label="Manage child visibility"
            @click.stop="toggleChildMenu(node.id, 'all')"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
              <path d="M4 5h16v2H4V5zm0 6h10v2H4v-2zm0 6h16v2H4v-2z" fill="currentColor" />
            </svg>
          </button>
          <div
            v-if="openChildMenuNodeId === node.id && openChildMenuMode === 'all'"
            class="child-manager"
            @pointerdown.stop
            @click.stop
            @wheel.stop
          >
            <div class="child-manager-list">
              <button
                v-for="child in menuChildrenOf(node.id)"
                :key="child.id"
                type="button"
                class="child-toggle"
                :class="[child.hidden ? 'hidden' : 'visible', `node-${child.node_type}`]"
                :title="child.hidden ? `Show ${child.title}` : `Hide ${child.title}`"
                @click.stop="$emit('toggle-child-hidden', { childNodeId: child.id, hidden: !child.hidden })"
              >
                {{ child.title }}
              </button>
              <div v-if="menuChildrenOf(node.id).length === 0" class="child-manager-empty">No children</div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="hasHiddenChildren(node.id)" class="hidden-child-indicator" @pointerdown.stop @click.stop>
        <svg viewBox="0 0 18 10" width="18" height="10" aria-hidden="true" class="hidden-child-line">
          <line x1="1" y1="5" x2="17" y2="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2 2" />
        </svg>
        <button
          class="node-action-btn hidden-child-btn"
          type="button"
          title="Manage hidden children"
          aria-label="Manage hidden children"
          @click.stop="toggleChildMenu(node.id, 'hidden')"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
            <circle cx="6" cy="12" r="1.8" fill="currentColor" />
            <circle cx="12" cy="12" r="1.8" fill="currentColor" />
            <circle cx="18" cy="12" r="1.8" fill="currentColor" />
          </svg>
        </button>
        <div
          v-if="openChildMenuNodeId === node.id && openChildMenuMode === 'hidden'"
          class="child-manager"
          @pointerdown.stop
          @click.stop
          @wheel.stop
        >
          <div class="child-manager-list">
            <button
              v-for="child in menuChildrenOf(node.id)"
              :key="child.id"
              type="button"
              class="child-toggle"
              :class="[child.hidden ? 'hidden' : 'visible', `node-${child.node_type}`]"
              :title="child.hidden ? `Show ${child.title}` : `Hide ${child.title}`"
              @click.stop="$emit('toggle-child-hidden', { childNodeId: child.id, hidden: !child.hidden })"
            >
              {{ child.title }}
            </button>
            <div v-if="menuChildrenOf(node.id).length === 0" class="child-manager-empty">No children</div>
          </div>
        </div>
      </div>
      <div v-show="!isNodeCollapsed(node.id)" class="content">
        <template v-if="sections(node.content).length > 0">
          <details
            v-for="(s, i) in sections(node.content)"
            :key="`${node.id}-${i}`"
            :open="isSectionOpen(sectionKey(node.id, i))"
            @toggle="onSectionToggle(sectionKey(node.id, i), $event)"
          >
            <summary class="summary-row" :data-section-key="sectionKey(node.id, i)">
              <span class="summary-chevron" aria-hidden="true">
                <svg viewBox="0 0 10 10" width="10" height="10">
                  <path d="M2 1.5 L8 5 L2 8.5 Z" fill="currentColor" />
                </svg>
              </span>
              <input
                type="checkbox"
                :checked="selectedSectionKeys.includes(sectionKey(node.id, i))"
                @click.stop
                @change="$emit('toggle-section', { nodeId: node.id, title: s.title, body: s.body, key: sectionKey(node.id, i) })"
              />
              <span
                class="section-title markdown-inline"
                :class="{ 'section-selected': selectedSectionKeys.includes(sectionKey(node.id, i)) }"
                :data-math-node-id="node.id"
                :data-math-section-key="sectionKey(node.id, i)"
                v-html="renderInlineMarkdown(s.title)"
              ></span>
            </summary>
            <div class="section-panel">
              <div
                :key="sectionBodyKey(node, i, s.body)"
                class="section-panel-inner section-body markdown-body"
                :data-math-node-id="node.id"
                :data-math-section-key="sectionKey(node.id, i)"
                v-html="renderMarkdown(s.body)"
              ></div>
            </div>
          </details>
        </template>
        <template v-else>
          <div
            :key="nodeBodyKey(node)"
            class="section-body markdown-body"
            :data-math-node-id="node.id"
            v-html="renderMarkdown(node.content)"
          ></div>
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
import { ensureMathJax, typesetMathInElements } from "../mathjax";

type DraftQuestion = { x: number; y: number; text: string };
type RenderEdge = Pick<EdgeItem, "id" | "source_node_id" | "target_node_id" | "source_section_key" | "edge_type">;
type ChildControl = {
  parentNodeId: string;
  children: Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }>;
};

const props = withDefaults(
  defineProps<{
    nodes: NodeItem[];
    edges: EdgeItem[];
    childControls: ChildControl[];
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
    initNodePosition: () => ({ x: 0, y: 0 }),
    childControls: () => []
  }
);

const emit = defineEmits<{
  (e: "move-end", payload: { nodeId: string; x: number; y: number }): void;
  (e: "resize-end", payload: { nodeId: string; width: number }): void;
  (e: "toggle-select", nodeId: string): void;
  (e: "toggle-section", payload: { nodeId: string; title: string; body: string; key: string }): void;
  (e: "clear-select"): void;
  (e: "canvas-dblclick", payload: { x: number; y: number }): void;
  (e: "draft-change", value: string): void;
  (e: "draft-move", payload: { x: number; y: number }): void;
  (e: "draft-submit"): void;
  (e: "draft-cancel"): void;
  (e: "init-topic-change", value: string): void;
  (e: "init-node-move", payload: { x: number; y: number }): void;
  (e: "init-submit"): void;
  (e: "delete-node", nodeId: string): void;
  (e: "hide-node", nodeId: string): void;
  (e: "toggle-child-hidden", payload: { childNodeId: string; hidden: boolean }): void;
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
const nodeCollapsed = ref<Record<string, boolean>>({});
const sectionOpen = ref<Record<string, boolean>>({});
const edgeRenderTick = ref(0);
const contentRenderTick = ref(0);
const openChildMenuNodeId = ref<string | null>(null);
const openChildMenuMode = ref<"all" | "hidden">("all");
let canvasObserver: ResizeObserver | null = null;
let rerenderRaf: number | null = null;
let mathRaf: number | null = null;
let mathTypesetting = false;
let mathRerunQueued = false;
const mathSignatureByElement = new WeakMap<Element, string>();

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
});
const MATH_TYPESET_TIMEOUT_MS = 4000;

function hasMathInText(text: string): boolean {
  if (!text) return false;
  return /(^|[^\\])\$\$[\s\S]+?\$\$|(^|[^\\])\$[^\n$]+?\$/.test(text);
}

async function typesetWithTimeout(element: Element, timeoutMs: number): Promise<void> {
  const typesetPromise = typesetMathInElements([element]);
  await Promise.race([
    typesetPromise,
    new Promise<never>((_resolve, reject) => {
      window.setTimeout(() => reject(new Error(`MathJax typeset timeout (${timeoutMs}ms)`)), timeoutMs);
    })
  ]);
}

const draftStyle = computed(() => {
  if (!props.draftQuestion) return {};
  return {
    transform: `translate(${worldToScreenX(props.draftQuestion.x)}px, ${worldToScreenY(props.draftQuestion.y)}px) scale(${scale.value})`,
    width: "400px",
    zIndex: 9999
  };
});

const initStyle = computed(() => ({
  transform: `translate(${worldToScreenX(props.initNodePosition.x)}px, ${worldToScreenY(props.initNodePosition.y)}px) scale(${scale.value})`,
  width: "400px",
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
      edge_type: "direct"
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
      edge_type: "direct"
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
  if (edgeType === "direct") return "#2563eb";
  return "#2563eb";
}

function edgePath(edge: RenderEdge): string {
  const src = sourceAnchor(edge);
  const dst = targetAnchor(edge);
  const dx = 130 * scale.value;
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
    const sourceNodeId = String(edge.source_section_key).split("::")[0] || edge.source_node_id;
    if (!isNodeCollapsed(sourceNodeId)) {
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
  const z = nodeZ.value[node.id] ?? 1;
  return {
    transform: `translate(${worldToScreenX(node.x)}px, ${worldToScreenY(node.y)}px) scale(${scale.value})`,
    width,
    zIndex: z
  };
}

function widthOf(node: NodeItem): number {
  return nodeWidth.value[node.id] ?? node.width ?? 400;
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
  // Drop empty math placeholders that can appear during streaming and cause KaTeX metrics warnings.
  out = out.replace(/(^|[^\\])\$\$\s*\$\$/g, (_m, prefix) => prefix as string);
  out = out.replace(/(^|[^\\])\$\s+\$/g, (_m, prefix) => prefix as string);
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
  return out;
}

function childrenOf(parentNodeId: string): Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }> {
  return props.childControls.find((it) => it.parentNodeId === parentNodeId)?.children ?? [];
}

function hiddenChildrenOf(parentNodeId: string): Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }> {
  return childrenOf(parentNodeId).filter((child) => child.hidden);
}

function hasHiddenChildren(parentNodeId: string): boolean {
  return hiddenChildrenOf(parentNodeId).length > 0;
}

function menuChildrenOf(parentNodeId: string): Array<{ id: string; title: string; node_type: NodeItem["node_type"]; hidden: boolean }> {
  if (openChildMenuMode.value === "hidden") return hiddenChildrenOf(parentNodeId);
  return childrenOf(parentNodeId);
}

function toggleChildMenu(parentNodeId: string, mode: "all" | "hidden"): void {
  if (openChildMenuNodeId.value === parentNodeId && openChildMenuMode.value === mode) {
    openChildMenuNodeId.value = null;
    return;
  }
  openChildMenuNodeId.value = parentNodeId;
  openChildMenuMode.value = mode;
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
  return DOMPurify.sanitize(restored, {
    ADD_ATTR: ["style", "aria-hidden"],
    ADD_TAGS: [
      "math",
      "semantics",
      "mrow",
      "mi",
      "mn",
      "mo",
      "msup",
      "msub",
      "msubsup",
      "mfrac",
      "msqrt",
      "mroot",
      "mspace",
      "annotation"
    ]
  });
}

function renderInlineMarkdown(text: string): string {
  const normalized = normalizeMathDelimiters((text || "").trim());
  const protectedMath = protectMathSegments(normalized);
  const raw = md.renderInline(protectedMath.content);
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

function isSectionOpen(key: string): boolean {
  return sectionOpen.value[key] ?? true;
}

function isNodeCollapsed(nodeId: string): boolean {
  return nodeCollapsed.value[nodeId] ?? false;
}

function toggleNodeCollapsed(nodeId: string): void {
  nodeCollapsed.value[nodeId] = !isNodeCollapsed(nodeId);
  scheduleCanvasRerender();
  scheduleMathTypeset();
}

function onSectionToggle(key: string, event: Event): void {
  const el = event.currentTarget as HTMLDetailsElement | null;
  if (!el) return;
  sectionOpen.value[key] = el.open;
  scheduleCanvasRerender();
  scheduleMathTypeset();
}

function bringToFront(nodeId: string): void {
  zCounter.value += 1;
  nodeZ.value[nodeId] = zCounter.value;
}

function onNodePointerDown(nodeId: string): void {
  bringToFront(nodeId);
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
    if (!root) return;
    await ensureMathJax();
    const elements = Array.from(root.querySelectorAll(".markdown-body, .markdown-inline"));
    if (elements.length === 0) return;
    if (mathTypesetting) {
      mathRerunQueued = true;
      return;
    }
    mathTypesetting = true;
    try {
      for (const el of elements) {
        const signature = (el as HTMLElement).innerHTML;
        const prevSignature = mathSignatureByElement.get(el);
        const hasMath = hasMathInText((el as HTMLElement).textContent || "");
        if (prevSignature === signature) continue;
        if (!hasMath) {
          mathSignatureByElement.set(el, signature);
          continue;
        }
        try {
          await typesetWithTimeout(el, MATH_TYPESET_TIMEOUT_MS);
          mathSignatureByElement.set(el, (el as HTMLElement).innerHTML);
        } catch {
          // Ignore malformed/incomplete TeX during streaming updates.
        }
      }
    } finally {
      mathTypesetting = false;
      if (mathRerunQueued) {
        mathRerunQueued = false;
        scheduleMathTypeset();
      }
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
  openChildMenuNodeId.value = null;
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
