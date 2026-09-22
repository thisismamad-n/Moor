import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { $backdrop, setBackdrop } from '@/store/backdrop'

import { Backdrop } from './Backdrop'

describe('Backdrop component', () => {
  beforeEach(() => {
    setBackdrop(false)
  })

  afterEach(() => {
    cleanup()
    setBackdrop(false)
  })

  it('renders nothing when backdrop is off', () => {
    const { container } = render(<Backdrop />)
    expect(container.firstChild).toBeNull()
  })

  it('renders subtle Moor chat backdrop artwork when backdrop is on', () => {
    act(() => {
      setBackdrop(true)
    })

    const { container } = render(<Backdrop />)
    const wrapper = container.querySelector('div[aria-hidden="true"]')
    expect(wrapper).not.toBeNull()
    expect(wrapper?.className).toContain('opacity-[0.025]')
    expect(wrapper?.className).toContain('mix-blend-difference')

    const img = wrapper?.querySelector('img')
    expect(img).not.toBeNull()
    expect(img?.getAttribute('src')).toContain('ds-assets/filler-bg0.jpg')
  })

  it('reactively updates when backdrop store toggles', () => {
    const { container } = render(<Backdrop />)
    expect(container.firstChild).toBeNull()

    act(() => {
      setBackdrop(true)
    })
    expect(container.querySelector('img')).not.toBeNull()

    act(() => {
      setBackdrop(false)
    })
    expect(container.firstChild).toBeNull()
  })
})
