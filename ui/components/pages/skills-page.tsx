'use client';

import * as React from 'react';

import { useBot } from '@/components/bot-provider';
import { DetectSkillsButton } from '@/components/detect-skills-button';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { Skill } from '@/types';

function CalibrationBadge({ skill, ratio }: { skill: Skill; ratio: number | null | undefined }) {
  if (!skill.region) {
    return <span className="text-destructive font-mono text-xs">sem área</span>;
  }
  if (!skill.ready_score) {
    return <span className="text-destructive font-mono text-xs">falta calibrar</span>;
  }
  const armed = ratio != null && ratio >= skill.threshold;
  return (
    <span className={cn('font-mono text-xs', armed ? 'text-success' : 'text-muted-foreground')}>
      {ratio == null ? '-' : ratio.toFixed(2)} / {skill.threshold.toFixed(2)}
    </span>
  );
}

function SkillCard({ skill }: { skill: Skill }) {
  const { telemetry, refresh } = useBot();
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

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Slot {skill.name}</CardTitle>
        <CalibrationBadge skill={skill} ratio={telemetry?.ratios?.[skill.id]} />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <Switch
            aria-label={`Ativar skill ${skill.name}`}
            checked={skill.enabled}
            onCheckedChange={(value) =>
              run(() => call('update_skill', skill.id, { enabled: value }))
            }
          />
          <span className="text-muted-foreground text-xs">Tecla</span>
          <Input
            aria-label={`Tecla da skill ${skill.name}`}
            className="h-8 w-28 text-center"
            defaultValue={skill.key}
            onBlur={(event) =>
              run(() => call('update_skill', skill.id, { key: event.target.value.trim() }))
            }
          />
          <span className="text-muted-foreground text-xs">Limite</span>
          <Input
            aria-label={`Limite da skill ${skill.name}`}
            type="number"
            min={0.05}
            max={2}
            step={0.01}
            className="h-8 w-24 text-center"
            defaultValue={skill.threshold}
            title="A skill dispara quando o ratio alcança este valor"
            onBlur={(event) =>
              run(() =>
                call('update_skill', skill.id, {
                  threshold: Number(event.target.value),
                }),
              )
            }
          />
          <span className="text-muted-foreground truncate text-xs">
            {skill.region ? `área ${skill.region.join(', ')}` : 'área não definida'}
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => run(() => call('select_skill_region', skill.id))}
          >
            Área
          </Button>
          <Button
            variant="accent"
            size="sm"
            disabled={busy || !skill.region}
            onClick={() => run(() => call('calibrate_skill', skill.id, 'ready'))}
          >
            Pronta
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !skill.region}
            title="Opcional: mede o ícone escuro e sugere um limite no log"
            onClick={() => run(() => call('calibrate_skill', skill.id, 'cooldown'))}
          >
            Em cooldown (sugere limite)
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function SkillsPage() {
  const { state, telemetry, refresh } = useBot();
  const automatic = telemetry?.autoSlots ?? state?.autoSlots;
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const run = async (action: () => Promise<boolean | null>) => {
    setBusy(true);
    try {
      const ok = await action();
      setError(ok ? '' : 'Não foi possível localizar. Deixe a barra visível e confira o log.');
      await refresh();
    } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Detecção automática das skills</CardTitle>
          <CardDescription>
            Detecte M2, 1 e 2 sem recortar ícones. Deixe a barra do Jogo 1 visível e
            capture Pronta uma vez por slot, com a skill sem cooldown.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <DetectSkillsButton />
            <Switch checked={automatic?.enabled ?? false} disabled={busy}
              aria-label="Localização automática dos slots"
              onCheckedChange={(enabled) => run(() => call('set_auto_slots', enabled))} />
            <span className="text-sm">Acompanhar a barra automaticamente</span>
          </div>
          <p className="text-muted-foreground text-xs" aria-live="polite">
            {automatic?.status ?? 'Aguardando conexão'}
            {automatic?.confidence != null ? ` — confiança ${(automatic.confidence * 100).toFixed(0)}%` : ''}
          </p>
          {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
          <p className="text-muted-foreground text-xs">Área desativa a detecção automática.</p>
        </CardContent>
      </Card>
      {(automatic?.skills ?? state?.skills ?? []).map((skill) => (
        <SkillCard key={skill.id} skill={skill} />
      ))}
    </div>
  );
}
