// Optional static EML media. No workout state, telemetry, globals or autoplay.
export const defaultLabels = Object.freeze({
  view: 'View movement', hide: 'Hide movement', play: 'Play', pause: 'Pause',
  loading: 'Loading movement…', paused: 'Paused', playing: 'Playing',
  unavailable: 'Movement preview unavailable.',
  position: 'Movement position', camera: 'Camera', reset: 'Reset view',
  left: 'Rotate left', right: 'Rotate right', up: 'Rotate up', down: 'Rotate down',
  in: 'Zoom in', out: 'Zoom out', credits: 'Anatomy credits and license',
  cycle: 'One movement cycle. Preview only; no workout results are recorded.',
  seconds: '{current} of {total} seconds',
});
let nextID = 0;

export function previewLabels(labels) {
  return Object.fromEntries(Object.entries(defaultLabels).map(([key, fallback]) =>
    [key, typeof labels?.[key] === 'string' && labels[key].trim() ? labels[key] : fallback]));
}

export function mappedEntry(manifest, exerciseID) {
  if (manifest?.format !== 'eml-web-bundle-v1' || typeof exerciseID !== 'string'
      || !Array.isArray(manifest.entries)) return null;
  const matches = manifest.entries.filter(entry => entry?.exercise_id === exerciseID);
  return matches.length === 1 ? matches[0] : null;
}

