import type { Meeting, Schedule, Section } from '../api'

export function meeting(day: number, start = '09:00:00', end = '10:00:00', overrides: Partial<Meeting> = {}): Meeting {
  return { days: [day], start_time: start, end_time: end, start_date: '2026-09-22', end_date: '2026-12-05', meeting_type: 'class', is_asynchronous: false, is_arranged: false, ...overrides }
}

export function section(id: number, meetings: Meeting[], overrides: Partial<Section> = {}): Section {
  return { id, subject: 'CS', course_number: '380', crn: String(41000 + id), section_number: '001', component: 'lecture', instructors: ['Ada Lovelace'], meetings, campus: 'University City', instructional_method: 'Face-To-Face', maximum_enrollment: 30, ...overrides }
}

export function schedule(id: number, meetings: Meeting[]): Schedule {
  const starts = meetings.flatMap((item) => item.start_time ? [item.start_time] : []).sort()
  const ends = meetings.flatMap((item) => item.end_time ? [item.end_time] : []).sort()
  return { sections: [section(id, meetings)], metrics: { campus_days: new Set(meetings.flatMap((item) => item.days)).size, total_gap_minutes: 0, earliest_start: starts[0] ?? null, latest_end: ends.at(-1) ?? null, total_meeting_minutes: 60 * meetings.length } }
}
