'use client';

import * as React from 'react';

import { useBot } from '@/components/bot-provider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { DialogConfig, DialogName } from '@/types';

const DIALOGS: { name: DialogName; title: string; description: string }[] = [
  {
    name: 'claim',
    title: 'Janela CLAIMS',
    description: 'Fecha no X ou pela tecla configurada',
  },
  {
    name: 'invite',
    title: 'Convite',
    description: 'Responde o diálogo quando alguém te convida',
  },
];

function ActionToggle({
  value,
  onChange,
}: {
  value: DialogConfig['action'];
  onChange: (value: DialogConfig['action']) => void;
}) {
  return (
    <div className="bg-input flex rounded-md p-0.5">
      {(['click', 'key'] as const).map((option) => (
        <button
          key={option}
          onClick={() => onChange(option)}
          className={cn(
            'rounded px-3 py-1 text-xs transition-colors',
            value === option
              ? 'bg-skyBlue text-white'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {option === 'click' ? 'Clicar' : 'Tecla'}
        </button>
      ))}
    </div>
  );
}

function DialogCard({
  name,
  title,
  description,
}: {
  name: DialogName;
  title: string;
  description: string;
}) {
  const { state, telemetry, refresh } = useBot();
  const config = state?.dialogs?.[name];
  const [busy, setBusy] = React.useState(false);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  if (!config) return null;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <span
          className={cn(
            'font-mono text-xs',
            config.template ? 'text-muted-foreground' : 'text-destructive',
          )}
        >
          {config.template ? (telemetry?.status?.[name] ?? 'pronto') : 'sem template'}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Switch
            checked={config.enabled}
            onCheckedChange={(value) => run(() => call('update_dialog', name, { enabled: value }))}
          />
          <ActionToggle
            value={config.action}
            onChange={(action) => run(() => call('update_dialog', name, { action }))}
          />
          {config.action === 'key' && (
            <Input
              className="h-8 w-16 text-center"
              defaultValue={config.key}
              onBlur={(event) =>
                run(() => call('update_dialog', name, { key: event.target.value.trim() }))
              }
            />
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="accent"
            size="sm"
            disabled={busy}
            onClick={() => run(() => call('capture_dialog_template', name))}
          >
            Capturar janela
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !config.template_region}
            onClick={() => run(() => call('set_dialog_click_point', name))}
          >
            Ponto de clique
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function DialogsPage() {
  return (
    <div className="grid gap-4">
      {DIALOGS.map((dialog) => (
        <DialogCard key={dialog.name} {...dialog} />
      ))}
    </div>
  );
}