function assetURL(base, path) {
  if (typeof path !== 'string' || !path || /[\\?#:%]/.test(path)
      || path.startsWith('/') || path.split('/').some(part => part === '..' || part === '.')) {
    throw new Error('Invalid bundle-relative asset path');
  }
  const url = new URL(path, base);
  if (url.origin !== base.origin || !url.pathname.startsWith(base.pathname)) {
    throw new Error('Asset escaped the bundle');
  }
  return url;
}

function validateClip(clip, entry, model, kit) {
  if (!['1.0', '1.1'].includes(clip?.eml) || clip.eml !== entry.eml_version
      || clip.id !== entry.eml_id || !Number.isFinite(clip.duration) || clip.duration <= 0
      || !Array.isArray(clip.frames) || clip.frames.length < 2 || clip.frames.length > 3600
      || !Array.isArray(model?.joints) || !model.joints.length
      || !Array.isArray(clip.equipment)) throw new Error('Invalid compiled clip');
  let previous = -1;
  const vector = (v, n) => Array.isArray(v) && v.length === n && v.every(Number.isFinite);
  for (const frame of clip.frames) {
    // The compiler may emit both a phase endpoint and a sample at the same time.
    if (!Number.isFinite(frame.time) || frame.time < previous || frame.time > clip.duration
        || !Array.isArray(frame.diagnostics) || frame.diagnostics.length) throw new Error('Invalid clip sample');
    previous = frame.time;
    for (const joint of model.joints) {
      if (!vector(frame.rotations?.[joint.name], 4) || !vector(frame.positions?.[joint.name], 3)) {
        throw new Error('Invalid joint sample');
      }
    }
    for (const item of clip.equipment) {
      const pose = frame.equipment?.[item.id];
      if (!kit[item.kind] || !vector(pose?.position, 3) || !vector(pose?.rotation, 4)) {
        throw new Error('Invalid equipment sample');
      }
    }
  }
  if (clip.frames[0].time !== 0 || previous !== clip.duration) throw new Error('Incomplete clip');
}

/** Mount inside a dedicated empty host; dispose on unmount or any exercise change.
 * The caller keeps its existing media alongside this host. Assets and the renderer
 * load only after View movement. All labels accept host-localized plain strings.
 */
export function mountEMLPreview(host, {
  manifest, baseURL, exerciseID, title, description, labels = {}, onUnavailable,
} = {}) {
  const entry = mappedEntry(manifest, exerciseID);
  if (!entry || typeof title !== 'string' || !title.trim()
      || typeof description !== 'string' || !description.trim()) return {dispose() {}};
  const text = previewLabels(labels);
  const doc = host.ownerDocument, win = doc.defaultView;
  const id = `eml-preview-${++nextID}`;
  const create = (tag, content, attrs = {}) => {
    const el = doc.createElement(tag);
    if (content !== undefined) el.textContent = content;
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
    return el;
  };
  const root = create('div', undefined, {class: 'eml-preview', role: 'group', 'aria-label': title});
  const toggle = create('button', text.view, {type: 'button', 'aria-expanded': false, 'aria-controls': id});
  const panel = create('div', undefined, {id}); panel.hidden = true;
  // Keep the live region mounted before changing its text; do not announce frames.
  const status = create('p', '', {role: 'status', 'aria-atomic': true});
  const content = create('div');
  panel.append(content); root.append(toggle, status, panel); host.append(root);
  const lifetime = new AbortController();
  let disposed = false, current = null;

  function release() {
    const run = current; current = null;
    if (!run) return;
    run.abort.abort(); win.cancelAnimationFrame(run.raf);
    run.observer?.disconnect(); run.atlas?.dispose();
    // Releasing the context prevents context-slot exhaustion across repeated mounts.
    run.context?.getExtension('WEBGL_lose_context')?.loseContext();
    run.canvas.width = run.canvas.height = 1;
  }
  function close() {
    release(); content.replaceChildren(); panel.hidden = true; status.textContent = '';
    toggle.textContent = text.view; toggle.setAttribute('aria-expanded', 'false');
  }
  async function open() {
    panel.hidden = false; toggle.textContent = text.hide; toggle.setAttribute('aria-expanded', 'true');
    status.textContent = text.loading;
    const canvas = create('canvas', undefined, {role: 'img', 'aria-label': title,
      'aria-describedby': `${id}-description ${id}-cycle`});
    const run = {abort: new AbortController(), canvas, atlas: null, raf: 0,
      playing: false, inView: true, observer: null, context: null};
    current = run;
    const valid = () => !disposed && current === run && !run.abort.signal.aborted;
    function fail(error) {
      if (!valid()) return;
      // If a focused control disappears, return focus to the stable disclosure.
      if (content.contains(doc.activeElement)) toggle.focus();
      release(); content.replaceChildren(); status.textContent = text.unavailable;
      // Host callbacks are optional and must not turn media failure into an app crash.
      try { onUnavailable?.(error); } catch { /* Host retains its existing media. */ }
    }
    try {
      const base = new URL(baseURL, doc.baseURI);
      if (base.origin !== win.location.origin || !base.pathname.endsWith('/') || base.search || base.hash) {
        throw new Error('Use a same-origin bundle directory URL ending in /');
      }
      async function load(path, kind, hash) {
        if (typeof hash !== 'string' || !/^[a-f0-9]{64}$/.test(hash)) throw new Error('Missing asset hash');
        const response = await win.fetch(assetURL(base, path), {signal: run.abort.signal,
          credentials: 'same-origin', redirect: 'error'});
        if (!response.ok) throw new Error(`Asset unavailable (${response.status})`);
        const bytes = await response.arrayBuffer();
        const digest = await win.crypto.subtle.digest('SHA-256', bytes);
        const actual = [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2, '0')).join('');
        if (actual !== hash) throw new Error('Asset does not match its manifest');
        return kind === 'json' ? JSON.parse(new TextDecoder().decode(bytes)) : bytes;
      }
      const assets = manifest.assets, hashes = manifest.asset_sha256;
      const asset = (path, kind) => load(path, kind, hashes?.[path]);
      const [module, cameraModule, model, vertices, indices, clip, kit] = await Promise.all([
        import('../../viewer/mesh.js'), import('../../viewer/camera-controls.js'), asset(assets?.model, 'json'),
        asset(assets?.vertices), asset(assets?.indices), load(entry.clip, 'json', entry.clip_sha256),
        asset(assets?.equipment?.[entry.eml_version], 'json'),
      ]);
      if (!valid()) return;
      validateClip(clip, entry, model, kit);
      const creditsURL = assetURL(base, assets.attribution);
      const desc = create('p', description, {id: `${id}-description`});
      const cycle = create('p', text.cycle, {id: `${id}-cycle`});
      const controls = create('div', undefined, {class: 'eml-preview-controls'});
      const play = create('button', text.play, {type: 'button'});
      const range = create('input', undefined, {type: 'range', id: `${id}-position`, min: 0,
        max: clip.duration, step: Math.min(0.05, clip.duration / 100), value: 0});
      const rangeLabel = create('label', text.position, {for: range.id});
      const clock = create('span', '', {'aria-hidden': true, dir: 'ltr', class: 'eml-preview-clock'});
      const camera = create('details'); camera.append(create('summary', text.camera));
      const cameraControls = create('div', undefined, {class: 'eml-preview-controls'});
      camera.append(cameraControls);
      const credits = create('a', text.credits, {href: creditsURL.href, target: '_blank', rel: 'noopener noreferrer'});
      controls.append(play, clock);
      // Keep playback next to the canvas. Long translated host instructions must
      // not scroll the canvas offscreen merely to reach Play (which pauses it).
      content.replaceChildren(canvas, controls, rangeLabel, range, camera, cycle, desc, credits);
      const on = (target, event, fn) => target.addEventListener(event, fn, {signal: run.abort.signal});
      on(canvas, 'webglcontextlost', () => fail(new Error('WebGL context lost')));
      // Own the context even if Atlas initialization throws after partial setup.
      run.context = canvas.getContext('webgl2', {antialias: true, alpha: true, preserveDrawingBuffer: true});
      run.atlas = new module.Atlas(canvas, model, vertices, indices, kit);
      run.context = run.atlas.gl;
      run.atlas.setClip(clip);
      function refresh() {
        range.value = run.atlas.time;
        const currentTime = run.atlas.time.toFixed(1), total = clip.duration.toFixed(1);
        range.setAttribute('aria-valuetext', text.seconds.replace('{current}', currentTime).replace('{total}', total));
        clock.textContent = `${currentTime} / ${total}`;
      }
      function pause() {
        run.playing = false; win.cancelAnimationFrame(run.raf); run.raf = 0;
        play.textContent = text.play; status.textContent = text.paused;
      }
      function tick(now) {
        run.raf = 0;
        if (!valid() || !run.playing) return;
        if (doc.hidden || !run.inView) { pause(); return; }
        try {
          run.atlas.time = Math.min(clip.duration, (now - run.startedAt) / 1000);
          run.atlas.draw(); refresh();
          if (run.atlas.time >= clip.duration) pause();
          else run.raf = win.requestAnimationFrame(tick);
        } catch (error) { fail(error); }
      }
      on(play, 'click', () => {
        if (run.playing) { pause(); return; }
        if (doc.hidden || !run.inView) return;
        if (run.atlas.time >= clip.duration) run.atlas.time = 0;
        run.playing = true; play.textContent = text.pause; status.textContent = text.playing;
        run.startedAt = win.performance.now() - run.atlas.time * 1000;
        run.raf = win.requestAnimationFrame(tick);
      });
      on(range, 'input', () => {
        pause();
        try { run.atlas.time = Math.min(clip.duration, Math.max(0, Number(range.value))); run.atlas.draw(); refresh(); }
        catch (error) { fail(error); }
      });
      for (const name of ['left', 'right', 'up', 'down', 'in', 'out', 'reset']) {
        const button = create('button', text[name], {type: 'button'});
        on(button, 'click', () => {
          try {
            if (name === 'reset') run.atlas.camera('recipe');
            else cameraModule.adjustCamera(run.atlas, name);
          } catch (error) { fail(error); }
        });
        cameraControls.append(button);
      }
      function visibility() {
        run.atlas.renderingSkipped = doc.hidden || !run.inView;
        if (run.atlas.renderingSkipped) pause();
        else { try { run.atlas.draw(); } catch (error) { fail(error); } }
      }
      on(doc, 'visibilitychange', visibility);
      on(win, 'pagehide', pause);
      const reduced = win.matchMedia('(prefers-reduced-motion: reduce)');
      on(reduced, 'change', () => { if (reduced.matches) pause(); });
      // No autoplay even without Reduce Motion. Explicit Play is always available.
      if (win.IntersectionObserver) {
        run.observer = new win.IntersectionObserver(entries => {
          if (!valid()) return;
          const latest = entries.filter(item => item.target === canvas).at(-1);
          if (!latest) return;
          run.inView = latest.isIntersecting; visibility();
        });
        run.observer.observe(canvas);
      }
      refresh(); pause(); visibility();
    } catch (error) { fail(error); }
  }
  toggle.addEventListener('click', () => {
    if (panel.hidden) void open(); else close();
  }, {signal: lifetime.signal});
  return {dispose() {
    if (disposed) return;
    disposed = true; release(); lifetime.abort(); root.remove();
  }};
}
