'use client';

import * as React from 'react';
import { useBot } from '@/components/bot-provider';
import { Button } from '@/components/ui/button';
import { call } from '@/lib/api';
import type { GameWindow } from '@/types';

export function WindowSelector() {
  const { state, telemetry, refresh } = useBot();
  const [windows, setWindows] = React.useState<GameWindow[]>([]);
  const [chosen, setChosen] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');

  const reload = React.useCallback(async () => {
    const items = await call('list_windows');
    setWindows(items ?? []);
    setChosen('');
  }, []);

  React.useEffect(() => { reload(); }, [reload]);

  const select = async () => {
    const candidate = windows.find((item) => String(item.hwnd) === chosen);
    if (!candidate) return;
    setBusy(true);
    try {
      const ok = await call('select_window', candidate);
      setError(ok ? '' : 'Seleção recusada. Consulte o log e atualize a lista.');
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="glass-panel border-border bg-card shrink-0 space-y-2 rounded-lg border p-3 text-xs">
      <div className="font-medium">Jogo 1 — ataques: {state?.selectedWindow
        ? `${state.selectedWindow.title} (PID ${state.selectedWindow.pid})`
        : 'selecione uma janela'}</div>
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Janela do jogo" className="bg-input min-w-0 flex-1 rounded p-2"
          value={chosen} onChange={(event) => setChosen(event.target.value)}>
          <option value="">Escolha a janela de ataques (Jogo 1)…</option>
          {windows.map((item, index) => (
            <option key={`${item.hwnd}:${item.process_created}`} value={String(item.hwnd)}>
              {index + 1}. {item.title} (PID {item.pid})
            </option>
          ))}
        </select>
        <Button size="sm" variant="outline" disabled={busy} onClick={reload}>Atualizar</Button>
        <Button size="sm" variant="accent" disabled={busy || !chosen} onClick={select}>Selecionar</Button>
      </div>
      {!windows.length && <p className="text-muted-foreground">Abra o Trove e clique em Atualizar.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="input-mode">Envio:</label>
        <select id="input-mode" className="bg-input rounded p-1" value={state?.inputMode ?? 'foreground'}
          disabled={busy} onChange={async (event) => {
            setBusy(true);
            try {
              const ok = await call('set_input_mode', event.target.value as 'foreground' | 'messages');
              setError(ok ? '' : 'Modo recusado. Consulte o log.');
              await refresh();
            } finally { setBusy(false); }
          }}>
          <option value="foreground">Compatibilidade (com foco)</option>
          <option value="messages">Mensagens (experimental)</option>
        </select>
        <span className="text-muted-foreground">{telemetry?.targetReason ?? 'Destino válido'}</span>
      </div>
      <p className="text-muted-foreground">{state?.inputMode === 'messages'
        ? 'Skills exigem ícones visíveis. Diálogos exigem foco.'
        : 'Pausa quando o Jogo 1 perde o foco.'}</p>
      {error && <p role="alert" className="text-red-400">{error}</p>}
    </section>
  );
}
