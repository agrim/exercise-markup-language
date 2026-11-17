import { lazy, Suspense } from 'react'

const Pilot = /* @__PURE__ */ lazy(() => import('./EMLPilot.jsx'))

// The ordinary build keeps its existing media and does not ship the preview.
export default function OptionalEMLMedia({ ex }) {
  if (import.meta.env.VITE_EML_PREVIEW !== '1' || !ex) return null
  return <Suspense fallback={null}><Pilot ex={ex} /></Suspense>
}
