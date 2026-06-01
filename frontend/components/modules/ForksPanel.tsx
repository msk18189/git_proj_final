'use client'
 
import { useState, useEffect } from 'react'
import { GitFork, Star, Clock, Activity, TrendingUp, Users, Heart } from 'lucide-react'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
import { getForksAnalytics, getForks } from '@/lib/api'
import { formatTelemetry } from '@/lib/format'
 
interface Props { repoId: number; syncStatus?: any }
 
export default function ForksPanel({ repoId, syncStatus }: Props) {
  const [analytics, setAnalytics] = useState<any>(null)
  const [forks, setForks] = useState<any>(null)
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
 
  useEffect(() => {
    setLoading(true)
    getForksAnalytics(repoId).then(setAnalytics).catch(console.error).finally(() => setLoading(false))
  }, [repoId])
 
  useEffect(() => {
    getForks(repoId, page, 20, filter).then(setForks).catch(console.error)
  }, [repoId, page, filter])
 
  const summary = analytics?.summary
  const growth = analytics?.growth_trend ?? []
 
  return (
    <div className="space-y-6">
 
      {/* KPI stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Total Forks', tooltipKey: 'totalForks', value: syncStatus ? formatTelemetry(syncStatus.synced_forks || syncStatus.total_forks, syncStatus.expected_forks) : (summary ? formatTelemetry(summary.synced_forks || summary.total_forks, summary.expected_forks) : '—'), sub: 'Ecosystem paths', icon: <GitFork className="h-4 w-4 text-indigo-500" />, accent: 'border-indigo-100/30 dark:border-indigo-950/40 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-400' },
          { label: 'Active Forks', tooltipKey: 'activeForks', value: (summary?.active_forks ?? 0).toLocaleString(), sub: 'Pushes <= 30 days', icon: <Activity className="h-4 w-4 text-emerald-500" />, accent: 'border-emerald-100/30 dark:border-emerald-950/40 bg-emerald-50/40 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400' },
          { label: 'Stale Forks', tooltipKey: 'staleForks', value: (summary?.stale_forks ?? 0).toLocaleString(), sub: '90+ days inactive', icon: <Clock className="h-4 w-4 text-rose-500" />, accent: 'border-rose-100/30 dark:border-rose-950/40 bg-rose-50/40 dark:bg-rose-950/20 text-rose-800 dark:text-rose-400' },
          { label: 'Starred Forks', tooltipKey: 'starredForks', value: (summary?.starred_forks ?? 0).toLocaleString(), sub: 'Ecosystem stars', icon: <Star className="h-4 w-4 text-amber-500" />, accent: 'border-amber-100/30 dark:border-amber-950/40 bg-amber-50/40 dark:bg-amber-950/20 text-amber-800 dark:text-amber-400' },
          { label: 'Avg Fork Stars', tooltipKey: 'avgForkStars', value: summary?.avg_fork_stars ?? 0, sub: 'Popularity index', icon: <Star className="h-4 w-4 text-yellow-500" />, accent: 'border-yellow-100/30 dark:border-yellow-950/40 bg-yellow-50/40 dark:bg-yellow-950/20 text-yellow-800 dark:text-yellow-400' },
          { label: 'Adoption Rate', tooltipKey: 'adoptionRate', value: `${summary?.adoption_rate ?? 0}%`, sub: 'Active fork ratio', icon: <TrendingUp className="h-4 w-4 text-violet-500" />, accent: 'border-violet-100/30 dark:border-violet-950/40 bg-violet-50/40 dark:bg-violet-950/20 text-violet-800 dark:text-violet-400' },
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
              <span className="text-xl font-black tracking-tight leading-none text-primary block">{card.value}</span>
              <span className="text-[9px] font-semibold text-muted">{card.sub}</span>
            </div>
          </div>
        ))}
      </div>
 
      {/* Growth Trend & Geographic distribution */}
      <div className="grid grid-cols-1 gap-6">
        
        {/* Fork Growth Trend (Area Chart) */}
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="mb-1">
            <h3 className="text-sm font-bold text-primary">Fork Growth Trend</h3>
          </div>
          <p className="text-[10px] text-muted font-semibold mb-4">Growth metrics: new forks created per month</p>
          
          {growth.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={growth} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="forkGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" vertical={false} />
                <XAxis dataKey="month" stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <YAxis stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <RechartsTooltip contentStyle={{ borderRadius: 12, border: '1px solid var(--border-primary)', backgroundColor: 'var(--bg-surface-elevated)', color: 'var(--text-primary)', fontSize: 11 }} />
                <Area type="monotone" dataKey="new_forks" name="New Forks" stroke="#6366f1" strokeWidth={2.5} fill="url(#forkGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted">No trend data available</div>
          )}
        </div>
 
      </div>
 
      {/* Forks list */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <h3 className="text-sm font-bold text-primary">Forks Ecosystem</h3>
          </div>
          <div className="flex gap-1.5">
            {['all', 'active', 'stale'].map(f => (
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
                {['Fork Repository', 'Owner', 'Stars', 'Language', 'Activity Status', 'Last Push'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wider text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-muted">
              {forks?.data?.map((f: any) => (
                <tr key={f.full_name} className="hover:bg-bg-hover/40 transition">
                  <td className="px-4 py-2.5 font-mono text-primary font-bold max-w-[200px] truncate flex items-center gap-1.5">
                    <GitFork className="h-3.5 w-3.5 text-muted shrink-0" />
                    <span>{f.full_name}</span>
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{f.owner}</td>
                  <td className="px-4 py-2.5 text-secondary font-bold flex items-center gap-1">
                    <Star className="h-3 w-3 text-amber-500 fill-current" />
                    {f.stars}
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{f.language || '—'}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      f.activity === 'active'
                        ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/30 text-emerald-700 dark:text-emerald-450'
                        : 'bg-surface-soft border-border text-muted'
                    }`}>
                      {f.activity}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-muted text-[10px]">{f.pushed_at ? new Date(f.pushed_at).toLocaleDateString() : '—'}</td>
                </tr>
              ))}
              {!forks?.data?.length && (
                <tr><td colSpan={6} className="py-10 text-center text-muted text-sm">No forks found</td></tr>
              )}
            </tbody>
          </table>
        </div>
 
        {/* Pagination */}
        {forks?.pages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">&larr; Prev</button>
            <span className="text-xs text-secondary">Page <span className="font-bold text-primary">{page}</span> of <span className="font-bold text-primary">{forks?.pages}</span></span>
            <button disabled={page >= forks?.pages} onClick={() => setPage(p => p + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">Next &rarr;</button>
          </div>
        )}
      </div>
 
    </div>
  )
}
