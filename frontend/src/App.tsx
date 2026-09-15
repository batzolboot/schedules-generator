import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { api, type Course, type Freshness, type GenerateResponse, type Term } from './api'
import { FeedbackForm } from './FeedbackForm'
import { ScheduleResults } from './ScheduleResults'

const MAX_SELECTED_COURSES = 8

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

function formatFreshness(freshness: Freshness | null, term: Term | undefined): string {
  const updatedAt = term?.latest_successful_import_at ?? freshness?.latest_successful_import_at
  if (!freshness?.has_successful_import || !updatedAt) {
    return 'Course data has not been imported yet.'
  }
  const formatted = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    dateStyle: 'medium',
  }).format(new Date(updatedAt))
  const termName = term?.name.replace(/(\d{2})-(\d{2})$/, '20$1–$2') ?? 'current term'
  return `Last updated on ${formatted} for ${termName}`
}

function credits(course: Course): string | null {
  if (course.minimum_credits === null) return null
  if (course.maximum_credits && course.maximum_credits !== course.minimum_credits) {
    return `${course.minimum_credits}–${course.maximum_credits} credits`
  }
  return `${course.minimum_credits} credits`
}

function compactCreditValue(value: string): string {
  return Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function compactCredits(course: Course): string | null {
  if (course.minimum_credits === null) return null
  const minimum = compactCreditValue(course.minimum_credits)
  const maximum = course.maximum_credits ? compactCreditValue(course.maximum_credits) : minimum
  return minimum === maximum ? `${minimum} credits` : `${minimum}–${maximum} credits`
}

export function App() {
  const [view, setView] = useState<'planner' | 'feedback'>(() => window.location.hash === '#feedback' ? 'feedback' : 'planner')
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = window.localStorage.getItem('schedule-generator-theme')
    return saved === 'light' ? 'light' : 'dark'
  })
  const [freshness, setFreshness] = useState<Freshness | null>(null)
  const [terms, setTerms] = useState<Term[]>([])
  const [termId, setTermId] = useState<number | null>(null)
  const [initialError, setInitialError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [courses, setCourses] = useState<Course[]>([])
  const [courseTotal, setCourseTotal] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Course[]>([])
  const [generating, setGenerating] = useState(false)
  const [generation, setGeneration] = useState<GenerateResponse | null>(null)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [deliveryPreferences, setDeliveryPreferences] = useState<Record<number, Array<'online' | 'face_to_face'>>>({})
  const generationAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    Promise.all([api.freshness(), api.terms()])
      .then(([loadedFreshness, loadedTerms]) => {
        setFreshness(loadedFreshness)
        setTerms(loadedTerms)
        setTermId((current) => current ?? loadedTerms[0]?.id ?? null)
      })
      .catch((error: unknown) => setInitialError(error instanceof Error ? error.message : 'Unable to load application data.'))
  }, [])

  useEffect(() => {
    setCourses([])
    setCourseTotal(0)
    setSearchError(null)
    setSearching(false)
    if (!termId || !query.trim()) return
    const controller = new AbortController()
    setSearching(true)
    const timeout = window.setTimeout(() => {
      api.courses(termId, query.trim(), controller.signal)
        .then((response) => {
          if (controller.signal.aborted) return
          setCourses(response.items)
          setCourseTotal(response.total)
        })
        .catch((error: unknown) => {
          if (!isAbortError(error) && !controller.signal.aborted) {
            setSearchError(error instanceof Error ? error.message : 'Course search failed.')
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false)
        })
    }, 300)
    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [query, termId])

  useEffect(() => () => generationAbortRef.current?.abort(), [])

  const selectedTerm = terms.find((term) => term.id === termId)
  const selectedIds = useMemo(() => new Set(selected.map((course) => course.id)), [selected])
  const selectedCreditTotal = useMemo(() => selected.reduce((total, course) => ({
    minimum: total.minimum + Number(course.minimum_credits ?? 0),
    maximum: total.maximum + Number(course.maximum_credits ?? course.minimum_credits ?? 0),
  }), { minimum: 0, maximum: 0 }), [selected])

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    window.localStorage.setItem('schedule-generator-theme', theme)
  }, [theme])

  useEffect(() => {
    const updateView = () => setView(window.location.hash === '#feedback' ? 'feedback' : 'planner')
    window.addEventListener('hashchange', updateView)
    return () => window.removeEventListener('hashchange', updateView)
  }, [])

  function showView(nextView: 'planner' | 'feedback') {
    window.location.hash = nextView === 'feedback' ? 'feedback' : ''
    setView(nextView)
  }

  function invalidateGeneration() {
    generationAbortRef.current?.abort()
    generationAbortRef.current = null
    setGenerating(false)
    setGeneration(null)
    setGenerationError(null)
  }

  async function generate() {
    if (!termId || selected.length === 0) return
    generationAbortRef.current?.abort()
    const controller = new AbortController()
    generationAbortRef.current = controller
    setGenerating(true)
    setGenerationError(null)
    setGeneration(null)
    try {
      const response = await api.generate(termId, selected.map((course) => course.id), deliveryPreferences, controller.signal)
      if (generationAbortRef.current === controller) setGeneration(response)
    } catch (error) {
      if (!isAbortError(error) && generationAbortRef.current === controller) {
        setGenerationError(error instanceof Error ? error.message : 'Schedule generation failed.')
      }
    } finally {
      if (generationAbortRef.current === controller) {
        generationAbortRef.current = null
        setGenerating(false)
      }
    }
  }

  function addCourse(course: Course) {
    if (selected.length >= MAX_SELECTED_COURSES || selectedIds.has(course.id)) return
    invalidateGeneration()
    setSelected((items) => [...items, course])
    if (course.delivery_modes?.includes('online') && course.delivery_modes.includes('face_to_face')) {
      setDeliveryPreferences((current) => ({ ...current, [course.id]: ['face_to_face', 'online'] }))
    }
  }

  function removeCourse(courseId: number) {
    invalidateGeneration()
    setSelected((items) => items.filter((item) => item.id !== courseId))
    setDeliveryPreferences((current) => {
      const next = { ...current }
      delete next[courseId]
      return next
    })
  }

  function toggleDeliveryMode(courseId: number, mode: 'online' | 'face_to_face') {
    invalidateGeneration()
    setDeliveryPreferences((current) => {
      const existing = current[courseId] ?? ['face_to_face', 'online']
      const next = existing.includes(mode) ? existing.filter((item) => item !== mode) : [...existing, mode]
      return next.length ? { ...current, [courseId]: next } : current
    })
  }

  return (
    <main>
      <header className="hero">
        <div className="theme-setting" role="group" aria-label="Color theme">
          <button type="button" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>Light</button>
          <button type="button" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>Dark</button>
        </div>
        <h1>Drexel Schedule Generator</h1>
        <p>Choose undergraduate courses from one term and compare conflict-free lecture and lab combinations.</p>
        <nav className="site-nav" aria-label="Main navigation">
          <a href="#" aria-current={view === 'planner' ? 'page' : undefined} onClick={() => showView('planner')}>Schedule generator</a>
          <a href="#feedback" aria-current={view === 'feedback' ? 'page' : undefined} onClick={() => showView('feedback')}>Feedback</a>
        </nav>
        <p className="freshness" role="status">{initialError ? `Course-data status unavailable: ${initialError}` : formatFreshness(freshness, selectedTerm)}</p>
        <p className="disclaimer">Planning aid only. Drexel’s official registration system remains authoritative.</p>
      </header>

      {view === 'feedback' ? <FeedbackForm /> : <>

      <div className="planner-layout">
        <div className="planner-main">
      <section className="panel" aria-labelledby="search-heading">
        <h2 id="search-heading">1. Find courses</h2>
        <label htmlFor="course-search">Search by subject, number, or title</label>
        <input id="course-search" value={query} disabled={!termId} onChange={(event) => setQuery(event.target.value)} placeholder="Try CS 172 or Computer Programming II" />
        {searching && <p role="status">Searching courses…</p>}
        {searchError && <p className="error" role="alert">Course search failed: {searchError}</p>}
        {!searching && termId && query.trim() && courses.length === 0 && !searchError && <p>No matching schedulable undergraduate courses.</p>}
        {!searching && courseTotal > courses.length && <p>Showing the first {courses.length} of {courseTotal} matches. Refine your search to see a specific course.</p>}
        <div className="course-grid">
          {courses.map((course) => {
            const alreadySelected = selectedIds.has(course.id)
            const selectionLimitReached = selected.length >= MAX_SELECTED_COURSES && !alreadySelected
            return (
            <article className="course-card" key={course.id}>
              <div><strong>{course.subject} {course.number}</strong><h3>{course.title}</h3></div>
              {credits(course) && <p>{credits(course)}</p>}
              <p>{course.schedulable_section_count} schedulable sections</p>
              <div className="badges">{course.component_types.map((component) => <span key={component}>{component}</span>)}</div>
              <button disabled={alreadySelected || selectionLimitReached} onClick={() => addCourse(course)}>{alreadySelected ? 'Added' : selectionLimitReached ? '8-course maximum' : 'Add course'}</button>
            </article>
            )
          })}
        </div>
      </section>

        </div>

      <section className="panel selection-cart" aria-labelledby="selected-heading">
        <h2 id="selected-heading">2. Selected courses</h2>
        {selected.length === 0 ? <p>No courses selected yet.</p> : (
          <ul className="selected-list">{selected.map((course) => { const modes = course.delivery_modes ?? []; const allowed = deliveryPreferences[course.id] ?? ['face_to_face', 'online']; const courseLabel = `${course.subject} ${course.number}`; const hasBothModes = modes.includes('online') && modes.includes('face_to_face'); return <li key={course.id}><div><span>{courseLabel} — {course.title}</span><div className="cart-course-meta">{hasBothModes ? <fieldset className="delivery-preference" aria-label={`${courseLabel} delivery options`}>{([['face_to_face', 'In person'], ['online', 'Online']] as const).map(([mode, label]) => <label key={mode}><input type="checkbox" aria-label={`${courseLabel} ${label}`} checked={allowed.includes(mode)} onChange={() => toggleDeliveryMode(course.id, mode)} />{label}</label>)}</fieldset> : modes.length === 1 ? <span className="single-delivery-mode">{modes[0] === 'online' ? 'Online' : 'In person'}</span> : null}<span className="cart-course-credits">{compactCredits(course)}</span></div></div><button onClick={() => removeCourse(course.id)}>Remove {courseLabel}</button></li> })}</ul>
        )}
        {selected.length > 0 && <p className="cart-credit-total"><span>Total credits</span><strong>{selectedCreditTotal.minimum === selectedCreditTotal.maximum ? compactCreditValue(String(selectedCreditTotal.minimum)) : `${compactCreditValue(String(selectedCreditTotal.minimum))}–${compactCreditValue(String(selectedCreditTotal.maximum))}`}</strong></p>}
        <button className="primary" disabled={!termId || selected.length === 0 || generating} onClick={generate}>{generating ? 'Generating…' : 'Generate schedules'}</button>
        {generationError && <p className="error" role="alert">Unable to generate schedules: {generationError}</p>}
        {generation?.no_results && <div className="notice" role="status"><strong>No schedules found.</strong><p>{generation.no_results.message}</p></div>}
      </section>
      </div>

      {generation && generation.schedules.length > 0 && <ScheduleResults generation={generation} selectedCourses={selected} />}
      </>}
    </main>
  )
}
