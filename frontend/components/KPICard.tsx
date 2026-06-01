'use client'

import { motion } from 'framer-motion'
import { ReactNode } from 'react'
import type { PaletteKey } from '@/lib/theme'
import { Tooltip } from './ui/Tooltip'
import type { TooltipProps } from './ui/Tooltip'

interface KPICardProps {
  title: string
  value: string | number
  icon: ReactNode
  trend?: number
  unit?: string
  accent?: PaletteKey
  tooltip?: TooltipProps['content']
}

const accentStyles: Record<
  PaletteKey,
  { glow: string; icon: string; title: string; value: string }
> = {
  emerald: {
    glow: 'bg-palette-emerald-light dark:bg-emerald-500/5',
    icon: 'border-palette-emerald/30 text-palette-emerald bg-palette-emerald-light dark:border-emerald-500/20 dark:text-emerald-400 dark:bg-emerald-500/10',
    title: 'text-palette-emerald-text dark:text-emerald-400/80',
    value: 'text-palette-emerald-dark dark:text-emerald-300',
  },
  teal: {
    glow: 'bg-palette-teal-light dark:bg-teal-500/5',
    icon: 'border-palette-teal/30 text-palette-teal bg-palette-teal-light dark:border-teal-500/20 dark:text-teal-400 dark:bg-teal-500/10',
    title: 'text-palette-teal-text dark:text-teal-400/80',
    value: 'text-palette-teal-dark dark:text-teal-300',
  },
  rose: {
    glow: 'bg-palette-rose-light dark:bg-rose-500/5',
    icon: 'border-palette-rose/30 text-palette-rose bg-palette-rose-light dark:border-rose-500/20 dark:text-rose-400 dark:bg-rose-500/10',
    title: 'text-palette-rose-text dark:text-rose-400/80',
    value: 'text-palette-rose-dark dark:text-rose-300',
  },
  amber: {
    glow: 'bg-palette-amber-light dark:bg-amber-500/5',
    icon: 'border-palette-amber/30 text-palette-amber bg-palette-amber-light dark:border-amber-500/20 dark:text-amber-400 dark:bg-amber-500/10',
    title: 'text-palette-amber-text dark:text-amber-400/80',
    value: 'text-palette-amber-dark dark:text-amber-300',
  },
  orange: {
    glow: 'bg-palette-orange-light dark:bg-orange-500/5',
    icon: 'border-palette-orange/30 text-palette-orange bg-palette-orange-light dark:border-orange-500/20 dark:text-orange-400 dark:bg-orange-500/10',
    title: 'text-palette-orange-text dark:text-orange-400/80',
    value: 'text-palette-orange-dark dark:text-orange-300',
  },
  lime: {
    glow: 'bg-palette-lime-light dark:bg-lime-500/5',
    icon: 'border-palette-lime/30 text-palette-lime bg-palette-lime-light dark:border-lime-500/20 dark:text-lime-400 dark:bg-lime-500/10',
    title: 'text-palette-lime-text dark:text-lime-400/80',
    value: 'text-palette-lime-dark dark:text-lime-300',
  },
}

// Values indicating unavailable/limited data — shown as styled badges
const LIMITED_VALUES = ['Limited', 'Unavailable', 'Partial', 'none', 'N/A', '—']

export default function KPICard({
  title,
  value,
  icon,
  trend,
  unit,
  accent = 'emerald',
  tooltip,
}: KPICardProps) {
  const a = accentStyles[accent]
  const isLimited = typeof value === 'string' && LIMITED_VALUES.includes(value)
  const isLongString = typeof value === 'string' && value.length > 8 && !isLimited

  const displayValue =
    typeof value === 'number' && value % 1 !== 0 ? value.toFixed(1) : value

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="card card-hover card-glow relative overflow-hidden"
    >
      <div className={`absolute -right-4 -top-4 h-20 w-20 rounded-full blur-2xl opacity-75 dark:opacity-40 ${a.glow}`} />
      <div className="relative flex items-start justify-between">
        <div className="flex-1 min-w-0 pr-2">
          <div className="flex items-center gap-2">
            <p className={`text-[11px] font-bold uppercase tracking-wider ${a.title}`}>{title}</p>
          </div>
          <div className="mt-3 flex items-baseline gap-2 min-w-0">
            {isLimited ? (
              // Badge pill for limited/unavailable data
              <span
                className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold border ${
                  accent === 'rose'
                    ? 'bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-450 border-rose-200 dark:border-rose-900/30'
                    : accent === 'amber'
                    ? 'bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-450 border-amber-200 dark:border-amber-900/30'
                    : 'bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
                }`}
              >
                {displayValue}
              </span>
            ) : (
              <h3
                className={`font-bold tracking-tight leading-none truncate ${
                  isLongString ? 'text-xl' : 'text-3xl'
                } ${a.value}`}
                title={String(displayValue)}
              >
                {displayValue}
              </h3>
            )}
            {unit && !isLimited && (
              <span className="text-sm text-secondary dark:text-slate-400 shrink-0">{unit}</span>
            )}
          </div>
          {trend !== undefined && (
            <p
              className={`mt-2 text-xs font-medium ${
                trend >= 0 ? 'text-palette-teal dark:text-teal-400' : 'text-palette-rose dark:text-rose-400'
              }`}
            >
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
            </p>
          )}
        </div>
        {tooltip ? (
          <Tooltip content={tooltip} position="left" showIcon={false}>
            <div className={`rounded-xl border p-2.5 shrink-0 ${a.icon}`}>{icon}</div>
          </Tooltip>
        ) : (
          <div className={`rounded-xl border p-2.5 shrink-0 ${a.icon}`}>{icon}</div>
        )}
      </div>
    </motion.div>
  )
}
