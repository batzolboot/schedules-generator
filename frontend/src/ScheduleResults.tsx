import { useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'

import type { Course, GenerateResponse, Meeting, Schedule, Section } from './api'
import { consolidateEquivalentSchedules, sectionEquivalenceKey, type ConsolidatedSchedule } from './scheduling/consolidate'
import { downloadOutlookCalendar, downloadScheduleImage, downloadSchedulePdf } from './scheduling/export'
import { clampEndMinutes, clampStartMinutes, describeActiveFilters, filterSchedules, filtersAreDefault } from './scheduling/filters'
import { getCourseStyleMap, getMeetingPosition, getTimetableRange, minutesToTime } from './scheduling/timetable'
import { DEFAULT_FILTERS, FILTER_DAYS, TIME_RANGE_MAX, TIME_RANGE_MIN, TIME_STEP_MINUTES, WEEKDAYS, type ScheduleFilters } from './scheduling/types'

export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function displayTime(value: string | null): string {
  if (!value) return 'No timed classes'
  const [hour, minute] = value.split(':').map(Number)
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(2000, 0, 1, hour, minute))
}

interface MeetingEntry { section: Section; meeting: Meeting & { start_time: string; end_time: string }; day: number }

function isTimedMeeting(meeting: Meeting): meeting is Meeting & { start_time: string; end_time: string } {
  return meeting.start_time !== null && meeting.end_time !== null && meeting.days.length > 0
}

function isOnlineSection(section: Section): boolean {
  return section.meetings.some((meeting) => meeting.is_asynchronous)
    || section.instructional_method?.toLowerCase().includes('online') === true
    || section.campus?.toLowerCase().includes('online') === true
}

function alternativeText(alternatives: Section[], field: 'section_number' | 'crn'): string {
  const representative = alternatives[0]
  const preserved = field === 'section_number' ? representative?.alternative_section_numbers : representative?.alternative_crns
  if (preserved?.length) return preserved.join(' or ')
  return alternatives.map((section) => section[field]).join(' or ')
}

function meetingAccessibleName(section: Section, alternatives: Section[], meeting: Meeting, day: number): string {
  return [`${section.subject} ${section.course_number}`, `${section.component} section ${alternativeText(alternatives, 'section_number')}`, DAY_NAMES[day - 1], `${displayTime(meeting.start_time)} to ${displayTime(meeting.end_time)}`, 'Show meeting details'].join(', ')
}

