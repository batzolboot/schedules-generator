import { describe, expect, it } from 'vitest'

import { schedule, meeting } from './testFixtures'
import { getCourseStyleMap, getMeetingPosition, getTimetableRange, minutesToTime } from './timetable'

describe('timetable calculations', () => {
  it('rounds the range around the earliest and latest meetings', () => {
    const range = getTimetableRange(schedule(1, [meeting(1, '09:30:00', '17:20:00')]))
    expect(range.startMinutes).toBe(8 * 60)
    expect(range.endMinutes).toBe(19 * 60)
    expect(range.labels[0]).toBe(8 * 60)
  })

  it('positions non-grid starts accurately and uses duration for height', () => {
    const range = getTimetableRange(schedule(1, [meeting(1, '09:30:00', '10:50:00')]))
    const short = getMeetingPosition('09:30:00', '10:50:00', range)
    const long = getMeetingPosition('09:30:00', '12:30:00', range)
    expect(short.top).toBeCloseTo(90 * 1.15)
    expect(short.height).toBeCloseTo(80 * 1.15)
    expect(long.height).toBeGreaterThan(short.height)
  })

  it('formats axis labels and assigns distinct deterministic styles to selected courses', () => {
    expect(minutesToTime(13 * 60 + 30)).toBe('1:30 PM')
    const styles = getCourseStyleMap(['MATH:201', 'CS:380', 'PHYS:201'])
    expect(new Set(styles.values())).toHaveLength(3)
    expect(styles).toEqual(getCourseStyleMap(['PHYS:201', 'MATH:201', 'CS:380']))
  })
})
