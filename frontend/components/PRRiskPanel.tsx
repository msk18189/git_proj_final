'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import { Brain, RefreshCw, AlertTriangle, GitPullRequest, ServerOff, Loader2 } from 'lucide-react'
import { riskColor } from '@/lib/format'
import { getMLStatus, refreshMLPredictions } from '@/lib/api'

interface PRRiskItem {
  number: number
  title: string
  author: string
  risk_score: number
  bottleneck_probability: number
  predicted_delay_days: number | null
  predicted_delay_display?: { value: number; unit: string }
  predicted_review_wait_hours: number | null
  score_source?: string
  _panel_note?: string
}

interface MLStatus {
  open_prs: number
  prs_with_predictions: number
  models_exist: boolean
  ready: boolean
  reasons: string[]
}

interface PRRiskPanelProps {
  repoId?: number | null
  data: PRRiskItem[]
  page?: number
  totalPages?: number
  onPageChange?: (newPage: number) => void
  totalResults?: number
  onRefreshed?: () => void
}

export default function PRRiskPanel({
  repoId,
  data,
  page = 1,
  totalPages,
  onPageChange,
  totalResults,
  onRefreshed,
}: PRRiskPanelProps) {
  const [mlStatus, setMLStatus] = useState<MLStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState<string | null>(null)

  async function loadMLStatus() {
    if (!repoId || loadingStatus) return
    setLoadingStatus(true)
    try {
      const status = await getMLStatus(repoId)
      setMLStatus(status)
    } catch {
      setMLStatus(null)
    } finally {
      setLoadingStatus(false)
    }
  }

  async function handleRefresh() {
    if (!repoId || refreshing) return
    setRefreshing(true)
    setRefreshMsg(null)
    try {
      const result = await refreshMLPredictions(repoId)
      setRefreshMsg(result.reason)
      if (result.refreshed > 0 && onRefreshed) {
        onRefreshed()
      }
      // Reload status
      const status = await getMLStatus(repoId)
      setMLStatus(status)
    } catch (e: any) {
      setRefreshMsg(e?.response?.data?.detail || 'ML refresh failed.')
    } finally {
      setRefreshing(false)
    }
  }

  // ─── Panel header ────────────────────────────────────────────────────────
  const PanelHeader = ({ showRefresh = false }: { showRefresh?: boolean }) => (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 gap-2">
      <div className="flex items-center gap-2">
        <Brain className="w-5 h-5 text-palette-rose" />
        <h3 className="text-lg font-bold text-primary">PR Risk &amp; Delay Predictions</h3>
      </div>
      <div className="flex items-center gap-2">
        {totalResults !== undefined && (
          <span className="text-xs text-muted font-medium">
            {totalResults.toLocaleString()} record{totalResults !== 1 ? 's' : ''}
          </span>
        )}
        {showRefresh && repoId && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 rounded-lg border border-warm-200 bg-white px-2.5 py-1 text-xs font-medium text-secondary transition hover:bg-warm-50 hover:text-primary disabled:pointer-events-none disabled:opacity-40"
            title="Re-run ML inference for open PRs"
          >
            <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Running…' : 'Refresh ML'}
          </button>
        )}
      </div>
    </div>
  )

  // ─── Empty state ─────────────────────────────────────────────────────────
  if (!data?.length) {
    // Determine which diagnostic icon + message to show
    const determineEmptyReason = () => {
      if (!mlStatus) {
        // Haven't fetched status yet — show a generic diagnostic prompt
        return {
          icon: <Brain className="h-8 w-8 text-muted mx-auto mb-3" />,
          title: 'No ML predictions yet',
          lines: ['Predictions will appear here once ML inference has run for open PRs.'],
          showDiagnose: true,
        }
      }

      if (!mlStatus.models_exist) {
        return {
          icon: <ServerOff className="h-8 w-8 text-rose-400 mx-auto mb-3" />,
          title: 'Model inference unavailable',
          lines: ['ML model files (.pkl) not found on the server.', 'Run the training script to generate models.'],
          showDiagnose: false,
        }
      }

      if (mlStatus.open_prs === 0) {
        return {
          icon: <GitPullRequest className="h-8 w-8 text-muted mx-auto mb-3" />,
          title: 'No open pull requests',
          lines: ['There are no open PRs in this repository.', 'Predictions only apply to currently open PRs.'],
          showDiagnose: false,
        }
      }

      if (mlStatus.prs_with_predictions === 0) {
        return {
          icon: <AlertTriangle className="h-8 w-8 text-amber-400 mx-auto mb-3" />,
          title: 'Insufficient telemetry',
          lines: [
            `${mlStatus.open_prs} open PR${mlStatus.open_prs !== 1 ? 's' : ''} found, but no predictions are stored.`,
            'Click "Refresh ML" to run inference now.',
          ],
          showDiagnose: false,
        }
      }

      return {
        icon: <Brain className="h-8 w-8 text-muted mx-auto mb-3" />,
        title: 'No open PRs with predictions',
        lines: mlStatus.reasons.length > 0 ? mlStatus.reasons : ['No predictions available for this repository.'],
        showDiagnose: false,
      }
    }

    const { icon, title, lines, showDiagnose } = determineEmptyReason()

    return (
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full">
        <PanelHeader showRefresh={!!mlStatus && mlStatus.models_exist && mlStatus.open_prs > 0} />

        <div className="flex flex-col items-center justify-center py-10 text-center">
          {loadingStatus ? (
            <Loader2 className="h-8 w-8 animate-spin text-muted mx-auto mb-3" />
          ) : (
            icon
          )}
          <p className="font-semibold text-primary text-sm mb-1">{loadingStatus ? 'Diagnosing ML status…' : title}</p>
          {!loadingStatus && lines.map((line, i) => (
            <p key={i} className="text-xs text-muted max-w-xs">{line}</p>
          ))}

          {!loadingStatus && refreshMsg && (
            <p className="mt-3 text-xs text-emerald-600 font-medium">{refreshMsg}</p>
          )}

          <div className="flex gap-2 mt-4">
            {showDiagnose && repoId && (
              <button
                onClick={loadMLStatus}
                disabled={loadingStatus}
                className="rounded-lg border border-warm-200 bg-white px-3 py-1.5 text-xs font-medium text-secondary transition hover:bg-warm-50 hover:text-primary disabled:pointer-events-none disabled:opacity-40"
              >
                Diagnose
              </button>
            )}
            {repoId && mlStatus?.models_exist && mlStatus.open_prs > 0 && (
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:pointer-events-none disabled:opacity-40"
              >
                <RefreshCw className={`h-3 w-3 ${refreshing ? 'animate-spin' : ''}`} />
                {refreshing ? 'Running…' : 'Refresh ML'}
              </button>
            )}
          </div>
        </div>
      </motion.div>
    )
  }

  // ─── Full panel with data ─────────────────────────────────────────────────
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full flex flex-col justify-between">
      <div>
        <PanelHeader showRefresh />
        <p className="text-xs text-secondary mb-4">
          {data[0]?._panel_note ||
            (data[0]?.score_source === 'heuristic'
              ? 'Rule-based risk estimates from PR age, reviews, and size. Train ML models for full model-powered predictions.'
              : 'ML-powered risk scores for open PRs — higher risk may need attention')}
        </p>

        {refreshMsg && (
          <p className="mb-3 text-xs text-emerald-600 font-medium">{refreshMsg}</p>
        )}

        <div className="overflow-x-auto rounded-xl border border-warm-200">
          <table className="w-full">
            <thead>
              <tr className="border-b border-warm-200 bg-warm-50/50">
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">#</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Title</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Author</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Risk</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Bottleneck</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Est. delay</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary">Est. review wait</th>
              </tr>
            </thead>
            <tbody>
              {data.map((pr) => (
                <tr key={pr.number} className="border-b border-warm-100 transition hover:bg-warm-50/40">
                  <td className="px-3 py-2 font-mono text-xs text-muted">#{pr.number}</td>
                  <td className="px-3 py-2 text-xs text-primary max-w-xs truncate">{pr.title}</td>
                  <td className="px-3 py-2 text-xs text-secondary">{pr.author}</td>
                  <td className={`px-3 py-2 text-xs font-bold ${riskColor(pr.risk_score)}`}>
                    {typeof pr.risk_score === 'number' ? `${pr.risk_score}%` : '—'}
                  </td>
                  <td className="px-3 py-2 text-xs text-secondary">
                    {typeof pr.bottleneck_probability === 'number' ? `${pr.bottleneck_probability}%` : '—'}
                  </td>
                  <td className="px-3 py-2 text-xs text-secondary">
                    {pr.predicted_delay_display
                      ? `${pr.predicted_delay_display.value} ${pr.predicted_delay_display.unit}`
                      : pr.predicted_delay_days != null
                      ? `${pr.predicted_delay_days} days`
                      : '—'}
                  </td>
                  <td className="px-3 py-2 text-xs text-secondary">
                    {pr.predicted_review_wait_hours != null
                      ? `${pr.predicted_review_wait_hours} hrs`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages !== undefined && onPageChange && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between border-t border-warm-200 pt-4">
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
