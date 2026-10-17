'use client';

import { X } from 'lucide-react';
import { useBot } from '@/components/bot-provider';
import { Button } from '@/components/ui/button';
import { Kbd } from '@/components/ui/kbd';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { HotkeyName } from '@/types';

export function HotkeyButton({ name }: { name: HotkeyName }) {
  const { state, telemetry, refresh } = useBot();
  const combo = state?.hotkeys?.[name] ?? '';
  const capturing = telemetry?.capturing === name;

  return (
    <div className="group flex items-center gap-1">
      <Button
        variant="ghost"
        size="xs"
        className="px-1.5"
        title="Clique e pressione a nova combinação"
        onClick={async () => {
          await call('capture_hotkey', name);
          await refresh();
        }}
      >
        {capturing ? (
          <span className="text-skyBlue text-xs">pressione…</span>
        ) : combo ? (
          <Kbd>{combo.toUpperCase()}</Kbd>
        ) : (
          <Kbd className="text-muted-foreground/60">definir</Kbd>
        )}
      </Button>
      <button
        title="Remover atalho"
        aria-label={`Remover atalho de ${name}`}
        className={cn(
          'text-muted-foreground hover:text-destructive rounded p-1 transition-opacity',
          combo && !capturing ? 'opacity-0 group-hover:opacity-100' : 'invisible',
        )}
        onClick={async () => {
          await call('clear_hotkey', name);
          await refresh();
        }}
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
