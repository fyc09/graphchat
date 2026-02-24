declare global {
  interface Window {
    MathJax?: {
      typesetPromise?: (elements?: Element[]) => Promise<void>;
      typesetClear?: (elements?: Element[]) => void;
    };
  }
}

let loading: Promise<void> | null = null;

export async function ensureMathJax(): Promise<void> {
  if (window.MathJax?.typesetPromise) return;
  if (!loading) {
    (window as Window & { MathJax: unknown }).MathJax = {
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
        skipHtmlTags: ["script", "noscript", "style", "textarea", "pre", "code"],
        enableAssistiveMml: false,
        enableExplorer: false,
        enableSpeech: false,
        enableBraille: false,
        a11y: {
          speech: false,
          braille: false
        },
        menuOptions: {
          settings: {
            assistiveMml: false,
            explorer: false,
            speech: false,
            braille: false
          }
        },
        worker: {
          path: "",
          pool: "",
          worker: ""
        }
      },
      startup: {
        typeset: false
      }
    };
    loading = import("mathjax/es5/tex-chtml.js").then(() => undefined);
  }
  await loading;
}
