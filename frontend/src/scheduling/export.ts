import type { Schedule } from '../api'

const DAY_CODES = ['', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
const EASTERN_TIME_ZONE = 'America/New_York'
const EASTERN_TIME_ZONE_COMPONENT = [
  'BEGIN:VTIMEZONE',
  `TZID:${EASTERN_TIME_ZONE}`,
  'BEGIN:DAYLIGHT',
  'TZOFFSETFROM:-0500',
  'TZOFFSETTO:-0400',
  'TZNAME:EDT',
  'DTSTART:20070311T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU',
  'END:DAYLIGHT',
  'BEGIN:STANDARD',
  'TZOFFSETFROM:-0400',
  'TZOFFSETTO:-0500',
  'TZNAME:EST',
  'DTSTART:20071104T020000',
  'RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU',
  'END:STANDARD',
  'END:VTIMEZONE',
]
const EASTERN_DATE_TIME_FORMATTER = new Intl.DateTimeFormat('en-US-u-ca-gregory-nu-latn', {
  timeZone: EASTERN_TIME_ZONE,
  hourCycle: 'h23',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function compactDate(date: string): string {
  return date.replaceAll('-', '')
}

function compactTime(time: string): string {
  return time.replaceAll(':', '').slice(0, 4) + '00'
}

function dateOnly(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}

function formatDateOnly(value: Date): string {
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, '0')}-${String(value.getUTCDate()).padStart(2, '0')}`
}

function calendarDayToUtcDay(day: number): number {
  return day === 7 ? 0 : day
}

function occurrenceDate(boundary: string, days: number[], direction: 'first' | 'last'): string {
  const date = dateOnly(boundary)
  const currentDay = date.getUTCDay()
  const offsets = days.map((day) => direction === 'first'
    ? (calendarDayToUtcDay(day) - currentDay + 7) % 7
    : -((currentDay - calendarDayToUtcDay(day) + 7) % 7))
  date.setUTCDate(date.getUTCDate() + (direction === 'first' ? Math.min(...offsets) : Math.max(...offsets)))
  return formatDateOnly(date)
}

function easternDateTimeToUtc(date: string, time: string): Date {
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute, second = 0] = time.split(':').map(Number)
  const desiredWallTime = Date.UTC(year, month - 1, day, hour, minute, second)
  let candidate = desiredWallTime

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const parts = Object.fromEntries(
      EASTERN_DATE_TIME_FORMATTER.formatToParts(new Date(candidate))
        .filter((part) => part.type !== 'literal')
        .map((part) => [part.type, Number(part.value)]),
    )
    const representedWallTime = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second)
    candidate += desiredWallTime - representedWallTime
  }

  return new Date(candidate)
}

function utcTimestamp(value: Date): string {
  return value.toISOString().replaceAll('-', '').replaceAll(':', '').replace(/\.\d{3}Z$/, 'Z')
}

function escapeIcs(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll(';', '\\;').replaceAll(',', '\\,').replaceAll('\n', '\\n')
}

export function scheduleToIcs(schedule: Schedule, titles: Map<string, string>): string {
  const generatedAt = utcTimestamp(new Date())
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Drexel Schedule Generator//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', `X-WR-TIMEZONE:${EASTERN_TIME_ZONE}`, ...EASTERN_TIME_ZONE_COMPONENT]
  for (const section of schedule.sections) {
    for (const [meetingIndex, meeting] of section.meetings.filter((item) => item.meeting_type !== 'final_exam').entries()) {
      if (!meeting.start_date || !meeting.start_time || !meeting.end_time || meeting.days.length === 0) continue
      const days = [...new Set(meeting.days)].sort((left, right) => left - right)
      const firstDate = occurrenceDate(meeting.start_date, days, 'first')
      const lastDate = meeting.end_date ? occurrenceDate(meeting.end_date, days, 'last') : null
      if (lastDate && lastDate < firstDate) continue
      const title = titles.get(`${section.subject}:${section.course_number}`) ?? 'Course'
      lines.push(
        'BEGIN:VEVENT',
        `UID:${section.id}-${meetingIndex}-${compactDate(firstDate)}@drexel-schedule-generator`,
        `DTSTAMP:${generatedAt}`,
        `DTSTART;TZID=${EASTERN_TIME_ZONE}:${compactDate(firstDate)}T${compactTime(meeting.start_time)}`,
        `DTEND;TZID=${EASTERN_TIME_ZONE}:${compactDate(firstDate)}T${compactTime(meeting.end_time)}`,
        `RRULE:FREQ=WEEKLY;BYDAY=${days.map((day) => DAY_CODES[day]).join(',')}${lastDate ? `;UNTIL=${utcTimestamp(easternDateTimeToUtc(lastDate, meeting.start_time))}` : ''}`,
        `SUMMARY:${escapeIcs(`${section.subject} ${section.course_number}: ${title}`)}`,
        `DESCRIPTION:${escapeIcs(`${section.component} section ${(section.alternative_section_numbers ?? [section.section_number]).join(' or ')}; CRN ${(section.alternative_crns ?? [section.crn]).join(' or ')}`)}`,
        'END:VEVENT',
      )
    }
  }
  return `${lines.concat('END:VCALENDAR').join('\r\n')}\r\n`
}

export function downloadOutlookCalendar(schedule: Schedule, titles: Map<string, string>): void {
  download(new Blob([scheduleToIcs(schedule, titles)], { type: 'text/calendar;charset=utf-8' }), 'drexel-schedule.ics')
}

async function captureSchedule(element: HTMLElement): Promise<string> {
  const { toPng } = await import('html-to-image')
  const backgroundColor = getComputedStyle(element).backgroundColor
  return toPng(element, {
    backgroundColor,
    cacheBust: true,
    filter: (node) => !(node instanceof HTMLElement) || node.dataset.exportExclude !== 'true',
    pixelRatio: 2,
  })
}

export async function downloadScheduleImage(element: HTMLElement): Promise<void> {
  const dataUrl = await captureSchedule(element)
  const response = await fetch(dataUrl)
  download(await response.blob(), 'drexel-schedule.png')
}

export async function downloadSchedulePdf(element: HTMLElement): Promise<void> {
  const { jsPDF } = await import('jspdf')
  const dataUrl = await captureSchedule(element)
  const image = new Image()
  image.src = dataUrl
  await image.decode()
  const pdf = new jsPDF({ unit: 'px', format: [image.width, image.height], orientation: image.width >= image.height ? 'landscape' : 'portrait', hotfixes: ['px_scaling'] })
  pdf.addImage(dataUrl, 'PNG', 0, 0, image.width, image.height)
  pdf.save('drexel-schedule.pdf')
}
