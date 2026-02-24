type MathJaxRuntime = {
  typesetPromise?: (elements?: Element[]) => Promise<void>;
  typesetClear?: (elements?: Element[]) => void;
  startup?: {
    defaultReady?: () => void;
    document?: {
      options?: Record<string, unknown>;
    };
  };
};

let loading: Promise<void> | null = null;
let runtime: MathJaxRuntime | null = null;

export async function ensureMathJax(): Promise<void> {
  if (runtime?.typesetPromise) return;
  const globalObj = globalThis as typeof globalThis & { MathJax?: MathJaxRuntime | unknown };
  if (!loading) {
    try {
      const toDelete: string[] = [];
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (key && key.startsWith("MathJax")) toDelete.push(key);
      }
      for (const key of toDelete) localStorage.removeItem(key);
    } catch {
      // ignore
    }
    globalObj.MathJax = {
      loader: {
        load: ["input/tex", "output/svg"]
      },
      tex: {
        inlineMath: [
          ["$", "$"],
          ["\\(", "\\)"]
        ],
        displayMath: [
          ["$$", "$$"],
          ["\\[", "\\]"]
        ],
        processEscapes: true
      },
      options: {
        skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"]
      },
      startup: {
        typeset: false,
        ready: () => {
          const mj = globalObj.MathJax as MathJaxRuntime & {
            startup?: {
              defaultReady?: () => void;
              document?: { options?: Record<string, unknown> };
            };
          };
          mj.startup?.defaultReady?.();
          const doc = mj.startup?.document;
          if (doc?.options) {
            const renderActions = (doc.options.renderActions ?? {}) as Record<string, unknown>;
            delete renderActions.addMenu;
            delete renderActions.checkLoading;
            delete renderActions.attachSpeech;
            delete renderActions.enrich;
            delete renderActions.complexity;
            delete renderActions.explorable;
            doc.options.renderActions = renderActions;
          }
        }
      }
    };
    loading = (async () => {
      try {
        await import("mathjax-full/es5/tex-svg.js");
      } catch (err) {
        // Vite dev prebundle may serve a stale/missing dep URL after dependency switches.
        await import(/* @vite-ignore */ "/node_modules/mathjax-full/es5/tex-svg.js");
      }
      return undefined;
    })();
  }
  await loading;
  runtime = (globalObj.MathJax as MathJaxRuntime) ?? null;
}

export async function typesetMathInElements(elements: Element[]): Promise<void> {
  if (elements.length === 0) return;
  await ensureMathJax();
  if (!runtime?.typesetPromise) return;
  runtime.typesetClear?.(elements);
  await runtime.typesetPromise(elements);
}
