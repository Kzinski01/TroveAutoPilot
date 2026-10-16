/** Read-only design preview. Never installs a bridge or sends game input. */
import type { AppState, Telemetry, Skill, DialogConfig } from '@/types';

const skills: Skill[] = [
  { id: 'm2', name: 'M2', key: 'mouse_right', enabled: true, region: null, ready_score: 0, cooldown_score: 0, threshold: 0.8, min_interval: 0.6 },
  { id: 's1', name: '1', key: '1', enabled: true, region: null, ready_score: 0, cooldown_score: 0, threshold: 0.8, min_interval: 0.6 },
  { id: 's2', name: '2', key: '2', enabled: true, region: null, ready_score: 0, cooldown_score: 0, threshold: 0.8, min_interval: 0.6 },
];
const dialog: DialogConfig = { enabled: true, template: '', template_region: null, confidence: 0.8, action: 'click', key: '', click_offset: [0, 0], cooldown: 1.5 };

export const previewState: AppState = {
  master: false,
  features: { autoclick: true, skills: true, potion: false, dialogs: false, holdkey: false },
  hotkeys: { master: 'f5', autoclick: 'f6', skills: 'f7', potion: 'f8', dialogs: 'f9', holdkey: 'f10', panic: 'f12' },
  skills, dialogs: { claim: { ...dialog, key: 'l' }, invite: { ...dialog } },
  settings: { only_when_focused: true, target_window: 'Trove', extra_windows: '', pause_on_dialog: true, autoclick: { mode: 'click', cps: 12, button: 'left' }, potion: { key: 'q', interval: 10 }, holdkey: { key: 't', duration: 3 } },
  autoSlots: { enabled: true, status: 'aguardando janela', confidence: null, skills },
  secondary: { selectedWindow: null, enabled: false, key: 'e', interval: 20, remaining: null, status: 'desligada' },
  selectedWindow: null, savedWindow: {}, inputMode: 'messages', admin: false, frozen: false, missingDeps: [],
};

export const previewTelemetry: Telemetry = {
  master: false, features: previewState.features, autoSlots: previewState.autoSlots,
  secondary: previewState.secondary, targetReason: 'Selecione uma janela para começar',
  focus: { title: '', matched: false }, logs: [], capturing: null,
  ratios: { m2: null, s1: null, s2: null },
  status: { autoclick: 'master off', skills: 'master off', potion: 'off', dialogs: 'off', holdkey: 'off' },
};
