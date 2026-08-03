import type { Schedule, Section } from '../api'

export interface ConsolidatedSchedule {
  schedule: Schedule
  alternativesBySectionKey: Map<string, Section[]>
}

function recurringMeetingKey(section: Section): string {
  return section.meetings
    .filter((meeting) => meeting.meeting_type !== 'final_exam')
    .map((meeting) => [
      [...meeting.days].sort((a, b) => a - b).join(','),
      meeting.start_time,
      meeting.end_time,
      meeting.start_date ?? '',
      meeting.end_date ?? '',
    ].join('|'))
    .sort()
    .join('~')
}

export function sectionEquivalenceKey(section: Section): string {
  return [section.subject, section.course_number, section.component, section.instructional_method ?? '', section.campus ?? '', recurringMeetingKey(section)].join('::')
}

function scheduleEquivalenceKey(schedule: Schedule): string {
  return schedule.sections.map(sectionEquivalenceKey).sort().join('||')
}

export function consolidateEquivalentSchedules(schedules: Schedule[]): ConsolidatedSchedule[] {
  const groups = new Map<string, ConsolidatedSchedule>()
  for (const schedule of schedules) {
    const key = scheduleEquivalenceKey(schedule)
    let group = groups.get(key)
    if (!group) {
      group = { schedule, alternativesBySectionKey: new Map() }
      groups.set(key, group)
    }
    for (const section of schedule.sections) {
      const sectionKey = sectionEquivalenceKey(section)
      const alternatives = group.alternativesBySectionKey.get(sectionKey) ?? []
      if (!alternatives.some((candidate) => candidate.id === section.id)) alternatives.push(section)
      alternatives.sort((left, right) => left.section_number.localeCompare(right.section_number, undefined, { numeric: true }))
      group.alternativesBySectionKey.set(sectionKey, alternatives)
    }
  }
  return [...groups.values()]
}
