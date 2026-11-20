import { useStore } from '../store/useStore.js'
import { t, useLang, exerciseNameFor, descFor, instrFor } from '../lib/i18n.js'
import { isCustomEx, figureOf } from '../lib/exercises.js'
import { useAnimSources } from './Animations.jsx'
import EMLPreview from '../vendor/eml-preview/EMLPreview.jsx'
import { defaultLabels, mappedEntry } from '../vendor/eml-preview/preview.js'
import manifest from './optional-eml-manifest.json'

export default function EMLPilot({ ex }) {
  useLang()
  const hidden = useStore(s => s.S.gifSize === 'off')
  const figure = useStore(s => figureOf(s.S))
  const animation = useAnimSources(ex, figure)
  if (!ex || ex.missing || isCustomEx(ex) || hidden || animation.still || !mappedEntry(manifest, ex.id)) return null
  return <EMLPreview enabled manifest={manifest}
    baseURL={new URL(`${import.meta.env.BASE_URL}eml-pilot/`, document.baseURI).href}
    exerciseID={ex.id} title={exerciseNameFor(ex)}
    description={[descFor(ex), ...instrFor(ex)].filter(Boolean).join(' ')}
    labels={Object.fromEntries(Object.entries(defaultLabels).map(([key, value]) => [key, t(value)]))} />
}
