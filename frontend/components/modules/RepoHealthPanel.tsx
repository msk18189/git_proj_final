'use client'
 
import { useEffect, useState } from 'react'
import { Heart, Shield, Zap, GitPullRequest, CircleDot, GitBranch, MessageCircle, AlertTriangle, CheckCircle, Info, Loader2, ShieldAlert } from 'lucide-react'
import { motion } from 'framer-motion'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts'
import { getRepoHealth } from '@/lib/api'
import { useTheme } from '@/components/ThemeProvider'
import { Tooltip } from '@/components/ui/Tooltip'
import { METRIC_TOOLTIPS } from '@/lib/tooltips'
 
interface Props { repoId: number; repoLabel: string }
 
const gradeColors: Record<string, string> = {
  A: 'text-emerald-600 dark:text-emerald-450',
  B: 'text-indigo-650 dark:text-indigo-400',
  C: 'text-amber-600 dark:text-amber-400',
  D: 'text-orange-600 dark:text-orange-400',
  F: 'text-rose-600 dark:text-rose-455',
}
 
const gradeRing: Record<string, string> = {
  A: 'border-emerald-250 bg-emerald-50 text-emerald-700 dark:border-emerald-800/40 dark:bg-emerald-950/20 dark:text-emerald-450',
  B: 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-800/40 dark:bg-indigo-950/20 dark:text-indigo-450',
  C: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/40 dark:bg-amber-950/20 dark:text-amber-450',
  D: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800/40 dark:bg-orange-950/20 dark:text-orange-450',
  F: 'border-rose-250 bg-rose-50 text-rose-700 dark:border-rose-800/40 dark:bg-rose-950/20 dark:text-rose-450',
}
 
const componentIcons: Record<string, React.ReactNode> = {
  pull_requests: <GitPullRequest className="h-3.5 w-3.5" />,
  ci_cd: <Zap className="h-3.5 w-3.5" />,
  branches: <GitBranch className="h-3.5 w-3.5" />,
  issues: <CircleDot className="h-3.5 w-3.5" />,
  community: <MessageCircle className="h-3.5 w-3.5" />,
  visibility: <Shield className="h-3.5 w-3.5" />,
}
 
const componentMaxes: Record<string, number> = {
  pull_requests: 20, ci_cd: 25, branches: 15, issues: 20, community: 10, visibility: 10,
}

// Map component keys to tooltip content
const componentTooltips: Record<string, keyof typeof METRIC_TOOLTIPS> = {
  pull_requests: 'pullRequestsScore',
  ci_cd: 'cicdScore',
  branches: 'branchesScore',
  issues: 'issuesScore',
  community: 'communityScore',
  visibility: 'visibilityScore',
}
 
function ScoreBar({ name, score, max, tooltip }: { name: string; score: number; max: number; tooltip?: any }) {
  const pct = max > 0 ? (score / max) * 100 : 0
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 55 ? 'bg-indigo-500' : pct >= 35 ? 'bg-amber-500' : 'bg-rose-500'
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 w-32 shrink-0 text-xs font-semibold text-secondary">
        {tooltip ? (
          <Tooltip content={tooltip} position="right" showIcon={false}>
            <span className="text-muted cursor-help">{componentIcons[name]}</span>
          </Tooltip>
        ) : (
          <span className="text-muted">{componentIcons[name]}</span>
        )}
        <span className="capitalize">{name.replace('_', ' ')}</span>
      </div>
      <div className="flex-1 h-2 bg-background rounded-full overflow-hidden">
        <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`h-full rounded-full ${color}`} />
      </div>
      <span className="text-xs font-bold text-primary w-16 text-right">{score} / {max}</span>
    </div>
  )
}
 