function Timetable({ schedule, courseTitles, courseStyles, alternativesBySectionKey }: { schedule: Schedule; courseTitles: Map<string, string>; courseStyles: Map<string, number>; alternativesBySectionKey: Map<string, Section[]> }) {
  const entries: MeetingEntry[] = schedule.sections.flatMap((section) => section.meetings.filter(isTimedMeeting).filter((meeting) => meeting.meeting_type !== 'final_exam').flatMap((meeting) => meeting.days.map((day) => ({ section, meeting, day }))))
  const displayedDays = entries.some(({ day }) => day === 6) ? [...FILTER_DAYS] : [...WEEKDAYS]
  const firstMeetingDay = displayedDays.find((day) => entries.some((entry) => entry.day === day)) ?? 1
  const [selectedDay, setSelectedDay] = useState(firstMeetingDay)
  const [selectedMeeting, setSelectedMeeting] = useState<MeetingEntry | null>(null)
  const range = getTimetableRange(schedule)
  const selectedAlternatives = selectedMeeting ? alternativesBySectionKey.get(sectionEquivalenceKey(selectedMeeting.section)) ?? [selectedMeeting.section] : []

  useEffect(() => {
    setSelectedDay(firstMeetingDay)
    setSelectedMeeting(null)
  }, [schedule, firstMeetingDay])

  return (
    <div className="timetable-shell">
      <div className="mobile-day-tabs" role="tablist" aria-label="Schedule day">
        {displayedDays.map((day) => <button key={day} type="button" role="tab" aria-selected={selectedDay === day} onClick={() => setSelectedDay(day)}>{DAY_NAMES[day - 1].slice(0, 3)}</button>)}
      </div>
      <div className="timetable" aria-label="Weekly timetable" style={{ '--day-count': displayedDays.length } as CSSProperties}>
        <div className="time-corner" aria-hidden="true">Time</div>
        {displayedDays.map((day) => <div className="day-header" key={day}>{DAY_NAMES[day - 1]}</div>)}
        <div className="time-axis" style={{ height: range.height }} aria-hidden="true">
          {range.labels.slice(0, -1).map((minute) => <span key={minute} style={{ top: (minute - range.startMinutes) * 1.15 }}>{minutesToTime(minute)}</span>)}
        </div>
        {displayedDays.map((day) => (
          <section className={`timetable-day${selectedDay === day ? ' is-selected' : ''}`} style={{ height: range.height }} key={day} aria-label={DAY_NAMES[day - 1]}>
            {range.labels.map((minute) => <span className="grid-line" aria-hidden="true" key={minute} style={{ top: (minute - range.startMinutes) * 1.15 }} />)}
            {entries.filter((entry) => entry.day === day).map((entry, index) => {
              const { section, meeting } = entry
              const position = getMeetingPosition(meeting.start_time, meeting.end_time, range)
              const alternatives = alternativesBySectionKey.get(sectionEquivalenceKey(section)) ?? [section]
              const title = courseTitles.get(`${section.subject}:${section.course_number}`) ?? 'Course'
              return (
                  <button type="button" className={`meeting-block course-style-${courseStyles.get(`${section.subject}:${section.course_number}`) ?? 0}`} style={{ top: position.top, height: position.height, '--meeting-height': `${position.height}px` } as CSSProperties} key={`${section.id}-${meeting.start_time}-${meeting.end_time}-${index}`} aria-label={meetingAccessibleName(section, alternatives, meeting, day)} aria-expanded={selectedMeeting?.section.id === section.id && selectedMeeting.day === day && selectedMeeting.meeting.start_time === meeting.start_time} aria-controls="meeting-details" onClick={() => setSelectedMeeting(entry)}>
                  <strong>{section.subject} {section.course_number}</strong>
                  <span className="meeting-extra meeting-title">{title}</span>
                  <span>{section.component} {alternativeText(alternatives, 'section_number')}</span>
                  <span className="meeting-extra">CRN {alternativeText(alternatives, 'crn')}</span>
                  <span className="meeting-time">{displayTime(meeting.start_time)}–{displayTime(meeting.end_time)}</span>
                  <span className="meeting-instructor meeting-extra">{section.instructors.join(', ') || 'Not listed'}</span>
                  <span className="meeting-extra">{section.instructional_method ?? 'Not listed'}</span>
                </button>
              )
            })}
          </section>
        ))}
      </div>
      <p className="timetable-help">Select any class block for full section details.</p>
      {selectedMeeting && (
        <section id="meeting-details" className="meeting-details" aria-labelledby="meeting-details-heading">
          <div><p className="eyebrow">Meeting details</p><h3 id="meeting-details-heading">{selectedMeeting.section.subject} {selectedMeeting.section.course_number}: {courseTitles.get(`${selectedMeeting.section.subject}:${selectedMeeting.section.course_number}`) ?? 'Course meeting'}</h3></div>
          <button type="button" aria-label="Close meeting details" onClick={() => setSelectedMeeting(null)}>Close</button>
          <dl>
            <div><dt>Component</dt><dd>{selectedMeeting.section.component}</dd></div><div><dt>Section</dt><dd>{alternativeText(selectedAlternatives, 'section_number')}</dd></div><div><dt>CRN</dt><dd>{alternativeText(selectedAlternatives, 'crn')}</dd></div>
            <div><dt>When</dt><dd>{DAY_NAMES[selectedMeeting.day - 1]}, {displayTime(selectedMeeting.meeting.start_time)}–{displayTime(selectedMeeting.meeting.end_time)}</dd></div>
            <div><dt>Instructor</dt><dd>{selectedMeeting.section.instructors.join(', ') || 'Not listed'}</dd></div><div><dt>Instructional method</dt><dd>{selectedMeeting.section.instructional_method ?? 'Not listed'}</dd></div>
          </dl>
        </section>
      )}
    </div>
  )
}

