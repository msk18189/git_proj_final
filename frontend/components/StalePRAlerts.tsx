'use client'

import { motion } from 'framer-motion'
import { AlertTriangle, Lightbulb, ChevronDown } from 'lucide-react'
import { severityColor } from '@/lib/format'
import { useRef, useState, useEffect } from 'react'

interface StaleAlert {
  number: number
  title: string
  author: string
  age_days: number
  severity: string
  reasons: string[]
  recommended_actions: string[]
}

interface StalePRAlertsProps {
  data: StaleAlert[]
  page?: number
  totalPages?: number
  onPageChange?: (newPage: number) => void
  totalResults?: number
}

export default function StalePRAlerts({
  data,
  page = 1,
  totalPages,
  onPageChange,
  totalResults,
}: StalePRAlertsProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [canScroll, setCanScroll] = useState(false)

  const handleScroll = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ top: 200, behavior: 'smooth' })
    }
  }

  const checkScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollHeight, clientHeight, scrollTop } = scrollContainerRef.current
      setCanScroll(scrollHeight > clientHeight && scrollTop + clientHeight < scrollHeight)
    }
  }

  useEffect(() => {
    checkScroll()
    const container = scrollContainerRef.current
    if (container) {
      container.addEventListener('scroll', checkScroll)
      window.addEventListener('resize', checkScroll)
      return () => {
        container.removeEventListener('scroll', checkScroll)
        window.removeEventListener('resize', checkScroll)
      }
    }
  }, [data])

  if (!data?.length) {
    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full">
        <div className="mb-2 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-palette-teal" />
          <h3 className="section-title text-primary">Stale PR Alerts</h3>
        </div>
        <p className="text-sm text-muted">No PRs need attention right now.</p>
      </motion.div>
    )
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full flex flex-col justify-between">
      <div>
        <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-palette-amber" />
            <h3 className="section-title text-primary">Stale PR Alerts</h3>
          </div>
          {totalResults !== undefined && (
            <span className="text-xs text-muted font-medium">
              Total: {totalResults.toLocaleString()} records
            </span>
          )}
        </div>
        <div 
          ref={scrollContainerRef}
          className="space-y-4 max-h-[420px] overflow-y-auto pr-2 scrollbar-thin"
        >
          {data.map((alert) => (
            <div
              key={alert.number}
              className={`border rounded-lg p-4 ${severityColor(alert.severity)}`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold text-primary">
                    #{alert.number} — {alert.title}
                  </p>
                  <p className="text-xs text-secondary mt-1 font-medium">
                    {alert.author} · {alert.age_days} days inactive · <span className={`uppercase font-bold tracking-wide ${
                      alert.severity === 'critical' ? 'text-palette-rose' :
                      alert.severity === 'stale' ? 'text-palette-amber' :
                      alert.severity === 'warning' ? 'text-palette-orange' :
                      'text-palette-emerald'
                    }`}>{alert.severity}</span>
                  </p>
                </div>
              </div>
              <div className="mt-3 grid md:grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-bold text-primary uppercase tracking-wider mb-1">Why flagged</p>
                  <ul className="text-sm text-secondary space-y-1 font-medium">
                    {alert.reasons.map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-bold text-primary uppercase tracking-wider mb-1 flex items-center gap-1">
                    <Lightbulb className="w-3 h-3 text-palette-emerald" /> Recommended actions
                  </p>
                  <ul className="text-sm text-palette-teal-text space-y-1 font-semibold">
                    {alert.recommended_actions.map((a, i) => (
                      <li key={i}>→ {a}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>
        {canScroll && (
          <button
            onClick={handleScroll}
            className="mt-4 flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-palette-orange/10 hover:bg-palette-orange/20 text-palette-orange font-semibold transition"
          >
            <ChevronDown className="h-4 w-4" />
            Scroll to more
          </button>
        )}
      </div>

      {totalPages !== undefined && onPageChange && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between border-t border-warm-200 pt-4 shrink-0">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-warm-200 bg-white px-3 py-1.5 text-xs font-medium text-secondary transition hover:bg-warm-50 hover:text-primary disabled:pointer-events-none disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-secondary">
            Page <span className="font-semibold text-primary">{page}</span> of{' '}
            <span className="font-semibold text-primary">{totalPages}</span>
          </span>
          <button
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="rounded-lg border border-warm-200 bg-white px-3 py-1.5 text-xs font-medium text-secondary transition hover:bg-warm-50 hover:text-primary disabled:pointer-events-none disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </motion.div>
  )
}
