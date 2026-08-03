import { describe, expect, it } from 'vitest'

import { consolidateEquivalentSchedules, sectionEquivalenceKey } from './consolidate'
import { meeting, section } from './testFixtures'

const metrics = { campus_days: 2, total_gap_minutes: 0, earliest_start: '09:00:00', latest_end: '12:50:00', total_meeting_minutes: 160 }
const lecture = section(1, [meeting(1, '09:00:00', '09:50:00')], { section_number: 'A', component: 'lecture' })
const lab066 = section(2, [meeting(2, '11:00:00', '12:50:00')], { section_number: '066', component: 'lab', crn: '10284' })
const lab067 = section(3, [meeting(2, '11:00:00', '12:50:00')], { section_number: '067', component: 'lab', crn: '10285' })
const lab068 = section(4, [meeting(2, '15:00:00', '16:50:00')], { section_number: '068', component: 'lab' })

describe('equivalent schedule consolidation', () => {
  it('groups schedules differing only by sections with identical recurring meetings', () => {
    const groups = consolidateEquivalentSchedules([
      { sections: [lecture, lab066], metrics },
      { sections: [lecture, lab067], metrics },
      { sections: [lecture, lab068], metrics: { ...metrics, latest_end: '16:50:00' } },
    ])
    expect(groups).toHaveLength(2)
    expect(groups[0].alternativesBySectionKey.get(sectionEquivalenceKey(lab066))?.map((item) => item.section_number)).toEqual(['066', '067'])
  })

  it('does not merge sections whose recurring days, times, or date ranges differ', () => {
    const differentDay = section(5, [meeting(3, '11:00:00', '12:50:00')], { section_number: '069', component: 'lab' })
    const differentDates = section(6, [meeting(2, '11:00:00', '12:50:00', { start_date: '2026-10-01' })], { section_number: '070', component: 'lab' })
    expect(sectionEquivalenceKey(lab066)).not.toBe(sectionEquivalenceKey(differentDay))
    expect(sectionEquivalenceKey(lab066)).not.toBe(sectionEquivalenceKey(differentDates))
  })
})
