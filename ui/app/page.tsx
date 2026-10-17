'use client';

import * as React from 'react';
import { Monitor, Radio, Link2 } from 'lucide-react';
import Link from 'next/link';

import { BotProvider, useBot } from '@/components/bot-provider';
import { DetectSkillsButton } from '@/components/detect-skills-button';
import { LogPanel } from '@/components/log-panel';
import { WindowSelector } from '@/components/window-selector';
import { DialogsPage } from '@/components/pages/dialogs-page';
import { FunctionsPage } from '@/components/pages/functions-page';
import { SettingsPage } from '@/components/pages/settings-page';
import { SkillsPage } from '@/components/pages/skills-page';
import { NAV, Sidebar, type PageKey } from '@/components/sidebar';
import { GlassFold } from '@/components/ui/glass-fold';

const HEADERS: Record<PageKey, { title: string; description: string }> = {
  funcoes: {
    title: 'Funções',
    description: 'Ative rotinas e configure atalhos.',
  },
  skills: {
    title: 'Skills',
    description: 'Detecte as skills e ajuste o cooldown.',
  },
  janelas: {
    title: 'Janelas',
    description: 'Configure Claim e convites.',
  },
  ajustes: {
    title: 'Ajustes',
    description: 'Configure cliques, teclas e segurança.',
  },
};

const VIEWS: Record<PageKey, React.ComponentType> = {
  funcoes: FunctionsPage,
  skills: SkillsPage,
  janelas: DialogsPage,
  ajustes: SettingsPage,
};

function Shell() {
  const [current, setCurrent] = React.useState<PageKey>(NAV[0].key);
  const { state, telemetry, ready, preview, connected, error } = useBot();
  const View = VIEWS[current];
  const header = HEADERS[current];

  return (
    <div className="app-shell relative isolate flex h-screen overflow-hidden">
      <div className="app-backdrop pointer-events-none absolute inset-0 -z-10" aria-hidden="true">
        <GlassFold speed={0.35} />
      </div>
      <Sidebar current={current} onNavigate={setCurrent} />

      <main className="app-main flex min-w-0 flex-1 flex-col gap-4 p-6">
        <header className="drag-region flex shrink-0 items-start justify-between gap-4">
          <div><h1 className="text-[28px] font-semibold leading-tight tracking-tight">{header.title}</h1>
          <p className="text-muted-foreground mt-1 text-sm">{header.description}</p>
          </div>
          <div className="no-drag flex shrink-0 flex-wrap items-center gap-2">
          <DetectSkillsButton onDetect={() => setCurrent('skills')} />
          <span className="connection-badge flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-[11px]">
            <Radio className="size-3" />{preview ? 'Prévia visual' : connected ? 'Conectado' : 'Sem conexão'}
          </span>
          </div>
        </header>

        {preview && <p className="preview-banner text-xs">Prévia visual com dados de exemplo. As ações estão desativadas.</p>}
        {error && <p role="status" className="text-sm text-amber-200">{error}</p>}

        <div className="hide-scrollbar min-h-0 flex-1 overflow-y-auto pr-1">
          {ready ? <>
            <div className="session-strip mb-4 grid grid-cols-2 gap-3" aria-label="Estado dos jogos">
              <div className="session-target flex items-center gap-3 rounded-lg border px-4 py-3">
                <Monitor className="size-4 shrink-0 text-primary" /><div className="min-w-0">
                  <p className="text-xs font-medium">Jogo 1 <span className="ml-1 text-muted-foreground">Ataques</span></p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{state?.selectedWindow?.title || 'Aguardando seleção'}</p>
                </div>
              </div>
              <div className="session-target flex items-center gap-3 rounded-lg border px-4 py-3">
                <Link2 className="size-4 shrink-0 text-primary" /><div className="min-w-0">
                  <p className="text-xs font-medium">Jogo 2 <span className="ml-1 text-muted-foreground">Tecla periódica</span></p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{(telemetry?.secondary ?? state?.secondary)?.selectedWindow?.title || 'Aguardando seleção'}</p>
                </div>
              </div>
            </div>
            <fieldset disabled={preview || !connected} className="min-w-0 space-y-4">
              <legend className="sr-only">Controles de automação</legend>
              <WindowSelector />
              <View />
            </fieldset>
          </> : <div className="connection-empty rounded-xl border p-8">
            <Monitor className="mb-4 size-8 text-primary" />
            <h2 className="font-medium">{error ? 'Abra o Trove AutoBot para começar' : 'Conectando ao motor do bot…'}</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">Execute o aplicativo para conectar suas janelas.</p>
            <Link href="/?preview=1" className="mt-5 inline-block rounded-md border px-4 py-2 text-sm text-primary">Explorar prévia visual</Link>
          </div>}
        </div>

        <LogPanel />
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <BotProvider>
      <Shell />
    </BotProvider>
  );
}
