'use client';

import { useBot } from '@/components/bot-provider';
import { Input } from '@/components/ui/input';
import { call } from '@/lib/api';
import type { Settings } from '@/types';

function useRoutineSettings() {
  const { state, refresh } = useBot();
  const patch = async (value: Partial<Settings>) => {
    await call('update_settings', value);
    await refresh();
  };
  return { settings: state?.settings, patch };
}

export function AutoclickSettings() {
  const { settings, patch } = useRoutineSettings();
  if (!settings) return null;
  const value = settings.autoclick;
  return <div className="flex flex-wrap items-end gap-3 text-xs">
    <label className="space-y-1">Modo
      <select aria-label="Modo do auto clique" className="block h-9 rounded-md bg-input px-2"
        value={value.mode} onChange={e => patch({ autoclick: { ...value, mode: e.target.value as 'click' | 'hold' } })}>
        <option value="click">Repetir cliques</option><option value="hold">Manter pressionado</option>
      </select>
    </label>
    {value.mode === 'click' && <label className="space-y-1">Cliques por segundo
      <Input aria-label="Cliques por segundo" className="h-9 w-24" type="number" min={1} max={40}
        defaultValue={value.cps} onBlur={e => patch({ autoclick: { ...value, cps: Number(e.target.value) } })} />
    </label>}
  </div>;
}

export function PotionSettings() {
  const { settings, patch } = useRoutineSettings();
  if (!settings) return null;
  const value = settings.potion;
  return <div className="flex flex-wrap gap-3 text-xs">
    <label className="space-y-1">Tecla
      <Input aria-label="Tecla da poção" className="h-9 w-24" defaultValue={value.key}
        onBlur={e => patch({ potion: { ...value, key: e.target.value.trim() } })} />
    </label>
    <label className="space-y-1">Intervalo (segundos)
      <Input aria-label="Intervalo da poção" className="h-9 w-28" type="number" min={0.5} step={0.5}
        defaultValue={value.interval} onBlur={e => patch({ potion: { ...value, interval: Number(e.target.value) } })} />
    </label>
  </div>;
}

export function HeldKeySettings() {
  const { settings, patch } = useRoutineSettings();
  if (!settings) return null;
  const value = settings.holdkey;
  return <div className="flex flex-wrap gap-3 text-xs">
    <label className="space-y-1">Tecla
      <Input aria-label="Tecla para segurar" className="h-9 w-24" defaultValue={value.key}
        onBlur={e => patch({ holdkey: { ...value, key: e.target.value.trim() } })} />
    </label>
    <label className="space-y-1">Tempo segurando (segundos)
      <Input aria-label="Tempo segurando" className="h-9 w-28" type="number" min={0.1} max={60} step={0.5}
        defaultValue={value.duration} onBlur={e => patch({ holdkey: { ...value, duration: Number(e.target.value) } })} />
    </label>
  </div>;
}
