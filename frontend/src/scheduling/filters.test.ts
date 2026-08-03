import { describe, expect, it } from 'vitest'

import { clampEndMinutes, clampStartMinutes, describeActiveFilters, filterSchedules, getCampusDayCount, getEarliestMeetingStart, getLatestMeetingEnd, getRecurringMeetings, getScheduleDays, timeToMinutes } from './filters'
import { meeting, schedule, section } from './testFixtures'
import { DEFAULT_FILTERS } from './types'

const mondayEarly = schedule(1, [meeting(1, '08:00:00', '09:20:00')])
const tuesdayLate = schedule(2, [meeting(2, '10:00:00', '18:20:00')])
const saturdayMidday = schedule(3, [meeting(6, '11:00:00', '12:00:00')])

describe('schedule filters', () => {
  it('normalizes times and calculates every recurring meeting row', () => {
    const value = { sections: [section(1, [meeting(1), meeting(3, '13:15:00', '14:50:00')])], metrics: mondayEarly.metrics }
    expect(timeToMinutes('13:15')).toBe(795)
    expect(getRecurringMeetings(value)).toHaveLength(2)
    expect(getScheduleDays(value)).toEqual([1, 3])
    expect(getEarliestMeetingStart(value)).toBe(540)
    expect(getLatestMeetingEnd(value)).toBe(890)
    expect(getCampusDayCount(value)).toBe(2)
  })

  it('excludes schedules containing a disabled weekday', () => {
    expect(filterSchedules([mondayEarly, tuesdayLate], { ...DEFAULT_FILTERS, allowedDays: [2, 3, 4, 5] })).toEqual([tuesdayLate])
  })

  it('the default allowlist includes Saturday but excludes Sunday', () => {
    const sundayMidday = schedule(4, [meeting(7, '11:00:00', '12:00:00')])
    expect(filterSchedules([mondayEarly, saturdayMidday, sundayMidday], DEFAULT_FILTERS)).toEqual([mondayEarly, saturdayMidday])
  })

  it('applies inclusive earliest-start and latest-end limits', () => {
    expect(filterSchedules([mondayEarly, tuesdayLate], { ...DEFAULT_FILTERS, earliestStartMinutes: 10 * 60 })).toEqual([tuesdayLate])
    expect(filterSchedules([mondayEarly, tuesdayLate], { ...DEFAULT_FILTERS, latestEndMinutes: 17 * 60 })).toEqual([mondayEarly])
  })

  it('combines weekday and time filters', () => {
    expect(filterSchedules([mondayEarly, tuesdayLate, saturdayMidday], { allowedDays: [2], earliestStartMinutes: 9 * 60 + 30, latestEndMinutes: 19 * 60 })).toEqual([tuesdayLate])
  })

  it('ignores final-exam rows when filtering', () => {
    const value = schedule(4, [meeting(1, '10:00:00', '11:00:00'), meeting(6, '08:00:00', '12:00:00', { meeting_type: 'final_exam' })])
    expect(filterSchedules([value], { allowedDays: [1], earliestStartMinutes: 9 * 60, latestEndMinutes: 11 * 60 })).toEqual([value])
    expect(getRecurringMeetings(value)).toHaveLength(1)
  })

  it('prevents handles from crossing and preserves at least a 15-minute gap', () => {
    expect(clampStartMinutes(700, 600)).toBe(585)
    expect(clampEndMinutes(500, 600)).toBe(615)
    expect(600 - clampStartMinutes(700, 600)).toBeGreaterThanOrEqual(15)
  })

  it('describes weekday and time-range constraints', () => {
    const format = (value: number) => `${value} minutes`
    expect(describeActiveFilters({ allowedDays: [1, 3, 5], earliestStartMinutes: 600, latestEndMinutes: 1020 }, ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], format)).toEqual(['Monday, Wednesday, Friday', 'Classes between 600 minutes and 1020 minutes'])
  })
})
