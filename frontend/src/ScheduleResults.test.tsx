import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Course, GenerateResponse, Schedule } from './api'
import { ScheduleResults } from './ScheduleResults'
import { meeting, schedule, section } from './scheduling/testFixtures'

const selectedCourses: Course[] = [{ id: 10, subject: 'CS', number: '380', title: 'Artificial Intelligence', minimum_credits: '3.00', maximum_credits: '3.00', schedulable_section_count: 5, component_types: ['lecture', 'lab', 'recitation'], delivery_modes: ['face_to_face'], has_saturday_sections: true }]

function withMetrics(sections: Schedule['sections']): Schedule {
  const recurring = sections.flatMap((item) => item.meetings).filter((item) => item.meeting_type !== 'final_exam')
  return { sections, metrics: { campus_days: new Set(recurring.flatMap((item) => item.days)).size, total_gap_minutes: 15, earliest_start: recurring.map((item) => item.start_time).sort()[0], latest_end: recurring.map((item) => item.end_time).sort().at(-1)!, total_meeting_minutes: 120 } }
}

const monday = schedule(1, [meeting(1, '08:00:00', '09:20:00')])
const tuesday = withMetrics([
  section(2, [meeting(2, '10:00:00', '10:50:00'), meeting(4, '13:15:00', '14:50:00')]),
  section(3, [meeting(3, '15:00:00', '16:50:00')], { component: 'lab', section_number: '061', instructors: [], instructional_method: null }),
  section(4, [meeting(5, '17:00:00', '17:50:00')], { component: 'recitation', section_number: 'R01' }),
])
const weekend = schedule(5, [meeting(6, '11:00:00', '12:00:00'), meeting(7, '09:00:00', '11:00:00', { meeting_type: 'final_exam' })])

const generation: GenerateResponse = { schedules: [monday, tuesday, weekend], total_valid_considered: 3, truncated: false, no_results: null, compatibility_limitation: 'Verify component compatibility.' }

