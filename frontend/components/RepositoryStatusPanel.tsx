'use client'

import { Database, RefreshCw, CheckCircle2, XCircle, Info, Clock } from 'lucide-react'
import { motion } from 'framer-motion'
import { formatTelemetry } from '@/lib/format'

interface SyncStatus {
  sync_status: 'IDLE' | 'PENDING' | 'VERIFYING' | 'SYNCING' | 'COMPLETED' | 'FAILED' | 'PARTIAL' | 'RATE_LIMITED'
  sync_progress: string | null
  sync_duration: number | null
  initial_sync_completed: boolean
  last_synced_at: string | null
  last_successful_sync: string | null
  error_message: string | null
  total_prs: number
  total_issues: number
  total_branches: number
  total_forks: number
  total_workflow_runs: number
  total_discussions: number
  total_projects: number
  total_contributors?: number
  rate_limit_remaining: number | null
  rate_limit_limit: number | null
  rate_limit_reset: string | null
  expected_prs?: number
  expected_issues?: number
  expected_forks?: number
  expected_workflows?: number
  synced_prs?: number
  synced_issues?: number
  synced_forks?: number
  synced_workflows?: number
}

interface Props {
  repoLabel: string
  syncStatus: SyncStatus
  onSync: () => void
  isSyncing: boolean
}

const statusColors: Record<string, string> = {
  PENDING: 'bg-slate-50 text-slate-800 border-slate-200',
  VERIFYING: 'bg-amber-50 text-amber-800 border-amber-200',
  SYNCING: 'bg-amber-50 text-amber-800 border-amber-200',
  COMPLETED: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  FAILED: 'bg-rose-50 text-rose-800 border-rose-200',
  PARTIAL: 'bg-orange-50 text-orange-800 border-orange-200',
  RATE_LIMITED: 'bg-rose-50 text-rose-800 border-rose-200',
  IDLE: 'bg-indigo-50 text-indigo-800 border-indigo-200',
}

function MetricCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-[10px] uppercase tracking-wider text-muted font-medium">{label}</p>
      <p className="text-base font-bold text-primary">{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  )
}

function fmt(iso: string | null): string {
  if (!iso) return 'Never'
  try {
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

export default function RepositoryStatusPanel({ repoLabel, syncStatus, onSync, isSyncing }: Props) {
  const status = syncStatus.sync_status
  const isBusy = status === 'SYNCING' || status === 'PENDING' || status === 'VERIFYING' || isSyncing

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-2xl border border-warm-200 bg-white/80 backdrop-blur-xl p-5 shadow-sm"
    >
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
        {/* Left: status */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2.5 mb-2">
            <Database className="h-4 w-4 text-indigo-600 shrink-0" />
            <h3 className="text-sm font-bold text-primary">{repoLabel}</h3>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${statusColors[status] ?? statusColors.IDLE}`}>
              {(status === 'SYNCING' || status === 'PENDING' || status === 'VERIFYING') && <RefreshCw className="w-2.5 h-2.5 animate-spin" />}
              {status === 'COMPLETED' && <CheckCircle2 className="w-2.5 h-2.5" />}
              {(status === 'FAILED' || status === 'RATE_LIMITED') && <XCircle className="w-2.5 h-2.5" />}
              {status === 'PARTIAL' && <Info className="w-2.5 h-2.5" />}
              {status === 'IDLE' && <Info className="w-2.5 h-2.5" />}
              {status === 'RATE_LIMITED' ? 'Rate Limited' : status}
            </span>
            {syncStatus.initial_sync_completed && (
              <span className="text-[10px] bg-warm-100 text-secondary border border-warm-200 px-2 py-0.5 rounded-full">
                Initial Sync Complete
              </span>
            )}
          </div>

          {syncStatus.sync_progress && (
            <p className="text-xs text-secondary mb-3 font-mono leading-relaxed">{syncStatus.sync_progress}</p>
          )}

          {/* Module record counts */}
          <div className="grid grid-cols-4 sm:grid-cols-8 gap-3 border-t border-warm-200/60 pt-3">
            <MetricCell 
              label="PRs" 
              value={formatTelemetry(syncStatus.synced_prs || syncStatus.total_prs, syncStatus.expected_prs)} 
            />
            <MetricCell 
              label="Issues" 
              value={formatTelemetry(syncStatus.synced_issues || syncStatus.total_issues, syncStatus.expected_issues)} 
            />
            <MetricCell label="Branches" value={syncStatus.total_branches ?? 0} />
            <MetricCell 
              label="Forks" 
              value={formatTelemetry(syncStatus.synced_forks || syncStatus.total_forks, syncStatus.expected_forks)} 
            />
            <MetricCell 
              label="CI Runs" 
              value={formatTelemetry(syncStatus.synced_workflows || syncStatus.total_workflow_runs, syncStatus.expected_workflows)} 
            />
            <MetricCell 
              label="Discussions" 
              value={formatTelemetry(syncStatus.total_discussions, 0)} 
            />
            <MetricCell 
              label="Projects" 
              value={formatTelemetry(syncStatus.total_projects, 0)} 
            />
            <MetricCell 
              label="Contributors" 
              value={formatTelemetry(syncStatus.total_contributors ?? 0, 0)} 
            />
          </div>

          <div className="flex flex-wrap gap-4 mt-3 border-t border-warm-200/60 pt-3">
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <Clock className="h-3 w-3" />
              <span>Last sync: {fmt(syncStatus.last_successful_sync)}</span>
            </div>
            {syncStatus.rate_limit_remaining !== null && (
              <div className="text-xs text-muted">
                API budget: {syncStatus.rate_limit_remaining?.toLocaleString()} / {syncStatus.rate_limit_limit?.toLocaleString()}
              </div>
            )}
          </div>

          {status === 'FAILED' && syncStatus.error_message && (
            <div className="mt-3 p-2.5 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-850 text-xs">
              <strong>Error:</strong> {syncStatus.error_message}
            </div>
          )}
        </div>

        {/* Right: sync button */}
        <div className="flex flex-col items-start lg:items-end gap-1.5 shrink-0">
          <button
            disabled={isBusy}
            onClick={onSync}
            className="btn-primary rounded-xl px-4 py-2 text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isBusy ? 'animate-spin' : ''}`} />
            {isBusy ? 'Syncing…' : 'Sync Now'}
          </button>
          <span className="text-[10px] text-muted text-right">Full incremental sync</span>
        </div>
      </div>
    </motion.div>
  )
}
