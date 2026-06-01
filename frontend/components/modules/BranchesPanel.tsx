'use client'
 
import { useState, useEffect } from 'react'
import { GitBranch, Shield, Clock, Activity, AlertTriangle, ChevronRight, RefreshCw, GitFork, BookOpen } from 'lucide-react'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
import { getBranchesAnalytics, getBranches } from '@/lib/api'
 
interface Props { repoId: number }
 
const FILTERS = ['all', 'active', 'inactive', 'stale', 'protected'] as const
 
const statusColors: Record<string, string> = {
  active: 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-250 dark:border-emerald-900/30 text-emerald-700 dark:text-emerald-400 font-bold',
  inactive: 'bg-amber-50 dark:bg-amber-950/20 border-amber-250 dark:border-amber-900/30 text-amber-700 dark:text-amber-400 font-bold',
  stale: 'bg-rose-50 dark:bg-rose-950/20 border-rose-250 dark:border-rose-900/30 text-rose-700 dark:text-rose-400 font-bold',
  unknown: 'bg-surface-soft border-border text-muted',
}
 
export default function BranchesPanel({ repoId }: Props) {
  const [summary, setSummary] = useState<any>(null)
  const [branches, setBranches] = useState<any>(null)
  const [filter, setFilter] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
 
  useEffect(() => {
    setLoading(true)
    getBranchesAnalytics(repoId).then(setSummary).catch(console.error).finally(() => setLoading(false))
  }, [repoId])
 
  useEffect(() => {
    getBranches(repoId, page, 20, filter).then(setBranches).catch(console.error)
  }, [repoId, page, filter])
 
  // Activity-only chart — Protected is independent metadata, not an activity state
  const chartData = summary ? [
    { name: 'Active', count: summary.active_branches ?? 0, color: '#10b981' },
    { name: 'Inactive', count: summary.inactive_branches ?? 0, color: '#f59e0b' },
    { name: 'Stale', count: summary.stale_branches ?? 0, color: '#ef4444' },
  ] : []
 
  return (
    <div className="space-y-6">
 
      {/* KPI row — 5 cards: Total, Active, Inactive, Stale, Protected */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {[
          { label: 'Total Branches', tooltipKey: 'totalBranches', value: summary?.total_branches ?? 0, sub: 'Repository total', icon: <GitBranch className="h-4 w-4 text-indigo-500" />, accent: 'border-indigo-100/30 dark:border-indigo-950/40 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-400' },
          { label: 'Active', tooltipKey: 'activeBranches', value: summary?.active_branches ?? 0, sub: 'Last commit ≤ 30 days', icon: <Activity className="h-4 w-4 text-emerald-500" />, accent: 'border-emerald-100/30 dark:border-emerald-950/40 bg-emerald-50/40 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400' },
          { label: 'Inactive', tooltipKey: 'inactiveBranches', value: summary?.inactive_branches ?? 0, sub: 'Last commit 31–89 days', icon: <Clock className="h-4 w-4 text-amber-500" />, accent: 'border-amber-100/30 dark:border-amber-950/40 bg-amber-50/40 dark:bg-amber-950/20 text-amber-800 dark:text-amber-400' },
          { label: 'Stale', tooltipKey: 'staleBranches', value: summary?.stale_branches ?? 0, sub: 'Last commit ≥ 90 days', icon: <AlertTriangle className="h-4 w-4 text-rose-500" />, accent: 'border-rose-100/30 dark:border-rose-950/40 bg-rose-50/40 dark:bg-rose-950/20 text-rose-800 dark:text-rose-400' },
          { label: 'Protected', tooltipKey: 'protectedBranches', value: summary?.protected_branches ?? 0, sub: 'Merge rules apply', icon: <Shield className="h-4 w-4 text-purple-500" />, accent: 'border-purple-100/30 dark:border-purple-950/40 bg-purple-50/40 dark:bg-purple-950/20 text-purple-800 dark:text-purple-400' },
        ].map((card: any) => (
          <div key={card.label} className={`rounded-xl border p-4 shadow-sm flex flex-col justify-between gap-1.5 ${card.accent}`}>
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-muted">{card.label}</span>
              <div className="flex items-center gap-2">
                {card.tooltipKey ? (
                  <Tooltip
                    content={METRIC_TOOLTIPS[card.tooltipKey as keyof typeof METRIC_TOOLTIPS]}
                    position="left"
                    showIcon={false}
                  >
                    <span className="cursor-help p-0.5 flex items-center">{card.icon}</span>
                  </Tooltip>
                ) : (
                  card.icon
                )}
              </div>
            </div>
            <div className="space-y-0.5">
              <span className="text-xl font-black tracking-tight leading-none text-primary block">{typeof card.value === 'number' ? card.value.toLocaleString() : card.value}</span>
              <span className="text-[9px] font-semibold text-muted">{card.sub}</span>
            </div>
          </div>
        ))}
      </div>
 
      {/* Branch Activity Breakdown chart — Active / Inactive / Stale only */}
      {summary && summary.total_branches > 0 && (
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="mb-1">
            <h3 className="text-sm font-bold text-primary">Branch Activity Breakdown</h3>
          </div>
          <p className="text-[10px] text-muted font-semibold mb-4">Active · Inactive · Stale — mutually exclusive by last commit date</p>
          
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <YAxis stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <RechartsTooltip contentStyle={{ borderRadius: 12, border: '1px solid var(--border-primary)', backgroundColor: 'var(--bg-surface-elevated)', color: 'var(--text-primary)', fontSize: 11 }} />
              <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
 
      {/* Branch list */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="text-sm font-bold text-primary">Branch List</h3>
          <div className="flex gap-1.5">
            {FILTERS.map(f => (
              <button key={f} onClick={() => { setFilter(f); setPage(1) }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold capitalize transition-all border ${
                  filter === f 
                    ? 'bg-orange-50 dark:bg-orange-950/20 text-[#c2410c] dark:text-orange-455 border-[#fce6d8] dark:border-orange-950/30' 
                    : 'text-secondary hover:text-primary bg-surface-soft border-border hover:bg-bg-hover'
                }`}>
                {f}
              </button>
            ))}
          </div>
        </div>
 
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-soft">
                {['Branch', 'Status', 'Protected', 'Last Commit Message', 'Author', 'Days Stale'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wider text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-muted">
              {branches?.data?.map((b: any) => (
                <tr key={b.name} className="hover:bg-bg-hover/40 transition">
                  <td className="px-4 py-2.5 font-mono text-primary text-xs font-bold max-w-[200px] truncate">
                    <div className="flex items-center gap-1.5">
                      <GitBranch className="h-3.5 w-3.5 text-muted shrink-0" />
                      <span>{b.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusColors[b.status] ?? statusColors.unknown}`}>
                      {b.status ?? '—'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {b.protected ? (
                      <span className="inline-flex items-center gap-1 text-[10px] bg-purple-50 dark:bg-purple-950/20 text-purple-750 dark:text-purple-400 font-bold border border-purple-200 dark:border-purple-900/30 px-2 py-0.5 rounded-full">
                        <Shield className="h-3 w-3 shrink-0" /> Yes
                      </span>
                    ) : <span className="text-muted">—</span>}
                  </td>
                  <td className="px-4 py-2.5 text-secondary text-xs max-w-[220px] truncate" title={b.last_commit_message}>{b.last_commit_message || '—'}</td>
                  <td className="px-4 py-2.5 text-secondary text-xs font-semibold">{b.last_commit_author || '—'}</td>
                  <td className="px-4 py-2.5 text-secondary text-xs font-bold">{b.staleness_days ?? '—'}</td>
                </tr>
              ))}
              {!branches?.data?.length && (
                <tr><td colSpan={6} className="py-10 text-center text-muted text-sm">No branches found</td></tr>
              )}
            </tbody>
          </table>
        </div>
 
        {/* Pagination */}
        {branches?.pages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">&larr; Prev</button>
            <span className="text-xs text-secondary">Page <span className="font-bold text-primary">{page}</span> of <span className="font-bold text-primary">{branches?.pages}</span></span>
            <button disabled={page >= branches?.pages} onClick={() => setPage(p => p + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">Next &rarr;</button>
          </div>
        )}
      </div>
 
    </div>
  )
}
