import { afterEach, describe, expect, it, vi } from 'vitest'

import { scheduleToIcs } from './export'
import { meeting, section, schedule } from './testFixtures'

describe('schedule export', () => {
  afterEach(() => vi.useRealTimers())

  it('creates an Outlook-compatible recurring calendar with preserved alternatives', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-17T15:04:05Z'))
    const item = section(1, [meeting(2, '13:00:00', '13:50:00')], {
      subject: 'CI',
      course_number: '102',
      section_number: 'A',
      crn: '10920',
      alternative_section_numbers: ['A', 'B'],
      alternative_crns: ['10920', '10921'],
    })
    const value = scheduleToIcs({ ...schedule(1, item.meetings), sections: [item] }, new Map([['CI:102', 'Computing and Informatics Design II']]))

    expect(value).toContain('BEGIN:VCALENDAR\r\nVERSION:2.0')
    expect(value).toContain('BEGIN:VTIMEZONE\r\nTZID:America/New_York')
    expect(value).toContain('DTSTAMP:20260817T150405Z')
    expect(value).toContain('DTSTART;TZID=America/New_York:20260922T130000')
    expect(value).toContain('DTEND;TZID=America/New_York:20260922T135000')
    expect(value).toContain('RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=20261201T180000Z')
    expect(value).toContain('SUMMARY:CI 102: Computing and Informatics Design II')
    expect(value).toContain('section A or B\\; CRN 10920 or 10921')
    expect(value).not.toContain('LOCATION:')
  })

  it('uses the earliest listed weekday and includes an occurrence on the meeting end date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-17T15:04:05Z'))
    const item = section(2, [meeting(4, '13:00:00', '13:50:00', {
      days: [6, 2, 4],
      start_date: '2026-09-22',
      end_date: '2026-12-05',
    })])

    const value = scheduleToIcs({ ...schedule(2, item.meetings), sections: [item] }, new Map())

    expect(value).toContain('DTSTART;TZID=America/New_York:20260922T130000')
    expect(value).toContain('RRULE:FREQ=WEEKLY;BYDAY=TU,TH,SA;UNTIL=20261205T180000Z')
  })
})