function MiniTimetable({ schedule, courseStyles, detailed = false, showSaturday }: { schedule: Schedule; courseStyles: Map<string, number>; detailed?: boolean; showSaturday?: boolean }) {
  const meetings = schedule.sections.flatMap((section) => section.meetings.filter(isTimedMeeting).filter((meeting) => meeting.meeting_type !== 'final_exam').flatMap((meeting) => meeting.days.filter((day) => day <= 6).map((day) => ({ section, meeting, day }))))
  const displayedDays = (showSaturday ?? meetings.some(({ day }) => day === 6)) ? FILTER_DAYS : WEEKDAYS
  const start = Math.min(...meetings.map(({ meeting }) => Number(meeting.start_time.slice(0, 2)) * 60 + Number(meeting.start_time.slice(3, 5))))
  const end = Math.max(...meetings.map(({ meeting }) => Number(meeting.end_time.slice(0, 2)) * 60 + Number(meeting.end_time.slice(3, 5))))
  const span = Math.max(60, end - start)
  return <div className={`mini-timetable${detailed ? ' is-detailed' : ''}`} aria-label="Compact weekly timetable" style={{ '--mini-day-count': displayedDays.length } as CSSProperties}>{displayedDays.map((day) => <div className="mini-day" key={day}><span>{detailed ? DAY_NAMES[day - 1].slice(0, 3) : DAY_NAMES[day - 1].slice(0, 1)}</span>{meetings.filter((entry) => entry.day === day).map(({ section, meeting }, index) => { const meetingStart = Number(meeting.start_time.slice(0, 2)) * 60 + Number(meeting.start_time.slice(3, 5)); const meetingEnd = Number(meeting.end_time.slice(0, 2)) * 60 + Number(meeting.end_time.slice(3, 5)); return <i className={`course-style-${courseStyles.get(`${section.subject}:${section.course_number}`) ?? 0}`} key={`${section.id}-${index}`} title={`${section.subject} ${section.course_number}, ${displayTime(meeting.start_time)}–${displayTime(meeting.end_time)}`} style={{ top: `${8 + ((meetingStart - start) / span) * 82}%`, height: `${Math.max(detailed ? 10 : 7, ((meetingEnd - meetingStart) / span) * 82)}%` }}>{detailed && <><b>{section.subject} {section.course_number}</b><small>{section.component}</small><small>{displayTime(meeting.start_time)}</small></>}</i> })}</div>)}</div>
}

function ScheduleGallery({ groups, courseStyles, selected, gapOrder, onToggle, onOpen, onToggleGap }: { groups: ConsolidatedSchedule[]; courseStyles: Map<string, number>; selected: number[]; gapOrder: 'ascending' | 'descending'; onToggle: (index: number) => void; onOpen: (index: number) => void; onToggleGap: () => void }) {
  const [page, setPage] = useState(0)
  const [pageSizeChoice, setPageSizeChoice] = useState<number | 'all'>(20)
  const pageSize = pageSizeChoice === 'all' ? Math.max(1, groups.length) : pageSizeChoice
  const pageCount = Math.ceil(groups.length / pageSize)
  useEffect(() => setPage(0), [groups, pageSizeChoice])
  const pageGroups = groups.slice(page * pageSize, (page + 1) * pageSize)
  const choosePageSize = (choice: number | 'all') => { setPageSizeChoice(choice); setPage(0) }
  return <section className="schedule-gallery" aria-labelledby="gallery-heading"><div className="gallery-heading"><p className="eyebrow" id="gallery-heading">Schedule gallery</p><div><button type="button" onClick={onToggleGap}>Gap time: {gapOrder === 'ascending' ? 'lowest to highest' : 'highest to lowest'}</button><span>Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, groups.length)} of {groups.length}</span></div></div><div className="page-size-controls" aria-label="Schedules per page"><span>Show</span>{([20, 50, 100, 'all'] as const).map((choice) => <button type="button" aria-pressed={pageSizeChoice === choice} key={choice} onClick={() => choosePageSize(choice)}>{choice === 'all' ? 'All' : choice}</button>)}</div><div className="schedule-card-grid">{pageGroups.map(({ schedule }, offset) => { const index = page * pageSize + offset; const hasOnline = schedule.sections.some(isOnlineSection); return <article className="schedule-card" key={index}><div className="schedule-card-heading"><strong>Schedule {index + 1}</strong><label><input type="checkbox" checked={selected.includes(index)} disabled={!selected.includes(index) && selected.length >= 6} onChange={() => onToggle(index)} /> Compare</label></div><MiniTimetable schedule={schedule} courseStyles={courseStyles} /><dl><div><dt>Gaps</dt><dd>{schedule.metrics.total_gap_minutes} min</dd></div><div><dt>Online class</dt><dd>{hasOnline ? 'Yes' : 'No'}</dd></div><div><dt>Starts</dt><dd>{displayTime(schedule.metrics.earliest_start)}</dd></div><div><dt>Ends</dt><dd>{displayTime(schedule.metrics.latest_end)}</dd></div></dl><button type="button" onClick={() => onOpen(index)}>View full schedule</button></article> })}</div>{pageCount > 1 && <div className="gallery-pagination"><button type="button" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Previous page</button><span>Page {page + 1} of {pageCount}</span><button type="button" disabled={page === pageCount - 1} onClick={() => setPage((value) => value + 1)}>Next page</button></div>}</section>
}

