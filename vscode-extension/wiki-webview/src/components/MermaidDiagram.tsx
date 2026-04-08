import { h } from 'preact';
import { useEffect, useRef } from 'preact/hooks';

declare const mermaid: { initialize: (cfg: object) => void; render: (id: string, def: string) => Promise<{ svg: string }> };

interface Props {
  definition: string;
  id: string;
}

let mermaidReady = false;

function ensureMermaid(): Promise<void> {
  if (mermaidReady) return Promise.resolve();
  return new Promise((resolve) => {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
    script.onload = () => {
      mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });
      mermaidReady = true;
      resolve();
    };
    document.head.appendChild(script);
  });
}

export function MermaidDiagram({ definition, id }: Props) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    let cancelled = false;
    ensureMermaid().then(async () => {
      if (cancelled || !container.current) return;
      try {
        const { svg } = await mermaid.render(id, definition);
        if (!cancelled && container.current) {
          container.current.innerHTML = svg;
        }
      } catch {
        if (!cancelled && container.current) {
          container.current.innerHTML = `<pre class="diagram-error">${definition}</pre>`;
        }
      }
    });
    return () => { cancelled = true; };
  }, [definition, id]);

  return <div class="mermaid-container" ref={container} />;
}
