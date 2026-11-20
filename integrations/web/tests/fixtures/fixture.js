import { mountEMLPreview } from '../../preview.js';
const manifest = await (await fetch('../generated/bundle/manifest.json')).json();
const baseURL = new URL('../generated/bundle/', import.meta.url).href;
let handle;
let second;
const original = document.querySelector('#original');
original.addEventListener('click', () => {
  document.querySelector('#original-status').textContent = 'Original media selected.';
});
window.fixture = {
  manifest,
  failures: [],
  mount(overrides = {}) {
    handle?.dispose();
    handle = mountEMLPreview(document.querySelector('#host'), {
      manifest, baseURL, exerciseID: 'demo:squat', title: 'Squat',
      description: 'Stand with feet planted, bend the hips and knees, then return to standing.',
      onUnavailable: error => this.failures.push(String(error)), ...overrides,
    });
  },
  async mountPackaged(overrides = {}) {
    handle?.dispose();
    document.querySelector('#preview-style').href = '../generated/package/preview.css';
    const packaged = await import('../generated/package/preview.js');
    handle = packaged.mountEMLPreview(document.querySelector('#host'), {
      manifest, baseURL, exerciseID: 'demo:squat', title: 'Squat',
      description: 'Stand with feet planted, bend the hips and knees, then return to standing.',
      onUnavailable: error => this.failures.push(String(error)), ...overrides,
    });
  },
  mountSecond(overrides = {}) {
    second?.dispose();
    second = mountEMLPreview(document.querySelector('#second-host'), {
      manifest, baseURL, exerciseID: 'demo:plank', title: 'Plank',
      description: 'Support your body on forearms and toes, keeping the trunk steady.', ...overrides,
    });
  },
  dispose() { handle?.dispose(); second?.dispose(); },
  originalUnchanged() { return document.querySelector('#original') === original; },
};
window.fixtureReady = true;