function FilterPanel({ filters, filterDays, onChange, onReset }: { filters: ScheduleFilters; filterDays: readonly number[]; onChange: (filters: ScheduleFilters) => void; onReset: () => void }) {
  const toggleDay = (day: number) => onChange({ ...filters, allowedDays: filters.allowedDays.includes(day) ? filters.allowedDays.filter((value) => value !== day) : [...filters.allowedDays, day].sort((a, b) => a - b) })
  const adjustRangeWithKeyboard = (event: KeyboardEvent<HTMLInputElement>, handle: 'start' | 'end') => {
    const direction = event.key === 'ArrowRight' || event.key === 'ArrowUp' ? 1 : event.key === 'ArrowLeft' || event.key === 'ArrowDown' ? -1 : 0
    if (!direction && event.key !== 'Home' && event.key !== 'End') return
    event.preventDefault()
    if (handle === 'start') {
      const requested = event.key === 'Home' ? TIME_RANGE_MIN : event.key === 'End' ? filters.latestEndMinutes : filters.earliestStartMinutes + direction * TIME_STEP_MINUTES
      onChange({ ...filters, earliestStartMinutes: Math.max(TIME_RANGE_MIN, clampStartMinutes(requested, filters.latestEndMinutes)) })
    } else {
      const requested = event.key === 'Home' ? filters.earliestStartMinutes : event.key === 'End' ? TIME_RANGE_MAX : filters.latestEndMinutes + direction * TIME_STEP_MINUTES
      onChange({ ...filters, latestEndMinutes: Math.min(TIME_RANGE_MAX, clampEndMinutes(requested, filters.earliestStartMinutes)) })
    }
  }
  const startPercent = ((filters.earliestStartMinutes - TIME_RANGE_MIN) / (TIME_RANGE_MAX - TIME_RANGE_MIN)) * 100
  const endPercent = ((filters.latestEndMinutes - TIME_RANGE_MIN) / (TIME_RANGE_MAX - TIME_RANGE_MIN)) * 100
  const timeTicks = [TIME_RANGE_MIN, 540, 660, 780, 900, 1020, 1140, 1260, TIME_RANGE_MAX]
  return (
    <aside className="filter-panel" aria-labelledby="filter-heading">
      <div className="filter-heading-row"><div><p className="eyebrow">Generated results</p><h3 id="filter-heading">Filter schedules</h3></div><button type="button" onClick={onReset} disabled={filtersAreDefault(filters, filterDays)}>Reset filters</button></div>
      <fieldset aria-label="Allowed days"><div className="day-checkboxes">{filterDays.map((day) => <label key={day}><input type="checkbox" checked={filters.allowedDays.includes(day)} onChange={() => toggleDay(day)} />{DAY_NAMES[day - 1]}</label>)}</div></fieldset>
      <fieldset className="time-range-fieldset" aria-label="Allowed class time">
        <p className="selected-time-range" aria-live="polite"><strong>{minutesToTime(filters.earliestStartMinutes)} – {minutesToTime(filters.latestEndMinutes)}</strong></p>
        <div className="range-scale" aria-hidden="true"><div>{timeTicks.map((minute) => <span className={minute === TIME_RANGE_MIN ? 'scale-start' : minute === TIME_RANGE_MAX ? 'scale-end' : ''} key={minute} style={{ left: `${((minute - TIME_RANGE_MIN) / (TIME_RANGE_MAX - TIME_RANGE_MIN)) * 100}%` }}>{minutesToTime(minute).replace(':00', '')}</span>)}</div></div>
        <div className="dual-range" style={{ '--range-start': `${startPercent}%`, '--range-end': `${endPercent}%` } as CSSProperties}>
          <div className="range-track" aria-hidden="true" />
          <label htmlFor="earliest-class-start">Earliest class start</label>
          <input id="earliest-class-start" className="range-input range-start" type="range" min={TIME_RANGE_MIN} max={TIME_RANGE_MAX} step={TIME_STEP_MINUTES} value={filters.earliestStartMinutes} aria-label="Earliest allowed class start time" aria-valuetext={minutesToTime(filters.earliestStartMinutes)} onInput={(event) => onChange({ ...filters, earliestStartMinutes: clampStartMinutes(Number(event.currentTarget.value), filters.latestEndMinutes) })} onKeyDown={(event) => adjustRangeWithKeyboard(event, 'start')} />
          <label htmlFor="latest-class-end">Latest class end</label>
          <input id="latest-class-end" className="range-input range-end" type="range" min={TIME_RANGE_MIN} max={TIME_RANGE_MAX} step={TIME_STEP_MINUTES} value={filters.latestEndMinutes} aria-label="Latest allowed class end time" aria-valuetext={minutesToTime(filters.latestEndMinutes)} onInput={(event) => onChange({ ...filters, latestEndMinutes: clampEndMinutes(Number(event.currentTarget.value), filters.earliestStartMinutes) })} onKeyDown={(event) => adjustRangeWithKeyboard(event, 'end')} />
        </div>
      </fieldset>
      <p className="filter-constraint-summary"><strong>Current filters:</strong> {describeActiveFilters(filters, DAY_NAMES, minutesToTime, filterDays).join(' · ')}</p>
    </aside>
  )
}

