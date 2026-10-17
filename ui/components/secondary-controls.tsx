'use client';

import * as React from 'react';
import { useBot } from '@/components/bot-provider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import type { GameWindow } from '@/types';

export function SecondaryControls() {
  const { state, telemetry, refresh } = useBot();
  const periodic = telemetry?.secondary ?? state?.secondary;
  const [windows, setWindows] = React.useState<GameWindow[]>([]);
  const [chosen, setChosen] = React.useState('');
  const [key, setKey] = React.useState(state?.secondary.key ?? 'e');
  const [interval, setIntervalValue] = React.useState(String(state?.secondary.interval ?? 20));
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const savedKey = state?.secondary.key;
  const savedInterval = state?.secondary.interval;
  React.useEffect(() => {
    if (savedKey !== undefined) setKey(savedKey);
    if (savedInterval !== undefined) setIntervalValue(String(savedInterval));
  }, [savedKey, savedInterval]);
  const load = React.useCallback(async () => {
    setWindows((await call('list_windows')) ?? []);
    setChosen('');
  }, []);
  React.useEffect(() => { load(); }, [load]);

  const act = async (action: () => Promise<boolean | null>) => {
    setBusy(true);
    try {
      const ok = await action();
      setError(ok ? '' : 'Ação recusada. Confira a janela, os ajustes e o log.');
      await refresh();
    } finally { setBusy(false); }
  };

  const target = periodic?.selectedWindow;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Jogo 2 — tecla periódica</CardTitle>
        <CardDescription>
          Envia uma tecla ao Jogo 2, mesmo com os ataques do Jogo 1 pausados. F12 para ambos.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs">{target
          ? `${target.title} (PID ${target.pid})`
          : 'Selecione o Jogo 2.'}</p>
        <div className="flex flex-wrap gap-2">
          <select aria-label="Janela da tecla periódica (Jogo 2)" className="bg-input min-w-0 flex-1 rounded p-2 text-xs"
            value={chosen} disabled={busy} onChange={(event) => setChosen(event.target.value)}>
            <option value="">Escolha outro processo do jogo…</option>
            {windows.map((item) => (
              <option key={`${item.hwnd}:${item.process_created}`} value={String(item.hwnd)}
                disabled={item.pid === state?.selectedWindow?.pid}>
                {item.title} (PID {item.pid})
                {item.pid === state?.selectedWindow?.pid ? ' (Jogo 1 — ataques)' : ''}
              </option>
            ))}
          </select>
          <Button size="sm" variant="outline" disabled={busy} onClick={load}>Atualizar</Button>
          <Button size="sm" variant="accent" disabled={busy || !chosen} onClick={() => act(async () => {
            const window = windows.find((item) => String(item.hwnd) === chosen);
            return window ? call('select_secondary_window', window) : false;
          })}>Selecionar</Button>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-xs">Tecla
            <Input aria-label="Tecla do Jogo 2" className="h-8 w-24" value={key}
              onChange={(event) => setKey(event.target.value)} />
          </label>
          <label className="space-y-1 text-xs">Intervalo (segundos)
            <Input aria-label="Intervalo do Jogo 2" className="h-8 w-32" type="number" min={0.5} max={86400} step={0.5}
              value={interval} onChange={(event) => setIntervalValue(event.target.value)} />
          </label>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => act(() => call('update_secondary', {
            key: key.trim(), interval: Number(interval),
          }))}>Salvar ajustes</Button>
          <label className="ml-auto flex items-center gap-2 text-sm">
            Tecla periódica
            <Switch checked={periodic?.enabled ?? false} disabled={busy || !target}
              onCheckedChange={(enabled) => act(() => call('set_secondary_enabled', enabled))} />
          </label>
        </div>
        <p className="text-muted-foreground text-xs" aria-live="polite">
          {periodic?.enabled
            ? `${periodic.key.toUpperCase()} a cada ${periodic.interval}s — ${periodic.status}${periodic.remaining !== null ? ` (${Math.ceil(periodic.remaining)}s)` : ''}`
            : `Desligada. Primeiro envio após ${periodic?.interval ?? 20}s ao ligar.`}
        </p>
        {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
      </CardContent>
    </Card>
  );
}
