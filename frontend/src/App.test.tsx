import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, type Course } from './api'
import { App } from './App'

vi.mock('./api', () => ({
  api: {
    freshness: vi.fn(),
    terms: vi.fn(),
    courses: vi.fn(),
    generate: vi.fn(),
    feedback: vi.fn(),
  },
}))

const term = { id: 1, source_code: '202545', name: 'Summer Quarter 25-26', active: true, latest_successful_import_at: '2026-08-02T20:00:00Z' }
const course: Course = { id: 10, subject: 'CS', number: '172', title: 'Computer Programming II', minimum_credits: '3.00', maximum_credits: '3.00', schedulable_section_count: 2, component_types: ['lecture', 'lab'], delivery_modes: ['face_to_face'], has_saturday_sections: false }
const section = (id: number, component: string, day: number) => ({ id, subject: 'CS', course_number: '172', crn: String(40000 + id), section_number: String(id), component, instructors: [], campus: 'University City', instructional_method: 'Face-To-Face', maximum_enrollment: null, meetings: [{ days: [day], start_time: '09:00:00', end_time: '10:00:00', start_date: '2026-06-22', end_date: '2026-08-29', meeting_type: 'class', is_asynchronous: false, is_arranged: false }] })

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.mocked(api.freshness).mockResolvedValue({ has_successful_import: true, latest_successful_import_at: '2026-08-02T20:00:00Z', timezone: 'America/New_York', term_updates: { '202545': '2026-08-02T20:00:00Z' } })
  vi.mocked(api.terms).mockResolvedValue([term])
  vi.mocked(api.courses).mockResolvedValue({ items: [course], total: 1 })
  vi.mocked(api.generate).mockResolvedValue({ schedules: [{ sections: [section(1, 'lecture', 1), section(2, 'lab', 3)], metrics: { campus_days: 2, total_gap_minutes: 0, earliest_start: '09:00:00', latest_end: '10:00:00', total_meeting_minutes: 120 } }], total_valid_considered: 1, truncated: false, no_results: null, compatibility_limitation: 'Compatibility is not authoritative.' })
})

async function selectAndSearch(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText(/Last updated on Aug 2, 2026/)
  await user.type(screen.getByLabelText('Search by subject, number, or title'), 'CS 172')
  await screen.findByText('Computer Programming II')
}

