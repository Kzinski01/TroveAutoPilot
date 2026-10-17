import { FRAGMENT, VERTEX } from '@/components/ui/glass-fold-shaders';

export interface GlassFoldSettings {
  color1: string;
  color2: string;
  color3: string;
  speed: number;
  scale: number;
  noise: number;
}

export const GLASS_FOLD_DEFAULTS: GlassFoldSettings = {
  color1: '#1e3cc8', color2: '#06081e', color3: '#96d7ff',
  speed: 0.5, scale: 1, noise: 0.12,
};

function hexToVec3(hex: string): [number, number, number] {
  const raw = /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(hex) ? hex.slice(1) : '06081e';
  const full = raw.length === 3 ? raw.split('').map(c => c + c).join('') : raw;
  const value = parseInt(full, 16);
  return [((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255];
}

function compile(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('Shader unavailable');
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    throw new Error('Shader compilation failed');
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext) {
  const shaders: WebGLShader[] = [];
  const program = gl.createProgram();
  if (!program) throw new Error('WebGL program unavailable');
  try {
    shaders.push(compile(gl, gl.VERTEX_SHADER, VERTEX));
    shaders.push(compile(gl, gl.FRAGMENT_SHADER, FRAGMENT));
    shaders.forEach(shader => gl.attachShader(program, shader));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Shader link failed');
    return program;
  } catch (error) {
    gl.deleteProgram(program);
    throw error;
  } finally {
    shaders.forEach(shader => gl.deleteShader(shader));
  }
}

function resize(canvas: HTMLCanvasElement, gl: WebGLRenderingContext) {
  // The game has priority over a decorative background on the same GPU.
  const pixels = Math.max(1, canvas.clientWidth * canvas.clientHeight);
  const ratio = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(1600000 / pixels));
  const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
  const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  gl.viewport(0, 0, width, height);
}

function createScene(canvas: HTMLCanvasElement) {
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power' });
  if (!gl) return null;
  const program = createProgram(gl);
  const buffer = gl.createBuffer();
  if (!buffer) { gl.deleteProgram(program); return null; }
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, -1,1, 1,-1, 1,1]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'position');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  const uniform = (name: string) => gl.getUniformLocation(program, name);
  const uniforms = { time: uniform('u_time'), color1: uniform('u_color1'), color2: uniform('u_color2'),
    color3: uniform('u_color3'), scale: uniform('u_scale'), noise: uniform('u_noise'), resolution: uniform('u_resolution') };
  return {
    lost: () => gl.isContextLost(),
    resize: () => resize(canvas, gl),
    draw: (settings: GlassFoldSettings, elapsed: number) => {
      gl.uniform1f(uniforms.time, elapsed);
      gl.uniform3fv(uniforms.color1, hexToVec3(settings.color1));
      gl.uniform3fv(uniforms.color2, hexToVec3(settings.color2));
      gl.uniform3fv(uniforms.color3, hexToVec3(settings.color3));
      gl.uniform1f(uniforms.scale, Math.max(0.1, settings.scale));
      gl.uniform1f(uniforms.noise, Math.max(0, Math.min(0.5, settings.noise)));
      gl.uniform2f(uniforms.resolution, canvas.width, canvas.height);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    },
    dispose: () => { gl.deleteBuffer(buffer); gl.deleteProgram(program); },
  };
}

function animate(scene: NonNullable<ReturnType<typeof createScene>>, settings: () => GlassFoldSettings) {
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let frame = 0;
  let last = 0;
  let elapsed = 0;
  const draw = (now: number) => {
    if (document.hidden || scene.lost()) return;
    const current = settings();
    if (!last || now - last >= 1000 / 30) {
      if (last && !motion.matches) elapsed += Math.min((now - last) / 1000, 0.1) * current.speed;
      last = now;
      scene.draw(current, elapsed);
    }
    if (!motion.matches && current.speed !== 0) frame = requestAnimationFrame(draw);
  };
  const repaint = () => { cancelAnimationFrame(frame); last = 0; frame = requestAnimationFrame(draw); };
  return { repaint, stop: () => cancelAnimationFrame(frame), motion };
}

export function startGlassFold(canvas: HTMLCanvasElement, settings: () => GlassFoldSettings) {
  const scene = createScene(canvas);
  if (!scene) return null;
  const animation = animate(scene, settings);
  const resized = () => { scene.resize(); animation.repaint(); };
  const observer = new ResizeObserver(resized);
  observer.observe(canvas);
  document.addEventListener('visibilitychange', animation.repaint);
  animation.motion.addEventListener('change', animation.repaint);
  resized();
  return {
    repaint: animation.repaint,
    dispose: () => {
      animation.stop();
      observer.disconnect();
      document.removeEventListener('visibilitychange', animation.repaint);
      animation.motion.removeEventListener('change', animation.repaint);
      scene.dispose();
    },
  };
}
