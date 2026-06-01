/** Warm dashboard palette — terracotta, sage, amber (no blue/violet). */
export const PALETTE = {
  emerald: { main: '#7A9E87', light: '#E2EDE5', dark: '#4F6F59', text: '#5A7D66' },
  teal: { main: '#6B8F7A', light: '#DCE8E0', dark: '#3D5C4A', text: '#4A6B58' },
  rose: { main: '#C75D5D', light: '#F8E8E8', dark: '#8B3D3D', text: '#A84848' },
  amber: { main: '#D4A054', light: '#F9F0E0', dark: '#9A7030', text: '#B8873A' },
  orange: { main: '#C67B5C', light: '#F8EDE8', dark: '#8F5A42', text: '#A86548' },
  lime: { main: '#9AAF5C', light: '#EEF2E0', dark: '#5C6B38', text: '#6D7D45' },
} as const

export type PaletteKey = keyof typeof PALETTE

export const CHART_SERIES = {
  created: PALETTE.emerald.main,
  merged: PALETTE.teal.main,
  closed: PALETTE.rose.main,
  throughput: PALETTE.orange.main,
  totalPrs: PALETTE.lime.main,
  mergedPrs: PALETTE.teal.main,
  open: PALETTE.amber.main,
  stale: PALETTE.rose.main,
  pie: [
    PALETTE.emerald.main,
    PALETTE.teal.main,
    PALETTE.rose.main,
    PALETTE.amber.main,
    PALETTE.orange.main,
    PALETTE.lime.main,
  ],
}

export const KPI_ACCENTS: PaletteKey[] = [
  'emerald',
  'amber',
  'orange',
  'lime',
  'teal',
  'rose',
  'teal',
  'emerald',
]
