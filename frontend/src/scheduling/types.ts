export interface ScheduleFilters {
  allowedDays: number[]
  earliestStartMinutes: number
  latestEndMinutes: number
}

export const ALL_DAYS = [1, 2, 3, 4, 5, 6, 7] as const
export const WEEKDAYS = [1, 2, 3, 4, 5] as const
export const FILTER_DAYS = [1, 2, 3, 4, 5, 6] as const
export const TIME_RANGE_MIN = 7 * 60 + 15
export const TIME_RANGE_MAX = 22 * 60 + 30
export const DEFAULT_EARLIEST_START = TIME_RANGE_MIN
export const DEFAULT_LATEST_END = TIME_RANGE_MAX
export const TIME_STEP_MINUTES = 15
export const MINIMUM_RANGE_MINUTES = TIME_STEP_MINUTES

export const DEFAULT_FILTERS: ScheduleFilters = {
  allowedDays: [...FILTER_DAYS],
  earliestStartMinutes: DEFAULT_EARLIEST_START,
  latestEndMinutes: DEFAULT_LATEST_END,
}
