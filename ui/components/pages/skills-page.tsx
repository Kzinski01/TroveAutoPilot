'use client';

import * as React from 'react';
import { useBot } from '@/components/bot-provider';
import { DetectSkillsButton } from '@/components/detect-skills-button';
import { FeatureControl } from '@/components/feature-control';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import type { Skill, SkillReading } from '@/types';

function SkillCard({ skill, reading, automatic }: { skill: Skill; reading?: SkillReading; automatic: boolean }) {
  const { refresh } = useBot();
  const [busy, setBusy] = React.useState(false);
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try { await action(); await refresh(); } finally { setBusy(false); }
  };
  return <Card>
    <CardHeader className="flex-row items-center justify-between gap-3 space-y-0">
      <CardTitle>Skill {skill.name}</CardTitle>
      <Switch aria-label={`Ativar skill ${skill.name}`} checked={skill.enabled} disabled={busy}
        onCheckedChange={enabled => run(() => call('update_skill', skill.id, { enabled }))} />
    </CardHeader>
    <CardContent className="space-y-4">
      <p role="status" className={`text-sm ${reading?.ready ? 'text-success' : 'text-muted-foreground'}`}>
        {!skill.region ? 'Aguardando localização do ícone' : automatic ? reading?.message ?? 'Aprendendo: use a skill normalmente no jogo' : skill.ready_score ? 'Calibração manual' : 'Calibração manual pendente'}
      </p>
      {automatic && reading?.lastCooldown != null && <p className="text-xs text-muted-foreground">Último retorno observado: {reading.lastCooldown.toFixed(1)}s. A próxima leitura depende do ícone.</p>}
      <label className="flex items-center gap-3 text-xs">Tecla da skill
        <Input aria-label={`Tecla da skill ${skill.name}`} className="h-8 w-28" defaultValue={skill.key}
          onBlur={e => run(() => call('update_skill', skill.id, { key: e.target.value.trim() }))} />
      </label>
      <details className="rounded-md border p-3">
        <summary className="cursor-pointer text-xs">Ajustes avançados</summary>
        <div className="mt-3 space-y-3 text-xs">
          <label className="flex flex-wrap items-center gap-3">Pausa mínima entre comandos (segundos)
            <Input aria-label={`Pausa mínima da skill ${skill.name}`} className="h-8 w-24" type="number" min={0.05} max={60} step={0.05}
              defaultValue={skill.min_interval} onBlur={e => run(() => call('update_skill', skill.id, { min_interval: Number(e.target.value) }))} />
          </label>
          {automatic ? <p className="text-muted-foreground">A pausa evita comandos repetidos; o cooldown é verificado pela imagem. Para recortar ou calibrar manualmente, desligue o modo automático acima.</p> : <>
            <label className="flex items-center gap-3">Limite de brilho
              <Input aria-label={`Limite da skill ${skill.name}`} className="h-8 w-24" type="number" min={0.05} max={2} step={0.01}
                defaultValue={skill.threshold} onBlur={e => run(() => call('update_skill', skill.id, { threshold: Number(e.target.value) }))} />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => call('select_skill_region', skill.id))}>Selecionar área</Button>
              <Button size="sm" variant="outline" disabled={busy || !skill.region} onClick={() => run(() => call('calibrate_skill', skill.id, 'ready'))}>Capturar pronta</Button>
              <Button size="sm" variant="outline" disabled={busy || !skill.region} onClick={() => run(() => call('calibrate_skill', skill.id, 'cooldown'))}>Capturar cooldown</Button>
            </div>
          </>}
        </div>
      </details>
    </CardContent>
  </Card>;
}

export function SkillsPage() {
  const { state, telemetry, refresh } = useBot();
  const automatic = telemetry?.autoSlots ?? state?.autoSlots;
  const readings = telemetry?.skillReadings ?? state?.skillReadings;
  const [busy, setBusy] = React.useState(false);
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    try { await action(); await refresh(); } finally { setBusy(false); }
  };
  return <div className="grid gap-4">
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div><CardTitle>Skills automáticas</CardTitle><CardDescription className="mt-1">M2, 1 e 2 na janela selecionada em Jogo 1.</CardDescription></div>
        <FeatureControl name="skills" label="Ativar skills" />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <DetectSkillsButton />
          <label className="flex items-center gap-2 text-sm">Modo automático
            <Switch aria-label="Modo automático das skills" checked={automatic?.enabled ?? false} disabled={busy}
              onCheckedChange={enabled => run(() => call('set_auto_slots', enabled))} />
          </label>
          {automatic?.enabled && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => call('reset_skill_learning'))}>Reaprender skills</Button>}
        </div>
        <p className="text-sm leading-6">{automatic?.enabled ? 'Use as skills normalmente com a barra visível. O app aprende ao observar um ciclo completo, sem capturas manuais.' : 'Clique em Detectar skills para localizar os ícones e iniciar o aprendizado automático.'}</p>
        <p className="text-xs text-muted-foreground" aria-live="polite">{automatic?.status ?? 'Aguardando conexão'}</p>
        <p className="text-xs leading-5 text-muted-foreground">A leitura acompanha reduções de cooldown. Um brilho isolado não libera a skill. Se não houver mudança visual suficiente, ela continua aguardando; o modo manual fica nos ajustes avançados de cada skill.</p>
      </CardContent>
    </Card>
    {(automatic?.skills ?? state?.skills ?? []).map(skill => <SkillCard key={skill.id} skill={skill} reading={readings?.[skill.id]} automatic={automatic?.enabled ?? false} />)}
  </div>;
}
