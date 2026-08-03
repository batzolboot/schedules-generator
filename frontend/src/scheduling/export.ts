import type { Schedule } from '../api'

const DAY_CODES = ['', 'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']

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

function firstMeetingDate(startDate: string, day: number): string {
  const date = new Date(`${startDate}T12:00:00`)
  const jsDay = day === 7 ? 0 : day
  date.setDate(date.getDate() + (jsDay - date.getDay() + 7) % 7)
  return date.toISOString().slice(0, 10)
}

function escapeIcs(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll(';', '\\;').replaceAll(',', '\\,').replaceAll('\n', '\\n')
}

export function scheduleToIcs(schedule: Schedule, titles: Map<string, string>): string {
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Drexel Schedule Generator//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH']
  for (const section of schedule.sections) {
    for (const [meetingIndex, meeting] of section.meetings.filter((item) => item.meeting_type !== 'final_exam').entries()) {
      if (!meeting.start_date || !meeting.start_time || !meeting.end_time || meeting.days.length === 0) continue
      const firstDate = firstMeetingDate(meeting.start_date, meeting.days[0])
      const title = titles.get(`${section.subject}:${section.course_number}`) ?? 'Course'
      lines.push(
        'BEGIN:VEVENT',
        `UID:${section.id}-${meetingIndex}-${compactDate(firstDate)}@drexel-schedule-generator`,
        `DTSTART:${compactDate(firstDate)}T${compactTime(meeting.start_time)}`,
        `DTEND:${compactDate(firstDate)}T${compactTime(meeting.end_time)}`,
        `RRULE:FREQ=WEEKLY;BYDAY=${meeting.days.map((day) => DAY_CODES[day]).join(',')}${meeting.end_date ? `;UNTIL=${compactDate(meeting.end_date)}T235959` : ''}`,
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
