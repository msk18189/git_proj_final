import { CHART_SERIES, PALETTE } from './theme'

export const CHART = {
  grid: 'rgba(100, 116, 139, 0.15)',
  axis: '#64748b',
  tooltipBg: '#ffffff',
  tooltipBorder: 'rgba(198, 123, 92, 0.25)',
  created: CHART_SERIES.created,
  merged: CHART_SERIES.merged,
  closed: CHART_SERIES.closed,
  line: CHART_SERIES.throughput,
  lineGlow: PALETTE.orange.main,
  total: CHART_SERIES.totalPrs,
  mergedBar: CHART_SERIES.mergedPrs,
  open: CHART_SERIES.open,
  stale: CHART_SERIES.stale,
  pie: CHART_SERIES.pie,
}

export const tooltipStyle = {
  backgroundColor: CHART.tooltipBg,
  border: `1px solid ${CHART.tooltipBorder}`,
  borderRadius: '12px',
  boxShadow: '0 8px 32px rgba(15, 23, 42, 0.1)',
  padding: '10px 14px',
  color: '#1e293b',
}

/** Colored legend labels for Recharts */
export const legendStyle = { fontSize: 12, color: '#475569' }
