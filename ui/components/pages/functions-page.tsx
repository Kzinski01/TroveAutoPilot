'use client';

import { FeatureControl } from '@/components/feature-control';
import { AutoclickSettings, HeldKeySettings, PotionSettings } from '@/components/routine-settings';
import { WindowSelector } from '@/components/window-selector';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function FunctionsPage() {
  return <div className="grid gap-4">
    <WindowSelector />
    <p className="text-xs text-muted-foreground">Escolha as rotinas abaixo e ligue os ataques na barra lateral. F5 também liga ou pausa.</p>
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div><CardTitle>Auto clique</CardTitle><CardDescription className="mt-1">Repete o clique esquerdo.</CardDescription></div>
          <FeatureControl name="autoclick" label="Ativar auto clique" />
        </CardHeader>
        <CardContent><AutoclickSettings /></CardContent>
      </Card>
      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div><CardTitle>Poção de HP</CardTitle><CardDescription className="mt-1">Usa a poção no intervalo escolhido.</CardDescription></div>
          <FeatureControl name="potion" label="Ativar poção" />
        </CardHeader>
        <CardContent><PotionSettings /></CardContent>
      </Card>
    </div>
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div><CardTitle>Skills automáticas</CardTitle><CardDescription className="mt-1">Usa M2, 1 e 2 quando a leitura indicar que estão prontas.</CardDescription></div>
        <FeatureControl name="skills" label="Ativar skills" />
      </CardHeader>
      <CardContent><p className="text-xs text-muted-foreground">Localização, aprendizado e leitura ao vivo ficam na aba Skills.</p></CardContent>
    </Card>
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div><CardTitle>Segurar tecla</CardTitle><CardDescription className="mt-1">Segura, solta e repete. Funciona com os ataques pausados; F12 desliga tudo.</CardDescription></div>
        <FeatureControl name="holdkey" label="Ativar segurar tecla" />
      </CardHeader>
      <CardContent><HeldKeySettings /></CardContent>
    </Card>
  </div>;
}
