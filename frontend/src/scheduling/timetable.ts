import type { Schedule } from '../api'
import { getEarliestMeetingStart, getLatestMeetingEnd, timeToMinutes } from './filters'

export const GRID_INTERVAL_MINUTES = 30
export const PIXELS_PER_MINUTE = 1.15
const EARLIEST_BOUNDARY = 6 * 60
const LATEST_BOUNDARY = 23 * 60

export interface TimetableRange {
  startMinutes: number
  endMinutes: number
  labels: number[]
  height: number
}

export interface MeetingPosition {
  top: number
  height: number
}

export function getTimetableRange(schedule: Schedule): TimetableRange {
  const earliest = getEarliestMeetingStart(schedule) ?? 9 * 60
  const latest = getLatestMeetingEnd(schedule) ?? 17 * 60
  const startMinutes = Math.max(EARLIEST_BOUNDARY, Math.floor((earliest - 60) / 60) * 60)
  const endMinutes = Math.min(LATEST_BOUNDARY, Math.ceil((latest + 60) / 60) * 60)
  const labels: number[] = []
  for (let minute = startMinutes; minute <= endMinutes; minute += GRID_INTERVAL_MINUTES) labels.push(minute)
  return { startMinutes, endMinutes, labels, height: (endMinutes - startMinutes) * PIXELS_PER_MINUTE }
}

export function getMeetingPosition(startTime: string, endTime: string, range: TimetableRange): MeetingPosition {
  const start = timeToMinutes(startTime)
  const end = timeToMinutes(endTime)
  return {
    top: (start - range.startMinutes) * PIXELS_PER_MINUTE,
    height: Math.max((end - start) * PIXELS_PER_MINUTE, 30),
  }
}

export function minutesToTime(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const minute = minutes % 60
  const suffix = hours >= 12 ? 'PM' : 'AM'
  const displayHour = hours % 12 || 12
  return `${displayHour}:${String(minute).padStart(2, '0')} ${suffix}`
}

export function getCourseStyleMap(courseKeys: string[]): Map<string, number> {
  const uniqueKeys = [...new Set(courseKeys)].sort()
  return new Map(uniqueKeys.map((key, index) => [key, index % 8]))
}
