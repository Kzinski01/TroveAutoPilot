'use client';

import { Crosshair, Keyboard, Settings2, Wand2, Square, type LucideIcon } from 'lucide-react';
import * as React from 'react';

import { useBot } from '@/components/bot-provider';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';

export type PageKey = 'funcoes' | 'skills' | 'janelas' | 'ajustes';

export const NAV: { key: PageKey; label: string; icon: LucideIcon }[] = [
  { key: 'funcoes', label: 'Funções', icon: Keyboard },
  { key: 'skills', label: 'Skills', icon: Wand2 },
  { key: 'janelas', label: 'Janelas', icon: Crosshair },
  { key: 'ajustes', label: 'Ajustes', icon: Settings2 },
];

export function Sidebar({
  current,
  onNavigate,
}: {
  current: PageKey;
  onNavigate: (key: PageKey) => void;
}) {
  const { state, telemetry, ready, preview, connected, refresh } = useBot();
  const master = telemetry?.master ?? false;
  const focus = telemetry?.focus;

  const toggleMaster = async (value: boolean) => {
    await call('set_master', value);
    await refresh();
  };

  return (
    <aside className="app-sidebar bg-sidebar border-sidebar-border flex w-52 shrink-0 flex-col border-r">
      <div className="drag-region px-5 py-5">
        <div className="flex items-center gap-3">
          <span className="voxel-mark" aria-hidden="true"><i /><i /><i /></span>
          <div><div className="text-base font-semibold tracking-tight">Trove</div>
            <div className="text-xs text-muted-foreground">AutoBot</div></div>
        </div>
        <div
          className={cn(
            'focus-label mt-6 truncate text-[11px]',
            focus?.matched ? 'text-success' : 'text-muted-foreground',
          )}
          title={focus?.title}
        >
          {focus?.matched ? 'Jogo em foco' : 'Aguardando foco do jogo'}
        </div>
      </div>

      <nav aria-label="Navegação principal" className="flex flex-col gap-1 px-3">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onNavigate(key)}
            aria-current={current === key ? 'page' : undefined}
            className={cn(
              'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
              current === key
                ? 'nav-active bg-sidebar-accent text-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground',
            )}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-controls mt-auto space-y-5 px-4 py-5">
        <div className="rounded-lg border border-sidebar-border p-3 text-xs leading-5 text-muted-foreground">
          <span className="block font-medium text-foreground">Controles do jogo</span>
          Jogo 1: ataques. Jogo 2: tecla periódica.
        </div>
        <div className="flex items-center justify-between">
          <span className={cn('text-sm font-medium', !master && 'text-muted-foreground')}>
            {master ? 'Ataques ligados' : 'Ataques pausados'}
          </span>
          <Switch aria-label="Master de ataques" disabled={!ready || preview || !connected} checked={master} onCheckedChange={toggleMaster} />
        </div>
        <button className="panic-button flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-xs font-medium"
          disabled={!ready || preview} onClick={async () => { await call('panic'); await refresh(); }}>
          <span className="flex items-center gap-2"><Square className="size-3" />Parar tudo</span>
          <span>{state?.hotkeys.panic.toUpperCase() || 'Sem atalho'}</span>
        </button>
        <p className="text-[11px] text-muted-foreground">{preview ? 'Prévia visual' : connected ? 'Motor conectado' : 'Motor desconectado'}</p>
      </div>
    </aside>
  );
}
