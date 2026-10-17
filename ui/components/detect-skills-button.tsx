'use client';

import { Loader2, ScanLine } from 'lucide-react';
import { useState } from 'react';

import { useBot } from '@/components/bot-provider';
import { Button } from '@/components/ui/button';
import { call } from '@/lib/api';

export function DetectSkillsButton({ onDetect }: { onDetect?: () => void }) {
  const { state, ready, connected, preview, refresh } = useBot();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = !!state?.selectedWindow;

  const detect = async () => {
    setBusy(true);
    setError('');
    onDetect?.();
    try {
      const found = await call('locate_skills');
      if (!found) setError('Deixe a barra do Jogo 1 visível e tente novamente. Consulte o log.');
      await refresh();
    } finally { setBusy(false); }
  };

  return <div className="no-drag flex flex-col items-start gap-1.5">
    <Button variant="accent" size="sm" disabled={busy || !ready || !connected || preview || !selected}
      title={selected ? 'Identificar M2, 1 e 2 na janela do Jogo 1, sem selecionar áreas manualmente' : 'Selecione a janela do Jogo 1 primeiro'}
      onClick={detect}>
      {busy ? <Loader2 className="animate-spin" /> : <ScanLine />}
      {busy ? 'Detectando…' : 'Detectar skills'}
    </Button>
    {error && <p role="alert" className="max-w-64 text-xs text-amber-200">{error}</p>}
  </div>;
}
