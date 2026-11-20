import {useEffect, useRef} from 'react';
import {mountEMLPreview, previewLabels} from './preview.js';
import './preview.css';

// Optional adjunct: render next to existing media, never around or instead of it.
export default function EMLPreview({enabled = false, manifest, baseURL, exerciseID,
  title, description, labels, onUnavailable}) {
  const host = useRef(null);
  const unavailable = useRef(onUnavailable);
  unavailable.current = onUnavailable;
  // Inline label maps/callbacks are common in React. An unrelated render must
  // not close an open preview; only changed label contents require rebuilding it.
  const labelKey = JSON.stringify(previewLabels(labels));
  useEffect(() => {
    if (!enabled || !host.current) return;
    const preview = mountEMLPreview(host.current, {
      manifest, baseURL, exerciseID, title, description, labels: JSON.parse(labelKey),
      onUnavailable: error => unavailable.current?.(error),
    });
    return () => preview.dispose();
  }, [enabled, manifest, baseURL, exerciseID, title, description, labelKey]);
  return enabled ? <div ref={host} /> : null;
}