export function ScheduleResults({ generation, selectedCourses }: { generation: GenerateResponse; selectedCourses: Course[] }) {
  const supportsSaturday = selectedCourses.some((course) => course.has_saturday_sections)
  const filterDays = supportsSaturday ? FILTER_DAYS : WEEKDAYS
  const defaultFilters = useMemo<ScheduleFilters>(() => ({ ...DEFAULT_FILTERS, allowedDays: [...filterDays] }), [filterDays])
  const [filters, setFilters] = useState<ScheduleFilters>(() => defaultFilters)
  const [scheduleIndex, setScheduleIndex] = useState(0)
  const [exporting, setExporting] = useState<'image' | 'pdf' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'gallery' | 'detail' | 'compare'>('gallery')
  const [comparisonIndices, setComparisonIndices] = useState<number[]>([])
  const [gapOrder, setGapOrder] = useState<'ascending' | 'descending'>('ascending')
  const scheduleCaptureRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    setFilters(defaultFilters)
    setScheduleIndex(0)
    setComparisonIndices([])
    setViewMode('gallery')
  }, [defaultFilters])
  const consolidatedSchedules = useMemo(() => consolidateEquivalentSchedules(generation.schedules), [generation.schedules])
  const filteredSchedules = useMemo(() => consolidatedSchedules.filter(({ schedule }) => filterSchedules([schedule], filters).length > 0).sort((left, right) => { const difference = left.schedule.metrics.total_gap_minutes - right.schedule.metrics.total_gap_minutes; return gapOrder === 'ascending' ? difference : -difference }), [consolidatedSchedules, filters, gapOrder])
  const currentGroup = filteredSchedules[scheduleIndex]
  const currentSchedule = currentGroup?.schedule
  const activeDescriptions = describeActiveFilters(filters, DAY_NAMES, minutesToTime, filterDays)
  const courseTitles = useMemo(() => new Map(selectedCourses.map((course) => [`${course.subject}:${course.number}`, course.title])), [selectedCourses])
  const courseStyles = useMemo(() => getCourseStyleMap(selectedCourses.map((course) => `${course.subject}:${course.number}`)), [selectedCourses])
  const changeFilters = (nextFilters: ScheduleFilters) => {
    setFilters(nextFilters)
    setScheduleIndex(0)
    setComparisonIndices([])
    setViewMode('gallery')
  }
  const resetFilters = () => changeFilters(defaultFilters)
  const toggleComparison = (index: number) => setComparisonIndices((values) => values.includes(index) ? values.filter((value) => value !== index) : values.length < 6 ? [...values, index] : values)
  const toggleGapOrder = () => {
    const selectedGroups = comparisonIndices.flatMap((index) => filteredSchedules[index] ? [filteredSchedules[index]] : [])
    const current = currentGroup
    const nextOrder = gapOrder === 'ascending' ? 'descending' : 'ascending'
    const reordered = [...filteredSchedules].sort((left, right) => {
      const difference = left.schedule.metrics.total_gap_minutes - right.schedule.metrics.total_gap_minutes
      return nextOrder === 'ascending' ? difference : -difference
    })
    setGapOrder(nextOrder)
    setComparisonIndices(selectedGroups.flatMap((group) => { const index = reordered.indexOf(group); return index >= 0 ? [index] : [] }))
    setScheduleIndex(Math.max(0, current ? reordered.indexOf(current) : 0))
  }
  const openSchedule = (index: number) => { setScheduleIndex(index); setViewMode('detail') }
  const exportRenderedSchedule = async (format: 'image' | 'pdf') => {
    if (!scheduleCaptureRef.current) return
    setExporting(format)
    setExportError(null)
    try {
      if (format === 'image') await downloadScheduleImage(scheduleCaptureRef.current)
      else await downloadSchedulePdf(scheduleCaptureRef.current)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Unable to save this schedule.')
    } finally {
      setExporting(null)
    }
  }

  return (
    <section className="panel results" aria-labelledby="results-heading">
      <FilterPanel filters={filters} filterDays={filterDays} onChange={changeFilters} onReset={resetFilters} />
      <div className="match-summary" aria-live="polite"><strong>{filteredSchedules.length} of {consolidatedSchedules.length} generated schedules match your filters</strong>{generation.schedules.length > consolidatedSchedules.length && <span>{generation.schedules.length} section combinations were consolidated into {consolidatedSchedules.length} distinct timetable {consolidatedSchedules.length === 1 ? 'option' : 'options'}.</span>}{generation.truncated && <span>The exploration guard was reached.</span>}</div>
      {generation.truncated && <p className="notice">Generation reached the 100,000-step exploration guard. The combination count and schedules shown may be incomplete.</p>}
      {!currentSchedule ? (
        <div className="empty-filter-state" role="status" aria-live="polite"><h2 id="results-heading">No generated schedules match</h2><p>Adjust your allowed days or time limits. Your course selection and generated schedules are still available.</p>{activeDescriptions.length > 0 && <><p>Active filters:</p><ul>{activeDescriptions.map((description) => <li key={description}>{description}</li>)}</ul></>}<button className="primary" type="button" onClick={resetFilters}>Reset filters</button></div>
      ) : (
        <>
          {viewMode === 'gallery' ? <><div className="comparison-toolbar"><h2>Compare your options</h2><div><button type="button" disabled={comparisonIndices.length < 2} onClick={() => setViewMode('compare')}>Compare selected ({comparisonIndices.length})</button><button type="button" disabled={comparisonIndices.length === 0} onClick={() => setComparisonIndices([])}>Clear selected</button></div></div><ScheduleGallery groups={filteredSchedules} courseStyles={courseStyles} selected={comparisonIndices} gapOrder={gapOrder} onToggle={toggleComparison} onOpen={openSchedule} onToggleGap={toggleGapOrder} /></> : viewMode === 'compare' ? <section className="comparison-view" aria-labelledby="comparison-heading"><div className="comparison-view-heading"><h2 id="comparison-heading">Schedule comparison</h2><button type="button" onClick={() => setViewMode('gallery')}>Back to gallery</button></div><div className="comparison-grid">{comparisonIndices.map((index) => { const schedule = filteredSchedules[index].schedule; return <article className="comparison-card" key={index}><h3>Schedule {index + 1}</h3><MiniTimetable schedule={schedule} courseStyles={courseStyles} detailed /><dl><div><dt>Campus days</dt><dd>{schedule.metrics.campus_days}</dd></div><div><dt>Total gaps</dt><dd>{schedule.metrics.total_gap_minutes} min</dd></div><div><dt>Earliest start</dt><dd>{displayTime(schedule.metrics.earliest_start)}</dd></div><div><dt>Latest end</dt><dd>{displayTime(schedule.metrics.latest_end)}</dd></div></dl><button type="button" onClick={() => openSchedule(index)}>View full schedule</button></article> })}</div></section> : <>
          <button className="back-to-gallery" type="button" onClick={() => setViewMode('gallery')}>Back to schedule gallery</button>
          <div className="export-controls" aria-label="Save this schedule"><strong>Save schedule</strong><button type="button" disabled={exporting !== null} onClick={() => void exportRenderedSchedule('image')}>{exporting === 'image' ? 'Saving image…' : 'Image'}</button><button type="button" disabled={exporting !== null} onClick={() => void exportRenderedSchedule('pdf')}>{exporting === 'pdf' ? 'Saving PDF…' : 'PDF'}</button><button type="button" onClick={() => downloadOutlookCalendar(currentSchedule, courseTitles)}>Outlook calendar</button></div>
          {exportError && <p className="error" role="alert">Unable to save schedule: {exportError}</p>}
          <div className="schedule-capture" ref={scheduleCaptureRef}>
          <div className="results-header"><div aria-live="polite"><p className="eyebrow">Schedule {scheduleIndex + 1} of {filteredSchedules.length}</p><h2 id="results-heading">Your weekly timetable</h2></div><div className="result-controls" data-export-exclude="true"><button disabled={scheduleIndex === 0} onClick={() => setScheduleIndex((index) => index - 1)}>Previous schedule</button><button disabled={scheduleIndex === filteredSchedules.length - 1} onClick={() => setScheduleIndex((index) => index + 1)}>Next schedule</button></div></div>
          <dl className="metrics"><div><dt>Campus days</dt><dd>{currentSchedule.metrics.campus_days}</dd></div><div><dt>Total gaps</dt><dd>{currentSchedule.metrics.total_gap_minutes} min</dd></div><div><dt>Earliest start</dt><dd>{displayTime(currentSchedule.metrics.earliest_start)}</dd></div><div><dt>Latest end</dt><dd>{displayTime(currentSchedule.metrics.latest_end)}</dd></div><div><dt>Selected sections</dt><dd>{currentSchedule.sections.length}</dd></div><div><dt>Result set</dt><dd>{generation.truncated ? 'Limited' : 'Complete'}</dd></div></dl>
          {currentSchedule.sections.some(isOnlineSection) && <section className="online-class-summary" aria-labelledby="online-class-heading"><h3 id="online-class-heading">Online classes in this schedule</h3><ul>{currentSchedule.sections.filter(isOnlineSection).map((section) => { const alternatives = currentGroup.alternativesBySectionKey.get(sectionEquivalenceKey(section)) ?? [section]; return <li key={section.id}><strong>{section.subject} {section.course_number}</strong> — {section.component}, section {alternativeText(alternatives, 'section_number')} (CRN {alternativeText(alternatives, 'crn')}){section.meetings.some((meeting) => meeting.is_asynchronous) ? ' · Asynchronous' : ''}</li> })}</ul></section>}
          <Timetable schedule={currentSchedule} courseTitles={courseTitles} courseStyles={courseStyles} alternativesBySectionKey={currentGroup.alternativesBySectionKey} />
          <details className="section-details"><summary>View all selected sections</summary><ul className="section-list">{currentSchedule.sections.map((section) => { const alternatives = currentGroup.alternativesBySectionKey.get(sectionEquivalenceKey(section)) ?? [section]; return <li key={section.id}><strong>{section.subject} {section.course_number} · {section.component} · Section {alternativeText(alternatives, 'section_number')}</strong><span>CRN {alternativeText(alternatives, 'crn')}</span><span>{isOnlineSection(section) ? `Online${section.meetings.some((meeting) => meeting.is_asynchronous) ? ' · Asynchronous' : ''}` : section.meetings.filter((meeting) => meeting.meeting_type !== 'final_exam' && isTimedMeeting(meeting)).map((meeting) => `${meeting.days.map((day) => DAY_NAMES[day - 1].slice(0, 3)).join('/')} ${displayTime(meeting.start_time)}–${displayTime(meeting.end_time)}`).join('; ')}</span></li> })}</ul></details>
          </div>
          </>}
        </>
      )}
    </section>
  )
}
