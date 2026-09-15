import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'
import { FeedbackForm } from './FeedbackForm'

vi.mock('./api', () => ({ api: { feedback: vi.fn() } }))

beforeEach(() => {
  vi.mocked(api.feedback).mockReset()
})

describe('FeedbackForm', () => {
  it('validates required fields before submitting', async () => {
    const user = userEvent.setup()
    render(<FeedbackForm />)

    await user.click(screen.getByRole('button', { name: 'Submit Feedback' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Please select at least one feedback type.')
    expect(api.feedback).not.toHaveBeenCalled()
  })

  it('submits multiple types, disables the button while pending, and clears on success', async () => {
    let resolveFeedback!: (value: Awaited<ReturnType<typeof api.feedback>>) => void
    vi.mocked(api.feedback).mockReturnValue(new Promise((resolve) => { resolveFeedback = resolve }))
    const user = userEvent.setup()
    render(<FeedbackForm />)

    await user.type(screen.getByLabelText(/Name/), 'Andrew')
    await user.type(screen.getByLabelText(/Email/), 'andrew@example.com')
    await user.click(screen.getByLabelText('Bug Report'))
    await user.click(screen.getByLabelText('Usability Feedback'))
    await user.type(screen.getByLabelText(/Message/), 'The calendar disappears.')
    await user.click(screen.getByRole('button', { name: 'Submit Feedback' }))

    expect(api.feedback).toHaveBeenCalledWith({ name: 'Andrew', email: 'andrew@example.com', type: ['Bug Report', 'Usability Feedback'], message: 'The calendar disappears.' })
    expect(screen.getByRole('button', { name: 'Submitting…' })).toBeDisabled()
    resolveFeedback({ success: true, message: 'Feedback submitted successfully.' })

    expect(await screen.findByRole('status')).toHaveTextContent('Thank you! Your feedback has been submitted.')
    expect(screen.getByLabelText(/Name/)).toHaveValue('')
    expect(screen.getByLabelText('Bug Report')).not.toBeChecked()
  })

  it('keeps entered values after a failed submission', async () => {
    vi.mocked(api.feedback).mockRejectedValue(new Error('Unable to submit feedback right now. Please try again later.'))
    const user = userEvent.setup()
    render(<FeedbackForm />)

    await user.click(screen.getByLabelText('Feature Suggestion'))
    await user.type(screen.getByLabelText(/Message/), 'Please add saved schedules.')
    await user.click(screen.getByRole('button', { name: 'Submit Feedback' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to submit feedback right now. Please try again later.')
    expect(screen.getByLabelText(/Message/)).toHaveValue('Please add saved schedules.')
    expect(screen.getByLabelText('Feature Suggestion')).toBeChecked()
  })
})
