'use client';

import * as React from 'react';

import { connectTelemetry, read, whenReady } from '@/lib/api';
import type { AppState, Telemetry } from '@/types';

const POLL_MS = 250;
const MAX_LOG_LINES = 300;

interface BotContextValue {
  state: AppState | null;
  telemetry: Telemetry | null;
  logs: string[];
  ready: boolean;
  preview: boolean;
  connected: boolean;
  error: string;
  refresh: () => Promise<void>;
}

const BotContext = React.createContext<BotContextValue | null>(null);

export function useBot() {
  const context = React.useContext(BotContext);
  if (!context) throw new Error('useBot precisa estar dentro de <BotProvider>');
  return context;
}

export function BotProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AppState | null>(null);
  const [telemetry, setTelemetry] = React.useState<Telemetry | null>(null);
  const [logs, setLogs] = React.useState<string[]>([]);
  const [ready, setReady] = React.useState(false);
  const [preview, setPreview] = React.useState(false);
  const [connected, setConnected] = React.useState(false);
  const [error, setError] = React.useState('');

  const refresh = React.useCallback(async () => {
    const next = await read<AppState>('state');
    if (next) setState(next);
  }, []);

  React.useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();

    if (new URLSearchParams(window.location.search).get('preview') === '1' && !window.pywebview) {
      import('@/lib/preview').then(({ previewState, previewTelemetry }) => {
        if (!alive) return;
        setState(previewState);
        setTelemetry(previewTelemetry);
        setLogs(['Prévia visual. Abra o aplicativo para conectar suas janelas.']);
        setPreview(true);
        setReady(true);
      });
      return () => { alive = false; };
    }

    const loop = async () => {
      // via servidor local: pela ponte, 4 chamadas/s derrubavam o processo
      const tick = await read<Telemetry>('poll');
      if (!alive) return;
      if (tick) {
        setConnected(true);
        setError('');
        setTelemetry(tick);
        if (tick.logs.length) {
          setLogs((previous) =>
            [...previous, ...tick.logs].slice(-MAX_LOG_LINES),
          );
        }
      } else {
        setConnected(false);
        setError('Sem resposta do motor. Aguardando reconexão…');
      }
      timer = setTimeout(loop, POLL_MS);
    };

    whenReady(controller.signal)
      .then(connectTelemetry)
      .then(async () => {
        if (!alive) return;
        const initial = await read<AppState>('state');
        if (!alive) return;
        if (!initial) throw new Error('Não foi possível ler a configuração. Reabra o aplicativo.');
        setState(initial);
        setReady(true);
        loop();
      }).catch((failure: Error) => {
        if (alive) setError(failure.message);
      });

    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [refresh]);

  const value = React.useMemo(
    () => ({ state, telemetry, logs, ready, preview, connected, error, refresh }),
    [state, telemetry, logs, ready, preview, connected, error, refresh],
  );

  return <BotContext.Provider value={value}>{children}</BotContext.Provider>;
}
