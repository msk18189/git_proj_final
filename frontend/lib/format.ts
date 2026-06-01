export interface DurationDisplay {
  value: number
  unit: string
  raw_hours?: number
}

export function formatDurationDisplay(
  display?: DurationDisplay | null,
  fallbackDays?: number | null
): { value: string | number; unit: string } {
  if (display && display.value !== null && display.value !== undefined) {
    let val = display.value;
    if (val < 0) val = 0;
    if (val === 0) return { value: 0, unit: 'hrs' };
    return { value: val, unit: display.unit || 'hrs' }
  }
  if (fallbackDays !== undefined && fallbackDays !== null) {
    let fallback = fallbackDays;
    if (fallback < 0) fallback = 0;
    if (fallback === 0) return { value: 0, unit: 'hrs' };
    if (fallback < 1) {
      const hrs = Math.round(fallback * 24 * 10) / 10
      return { value: hrs === Math.floor(hrs) ? Math.floor(hrs) : hrs, unit: 'hrs' }
    }
    return { value: fallback, unit: 'days' }
  }
  return { value: 'Limited', unit: '' }
}

export function formatDurationFromDays(days?: number | null): { value: string | number; unit: string } {
  if (days === undefined || days === null) return { value: 'Limited', unit: '' }
  let d = days;
  if (d < 0) d = 0;
  if (d === 0) return { value: 0, unit: 'hrs' }
  if (d < 1) {
    const hrs = Math.round(d * 24 * 10) / 10
    return { value: hrs === Math.floor(hrs) ? Math.floor(hrs) : hrs, unit: 'hrs' }
  }
  return { value: d, unit: 'days' }
}

export function severityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'border-palette-rose/50 bg-palette-rose-light dark:bg-palette-rose-light/20 dark:border-palette-rose/30'
    case 'stale':
      return 'border-palette-amber/40 bg-palette-amber-light dark:bg-palette-amber-light/20 dark:border-palette-amber/30'
    case 'warning':
      return 'border-palette-orange/35 bg-palette-orange-light dark:bg-palette-orange-light/20 dark:border-palette-orange/30'
    case 'healthy':
      return 'border-palette-emerald/35 bg-palette-emerald-light dark:bg-palette-emerald-light/20 dark:border-palette-emerald/30'
    // Legacy support for old severity levels
    case 'high':
      return 'border-palette-rose/50 bg-palette-rose-light dark:bg-palette-rose-light/20 dark:border-palette-rose/30'
    case 'medium':
      return 'border-palette-amber/40 bg-palette-amber-light dark:bg-palette-amber-light/20 dark:border-palette-amber/30'
    case 'low':
      return 'border-palette-emerald/35 bg-palette-emerald-light dark:bg-palette-emerald-light/20 dark:border-palette-emerald/30'
    default:
      return 'border-palette-emerald/35 bg-palette-emerald-light dark:bg-palette-emerald-light/20 dark:border-palette-emerald/30'
  }
}

export function riskColor(score: number): string {
  if (score >= 70) return 'text-palette-rose font-bold'
  if (score >= 40) return 'text-palette-amber font-bold'
  return 'text-palette-teal font-bold'
}

export function formatTelemetry(
  synced: number | undefined | null,
  expected: number | undefined | null
): string {
  const s = synced !== undefined && synced !== null ? synced : 0;
  const exp = expected !== undefined && expected !== null ? expected : 0;
  
  if (exp <= 0) {
    return `${s}`;
  }
  
  const display_total = Math.max(exp, s);
  return `${s} / ${display_total}`;
}