export default function RepoHealthPanel({ repoId, repoLabel }: Props) {
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const { isDark } = useTheme()
 
  useEffect(() => {
    setLoading(true)
    getRepoHealth(repoId).then(setHealth).catch(console.error).finally(() => setLoading(false))
  }, [repoId])
 
  const grade = health?.grade ?? '—'
  const score = health?.score ?? 0
  const components = health?.components ?? {}
 
  const radarData = Object.entries(components).map(([key, val]) => ({
    subject: key.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
    score: val as number,
    max: componentMaxes[key] ?? 20,
  }))
 
  const getRecommendations = () => {
    const recs = []
    if (components.branches !== undefined && components.branches < 10) {
      recs.push({ text: 'Prune stale or inactive branches to optimize git fetches and branches health.', type: 'warning' })
    }
    if (components.ci_cd !== undefined && components.ci_cd < 18) {
      recs.push({ text: 'Address flaky workflow tests in your main CI pipeline to improve pipeline stability.', type: 'critical' })
    }
    if (components.pull_requests !== undefined && components.pull_requests < 14) {
      recs.push({ text: 'Resolve stale Pull Requests that have been open for over 30 days.', type: 'warning' })
    }
    if (components.community !== undefined && components.community < 7) {
      recs.push({ text: 'Balance code review workloads: currently one contributor handles >50% of merges.', type: 'info' })
    }
    if (recs.length === 0) {
      recs.push({ text: 'Repository meets all standard engineering KPIs. Keep up the clean git state!', type: 'success' })
    }
    return recs
  }
 
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin h-8 w-8 text-indigo-600 dark:text-indigo-400" />
      </div>
    )
  }
 
  const recommendations = getRecommendations()
 
  // Theme-aware radar color configurations
  const gridStroke = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(100, 116, 139, 0.25)'
  const labelFill = isDark ? '#cbd5e1' : '#64748b'
  const radarFill = '#6366f1'
 
  return (
    <div className="space-y-6">
 
      {/* Main Score overview layout */}
      <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-border bg-surface p-6 flex flex-col lg:flex-row items-center gap-8 shadow-sm">
        
        {/* Large Grade Circle */}
        <div className={`flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-4 shadow-sm ${gradeRing[grade] ?? gradeRing.F}`}>
          <div className="text-center">
            <p className={`text-5xl font-black ${gradeColors[grade] ?? 'text-muted'}`}>{grade}</p>
            <p className="text-[10px] font-bold text-slate-500 dark:text-slate-400 mt-0.5 uppercase tracking-wider">{score}/100 Score</p>
          </div>
        </div>
 
        {/* Detailed stats bars */}
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-primary uppercase tracking-wider">Repository Health breakdown</h2>
          </div>
          <p className="text-xs text-muted font-semibold">{repoLabel}</p>
          <div className="space-y-2.5">
            {Object.entries(components).map(([key, val]) => {
              const tooltipKey = componentTooltips[key]
              const tooltipContent = tooltipKey ? METRIC_TOOLTIPS[tooltipKey] : undefined
              return (
                <ScoreBar 
                  key={key} 
                  name={key} 
                  score={val as number} 
                  max={componentMaxes[key] ?? 20}
                  tooltip={tooltipContent}
                />
              )
            })}
          </div>
        </div>
 
        {/* Radar chart */}
        {radarData.length > 0 && (
          <div className="shrink-0 w-64 h-64 border border-border rounded-2xl bg-surface-soft/40 p-2">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius={75}>
                <PolarGrid stroke={gridStroke} />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 8, fontWeight: 700, fill: labelFill }} />
                <RechartsTooltip 
                  contentStyle={{ 
                    borderRadius: 12, 
                    border: '1px solid var(--border-primary)', 
                    backgroundColor: 'var(--bg-surface-elevated)',
                    color: 'var(--text-secondary)',
                    fontSize: 10 
                  }} 
                />
                <Radar name="Health Index" dataKey="score" stroke={radarFill} fill={radarFill} fillOpacity={isDark ? 0.15 : 0.25} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
      </motion.div>
 
      {/* Recommendations & metadata row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Recommendations block */}
        <div className="lg:col-span-2 rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2">
            <div>
              <h3 className="text-sm font-bold text-primary mb-1">Executive Recommendations</h3>
              <p className="text-[10px] text-muted font-semibold">Actionable suggestions to improve engineering metrics</p>
            </div>
          </div>
 
          <div className="space-y-2.5">
            {recommendations.map((rec, i) => (
              <div key={i} className={`flex items-start gap-2.5 p-3 rounded-xl border ${
                rec.type === 'critical' ? 'bg-rose-50 dark:bg-rose-950/20 border-rose-100 dark:border-rose-900/30 text-rose-900 dark:text-rose-300' :
                rec.type === 'warning' ? 'bg-amber-50 dark:bg-amber-950/20 border-amber-100 dark:border-amber-900/30 text-amber-900 dark:text-amber-300' :
                rec.type === 'success' ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-100 dark:border-emerald-900/30 text-emerald-900 dark:text-emerald-300' :
                'bg-blue-50 dark:bg-blue-950/20 border-blue-100 dark:border-blue-900/30 text-blue-900 dark:text-blue-300'
              }`}>
                {rec.type === 'critical' && <ShieldAlert className="h-4.5 w-4.5 text-rose-500 shrink-0 mt-0.5" />}
                {rec.type === 'warning' && <AlertTriangle className="h-4.5 w-4.5 text-amber-500 shrink-0 mt-0.5" />}
                {rec.type === 'success' && <CheckCircle className="h-4.5 w-4.5 text-emerald-500 shrink-0 mt-0.5" />}
                {rec.type === 'info' && <Info className="h-4.5 w-4.5 text-blue-500 shrink-0 mt-0.5" />}
                <p className="text-xs leading-relaxed font-semibold">{rec.text}</p>
              </div>
            ))}
          </div>
        </div>
 
        {/* Metadata info cards list */}
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm space-y-4">
          <div>
            <h3 className="text-sm font-bold text-primary">Repository Details</h3>
          </div>
          <div className="space-y-3">
            {[
              { label: 'Visibility', value: health?.visibility ?? '—', icon: <Shield className="h-4 w-4 text-indigo-500" /> },
              { label: 'Sync Status', value: health?.sync_status ?? '—', icon: <Heart className="h-4 w-4 text-rose-500" /> },
              { label: 'Last Synced', value: health?.last_synced ? new Date(health.last_synced).toLocaleDateString() : 'Never', icon: <Zap className="h-4 w-4 text-amber-500" /> },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 p-3 bg-surface-soft dark:bg-slate-900/30 border border-border dark:border-slate-800/80 rounded-xl">
                <div className="p-1.5 bg-surface dark:bg-slate-800 border border-border dark:border-slate-700 rounded-lg shrink-0 text-muted shadow-sm">
                  {item.icon}
                </div>
                <div>
                  <p className="text-[10px] font-bold text-muted uppercase tracking-wider leading-none mb-1">{item.label}</p>
                  <p className="text-xs font-bold text-primary capitalize leading-none">{item.value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
 
      </div>
 
    </div>
  )
}
