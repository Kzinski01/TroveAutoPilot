/** Contrato entre a interface React e a API Python (bridge do pywebview). */

export type FeatureKey =
  | 'autoclick'
  | 'skills'
  | 'potion'
  | 'dialogs'
  | 'holdkey';
export type DialogName = 'claim' | 'invite';
export type HotkeyName = FeatureKey | 'master' | 'panic';
export type CalibrationState = 'ready' | 'cooldown';

export interface Skill {
  id: string;
  name: string;
  key: string;
  enabled: boolean;
  region: number[] | null;
  ready_score: number;
  cooldown_score: number;
  threshold: number;
  min_interval: number;
}

export interface DialogConfig {
  enabled: boolean;
  template: string;
  template_region: number[] | null;
  confidence: number;
  action: 'click' | 'key';
  key: string;
  click_offset: number[];
  cooldown: number;
}

export interface Settings {
  only_when_focused: boolean;
  target_window: string;
  extra_windows: string;
  pause_on_dialog: boolean;
  autoclick: { mode: 'click' | 'hold'; cps: number; button: string };
  potion: { key: string; interval: number };
  holdkey: { key: string; duration: number };
}

/** Estado completo, buscado ao abrir e depois de cada acao. */
export interface AppState {
  skillReadings?: Record<string, SkillReading>;
  autoSlots: AutoSlotsState;
  secondary: SecondaryState;
  selectedWindow: GameWindow | null;
  savedWindow: Partial<GameWindow>;
  inputMode: 'foreground' | 'messages';
  master: boolean;
  features: Record<FeatureKey, boolean>;
  hotkeys: Record<HotkeyName, string>;
  skills: Skill[];
  dialogs: Record<DialogName, DialogConfig>;
  settings: Settings;
  admin: boolean;
  frozen: boolean;
  missingDeps: string[];
}

/** Dados vivos, buscados a cada tick. */
export interface Telemetry {
  skillReadings?: Record<string, SkillReading>;
  autoSlots: AutoSlotsState;
  secondary: SecondaryState;
  targetReason: string | null;
  master: boolean;
  features: Record<FeatureKey, boolean>;
  status: Record<string, string>;
  ratios: Record<string, number | null>;
  focus: { title: string; matched: boolean };
  logs: string[];
  capturing: HotkeyName | null;
}

export interface GameWindow {
  hwnd: number;
  pid: number;
  process_created: string;
  title: string;
  exe: string;
  region?: number[] | null;
}

export interface SecondaryState {
  selectedWindow: GameWindow | null;
  enabled: boolean;
  key: string;
  interval: number;
  remaining: number | null;
  status: string;
}

export interface AutoSlotsState {
  warning?: string | null;
  enabled: boolean;
  status: string;
  confidence: number | null;
  skills: Skill[];
}

export interface SkillReading {
  status: 'learning' | 'watching' | 'ready' | 'cooldown' | 'confirming' | 'blocked';
  message: string;
  ratio: number | null;
  calibrated: boolean;
  ready: boolean;
  lastCooldown: number | null;
}
