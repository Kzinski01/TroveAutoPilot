'use client';

import { X } from 'lucide-react';
import * as React from 'react';

import { useBot } from '@/components/bot-provider';
import { SecondaryControls } from '@/components/secondary-controls';
import { SettingsRow } from '@/components/settings-row';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Kbd } from '@/components/ui/kbd';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { FeatureKey, HotkeyName } from '@/types';

const FEATURES: {
  key: FeatureKey;
  title: string;
  description: string;
  standalone?: boolean;
}[] = [
  {
    key: 'autoclick',
    title: 'Auto clique (M1)',
    description: 'Clique esquerdo contínuo, prioridade máxima',
  },
  {
    key: 'skills',
    title: 'Skills (M2 / 1 / 2)',
    description: 'Dispara cada skill ao sair do cooldown',
  },
  { key: 'potion', title: 'Poção de HP', description: 'Usa a poção em intervalo fixo' },
  {
    key: 'holdkey',
    title: 'Segurar tecla',
    description: 'Segura a tecla, solta e repete sem pausa — roda sozinha, sem o master',
    standalone: true,
  },
  {
    key: 'dialogs',
    title: 'Janelas',
    description: 'Fecha o Claim e responde aos convites',
  },
];

const GENERAL: { key: HotkeyName; title: string; description: string }[] = [
  { key: 'master', title: 'Master de ataques', description: 'Controla ataques do Jogo 1. A tecla periódica do Jogo 2 e Segurar tecla têm controles próprios.' },
  { key: 'panic', title: 'Pânico', description: 'Solta o mouse e para tudo imediatamente.' },
];

function HotkeyButton({ name }: { name: HotkeyName }) {
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

export function FunctionsPage() {
  const { state, telemetry, refresh } = useBot();

  const toggle = async (key: FeatureKey, value: boolean) => {
    await call('set_feature', key, value);
    await refresh();
  };

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Rotinas</CardTitle>
          <CardDescription>O atalho funciona com o jogo em foco.</CardDescription>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          {FEATURES.map(({ key, title, description, standalone }) => (
            <SettingsRow
              key={key}
              title={
                <span className="flex items-center gap-2">
                  {title}
                  {standalone && (
                    <span className="border-skyBlue/40 text-skyBlue rounded border px-1.5 py-0.5 text-[10px] font-medium">
                      independente
                    </span>
                  )}
                </span>
              }
              description={description}
            >
              <span className="text-muted-foreground mr-1 w-32 truncate text-right font-mono text-xs">
                {telemetry?.status?.[key] ?? '-'}
              </span>
              <HotkeyButton name={key} />
              <Switch
                aria-label={title}
                checked={telemetry?.features?.[key] ?? state?.features?.[key] ?? false}
                onCheckedChange={(value) => toggle(key, value)}
              />
            </SettingsRow>
          ))}
        </CardContent>
      </Card>

      <SecondaryControls />

      <Card>
        <CardHeader>
          <CardTitle>Controle geral</CardTitle>
          <CardDescription>Atalhos que valem para tudo.</CardDescription>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          {GENERAL.map(({ key, title, description }) => (
            <SettingsRow key={key} title={title} description={description}>
              <HotkeyButton name={key} />
            </SettingsRow>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
