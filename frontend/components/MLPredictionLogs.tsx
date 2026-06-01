'use client'

import { motion } from 'framer-motion'
import { ListChecks } from 'lucide-react'

interface MLPredictionLogItem {
  number: number
  title: string
  risk_score: number
  bottleneck_probability: number
  predicted_delay_days: number | null
  predicted_review_wait_hours: number | null
  score_source?: string
}

export default function MLPredictionLogs({ data }: { data: MLPredictionLogItem[] }) {
  if (!data?.length) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="card card-hover card-glow h-full"
      >
        <div className="flex items-center gap-2 mb-2">
          <ListChecks className="h-5 w-5 text-palette-blue" />
          <h3 className="section-title">ML Prediction Logs</h3>
        </div>
        <p className="text-sm text-midnight-400">No ML predictions available yet.</p>
      </motion.div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card card-hover card-glow h-full"
    >
      <div className="flex items-center gap-2 mb-4">
        <ListChecks className="w-5 h-5 text-palette-blue" />
        <h3 className="text-lg font-bold">ML Prediction Logs</h3>
      </div>
      <div className="space-y-3 overflow-y-auto max-h-[32rem] pr-2">
        {data.map((pr) => (
          <div
            key={pr.number}
            className="rounded-2xl border border-white/10 bg-white/5 p-3 text-sm"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-semibold text-midnight-900">PR #{pr.number}</p>
                <p className="truncate text-midnight-500">{pr.title}</p>
              </div>
              <span className="rounded-full bg-palette-slate/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-palette-slate">
                {pr.score_source || 'ml'}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-[13px] text-midnight-600">
              <div>
                <p className="font-semibold text-midnight-800">Risk</p>
                <p>{pr.risk_score}%</p>
              </div>
              <div>
                <p className="font-semibold text-midnight-800">Bottleneck</p>
                <p>{pr.bottleneck_probability}%</p>
              </div>
              <div>
                <p className="font-semibold text-midnight-800">Delay</p>
                <p>{pr.predicted_delay_days != null ? `${pr.predicted_delay_days} days` : '—'}</p>
              </div>
              <div>
                <p className="font-semibold text-midnight-800">Review wait</p>
                <p>{pr.predicted_review_wait_hours != null ? `${pr.predicted_review_wait_hours} hrs` : '—'}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
