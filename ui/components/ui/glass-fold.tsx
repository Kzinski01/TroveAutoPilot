'use client';

// Glass Fold by Meerbahadin / GradFlow, integrated from the supplied component.
// https://gradflow.meerbahadin.dev
import { useEffect, useRef, useState } from 'react';

import { GLASS_FOLD_DEFAULTS, startGlassFold, type GlassFoldSettings } from '@/lib/glass-fold-renderer';

export interface GlassFoldProps extends Partial<GlassFoldSettings> { className?: string }

export function GlassFold({ className, ...options }: GlassFoldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const settings = useRef({ ...GLASS_FOLD_DEFAULTS, ...options });
  const repaint = useRef<(() => void) | null>(null);
  const [contextVersion, setContextVersion] = useState(0);
  const [available, setAvailable] = useState(false);
  const { color1, color2, color3, speed, scale, noise } = options;

  useEffect(() => {
    settings.current = { color1: color1 ?? GLASS_FOLD_DEFAULTS.color1,
      color2: color2 ?? GLASS_FOLD_DEFAULTS.color2, color3: color3 ?? GLASS_FOLD_DEFAULTS.color3,
      speed: speed ?? GLASS_FOLD_DEFAULTS.speed, scale: scale ?? GLASS_FOLD_DEFAULTS.scale,
      noise: noise ?? GLASS_FOLD_DEFAULTS.noise };
    repaint.current?.();
  }, [color1, color2, color3, speed, scale, noise]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let renderer: ReturnType<typeof startGlassFold> = null;
    try { renderer = startGlassFold(canvas, () => settings.current); }
    catch { /* The CSS background remains available if the GPU rejects the shader. */ }
    setAvailable(!!renderer);
    repaint.current = renderer?.repaint ?? null;
    const lost = (event: Event) => { event.preventDefault(); setAvailable(false); };
    const restored = () => setContextVersion(version => version + 1);
    canvas.addEventListener('webglcontextlost', lost);
    canvas.addEventListener('webglcontextrestored', restored);
    return () => {
      repaint.current = null;
      canvas.removeEventListener('webglcontextlost', lost);
      canvas.removeEventListener('webglcontextrestored', restored);
      renderer?.dispose();
    };
  }, [contextVersion]);

  return <canvas ref={canvasRef} aria-hidden="true" className={className}
    data-renderer={available ? 'webgl' : 'fallback'}
    style={{ display: 'block', width: '100%', height: '100%', visibility: available ? 'visible' : 'hidden' }} />;
}
