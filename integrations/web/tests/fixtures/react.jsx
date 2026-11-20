import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import EMLPreview from '../../EMLPreview.jsx';
const manifest = await (await fetch('/integrations/web/tests/generated/bundle/manifest.json')).json();
const baseURL = new URL('/integrations/web/tests/generated/bundle/', location.href).href;
const root = createRoot(document.querySelector('#react-root'));
window.reactFixture = {
  render(overrides = {}) {
    root.render(<StrictMode><EMLPreview enabled manifest={manifest} baseURL={baseURL} exerciseID="demo:squat"
      title="Squat" description="Stand with feet planted, bend the hips and knees, then return to standing." {...overrides} /></StrictMode>);
  },
  unmount() { root.unmount(); },
};
window.fixtureReady = true;
