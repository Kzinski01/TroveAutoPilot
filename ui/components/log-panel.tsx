'use client';

import * as React from 'react';

import { useBot } from '@/components/bot-provider';

export function LogPanel() {
  const { logs } = useBot();
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [logs]);

  return (
    <details className="event-log bg-popover border-border shrink-0 rounded-lg border" open>
      <summary className="cursor-pointer px-3 py-2 text-xs font-medium">Atividade <span className="ml-2 text-muted-foreground">{logs.length} eventos</span></summary>
      <div className="hide-scrollbar h-20 overflow-y-auto px-3 pb-3" aria-label="Log de atividade">
      {logs.length === 0 ? (
        <div className="text-muted-foreground font-mono text-xs">
          Aguardando eventos…
        </div>
      ) : (
        logs.map((line, index) => (
          <div key={index} className="text-muted-foreground font-mono text-xs leading-5">
            {line}
          </div>
        ))
      )}
      <div ref={endRef} />
      </div>
    </details>
  );
}
