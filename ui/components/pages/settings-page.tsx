'use client';

import * as React from 'react';

import { useBot } from '@/components/bot-provider';
import { SettingsRow } from '@/components/settings-row';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';

function ModeToggle({
  value,
  onChange,
}: {
  value: 'click' | 'hold';
  onChange: (value: 'click' | 'hold') => void;
}) {
  return (
    <div className="bg-input flex rounded-md p-0.5">
      {(['click', 'hold'] as const).map((option) => (
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
          {option === 'click' ? 'Clicar' : 'Segurar'}
        </button>
      ))}
    </div>
  );
}

export function SettingsPage() {
  const { state, refresh } = useBot();
  const [installing, setInstalling] = React.useState(false);
  const settings = state?.settings;

  const patch = async (value: Record<string, unknown>) => {
    await call('update_settings', value as never);
    await refresh();
  };

  if (!settings) return null;

  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Auto clique</CardTitle>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          <SettingsRow title="Modo" description="Segurar mantém o botão pressionado.">
            <ModeToggle
              value={settings.autoclick.mode}
              onChange={(mode) => patch({ autoclick: { ...settings.autoclick, mode } })}
            />
          </SettingsRow>
          <SettingsRow title="Cliques por segundo" description="Usado apenas no modo Clicar.">
            <Input
              type="number"
              min={1}
              max={40}
              className="h-8 w-20 text-center"
              defaultValue={settings.autoclick.cps}
              onBlur={(event) =>
                patch({ autoclick: { ...settings.autoclick, cps: Number(event.target.value) } })
              }
            />
          </SettingsRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Poção de HP</CardTitle>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          <SettingsRow title="Tecla">
            <Input
              className="h-8 w-20 text-center"
              defaultValue={settings.potion.key}
              onBlur={(event) =>
                patch({ potion: { ...settings.potion, key: event.target.value.trim() } })
              }
            />
          </SettingsRow>
          <SettingsRow title="Intervalo (segundos)">
            <Input
              type="number"
              min={0.5}
              step={0.5}
              className="h-8 w-20 text-center"
              defaultValue={settings.potion.interval}
              onBlur={(event) =>
                patch({ potion: { ...settings.potion, interval: Number(event.target.value) } })
              }
            />
          </SettingsRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Segurar tecla</CardTitle>
          <CardDescription>
            Aperta a tecla, segura pelo tempo abaixo, solta e repete na hora.
          </CardDescription>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          <SettingsRow title="Tecla">
            <Input
              className="h-8 w-20 text-center"
              defaultValue={settings.holdkey.key}
              onBlur={(event) =>
                patch({ holdkey: { ...settings.holdkey, key: event.target.value.trim() } })
              }
            />
          </SettingsRow>
          <SettingsRow title="Tempo segurando (segundos)">
            <Input
              type="number"
              min={0.1}
              max={60}
              step={0.5}
              className="h-8 w-20 text-center"
              defaultValue={settings.holdkey.duration}
              onBlur={(event) =>
                patch({
                  holdkey: { ...settings.holdkey, duration: Number(event.target.value) },
                })
              }
            />
          </SettingsRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Segurança</CardTitle>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          <SettingsRow
            title="Somente com o jogo em foco"
            description="Obrigatório no modo Compatibilidade. Use o seletor de instância acima."
          >
            <Switch
              checked={true}
              disabled
            />
          </SettingsRow>
          <SettingsRow title="Título da janela do jogo">
            <Input
              className="h-8 w-44"
              defaultValue={settings.target_window}
              onBlur={(event) => patch({ target_window: event.target.value })}
            />
          </SettingsRow>
          <SettingsRow
            title="Outros títulos aceitos"
            description="Separe por vírgula. Útil quando o jogo troca o nome da janela."
          >
            <Input
              className="h-8 w-44"
              placeholder="Glyph, Carregando"
              defaultValue={settings.extra_windows}
              onBlur={(event) => patch({ extra_windows: event.target.value })}
            />
          </SettingsRow>
          <SettingsRow
            title="Pausar cliques com janela aberta"
            description="Evita clicar no jogo por baixo do diálogo."
          >
            <Switch
              checked={settings.pause_on_dialog}
              onCheckedChange={(value) => patch({ pause_on_dialog: value })}
            />
          </SettingsRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Manutenção</CardTitle>
          <CardDescription>
            {state.admin
              ? 'Rodando como administrador.'
              : 'Sem privilégio de administrador: o Windows pode descartar o input.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="divide-border divide-y">
          <SettingsRow
            title="Dependências"
            description={
              state.frozen
                ? 'Já embutidas no executável.'
                : state.missingDeps.length
                  ? `Faltando: ${state.missingDeps.join(', ')}`
                  : 'Todas instaladas.'
            }
          >
            <Button
              variant="accent"
              size="sm"
              disabled={state.frozen || installing}
              onClick={async () => {
                setInstalling(true);
                try {
                  await call('install_deps');
                  await refresh();
                } finally {
                  setInstalling(false);
                }
              }}
            >
              {installing ? 'Instalando…' : 'Instalar dependências'}
            </Button>
          </SettingsRow>
          <SettingsRow
            title="Diagnóstico"
            description="Mostra no log por que cada rotina está ou não agindo."
          >
            <Button variant="outline" size="sm" onClick={() => call('diagnose')}>
              Executar
            </Button>
          </SettingsRow>
        </CardContent>
      </Card>
    </div>
  );
}
