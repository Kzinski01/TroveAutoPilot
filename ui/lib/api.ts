/** Ponte com o backend Python.
 *
 * Sao dois canais, de proposito:
 *
 * - **Acoes** (cliques do usuario) vao pela ponte do pywebview. Sao raras.
 * - **Leitura de estado** (`poll`, `get_state`) vai por `fetch` num servidor
 *   HTTP local. A ponte cria uma thread nova e delegates .NET por chamada;
 *   com a leitura a 4 Hz o processo morria durante a coleta de lixo.
 */

import type {
  AppState,
  CalibrationState,
  DialogConfig,
  DialogName,
  FeatureKey,
  GameWindow,
  HotkeyName,
  Settings,
  Skill,
  Telemetry,
} from '@/types';

type Bridge = {
  panic(): Promise<void>;
  set_auto_slots(enabled: boolean): Promise<boolean>;
  locate_skills(): Promise<boolean>;
  reset_skill_learning(): Promise<boolean>;
  select_secondary_window(candidate: GameWindow): Promise<boolean>;
  update_secondary(patch: { key?: string; interval?: number }): Promise<boolean>;
  set_secondary_enabled(enabled: boolean): Promise<boolean>;
  list_windows(): Promise<GameWindow[]>;
  select_window(candidate: GameWindow): Promise<boolean>;
  set_input_mode(mode: 'foreground' | 'messages'): Promise<boolean>;
  get_endpoint(): Promise<{ url: string; token: string }>;
  get_state(): Promise<AppState>;
  poll(): Promise<Telemetry>;
  set_master(value: boolean): Promise<void>;
  set_feature(key: FeatureKey, value: boolean): Promise<void>;
  capture_hotkey(name: HotkeyName): Promise<void>;
  clear_hotkey(name: HotkeyName): Promise<void>;
  update_skill(id: string, patch: Partial<Skill>): Promise<void>;
  select_skill_region(id: string): Promise<void>;
  calibrate_skill(id: string, state: CalibrationState): Promise<void>;
  update_dialog(name: DialogName, patch: Partial<DialogConfig>): Promise<void>;
  capture_dialog_template(name: DialogName): Promise<void>;
  set_dialog_click_point(name: DialogName): Promise<void>;
  update_settings(patch: Partial<Settings>): Promise<void>;
  diagnose(): Promise<void>;
  install_deps(): Promise<void>;
};

declare global {
  interface Window {
    pywebview?: { api: Bridge };
  }
}

/** Endereco do servidor de telemetria, pedido uma unica vez a ponte. */
let telemetry: { url: string; token: string } | null = null;

/**
 * Resolve quando a ponte estiver utilizavel.
 *
 * Nao basta ouvir `pywebviewready`: o pywebview injeta `window.pywebview` e so
 * depois preenche `.api`, e o evento pode disparar antes do React montar o
 * listener. Por isso sondamos ate os metodos existirem de fato.
 */
export function whenReady(signal?: AbortSignal, pollMs = 60): Promise<Bridge> {
  const usable = () =>
    typeof window.pywebview?.api?.poll === 'function' ? window.pywebview!.api : null;

  const immediate = usable();
  if (immediate) return Promise.resolve(immediate);

  return new Promise((resolve, reject) => {
    const cleanup = () => {
      clearInterval(timer);
      clearTimeout(timeout);
      signal?.removeEventListener('abort', abort);
    };
    const abort = () => {
      cleanup();
      reject(new Error('Conexão cancelada.'));
    };
    const timer = setInterval(() => {
      const bridge = usable();
      if (bridge) {
        cleanup();
        resolve(bridge);
      }
    }, pollMs);
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error('Abra o aplicativo Python para conectar ao motor do bot.'));
    }, 12000);
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();
  });
}

/** Descobre (uma vez) o endereco de telemetria. */
export async function connectTelemetry(): Promise<boolean> {
  if (telemetry) return true;
  const resposta = await call('get_endpoint');
  telemetry = resposta?.url ? { url: resposta.url, token: resposta.token } : null;
  return !!telemetry;
}

/**
 * Le estado pelo servidor local. Cai para a ponte se ele nao estiver de pe,
 * para a interface nunca ficar muda.
 */
export async function read<T>(rota: 'poll' | 'state'): Promise<T | null> {
  if (telemetry) {
    try {
      const resposta = await fetch(`${telemetry.url}/${rota}?t=${telemetry.token}`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(2000),
      });
      if (resposta.ok) return (await resposta.json()) as T;
    } catch {
      // Keep polling failures away from the .NET bridge: its high-frequency
      // fallback was the same crash path this HTTP channel was built to avoid.
    }
    return null;
  }
  return (await call(rota === 'poll' ? 'poll' : 'get_state')) as T | null;
}

/**
 * Chama a ponte com seguranca. Fora do pywebview (ex.: `npm run dev` no
 * navegador) devolve null em vez de quebrar a interface.
 */
export async function call<K extends keyof Bridge>(
  method: K,
  ...args: Parameters<Bridge[K]>
): Promise<Awaited<ReturnType<Bridge[K]>> | null> {
  const bridge = window.pywebview?.api;
  if (typeof bridge?.[method] !== 'function') return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return await (bridge[method] as any)(...args);
  } catch (error) {
    console.error(`Falha ao chamar ${String(method)}:`, error);
    return null;
  }
}

export const isBridged = () => typeof window !== 'undefined' && !!window.pywebview;
