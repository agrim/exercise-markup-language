// @vitest-environment happy-dom
import React, { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import OptionalEMLMedia from './OptionalEMLMedia.jsx'
import { EXIDX, registerCustom } from '../lib/exercises.js'

const mocks = vi.hoisted(() => ({ S: { gifSize: 'full' }, still: false, props: null, renders: 0 }))
vi.mock('../store/useStore.js', () => ({ useStore: fn => fn({ S: mocks.S }) }))
vi.mock('./Animations.jsx', () => ({ useAnimSources: () => ({ still: mocks.still, sources: [] }) }))
vi.mock('../lib/i18n.js', () => ({
  t: value => `translated:${value}`, useLang: () => {},
  exerciseNameFor: () => 'Localized plank', descFor: () => 'Localized description',
  instrFor: () => ['Localized instruction one', 'Localized instruction two'],
}))
vi.mock('../vendor/eml-preview/EMLPreview.jsx', () => ({ default: props => {
  mocks.props = props; mocks.renders++
  return <span data-testid="preview">Optional movement</span>
} }))
let root, host
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  mocks.S = { gifSize: 'full' }; mocks.still = false; mocks.props = null; mocks.renders = 0
  registerCustom([])
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove(); registerCustom([]); vi.unstubAllEnvs() })
const mount = async ex => { await act(async () => { root.render(<OptionalEMLMedia ex={ex} />) }); await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) }) }
it('stays absent with the default or any non-opt-in build flag', async () => {
  for (const value of [undefined, '', '0', 'true']) {
    vi.stubEnv('VITE_EML_PREVIEW', value); await mount(EXIDX['0463'])
    expect(host.innerHTML).toBe('')
  }
  expect(mocks.renders).toBe(0)
})
it('enables only the exact reviewed string ID and supplies host-localized text', async () => {
  vi.stubEnv('VITE_EML_PREVIEW', '1'); await mount(EXIDX['0463'])
  await vi.waitFor(async () => { await act(async () => {}); expect(host.querySelector('[data-testid="preview"]')).toBeTruthy() })
  expect(mocks.props).toMatchObject({ enabled: true, exerciseID: '0463', title: 'Localized plank',
    description: 'Localized description Localized instruction one Localized instruction two' })
  expect(mocks.props.labels.play).toBe('translated:Play')
  expect(mocks.props.labels.view).toBe('translated:View movement')
  expect(new URL(mocks.props.baseURL).pathname).toMatch(/\/eml-pilot\/$/)
  for (const ex of [EXIDX['0043'], { ...EXIDX['0463'], id: 463 }, { ...EXIDX['0463'], id: '463' }]) {
    await mount(ex); expect(host.innerHTML).toBe('')
  }
})
it('suppresses missing and custom exercises including an imported custom ID shadow', async () => {
  vi.stubEnv('VITE_EML_PREVIEW', '1')
  await mount({ ...EXIDX['0463'], missing: true }); expect(host.innerHTML).toBe('')
  await mount({ ...EXIDX['0463'], custom: true }); expect(host.innerHTML).toBe('')
  const imported = { id: '0463', n: 'My movement' }; registerCustom([imported])
  await mount(imported); expect(host.innerHTML).toBe('')
})
it('respects hidden media and still-only preference without writing profile state', async () => {
  vi.stubEnv('VITE_EML_PREVIEW', '1')
  const before = structuredClone(mocks.S)
  await mount(EXIDX['0463']); expect(mocks.props).toBeTruthy(); expect(mocks.S).toEqual(before)
  mocks.S.gifSize = 'off'; await mount(EXIDX['0463']); expect(host.innerHTML).toBe('')
  mocks.S.gifSize = 'full'; mocks.still = true; await mount(EXIDX['0463']); expect(host.innerHTML).toBe('')
  mocks.still = false; await mount(EXIDX['0463']); expect(host.querySelector('[data-testid="preview"]')).toBeTruthy()
})
