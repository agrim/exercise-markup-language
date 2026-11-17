// Test-only accounting around the browser's real APIs. The renderer is never replaced.
export function installAccounting() {
  const live = { buffer: new Set(), vertexArray: new Set(), program: new Set(), shader: new Set() };
  const counts = { created: 0, deleted: 0, draws: 0 };
  const observers = new Set();
  const frames = new Set();
  const listeners = [];
  const activeFetches = new Set();
  const proto = globalThis.WebGL2RenderingContext?.prototype;
  if (proto) {
    for (const [kind, suffix] of [['buffer', 'Buffer'], ['vertexArray', 'VertexArray'], ['program', 'Program'], ['shader', 'Shader']]) {
      const create = proto[`create${suffix}`];
      const remove = proto[`delete${suffix}`];
      proto[`create${suffix}`] = function (...args) {
        const value = create.apply(this, args);
        if (value) { live[kind].add(value); counts.created++; }
        return value;
      };
      proto[`delete${suffix}`] = function (value) {
        if (live[kind].delete(value)) counts.deleted++;
        return remove.call(this, value);
      };
    }
    for (const name of ['drawElements', 'drawArrays']) {
      const draw = proto[name];
      proto[name] = function (...args) { counts.draws++; return draw.apply(this, args); };
    }
  }
  for (const name of ['ResizeObserver', 'IntersectionObserver']) {
    const Native = globalThis[name];
    if (!Native) continue;
    globalThis[name] = class extends Native {
      observe(...args) { observers.add(this); return super.observe(...args); }
      disconnect() { observers.delete(this); return super.disconnect(); }
    };
  }
  const request = requestAnimationFrame.bind(window);
  const cancel = cancelAnimationFrame.bind(window);
  window.requestAnimationFrame = callback => {
    let id;
    id = request(time => { frames.delete(id); callback(time); });
    frames.add(id);
    return id;
  };
  window.cancelAnimationFrame = id => { frames.delete(id); return cancel(id); };
  const nativeAdd = EventTarget.prototype.addEventListener;
  const nativeRemove = EventTarget.prototype.removeEventListener;
  const trackedTarget = target => target === document || target === window
    || target instanceof HTMLCanvasElement || target instanceof MediaQueryList;
  EventTarget.prototype.addEventListener = function (type, callback, options) {
    if (trackedTarget(this) && callback && !options?.signal?.aborted) {
      const capture = typeof options === 'boolean' ? options : Boolean(options?.capture);
      if (!listeners.some(item => item.target === this && item.type === type && item.callback === callback && item.capture === capture)) {
        const item = { target: this, type, callback, capture };
        listeners.push(item);
        if (options?.signal) nativeAdd.call(options.signal, 'abort', () => {
          const index = listeners.indexOf(item); if (index >= 0) listeners.splice(index, 1);
        }, { once: true });
      }
    }
    return nativeAdd.call(this, type, callback, options);
  };
  EventTarget.prototype.removeEventListener = function (type, callback, options) {
    const capture = typeof options === 'boolean' ? options : Boolean(options?.capture);
    const index = listeners.findIndex(item => item.target === this && item.type === type && item.callback === callback && item.capture === capture);
    if (index >= 0) listeners.splice(index, 1);
    return nativeRemove.call(this, type, callback, options);
  };
  const fetch = window.fetch.bind(window);
  window.fetch = (...args) => {
    const token = {};
    activeFetches.add(token);
    return fetch(...args).finally(() => activeFetches.delete(token));
  };
  window.accounting = () => ({
    live: Object.fromEntries(Object.entries(live).map(([key, set]) => [key, set.size])),
    ...counts, observers: observers.size, frames: frames.size,
    listeners: listeners.map(({ target, type }) => `${target.constructor.name}:${type}`).sort(),
    activeFetches: activeFetches.size,
  });
}
