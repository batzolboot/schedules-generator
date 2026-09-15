import { useState, type FormEvent } from 'react'

import { api } from './api'

const feedbackTypes = ['Bug Report', 'Feature Suggestion', 'Usability Feedback', 'Other'] as const

export function FeedbackForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [types, setTypes] = useState<Array<typeof feedbackTypes[number]>>([])
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  function toggleType(type: typeof feedbackTypes[number]) {
    setTypes((current) => current.includes(type) ? current.filter((item) => item !== type) : [...current, type])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSuccess(false)
    if (!types.length) {
      setError('Please select at least one feedback type.')
      return
    }
    if (!message.trim()) {
      setError('Please enter a feedback message.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await api.feedback({ name, email, type: types, message })
      setName('')
      setEmail('')
      setTypes([])
      setMessage('')
      setSuccess(true)
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Unable to submit feedback right now. Please try again later.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="panel feedback-panel" aria-labelledby="feedback-heading">
      <p className="eyebrow">Help improve the planner</p>
      <h2 id="feedback-heading">Feedback</h2>
      <p>Tell us what is working, what is not, or what would make planning easier.</p>
      <form onSubmit={submit} noValidate>
        <div className="feedback-field">
          <label htmlFor="feedback-name">Name <span className="optional">(optional)</span></label>
          <input id="feedback-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={100} autoComplete="name" />
        </div>
        <div className="feedback-field">
          <label htmlFor="feedback-email">Email <span className="optional">(optional)</span></label>
          <input id="feedback-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} maxLength={254} autoComplete="email" />
        </div>
        <fieldset className="feedback-types" aria-describedby="feedback-type-help">
          <legend>Feedback Type <span aria-hidden="true">*</span></legend>
          <p id="feedback-type-help">Select one or more options.</p>
          {feedbackTypes.map((type) => <label key={type}><input type="checkbox" checked={types.includes(type)} onChange={() => toggleType(type)} />{type}</label>)}
        </fieldset>
        <div className="feedback-field">
          <label htmlFor="feedback-message">Message <span aria-hidden="true">*</span></label>
          <textarea id="feedback-message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={5000} rows={8} aria-describedby="feedback-message-help" />
          <p id="feedback-message-help">Required. Please do not include private academic or account information.</p>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {success && <p className="success" role="status">Thank you! Your feedback has been submitted.</p>}
        <button className="primary" disabled={submitting} type="submit">{submitting ? 'Submitting…' : 'Submit Feedback'}</button>
      </form>
    </section>
  )
}
