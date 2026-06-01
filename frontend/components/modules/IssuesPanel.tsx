'use client'
 
import { useState, useEffect } from 'react'
import { CircleDot, Bug, Clock, TrendingDown, AlertTriangle, ChevronRight, Activity, Shield, Users, Inbox, CheckCircle2 } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell, Legend } from 'recharts'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
import { getIssuesAnalytics, getIssues, getStaleIssues } from '@/lib/api'
import { formatTelemetry } from '@/lib/format'

interface Props { repoId: number; syncStatus?: any }
 
const TABS = ['All Issues', 'Stale Issues'] as const
type Tab = typeof TABS[number]
 
export default function IssuesPanel({ repoId, syncStatus }: Props) {
  const [analytics, setAnalytics] = useState<any>(null)
  const [issues, setIssues] = useState<any>(null)
  const [stale, setStale] = useState<any>(null)
  const [tab, setTab] = useState<Tab>('All Issues')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [sortField, setSortField] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')
  const [loading, setLoading] = useState(true)
 
  useEffect(() => {
    setLoading(true)
    Promise.all([getIssuesAnalytics(repoId), getIssues(repoId, 1), getStaleIssues(repoId)])
      .then(([a, i, s]) => { setAnalytics(a); setIssues(i); setStale(s) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [repoId])
 
  useEffect(() => {
    if (tab === 'All Issues') {
      getIssues(repoId, page, 20, 'all', undefined, search, sortField, sortDir).then(setIssues).catch(console.error)
    } else {
      getStaleIssues(repoId, 30, page, 20, search, sortField, sortDir).then(setStale).catch(console.error)
    }
  }, [page, tab, repoId, search, sortField, sortDir])
 
  const summary = analytics?.summary
  const velocity = analytics?.velocity || []
 
  const priorityData = analytics?.priority || [
    { name: 'Critical', value: 0, color: '#ef4444' },
    { name: 'High', value: 0, color: '#f97316' },
    { name: 'Medium', value: 0, color: '#f59e0b' },
    { name: 'Low', value: 0, color: '#10b981' },
  ]
 
  const heatmapData = analytics?.heatmap || Array.from({ length: 371 }).map(() => ({ count: 0 }))
 
  // Issue Heatmap columns
  const heatmapMonths = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
 
  return (
    <div className="space-y-6">
 
      {/* KPI cards strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Total Issues', tooltipKey: 'totalIssues', value: syncStatus ? formatTelemetry(syncStatus.synced_issues || syncStatus.total_issues, syncStatus.expected_issues) : (summary ? formatTelemetry(summary.synced_issues || summary.total_issues, summary.expected_issues) : '—'), sub: 'All time', icon: <CircleDot className="h-4 w-4 text-indigo-500" />, accent: 'border-indigo-100/30 dark:border-indigo-950/40 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-400' },
          { label: 'Open Issues', tooltipKey: 'openIssues', value: summary ? (summary.open_issues ?? Math.max(0, (summary.total_issues || 0) - (summary.closed_issues || 0))).toLocaleString() : '—', sub: 'Active backlog', icon: <CircleDot className="h-4 w-4 text-orange-500" />, accent: 'border-orange-100/30 dark:border-orange-950/40 bg-orange-50/40 dark:bg-orange-950/20 text-orange-850 dark:text-orange-400' },
          { label: 'Closed Issues', tooltipKey: 'closedIssues', value: summary ? (summary.closed_issues ?? 0).toLocaleString() : '—', sub: 'Completed task', icon: <CheckCircle2 className="h-4 w-4 text-emerald-500" />, accent: 'border-emerald-100/30 dark:border-emerald-950/40 bg-emerald-50/40 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400' },
          { label: 'Stale (30d+)', tooltipKey: 'staleIssues', value: summary ? (summary.stale_issues ?? 0).toLocaleString() : '—', sub: 'Needs attention', icon: <AlertTriangle className="h-4 w-4 text-amber-500" />, accent: 'border-amber-100/30 dark:border-amber-950/40 bg-amber-50/40 dark:bg-amber-950/20 text-amber-800 dark:text-amber-400' },
          { label: 'Bug Reports', tooltipKey: 'bugReports', value: summary ? (summary.bug_count ?? 0).toLocaleString() : '—', sub: 'Severity bugs', icon: <Bug className="h-4 w-4 text-rose-500" />, accent: 'border-rose-100/30 dark:border-rose-950/40 bg-rose-50/40 dark:bg-rose-950/20 text-rose-800 dark:text-rose-400' },
          { label: 'Avg Resolution', tooltipKey: 'avgResolutionTime', value: summary ? `${summary.avg_resolution_days ?? 0}d` : '—', sub: 'Backlog cycle time', icon: <Clock className="h-4 w-4 text-purple-500" />, accent: 'border-purple-100/30 dark:border-purple-950/40 bg-purple-50/40 dark:bg-purple-950/20 text-purple-800 dark:text-purple-400' },
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
 
      {/* Asymmetric charts section (Trend, Donut, Heatmap) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Trend Chart (Line Chart) */}
        <div className="lg:col-span-2 rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-primary">Issue Trend</h3>
          </div>
          <p className="text-[10px] text-muted font-semibold mb-3">Backlog growth: Opened vs Closed issues</p>
          {velocity.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={velocity} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" vertical={false} />
                <XAxis dataKey="month" stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <YAxis stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                <RechartsTooltip contentStyle={{ borderRadius: 12, border: '1px solid var(--border-primary)', backgroundColor: 'var(--bg-surface-elevated)', color: 'var(--text-primary)', fontSize: 11 }} />
                <Legend verticalAlign="top" height={36} iconSize={8} wrapperStyle={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)' }} />
                <Line type="monotone" dataKey="opened" name="Opened" stroke="#f97316" strokeWidth={2.5} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="closed" name="Closed" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted">No trend data available</div>
          )}
        </div>
 
        {/* Priority Donut chart */}
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="mb-1">
              <h3 className="text-sm font-bold text-primary">Issues by Priority</h3>
            </div>
            <p className="text-[10px] text-muted font-semibold">Priority distribution for open issues</p>
          </div>
 
          <div className="flex items-center justify-between gap-4 py-2">
            <ResponsiveContainer width="45%" height={110}>
              <PieChart>
                <Pie
                  data={priorityData}
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={42}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {priorityData.map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1 text-[11px] font-semibold text-secondary">
              {priorityData.map((item: any) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                    <span>{item.name}</span>
                  </div>
                  <span className="font-bold text-primary">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
 
      </div>
 
      {/* Heatmap block */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="mb-1">
          <h3 className="text-sm font-bold text-primary">Issue Heatmap</h3>
        </div>
        <p className="text-[10px] text-muted font-semibold mb-4">Backlog activity mapped by day of the week</p>
        
        <div className="flex flex-col">
          {/* Months Header Row */}
          <div className="flex gap-2 text-[10px] font-semibold text-muted mb-2">
            {/* Spacer matching days column width */}
            <div className="w-8 shrink-0" />
            {/* Months labels */}
            <div className="flex-1 flex justify-between px-1">
              {heatmapMonths.map(m => <span key={m}>{m}</span>)}
            </div>
          </div>

          {/* Grid Area Row */}
          <div className="flex gap-2">
            {/* Days column */}
            <div className="w-8 shrink-0 grid grid-rows-7 gap-1 text-[9px] font-semibold text-muted pr-1">
              <span className="h-2 flex items-center justify-end leading-none" />
              <span className="h-2 flex items-center justify-end leading-none">Mon</span>
              <span className="h-2 flex items-center justify-end leading-none" />
              <span className="h-2 flex items-center justify-end leading-none">Wed</span>
              <span className="h-2 flex items-center justify-end leading-none" />
              <span className="h-2 flex items-center justify-end leading-none">Fri</span>
              <span className="h-2 flex items-center justify-end leading-none" />
            </div>
            {/* Calendar grids */}
            <div className="flex-1 grid grid-rows-7 gap-1 grid-flow-col" style={{ gridTemplateColumns: 'repeat(53, minmax(0, 1fr))' }}>
              {(analytics?.heatmap || Array.from({ length: 371 }).fill(0)).map((entry: any, i: number) => {
                const count = typeof entry === 'number' ? entry : (entry?.count ?? 0)
                let level = 0
                if (count >= 6) level = 4
                else if (count >= 4) level = 3
                else if (count >= 2) level = 2
                else if (count >= 1) level = 1
                const levels = ['bg-slate-100', 'bg-emerald-200', 'bg-emerald-300', 'bg-emerald-500', 'bg-emerald-700']
                return (
                  <div key={i} className={`h-2 w-2 rounded-sm ${levels[level]}`} />
                )
              })}
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-1.5 mt-3 text-[10px] font-semibold text-muted">
          <span>Less</span>
          <div className="h-2 w-2 rounded-sm bg-slate-100" />
          <div className="h-2 w-2 rounded-sm bg-emerald-200" />
          <div className="h-2 w-2 rounded-sm bg-emerald-300" />
          <div className="h-2 w-2 rounded-sm bg-emerald-500" />
          <div className="h-2 w-2 rounded-sm bg-emerald-700" />
          <span>More</span>
        </div>
      </div>
 
      {/* Issues Table Panel */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex gap-1.5">
            {TABS.map(t => (
              <button key={t} onClick={() => { setTab(t); setPage(1) }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                  tab === t 
                    ? 'bg-orange-50 dark:bg-orange-950/20 text-[#c2410c] dark:text-orange-455 border-[#fce6d8] dark:border-orange-950/30' 
                    : 'text-secondary hover:text-primary bg-surface-soft border-border hover:bg-bg-hover'
                }`}>
                {t}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <input 
              type="text" 
              placeholder="Search issues..." 
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="px-3 py-1.5 text-xs rounded-lg border border-border bg-surface text-primary outline-none focus:border-indigo-500 w-48"
            />
            <select 
              value={`${sortField}-${sortDir}`} 
              onChange={e => {
                const [f, d] = e.target.value.split('-')
                setSortField(f)
                setSortDir(d)
                setPage(1)
              }}
              className="px-3 py-1.5 text-xs rounded-lg border border-border bg-surface text-primary outline-none focus:border-indigo-500"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="updated_at-desc">Recently Updated</option>
              <option value="comment_count-desc">Most Comments</option>
            </select>
          </div>
        </div>
 
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-soft">
                {['#', 'Title', 'State', 'Author', 'Age', 'Comments'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wider text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-muted">
              {(tab === 'All Issues' ? issues?.data : stale?.data)?.map((iss: any) => (
                <tr key={iss.number} className="group hover:bg-bg-hover/40 transition">
                  <td className="px-4 py-2.5 font-mono text-muted text-xs">#{iss.number}</td>
                  <td className="px-4 py-2.5 max-w-[280px]">
                    <span className="font-semibold text-primary text-xs line-clamp-1">{iss.title}</span>
                    {iss.is_bug && <span className="ml-1.5 text-[9px] px-1.5 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 text-rose-650 dark:text-rose-400 font-bold">bug</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      iss.state === 'open'
                        ? 'bg-orange-50 dark:bg-orange-950/20 text-orange-700 dark:text-orange-400 border border-orange-100 dark:border-orange-900/30'
                        : 'bg-surface-soft border-border text-muted'
                    }`}>
                      {iss.state}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-secondary text-xs">{iss.author}</td>
                  <td className="px-4 py-2.5 text-secondary text-xs font-bold">{iss.age_days}d</td>
                  <td className="px-4 py-2.5 text-secondary text-xs">{iss.comment_count}</td>
                </tr>
              ))}
              {!(tab === 'All Issues' ? issues?.data : stale?.data)?.length && (
                <tr><td colSpan={6} className="py-10 text-center text-muted text-sm">No issues found</td></tr>
              )}
            </tbody>
          </table>
        </div>
 
        {/* Pagination */}
        {(tab === 'All Issues' ? issues : stale)?.pages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
              className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">&larr; Prev</button>
            <span className="text-xs text-secondary">
              Page <span className="font-bold text-primary">{page}</span> of <span className="font-bold text-primary">{(tab === 'All Issues' ? issues : stale)?.pages}</span>
              {(tab === 'All Issues' ? issues : stale)?.total != null && (
                <span className="ml-2 text-muted">({(tab === 'All Issues' ? issues : stale)?.total.toLocaleString()} total)</span>
              )}
            </span>
            <button disabled={page >= (tab === 'All Issues' ? issues : stale)?.pages} onClick={() => setPage(p => p + 1)}
              className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">Next &rarr;</button>
          </div>
        )}
      </div>
 
    </div>
  )
}
