import type { Meeting, Schedule } from '../api'
import { DEFAULT_EARLIEST_START, DEFAULT_LATEST_END, FILTER_DAYS, MINIMUM_RANGE_MINUTES, type ScheduleFilters } from './types'

export interface ScheduleMeeting {
  meeting: Meeting & { start_time: string; end_time: string }
  day: number
}

export function timeToMinutes(value: string): number {
  const [hours, minutes] = value.split(':').map(Number)
  if (!Number.isInteger(hours) || !Number.isInteger(minutes) || hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    throw new Error(`Invalid time: ${value}`)
  }
  return hours * 60 + minutes
}

export function getRecurringMeetings(schedule: Schedule): ScheduleMeeting[] {
  return schedule.sections.flatMap((section) =>
    section.meetings
      .filter((meeting): meeting is Meeting & { start_time: string; end_time: string } => meeting.start_time !== null && meeting.end_time !== null && meeting.days.length > 0)
      .filter((meeting) => meeting.meeting_type !== 'final_exam')
      .flatMap((meeting) => meeting.days.map((day) => ({ meeting, day }))),
  )
}

export function getScheduleDays(schedule: Schedule): number[] {
  return [...new Set(getRecurringMeetings(schedule).map(({ day }) => day))].sort((a, b) => a - b)
}

export function getEarliestMeetingStart(schedule: Schedule): number | null {
  const starts = getRecurringMeetings(schedule).map(({ meeting }) => timeToMinutes(meeting.start_time))
  return starts.length ? Math.min(...starts) : null
}

export function getLatestMeetingEnd(schedule: Schedule): number | null {
  const ends = getRecurringMeetings(schedule).map(({ meeting }) => timeToMinutes(meeting.end_time))
  return ends.length ? Math.max(...ends) : null
}

export function getCampusDayCount(schedule: Schedule): number {
  return getScheduleDays(schedule).length
}

export function filterSchedules(schedules: Schedule[], filters: ScheduleFilters): Schedule[] {
  const allowedDays = new Set(filters.allowedDays)

  return schedules.filter((schedule) =>
    getRecurringMeetings(schedule).every(({ meeting, day }) =>
      allowedDays.has(day)
      && timeToMinutes(meeting.start_time) >= filters.earliestStartMinutes
      && timeToMinutes(meeting.end_time) <= filters.latestEndMinutes,
    ),
  )
}

export function filtersAreDefault(filters: ScheduleFilters, filterDays: readonly number[] = FILTER_DAYS): boolean {
  return filters.allowedDays.length === filterDays.length
    && filterDays.every((day) => filters.allowedDays.includes(day))
    && filters.earliestStartMinutes === DEFAULT_EARLIEST_START
    && filters.latestEndMinutes === DEFAULT_LATEST_END
}

export function clampStartMinutes(requested: number, endMinutes: number): number {
  return Math.min(requested, endMinutes - MINIMUM_RANGE_MINUTES)
}

export function clampEndMinutes(requested: number, startMinutes: number): number {
  return Math.max(requested, startMinutes + MINIMUM_RANGE_MINUTES)
}

export function describeActiveFilters(filters: ScheduleFilters, dayNames: string[], formatMinutes: (value: number) => string, filterDays: readonly number[] = FILTER_DAYS): string[] {
  const selectedDays = filterDays.filter((day) => filters.allowedDays.includes(day))
  const dayDescription = selectedDays.length === filterDays.length
    ? filterDays.includes(6) ? 'Monday–Saturday' : 'Monday–Friday'
    : selectedDays.length
      ? selectedDays.map((day) => dayNames[day - 1]).join(', ')
      : 'No weekdays selected'
  return [dayDescription, `Classes between ${formatMinutes(filters.earliestStartMinutes)} and ${formatMinutes(filters.latestEndMinutes)}`]
}
