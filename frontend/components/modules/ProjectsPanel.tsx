'use client'
 
import { useState, useEffect } from 'react'
import { Kanban, CheckCircle2, Circle, Clock, AlertCircle, TrendingUp, ChevronRight } from 'lucide-react'
import { motion } from 'framer-motion'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
import { getProjectsAnalytics, getProjects } from '@/lib/api'
import { formatTelemetry } from '@/lib/format'
 
interface Props { repoId: number; syncStatus?: any }
 
export default function ProjectsPanel({ repoId, syncStatus }: Props) {
  const [summary, setSummary] = useState<any>(null)
  const [projects, setProjects] = useState<any>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
 
  useEffect(() => {
    setLoading(true)
    getProjectsAnalytics(repoId).then(setSummary).catch(console.error).finally(() => setLoading(false))
  }, [repoId])
 
  useEffect(() => {
    getProjects(repoId, page).then(setProjects).catch(console.error)
  }, [repoId, page])

  return (
    <div className="space-y-6">
 
      {summary?.total_projects === 0 && !loading && (
        <div className="rounded-2xl border border-indigo-200 dark:border-indigo-900/30 bg-indigo-50/30 dark:bg-indigo-950/10 p-5 text-primary text-sm">
          No GitHub Projects found for this repository
        </div>
      )}
 
      {/* KPI row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Total Projects', tooltipKey: 'totalProjects', value: syncStatus ? formatTelemetry(syncStatus.total_projects, 0) : (summary ? formatTelemetry(summary.total_projects, 0) : '—'), sub: 'Project boards', icon: <Kanban className="h-4 w-4 text-indigo-500" />, accent: 'border-indigo-100/30 dark:border-indigo-950/40 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-400' },
          { label: 'Open Boards', tooltipKey: 'openBoards', value: summary?.open_projects ?? 0, sub: 'Active planning', icon: <Circle className="h-4 w-4 text-emerald-500" />, accent: 'border-emerald-100/30 dark:border-emerald-950/40 bg-emerald-50/40 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400' },
          { label: 'Closed Boards', tooltipKey: 'closedBoards', value: summary?.closed_projects ?? 0, sub: 'Archived boards', icon: <CheckCircle2 className="h-4 w-4 text-slate-400" />, accent: 'border-border bg-surface-soft/40 text-secondary' },
        ].map((card: any) => (
          <div key={card.label} className={`rounded-xl border p-4 shadow-sm flex items-center justify-between gap-3 ${card.accent}`}>
            <div className="space-y-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted block">{card.label}</span>
              <span className="text-2xl font-black tracking-tight leading-none text-primary block">{card.value}</span>
              <span className="text-[9px] font-semibold text-muted block">{card.sub}</span>
            </div>
            <div className="flex items-center gap-2">
              {card.tooltipKey ? (
                <Tooltip
                  content={METRIC_TOOLTIPS[card.tooltipKey as keyof typeof METRIC_TOOLTIPS]}
                  position="left"
                  showIcon={false}
                >
                  <div className="p-2 bg-surface-soft rounded-lg border border-border shadow-sm shrink-0 cursor-help">
                    {card.icon}
                  </div>
                </Tooltip>
              ) : (
                <div className="p-2 bg-surface-soft rounded-lg border border-border shadow-sm shrink-0">
                  {card.icon}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
 
      {/* Main layout grid (Projects list) */}
      <div className="grid grid-cols-1 gap-6">
        
        {/* Projects list */}
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="mb-1">
            <h3 className="text-sm font-bold text-primary">Active Projects</h3>
          </div>
          <p className="text-[10px] text-muted font-semibold mb-4">Board progress tracking and task status</p>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {projects?.data?.map((p: any) => (
              <div key={p.number} className="rounded-xl border border-border bg-surface-soft/60 p-4 space-y-3 flex flex-col justify-between">
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-xs font-bold text-primary line-clamp-1" title={p.name}>{p.name}</h4>
                    <span className={`shrink-0 px-2 py-0.5 rounded text-[9px] font-bold border ${
                      p.state === 'open'
                        ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                        : 'bg-surface-soft border-border text-muted'
                    }`}>
                      {p.state}
                    </span>
                  </div>
                  <p className="text-[9px] font-semibold text-muted font-mono">by {p.creator ?? 'System'} · {p.project_type}</p>
                </div>
 
                <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                  {[['Total', p.items_count ?? 0], ['Open', p.open_items ?? 0], ['Done', p.closed_items ?? 0]].map(([l, v]) => (
                    <div key={String(l)} className="bg-surface border border-border rounded-lg py-1">
                      <p className="font-bold text-primary">{v}</p>
                      <p className="text-[8px] font-bold text-muted uppercase">{l}</p>
                    </div>
                  ))}
                </div>
 
                {p.items_count > 0 && (
                  <div className="space-y-1 pt-1">
                    <div className="flex justify-between text-[9px] font-semibold text-secondary">
                      <span>Completion Rate</span>
                      <span className="font-bold text-primary">{Math.round((p.closed_items / p.items_count) * 100)}%</span>
                    </div>
                    <div className="h-1.5 bg-background rounded-full overflow-hidden">
                      <div className="h-full bg-emerald-500 rounded-full transition-all"
                        style={{ width: `${Math.min(100, Math.round((p.closed_items / p.items_count) * 100))}%` }} />
                    </div>
                  </div>
                )}
              </div>
            ))}
            {!projects?.data?.length && (
              <div className="col-span-2 py-10 text-center text-muted text-xs font-semibold">No active projects found</div>
            )}
          </div>
 
          {projects?.pages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
              <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">&larr; Prev</button>
              <span className="text-xs text-secondary">Page <span className="font-bold text-primary">{page}</span> of <span className="font-bold text-primary">{projects?.pages}</span></span>
              <button disabled={page >= projects?.pages} onClick={() => setPage(p => p + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">Next &rarr;</button>
            </div>
          )}
        </div>
 
      </div>
 
    </div>
  )
}
