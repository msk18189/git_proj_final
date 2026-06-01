'use client'
 
import { useState, useEffect } from 'react'
import { MessageCircle, CheckCircle2, ThumbsUp, Users, Percent, Activity, ExternalLink, Calendar } from 'lucide-react'
import { motion } from 'framer-motion'
import { AreaChart, Area, XAxis, YAxis, Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
import { getDiscussionsAnalytics, getDiscussions, getDiscussionsTimeline } from '@/lib/api'
import { formatTelemetry } from '@/lib/format'
 
interface Props { repoId: number; syncStatus?: any }
 
export default function DiscussionsPanel({ repoId, syncStatus }: Props) {
  const [summary, setSummary] = useState<any>(null)
  const [discussions, setDiscussions] = useState<any>(null)
  const [timeline, setTimeline] = useState<any>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getDiscussionsAnalytics(repoId).then(setSummary).catch(console.error),
      getDiscussionsTimeline(repoId).then(setTimeline).catch(console.error)
    ]).finally(() => setLoading(false))
    getDiscussions(repoId, page).then(setDiscussions).catch(console.error)
  }, [repoId, page])
 
 
 
  // Use real timeline data or empty array
  const activityData = timeline?.timeline && timeline.timeline.length > 0 
    ? timeline.timeline 
    : []

  return (
    <div className="space-y-6">

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: 'Total Discussions', tooltipKey: 'totalDiscussions', value: syncStatus ? formatTelemetry(syncStatus.total_discussions, 0) : (summary ? formatTelemetry(summary.total_discussions, 0) : '—'), sub: 'Threads created', icon: <MessageCircle className="h-4 w-4 text-indigo-500" />, accent: 'border-indigo-100/30 dark:border-indigo-950/40 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-800 dark:text-indigo-400' },
          { label: 'Open Discussions', tooltipKey: 'openDiscussions', value: (summary?.open_discussions ?? 0).toLocaleString(), sub: 'Active threads', icon: <MessageCircle className="h-4 w-4 text-emerald-500" />, accent: 'border-emerald-100/30 dark:border-emerald-950/40 bg-emerald-50/40 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-400' },
          { label: 'Answered', tooltipKey: 'answeredDiscussions', value: (summary?.answered_discussions ?? 0).toLocaleString(), sub: 'Resolved threads', icon: <CheckCircle2 className="h-4 w-4 text-purple-500" />, accent: 'border-purple-100/30 dark:border-purple-950/40 bg-purple-50/40 dark:bg-purple-950/20 text-purple-800 dark:text-purple-400' },
          { label: 'Answer Rate', tooltipKey: 'answerRate', value: `${summary?.answer_rate ?? 0}%`, sub: 'Backlog solved %', icon: <Percent className="h-4 w-4 text-violet-500" />, accent: 'border-violet-100/30 dark:border-violet-950/40 bg-violet-50/40 dark:bg-violet-950/20 text-violet-800 dark:text-violet-400' },
          { label: 'Avg Comments', tooltipKey: 'avgComments', value: summary?.avg_comments ?? 0, sub: 'Engagement depth', icon: <MessageCircle className="h-4 w-4 text-amber-500" />, accent: 'border-amber-100/30 dark:border-amber-950/40 bg-amber-50/40 dark:bg-amber-950/20 text-amber-800 dark:text-amber-400' },
          { label: 'Avg Reactions', tooltipKey: 'avgReactions', value: summary?.avg_reactions ?? 0, sub: 'Sentiment rating', icon: <ThumbsUp className="h-4 w-4 text-rose-500" />, accent: 'border-rose-100/30 dark:border-rose-950/40 bg-rose-50/40 dark:bg-rose-950/20 text-rose-800 dark:text-rose-400' },
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
 
      {/* Activity Timeline */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="mb-4">
          <h3 className="text-sm font-bold text-primary">Discussion Activity</h3>
          <p className="text-[10px] text-muted font-semibold">Active threads timeline over time</p>
        </div>
        
        {activityData.length === 0 ? (
          <div className="h-[180px] flex items-center justify-center text-sm text-muted">
            No discussion data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={activityData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
              <defs>
                <linearGradient id="discGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" vertical={false} />
              <XAxis dataKey="date" stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <YAxis stroke="var(--border-primary)" tick={{ fontSize: 9, fontWeight: 600, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
              <RechartsTooltip contentStyle={{ borderRadius: 12, border: '1px solid var(--border-primary)', backgroundColor: 'var(--bg-surface-elevated)', color: 'var(--text-primary)', fontSize: 11 }} />
              <Area type="monotone" dataKey="activity" name="Discussions" stroke="#6366f1" strokeWidth={2.5} fill="url(#discGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Discussion list */}
      <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <h3 className="text-sm font-bold text-primary">Discussions Workspace</h3>
        </div>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-surface-soft">
                {['#', 'Title', 'Category', 'Author', 'Status', 'Comments', 'Resolved'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] font-bold uppercase tracking-wider text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-muted">
              {discussions?.data?.map((d: any) => (
                <tr key={d.number} className="hover:bg-bg-hover/40 transition">
                  <td className="px-4 py-2.5 font-mono text-muted">#{d.number}</td>
                  <td className="px-4 py-2.5 max-w-[220px]">
                    <span className="text-primary font-bold line-clamp-1 flex items-center gap-1">
                      {d.title}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-secondary">
                    <span className="px-2 py-0.5 rounded bg-surface-soft text-secondary border border-border text-[10px] font-semibold">{d.category || 'General'}</span>
                  </td>
                  <td className="px-4 py-2.5 text-secondary font-semibold">{d.author}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                      d.state === 'OPEN'
                        ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/30 text-emerald-700 dark:text-emerald-450'
                        : 'bg-surface-soft border-border text-muted'
                    }`}>{d.state}</span>
                  </td>
                  <td className="px-4 py-2.5 text-secondary font-bold">{d.comment_count}</td>
                  <td className="px-4 py-2.5">
                    {d.answer_chosen ? (
                      <span className="inline-flex items-center gap-1 text-[10px] bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 font-bold border border-emerald-250 dark:border-emerald-900/30 px-2 py-0.5 rounded-full">
                        <CheckCircle2 className="h-3 w-3 shrink-0" /> Answered
                      </span>
                    ) : <span className="text-muted">—</span>}
                  </td>
                </tr>
              ))}
              {!discussions?.data?.length && (
                <tr><td colSpan={7} className="py-10 text-center text-muted text-sm">No discussions found</td></tr>
              )}
            </tbody>
          </table>
        </div>
 
        {/* Pagination */}
        {discussions?.pages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">&larr; Prev</button>
            <span className="text-xs text-secondary">Page <span className="font-bold text-primary">{page}</span> of <span className="font-bold text-primary">{discussions?.pages}</span></span>
            <button disabled={page >= discussions?.pages} onClick={() => setPage(p => p + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-semibold text-secondary transition hover:bg-bg-hover disabled:pointer-events-none disabled:opacity-40">Next &rarr;</button>
          </div>
        )}
      </div>
 
    </div>
  )
}
