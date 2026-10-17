'use client';

import { useBot } from '@/components/bot-provider';
import { HotkeyButton } from '@/components/hotkey-button';
import { Switch } from '@/components/ui/switch';
import { call } from '@/lib/api';
import type { FeatureKey } from '@/types';

export function FeatureControl({ name, label }: { name: FeatureKey; label: string }) {
  const { state, telemetry, refresh } = useBot();
  return <div className="flex shrink-0 items-center gap-3">
    <HotkeyButton name={name} />
    <Switch aria-label={label} checked={telemetry?.features[name] ?? state?.features[name] ?? false}
      onCheckedChange={async enabled => { await call('set_feature', name, enabled); await refresh(); }} />
  </div>;
}
