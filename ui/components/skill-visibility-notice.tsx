'use client';

import { EyeOff, ScanLine } from 'lucide-react';
import { useBot } from '@/components/bot-provider';

export function SkillVisibilityNotice() {
  const { state, telemetry } = useBot();
  const automatic = telemetry?.autoSlots ?? state?.autoSlots;
  const readings = telemetry?.skillReadings ?? state?.skillReadings ?? {};
  const covered = Object.values(readings).find(item => item.status === 'blocked' && item.issue === 'covered');
  const message = automatic?.enabled ? automatic.warning ?? covered?.message : null;
  if (!message) return null;
  const issue = automatic?.issue ?? covered?.issue;
  const title = issue === 'covered' ? 'Ícones encobertos'
    : issue === 'not_found' ? 'Barra não reconhecida'
    : issue === 'outside' ? 'Área precisa ser atualizada'
    : issue === 'unavailable' ? 'Jogo 1 indisponível' : 'Leitura das skills';
  const Icon = issue === 'covered' ? EyeOff : ScanLine;
  return <div role="alert" className="flex shrink-0 items-start gap-3 rounded-lg border border-amber-300/40 bg-amber-950/90 px-4 py-3 text-sm text-amber-100">
    <Icon className="mt-0.5 size-4 shrink-0" />
    <div><p className="font-medium">{title}</p><p className="mt-1 text-xs leading-5">{message}</p></div>
  </div>;
}
