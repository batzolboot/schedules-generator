import { describe, expect, it } from 'vitest'

import { scheduleToIcs } from './export'
import { meeting, section, schedule } from './testFixtures'

describe('schedule export', () => {
  it('creates an Outlook-compatible recurring calendar with preserved alternatives', () => {
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
    expect(value).toContain('RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=20261205T235959')
    expect(value).toContain('SUMMARY:CI 102: Computing and Informatics Design II')
    expect(value).toContain('section A or B\\; CRN 10920 or 10921')
    expect(value).not.toContain('LOCATION:')
  })
})
