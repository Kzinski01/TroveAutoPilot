'use client';

import { useState } from 'react';
import { useBot } from '@/components/bot-provider';
import { HotkeyButton } from '@/components/hotkey-button';
import { SettingsRow } from '@/components/settings-row';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';

export function SettingsPage() {
  const { state, refresh } = useBot();
  const [installing, setInstalling] = useState(false);
  const settings = state?.settings;
  if (!settings) return null;
  return <div className="grid gap-4">
    <Card>
      <CardHeader><CardTitle>Atalhos gerais</CardTitle><CardDescription>Os atalhos de cada rotina ficam junto ao seu controle.</CardDescription></CardHeader>
      <CardContent>
        <SettingsRow title="Ligar ou pausar ataques" description="Controla clique, skills, poção e diálogos do Jogo 1."><HotkeyButton name="master" /></SettingsRow>
        <SettingsRow title="Parar tudo" description="Desliga também Segurar tecla e Jogo 2."><HotkeyButton name="panic" /></SettingsRow>
      </CardContent>
    </Card>
    <Card>
      <CardHeader><CardTitle>Segurança</CardTitle><CardDescription>Compatibilidade exige foco. Mensagens é experimental.</CardDescription></CardHeader>
      <CardContent>
        <SettingsRow title="Pausar cliques durante diálogos" description="Evita clicar no jogo por baixo do diálogo.">
          <Switch checked={settings.pause_on_dialog} onCheckedChange={async value => { await call('update_settings', { pause_on_dialog: value }); await refresh(); }} />
        </SettingsRow>
      </CardContent>
    </Card>
    <details className="glass-panel rounded-lg border p-4">
      <summary className="cursor-pointer text-sm font-medium">Opções avançadas</summary>
      <div className="mt-4 space-y-4">
        <label className="block space-y-2 text-xs">Título da janela do jogo
          <Input defaultValue={settings.target_window} onBlur={async e => { await call('update_settings', { target_window: e.target.value }); await refresh(); }} />
        </label>
        <label className="block space-y-2 text-xs">Outros títulos aceitos (separados por vírgula)
          <Input defaultValue={settings.extra_windows} onBlur={async e => { await call('update_settings', { extra_windows: e.target.value }); await refresh(); }} />
        </label>
        <p className="text-xs text-muted-foreground">{state.admin ? 'Executando como administrador.' : 'O jogo pode exigir execução como administrador.'}</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => call('diagnose')}>Gerar diagnóstico no log</Button>
          {!state.frozen && state.missingDeps.length > 0 && <Button size="sm" variant="outline" disabled={installing} onClick={async () => {
            setInstalling(true);
            try { await call('install_deps'); await refresh(); } finally { setInstalling(false); }
          }}>{installing ? 'Instalando…' : 'Instalar dependências'}</Button>}
        </div>
      </div>
    </details>
  </div>;
}
