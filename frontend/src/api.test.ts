import { describe, expect, it } from 'vitest'

import { formatErrorDetail } from './api'

describe('API error formatting', () => {
  it('formats FastAPI validation errors instead of displaying object coercion', () => {
    expect(formatErrorDetail([{ loc: ['body', 'maximum_results'], msg: 'Input should be less than or equal to 100' }]))
      .toBe('maximum_results: Input should be less than or equal to 100')
  })

  it('preserves ordinary string details', () => {
    expect(formatErrorDetail('One or more courses are invalid.')).toBe('One or more courses are invalid.')
  })
})
