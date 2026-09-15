const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export interface Term {
  id: number
  source_code: string
  name: string
  active: boolean
  latest_successful_import_at: string | null
}

export interface Course {
  id: number
  subject: string
  number: string
  title: string
  minimum_credits: string | null
  maximum_credits: string | null
  schedulable_section_count: number
  component_types: string[]
  delivery_modes?: Array<'online' | 'face_to_face'>
  has_saturday_sections: boolean
}

export interface Meeting {
  days: number[]
  start_time: string | null
  end_time: string | null
  start_date: string | null
  end_date: string | null
  meeting_type: string
  is_asynchronous?: boolean
  is_arranged?: boolean
}

export interface Section {
  id: number
  subject: string
  course_number: string
  crn: string
  section_number: string
  component: string
  instructors: string[]
  meetings: Meeting[]
  campus: string | null
  instructional_method: string | null
  maximum_enrollment: number | null
  alternative_section_numbers?: string[]
  alternative_crns?: string[]
}

export interface Metrics {
  campus_days: number
  total_gap_minutes: number
  earliest_start: string | null
  latest_end: string | null
  total_meeting_minutes: number
}

export interface Schedule {
  sections: Section[]
  metrics: Metrics
}

export interface GenerateResponse {
  schedules: Schedule[]
  total_valid_considered: number
  truncated: boolean
  no_results: { code: string; message: string } | null
  compatibility_limitation: string | null
}

export interface Freshness {
  has_successful_import: boolean
  latest_successful_import_at: string | null
  timezone: string
  term_updates: Record<string, string>
}

export type FeedbackType = 'Bug Report' | 'Feature Suggestion' | 'Usability Feedback' | 'Other'

export interface FeedbackRequest {
  name: string
  email: string
  type: FeedbackType[]
  message: string
}

export interface FeedbackResponse {
  success: boolean
  message: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`
    try {
      const body = (await response.json()) as { detail?: unknown }
      const detail = formatErrorDetail(body.detail)
      if (detail) message = detail
    } catch {
      // Preserve the useful status message when the response is not JSON.
    }
    throw new Error(message)
  }
  return (await response.json()) as T
}

export function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== 'object') return []
      const error = item as { loc?: unknown; msg?: unknown }
      if (typeof error.msg !== 'string') return []
      const location = Array.isArray(error.loc) ? error.loc.filter((part) => part !== 'body').join('.') : ''
      return [location ? `${location}: ${error.msg}` : error.msg]
    })
    return messages.length ? messages.join(' ') : null
  }
  if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') return detail.message
  return null
}

export const api = {
  freshness: () => request<Freshness>('/api/v1/data-freshness'),
  terms: () => request<Term[]>('/api/v1/terms'),
  courses: (termId: number, search: string, signal?: AbortSignal) =>
    request<{ items: Course[]; total: number }>(
      `/api/v1/terms/${termId}/courses?search=${encodeURIComponent(search)}&page_size=100`,
      { signal },
    ),
  generate: (termId: number, courseIds: number[], deliveryPreferences: Record<number, Array<'online' | 'face_to_face'>>, signal?: AbortSignal) =>
    request<GenerateResponse>('/api/v1/schedules/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal,
      body: JSON.stringify({
        term_id: termId,
        course_ids: courseIds,
        delivery_preferences: deliveryPreferences,
      }),
    }),
  feedback: (payload: FeedbackRequest) =>
    request<FeedbackResponse>('/api/v1/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
}