describe('ScheduleResults', () => {
  async function openFirstSchedule(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getAllByRole('button', { name: 'View full schedule' })[0])
  }

  it('renders a gallery and opens day columns, recurring rows, and components', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={{ ...generation, schedules: [tuesday] }} selectedCourses={selectedCourses} />)
    expect(screen.getByRole('heading', { name: 'Compare your options' })).toBeInTheDocument()
    expect(screen.queryByText('1 valid combinations generated.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '20', pressed: true })).toBeInTheDocument()
    expect(within(screen.getByRole('article')).queryByText('Days')).not.toBeInTheDocument()
    expect(within(screen.getByLabelText('Compact weekly timetable')).queryByText('S')).not.toBeInTheDocument()
    for (const size of ['50', '100', 'All']) expect(screen.getByRole('button', { name: size })).toBeInTheDocument()
    await openFirstSchedule(user)
    expect(screen.getByLabelText('Weekly timetable')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Tuesday' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /CS 380, lecture section 001/ })).toHaveLength(2)
    expect(screen.getByRole('button', { name: /lab section 061/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /recitation section R01/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Sunday, 9:00 AM/ })).not.toBeInTheDocument()
    expect(screen.getByText('Save schedule')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Image' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'PDF' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Outlook calendar' })).toBeInTheDocument()
  })

  it('positions meetings by start time and duration', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={{ ...generation, schedules: [tuesday] }} selectedCourses={selectedCourses} />)
    await openFirstSchedule(user)
    const morning = screen.getByRole('button', { name: /Tuesday, 10:00 AM to 10:50 AM/ })
    const afternoon = screen.getByRole('button', { name: /Thursday, 1:15 PM to 2:50 PM/ })
    expect(Number.parseFloat(morning.style.top)).toBeLessThan(Number.parseFloat(afternoon.style.top))
    expect(Number.parseFloat(morning.style.height)).toBeLessThan(Number.parseFloat(afternoon.style.height))
  })

  it('filters weekdays immediately and reset restores all schedules', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    await user.click(screen.getByRole('checkbox', { name: 'Monday' }))
    expect(screen.getByText('2 of 3 generated schedules match your filters')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reset filters' }))
    expect(screen.getByText('3 of 3 generated schedules match your filters')).toBeInTheDocument()
  })

  it('shows Monday through Saturday controls, omits Sunday, and has no day shortcut buttons', () => {
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    expect(screen.getByText('3 of 3 generated schedules match your filters')).toBeInTheDocument()
    for (const day of ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']) expect(screen.getByRole('checkbox', { name: day })).toBeChecked()
    expect(screen.queryByRole('checkbox', { name: 'Sunday' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Select Monday–Saturday' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Clear all' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Weekdays only' })).not.toBeInTheDocument()
  })

  it('hides Saturday and excludes Saturday schedules when selected courses have no Saturday sections', () => {
    const weekdayCourses = selectedCourses.map((course) => ({ ...course, has_saturday_sections: false }))
    render(<ScheduleResults generation={generation} selectedCourses={weekdayCourses} />)

    for (const day of ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']) {
      expect(screen.getByRole('checkbox', { name: day })).toBeChecked()
    }
    expect(screen.queryByRole('checkbox', { name: 'Saturday' })).not.toBeInTheDocument()
    expect(screen.getByText('2 of 3 generated schedules match your filters')).toBeInTheDocument()
    expect(screen.getByText(/Monday–Friday/)).toBeInTheDocument()
  })

  it('defaults to 7:15 AM–10:30 PM and applies inclusive slider boundaries', () => {
    render(<ScheduleResults generation={{ ...generation, schedules: [monday, tuesday] }} selectedCourses={selectedCourses} />)
    const start = screen.getByRole('slider', { name: 'Earliest allowed class start time' })
    const end = screen.getByRole('slider', { name: 'Latest allowed class end time' })
    expect(start).toHaveValue('435')
    expect(end).toHaveValue('1350')
    expect(start).toHaveAttribute('aria-valuetext', '7:15 AM')
    expect(end).toHaveAttribute('aria-valuetext', '10:30 PM')
    expect(screen.getByText('7:15 AM – 10:30 PM')).toBeInTheDocument()
    expect(screen.queryByText('Allowed class time')).not.toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Allowed class time' })).toBeInTheDocument()
    expect(screen.getByText('Current filters:').closest('p')).toHaveTextContent('Monday–Saturday · Classes between 7:15 AM and 10:30 PM')
    for (const tick of ['9 AM', '11 AM', '1 PM', '3 PM', '5 PM', '7 PM', '9 PM']) expect(screen.getByText(tick)).toBeInTheDocument()
    fireEvent.input(start, { target: { value: '600' } })
    expect(screen.getByText('1 of 2 generated schedules match your filters')).toBeInTheDocument()
    fireEvent.input(end, { target: { value: '1070' } })
    expect(screen.getByText('1 of 2 generated schedules match your filters')).toBeInTheDocument()
    fireEvent.input(end, { target: { value: '1050' } })
    expect(screen.getByText('0 of 2 generated schedules match your filters')).toBeInTheDocument()
  })

  it('prevents handles from crossing and keeps one slider step between them', () => {
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    const start = screen.getByRole('slider', { name: 'Earliest allowed class start time' })
    const end = screen.getByRole('slider', { name: 'Latest allowed class end time' })
    fireEvent.input(start, { target: { value: '1350' } })
    expect(start).toHaveValue('1335')
    fireEvent.input(end, { target: { value: '435' } })
    expect(end).toHaveValue('1350')
    expect(Number((end as HTMLInputElement).value) - Number((start as HTMLInputElement).value)).toBeGreaterThanOrEqual(15)
  })

  it('adjusts both handles by keyboard in 15-minute steps', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    const start = screen.getByRole('slider', { name: 'Earliest allowed class start time' })
    const end = screen.getByRole('slider', { name: 'Latest allowed class end time' })
    start.focus()
    await user.keyboard('{ArrowRight}')
    expect(start).toHaveValue('450')
    expect(start).toHaveAttribute('aria-valuetext', '7:30 AM')
    end.focus()
    await user.keyboard('{ArrowLeft}')
    expect(end).toHaveValue('1335')
    expect(end).toHaveAttribute('aria-valuetext', '10:15 PM')
  })

  it('reset restores every weekday and the default slider range', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    await user.click(screen.getByRole('checkbox', { name: 'Friday' }))
    fireEvent.input(screen.getByRole('slider', { name: 'Earliest allowed class start time' }), { target: { value: '600' } })
    fireEvent.input(screen.getByRole('slider', { name: 'Latest allowed class end time' }), { target: { value: '1080' } })
    await user.click(screen.getAllByRole('button', { name: 'Reset filters' })[0])
    for (const day of ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']) expect(screen.getByRole('checkbox', { name: day })).toBeChecked()
    expect(screen.getByRole('slider', { name: 'Earliest allowed class start time' })).toHaveValue('435')
    expect(screen.getByRole('slider', { name: 'Latest allowed class end time' })).toHaveValue('1350')
  })

  it('navigates the filtered list and resets position when filters change', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    await openFirstSchedule(user)
    await user.click(screen.getByRole('button', { name: 'Next schedule' }))
    expect(screen.getByText('Schedule 2 of 3')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: 'Monday' }))
    expect(screen.getByText('Showing 1–2 of 2')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Compare your options' })).toBeInTheDocument()
  })

  it('reveals details without rendering a location field', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={{ ...generation, schedules: [tuesday] }} selectedCourses={selectedCourses} />)
    await openFirstSchedule(user)
    const block = screen.getByRole('button', { name: /lab section 061/ })
    block.focus()
    expect(block).toHaveFocus()
    await user.click(block)
    expect(screen.getByRole('heading', { name: 'CS 380: Artificial Intelligence' })).toBeInTheDocument()
    expect(screen.getByText('CRN').nextElementSibling).toHaveTextContent('41003')
    expect(screen.getByText('Instructor').nextElementSibling).toHaveTextContent('Not listed')
    expect(screen.getByText('Instructional method').nextElementSibling).toHaveTextContent('Not listed')
    expect(screen.queryByText('Location')).not.toBeInTheDocument()
  })

  it('shows equivalent same-time sections as one timetable option with both section choices', async () => {
    const user = userEvent.setup()
    const lecture = section(20, [meeting(1, '13:00:00', '13:50:00')], { subject: 'PHYS', course_number: '201', section_number: 'A', crn: '10270' })
    const lab066 = section(21, [meeting(2, '11:00:00', '12:50:00')], { subject: 'PHYS', course_number: '201', component: 'lab', section_number: '066', crn: '10284' })
    const lab067 = section(22, [meeting(2, '11:00:00', '12:50:00')], { subject: 'PHYS', course_number: '201', component: 'lab', section_number: '067', crn: '10285' })
    const alternatives = { ...generation, schedules: [withMetrics([lecture, lab066]), withMetrics([lecture, lab067])] }
    const physics: Course[] = [{ ...selectedCourses[0], id: 20, subject: 'PHYS', number: '201', title: 'Fundamentals of Physics I' }]

    render(<ScheduleResults generation={alternatives} selectedCourses={physics} />)

    expect(screen.getByText('1 of 1 generated schedules match your filters')).toBeInTheDocument()
    expect(screen.getByText('2 section combinations were consolidated into 1 distinct timetable option.')).toBeInTheDocument()
    await openFirstSchedule(user)
    const block = screen.getByRole('button', { name: /PHYS 201, lab section 066 or 067/ })
    expect(block).toHaveTextContent('lab 066 or 067')
    await user.click(block)
    expect(screen.getByText('Section').nextElementSibling).toHaveTextContent('066 or 067')
    expect(screen.getByText('CRN').nextElementSibling).toHaveTextContent('10284 or 10285')
  })

  it('uses one color for components of a course and another color for a different course', async () => {
    const user = userEvent.setup()
    const csLecture = section(30, [meeting(1, '09:00:00', '09:50:00')])
    const csLab = section(31, [meeting(2, '09:00:00', '09:50:00')], { component: 'lab', section_number: '061' })
    const mathLecture = section(32, [meeting(3, '09:00:00', '09:50:00')], { subject: 'MATH', course_number: '200' })
    const courses: Course[] = [selectedCourses[0], { ...selectedCourses[0], id: 32, subject: 'MATH', number: '200', title: 'Multivariate Calculus' }]
    render(<ScheduleResults generation={{ ...generation, schedules: [withMetrics([csLecture, csLab, mathLecture])] }} selectedCourses={courses} />)
    await openFirstSchedule(user)

    const csBlocks = screen.getAllByRole('button', { name: /CS 380/ })
    const mathBlock = screen.getByRole('button', { name: /MATH 200/ })
    expect(csBlocks[0].className).toBe(csBlocks[1].className)
    expect(mathBlock.className).not.toBe(csBlocks[0].className)
  })

  it('sorts schedules by gaps in either direction', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    const cards = screen.getAllByRole('article')
    expect(cards[0]).toHaveTextContent('Gaps0 min')
    await user.click(screen.getByRole('button', { name: 'Gap time: lowest to highest' }))
    expect(screen.getAllByRole('article')[0]).toHaveTextContent('Gaps15 min')
  })

  it('shows Saturday in a gallery timetable only when that schedule meets Saturday', () => {
    render(<ScheduleResults generation={{ ...generation, schedules: [weekend] }} selectedCourses={selectedCourses} />)
    expect(within(screen.getByLabelText('Compact weekly timetable')).getByText('S')).toBeInTheDocument()
  })

  it('does not add Sunday to the full timetable for a Saturday schedule', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={{ ...generation, schedules: [weekend] }} selectedCourses={selectedCourses} />)
    await user.click(screen.getByRole('button', { name: 'View full schedule' }))

    const timetable = screen.getByLabelText('Weekly timetable')
    expect(within(timetable).getByText('Saturday')).toBeInTheDocument()
    expect(within(timetable).queryByText('Sunday')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sun' })).not.toBeInTheDocument()
  })

  it('preserves selected comparisons when gap order changes', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    const compare = screen.getAllByRole('checkbox', { name: /Compare schedule/ })
    await user.click(compare[0])
    await user.click(compare[1])

    await user.click(screen.getByRole('button', { name: 'Gap time: lowest to highest' }))

    expect(screen.getByRole('button', { name: 'Compare selected (2)' })).toBeEnabled()
    expect(screen.getAllByRole('checkbox', { name: /Compare schedule/ }).filter((checkbox) => (checkbox as HTMLInputElement).checked)).toHaveLength(2)
  })

  it('clears selected gallery comparisons on request', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={generation} selectedCourses={selectedCourses} />)
    await user.click(screen.getAllByRole('checkbox', { name: /Compare schedule/ })[0])
    expect(screen.getByRole('button', { name: 'Clear selected' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Clear selected' }))

    expect(screen.getByRole('button', { name: 'Compare selected (0)' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Clear selected' })).toBeDisabled()
  })

  it('compares up to six selected gallery schedules', async () => {
    const user = userEvent.setup()
    const manySchedules = Array.from({ length: 7 }, (_, index) => schedule(index + 20, [meeting((index % 6) + 1, `${String(8 + index).padStart(2, '0')}:00:00`, `${String(9 + index).padStart(2, '0')}:00:00`)]))
    render(<ScheduleResults generation={{ ...generation, schedules: manySchedules, total_valid_considered: 7 }} selectedCourses={selectedCourses} />)
    const compare = screen.getAllByRole('checkbox', { name: /Compare schedule/ })
    for (let index = 0; index < 6; index += 1) await user.click(compare[index])
    expect(compare[6]).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Compare selected (6)' }))
    expect(screen.getByRole('heading', { name: 'Schedule comparison' })).toBeInTheDocument()
    expect(screen.getAllByLabelText('Compact weekly timetable')).toHaveLength(6)
  })

  it('exposes mobile day tabs and exploration-limit context', async () => {
    const user = userEvent.setup()
    render(<ScheduleResults generation={{ ...generation, schedules: [tuesday], truncated: true }} selectedCourses={selectedCourses} />)
    await openFirstSchedule(user)
    expect(screen.getByRole('group', { name: 'Schedule day' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tue' })).toHaveAttribute('aria-pressed')
    expect(screen.getByText(/100,000-step exploration guard/)).toBeInTheDocument()
  })

  it('identifies asynchronous classes in the gallery and full schedule', async () => {
    const user = userEvent.setup()
    const onlineMeeting = meeting(1, '09:00:00', '10:00:00', { days: [], start_time: null, end_time: null, is_asynchronous: true })
    const onlineSchedule: Schedule = {
      sections: [section(99, [onlineMeeting], { subject: 'INFO', course_number: '101', crn: '11313', section_number: '900', alternative_section_numbers: ['900', '901', '902', '903'], alternative_crns: ['11313', '10706', '10563', '14325'], instructional_method: 'Online-Asynchronous', campus: 'Online', instructors: ['Andrew W Calhoun'] })],
      metrics: { campus_days: 0, total_gap_minutes: 0, earliest_start: null, latest_end: null, total_meeting_minutes: 0 },
    }
    render(<ScheduleResults generation={{ ...generation, schedules: [onlineSchedule], total_valid_considered: 1 }} selectedCourses={[{ ...selectedCourses[0], subject: 'INFO', number: '101', title: 'Introduction to Computing and Security Technology', delivery_modes: ['online'] }]} />)

    expect(screen.getByText('Online class').nextElementSibling).toHaveTextContent('Yes')
    await user.click(screen.getByRole('button', { name: 'View full schedule' }))
    const onlineSummary = screen.getByRole('heading', { name: 'Online classes in this schedule' }).parentElement
    expect(onlineSummary).toHaveTextContent('INFO 101')
    expect(onlineSummary).toHaveTextContent('section 900 or 901 or 902 or 903')
    expect(onlineSummary).toHaveTextContent('CRN 11313 or 10706 or 10563 or 14325')
    expect(onlineSummary).toHaveTextContent('Asynchronous')
  })
})