describe('App', () => {
  it('defaults to dark mode and allows an explicit light theme', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    expect(window.localStorage.getItem('schedule-generator-theme')).toBe('light')
  })

  it('shows the automatically selected term and its latest update date', async () => {
    render(<App />)
    expect(await screen.findByText(/Last updated on Aug 2, 2026/)).toHaveTextContent('Last updated on Aug 2, 2026 for Summer Quarter 2025–26')
    expect(screen.queryByLabelText('Academic term')).not.toBeInTheDocument()
    expect(screen.queryByText('Drexel schedules planner')).not.toBeInTheDocument()
  })

  it('uses the current term and searches courses with a debounce', async () => {
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    expect(api.courses).toHaveBeenCalledWith(1, 'CS 172', expect.any(AbortSignal))
    expect(screen.getByText('lecture')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Try CS 172 or Computer Programming II')).toBeInTheDocument()
  })

  it('adds and removes a course', async () => {
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    const cart = screen.getByRole('heading', { name: '2. Selected courses' }).closest('section')!
    expect(within(cart).getByText('In person')).toBeInTheDocument()
    expect(within(cart).getByText('3 credits')).toBeInTheDocument()
    expect(within(cart).getByText('Total credits').nextElementSibling).toHaveTextContent('3')
    expect(screen.queryByText(/Active term:/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove CS 172' }))
    expect(screen.getByText('No courses selected yet.')).toBeInTheDocument()
  })

  it('does not crash when an older course response omits delivery modes', async () => {
    vi.mocked(api.courses).mockResolvedValue({ items: [{ ...course, delivery_modes: undefined }], total: 1 })
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))

    expect(screen.getByText(/CS 172 — Computer Programming II/)).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Delivery preference' })).not.toBeInTheDocument()
  })

  it('shows a plain Online label for an online-only course', async () => {
    vi.mocked(api.courses).mockResolvedValue({ items: [{ ...course, subject: 'PSCI', number: '100', title: 'Introduction to Political Science', delivery_modes: ['online'] }], total: 1 })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText(/Last updated on Aug 2, 2026/)
    await user.type(screen.getByLabelText('Search by subject, number, or title'), 'PSCI 100')
    await screen.findByText('Introduction to Political Science')
    await user.click(screen.getByRole('button', { name: 'Add course' }))

    expect(screen.getByText('Online')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: /PSCI 100/ })).not.toBeInTheDocument()
  })

  it('disables generation until a course is selected', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByRole('button', { name: 'Generate schedules' })).toBeDisabled()
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    expect(screen.getByRole('button', { name: 'Generate schedules' })).toBeEnabled()
  })

  it('offers delivery preferences only when a course has both modes', async () => {
    vi.mocked(api.courses).mockResolvedValue({ items: [{ ...course, delivery_modes: ['face_to_face', 'online'] }], total: 1 })
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))

    const online = screen.getByRole('checkbox', { name: 'CS 172 Online' })
    expect(screen.getByRole('checkbox', { name: 'CS 172 In person' })).toBeChecked()
    expect(online).toBeChecked()
    await user.click(online)
    await user.click(screen.getByRole('button', { name: 'Generate schedules' }))

    expect(api.generate).toHaveBeenCalledWith(1, [10], { 10: ['face_to_face'] }, expect.any(AbortSignal))
  })

  it('keeps delivery preferences independent for two courses', async () => {
    const info: Course = { ...course, id: 11, subject: 'INFO', number: '101', title: 'Introduction to Computing and Security Technology', delivery_modes: ['face_to_face', 'online'] }
    vi.mocked(api.courses).mockResolvedValue({ items: [{ ...course, delivery_modes: ['face_to_face', 'online'] }, info], total: 2 })
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    for (const button of screen.getAllByRole('button', { name: 'Add course' })) await user.click(button)

    await user.click(screen.getByRole('checkbox', { name: 'CS 172 Online' }))

    expect(screen.getByRole('checkbox', { name: 'CS 172 Online' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'INFO 101 Online' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'INFO 101 In person' })).toBeChecked()
  })

  it('renders a successful weekly schedule and metrics', async () => {
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    await user.click(screen.getByRole('button', { name: 'Generate schedules' }))
    await user.click(await screen.findByRole('button', { name: 'View full schedule' }))
    expect(await screen.findByRole('heading', { name: 'Your weekly timetable' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CS 172, lecture section 1, Monday/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CS 172, lab section 2, Wednesday/ })).toBeInTheDocument()
    expect(screen.queryByText('Compatibility is not authoritative.')).not.toBeInTheDocument()
    expect(screen.getByText('Campus days').nextElementSibling).toHaveTextContent('2')
  })

  it('renders a useful no-results state', async () => {
    vi.mocked(api.generate).mockResolvedValue({ schedules: [], total_valid_considered: 0, truncated: false, no_results: { code: 'no_conflict_free_schedule', message: 'Every combination overlaps.' }, compatibility_limitation: null })
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    await user.click(screen.getByRole('button', { name: 'Generate schedules' }))
    expect(await screen.findByText('Every combination overlaps.')).toBeInTheDocument()
  })

  it('clears generated schedules when the cart changes', async () => {
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    await user.click(screen.getByRole('button', { name: 'Generate schedules' }))
    expect(await screen.findByRole('heading', { name: 'Compare your options' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove CS 172' }))

    expect(screen.queryByRole('heading', { name: 'Compare your options' })).not.toBeInTheDocument()
    expect(screen.getByText('No courses selected yet.')).toBeInTheDocument()
  })

  it('ignores a generation response that finishes after the cart changes', async () => {
    let resolveGeneration!: (value: Awaited<ReturnType<typeof api.generate>>) => void
    const pendingGeneration = new Promise<Awaited<ReturnType<typeof api.generate>>>((resolve) => {
      resolveGeneration = resolve
    })
    vi.mocked(api.generate).mockReturnValue(pendingGeneration)
    const user = userEvent.setup()
    render(<App />)
    await selectAndSearch(user)
    await user.click(screen.getByRole('button', { name: 'Add course' }))
    await user.click(screen.getByRole('button', { name: 'Generate schedules' }))
    await user.click(screen.getByRole('button', { name: 'Remove CS 172' }))

    resolveGeneration({ schedules: [{ sections: [section(1, 'lecture', 1)], metrics: { campus_days: 1, total_gap_minutes: 0, earliest_start: '09:00:00', latest_end: '10:00:00', total_meeting_minutes: 60 } }], total_valid_considered: 1, truncated: false, no_results: null, compatibility_limitation: null })

    expect(await screen.findByText('No courses selected yet.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Compare your options' })).not.toBeInTheDocument()
  })

  it('enforces the eight-course selection limit before generation', async () => {
    const courses = Array.from({ length: 9 }, (_, index): Course => ({
      ...course,
      id: index + 1,
      number: String(171 + index),
      title: `Course ${index + 1}`,
    }))
    vi.mocked(api.courses).mockResolvedValue({ items: courses, total: courses.length })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText(/Last updated on Aug 2, 2026/)
    await user.type(screen.getByLabelText('Search by subject, number, or title'), 'CS 172')
    await screen.findByText('Course 1')

    for (let index = 0; index < 8; index += 1) {
      await user.click(screen.getAllByRole('button', { name: 'Add course' })[0])
    }

    expect(screen.getByRole('button', { name: '8-course maximum' })).toBeDisabled()
    expect(screen.getAllByRole('button', { name: /^Remove CS/ })).toHaveLength(8)
  })

  it('shows an API error state', async () => {
    vi.mocked(api.freshness).mockRejectedValue(new Error('Backend unavailable'))
    render(<App />)
    expect(await screen.findByText(/Course-data status unavailable: Backend unavailable/)).toBeInTheDocument()
  })
})
