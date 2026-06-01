'use client'

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { motion } from 'framer-motion'
import { CHART } from '@/lib/chartTheme'
import { PALETTE } from '@/lib/theme'
import { useTheme } from '@/components/ThemeProvider'

function useDynamicChartStyle() {
  const { isDark } = useTheme()
  
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(100, 116, 139, 0.15)'
  const axisColor = isDark ? '#334155' : '#e2e8f0'
  const textColor = isDark ? '#94a3b8' : '#64748b'
  
  const tooltipStyle = {
    backgroundColor: isDark ? '#0f1422' : '#ffffff',
    border: `1px solid ${isDark ? '#1e293d' : 'rgba(198, 123, 92, 0.25)'}`,
    borderRadius: '12px',
    boxShadow: isDark ? '0 12px 30px rgba(0, 0, 0, 0.4)' : '0 8px 24px rgba(15, 23, 42, 0.08)',
    padding: '10px 14px',
    color: isDark ? '#f8fafc' : '#1e293b',
    fontSize: '11px',
    fontWeight: 650,
  }
  
  const legendStyle = { 
    fontSize: 11, 
    color: isDark ? '#cbd5e1' : '#475569',
    marginTop: '10px'
  }
  
  return { gridColor, axisColor, textColor, tooltipStyle, legendStyle }
}

function EmptyChart({ title, message }: { title: string; message: string }) {
  return (
    <motion.div className="card card-hover flex h-[320px] flex-col items-center justify-center text-slate-400 dark:text-slate-500">
      <p className="section-title mb-1">{title}</p>
      <p className="text-sm">{message}</p>
    </motion.div>
  )
}

function ChartShell({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full">
      <h3 className="section-title">{title}</h3>
      {subtitle && <p className="section-subtitle mb-4">{subtitle}</p>}
      {!subtitle && <div className="mb-4" />}
      {children}
    </motion.div>
  )
}

const renderColorLegend = (value: string) => {
  const colors: Record<string, string> = {
    Created: CHART.created,
    Merged: CHART.merged,
    'Closed (unmerged)': CHART.closed,
    Closed: CHART.closed,
    'Merged PRs': CHART.line,
    'Total PRs': CHART.total,
  }
  const color = colors[value] || PALETTE.emerald.main
  return (
    <span style={{ color, fontWeight: 700, fontSize: 11 }} className="mr-3">{value}</span>
  )
}

export function MonthlyFlowChart({ data, isAnimationActive = true }: { data: any[], isAnimationActive?: boolean }) {
  const chartStyles = useDynamicChartStyle()
  const chartData = Array.isArray(data)
    ? data
    : Object.entries(data || {}).map(([month, flow]: [string, any]) => ({
        month,
        ...(typeof flow === 'object' ? flow : {}),
      }))

  if (!chartData.length) {
    return <EmptyChart title="Monthly PR Flow" message="No PR activity in the selected period." />
  }

  return (
    <ChartShell title="Monthly PR Flow" subtitle="Created · Merged · Closed — each in a distinct color">
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartStyles.gridColor} vertical={false} />
          <XAxis dataKey="month" stroke={chartStyles.axisColor} tick={{ fontSize: 10, fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
          <YAxis stroke={chartStyles.axisColor} allowDecimals={false} tick={{ fontSize: 10, fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={chartStyles.tooltipStyle} cursor={{ fill: 'rgba(148, 163, 184, 0.05)' }} />
          <Legend wrapperStyle={chartStyles.legendStyle} formatter={renderColorLegend} iconType="circle" iconSize={6} />
          <Bar dataKey="created" name="Created" fill={CHART.created} radius={[4, 4, 0, 0]} isAnimationActive={isAnimationActive} />
          <Bar dataKey="merged" name="Merged" fill={CHART.merged} radius={[4, 4, 0, 0]} isAnimationActive={isAnimationActive} />
          <Bar dataKey="closed" name="Closed (unmerged)" fill={CHART.closed} radius={[4, 4, 0, 0]} isAnimationActive={isAnimationActive} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function ThroughputChart({ data, isAnimationActive = true }: { data: any[] | Record<string, number>, isAnimationActive?: boolean }) {
  const chartStyles = useDynamicChartStyle()
  const { isDark } = useTheme()
  const chartData = Array.isArray(data)
    ? data
    : Object.entries(data || {})
        .map(([week, count]) => ({ week, prs: count }))
        .sort((a, b) => a.week.localeCompare(b.week))

  if (!chartData.length) {
    return <EmptyChart title="PR Throughput" message="No merged PRs in the last 8 weeks." />
  }

  return (
    <ChartShell title="PR Throughput" subtitle={`Weekly merges — ${PALETTE.orange.main} trend`}>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <defs>
            <linearGradient id="throughputGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.line} stopOpacity={isDark ? 0.35 : 0.45} />
              <stop offset="100%" stopColor={CHART.line} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={chartStyles.gridColor} vertical={false} />
          <XAxis dataKey="week" stroke={chartStyles.axisColor} tick={{ fontSize: 10, fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
          <YAxis stroke={chartStyles.axisColor} allowDecimals={false} tick={{ fontSize: 10, fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={chartStyles.tooltipStyle} formatter={(value: number) => [`${value} PRs`, 'Merged']} />
          <Legend wrapperStyle={chartStyles.legendStyle} formatter={renderColorLegend} iconType="circle" iconSize={6} />
          <Area
            type="monotone"
            dataKey="prs"
            name="Merged PRs"
            stroke={CHART.line}
            strokeWidth={2.5}
            fill="url(#throughputGrad)"
            isAnimationActive={isAnimationActive}
            dot={{ fill: CHART.line, r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: isDark ? '#0f1422' : '#fff', stroke: CHART.line, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function ContributorChart({ data }: { data: any[] }) {
  const chartStyles = useDynamicChartStyle()
  const chartData = (data || [])
    .slice()
    .sort((a, b) => (b.total_prs || 0) - (a.total_prs || 0))
    .map((c) => ({
      ...c,
      label:
        (c.username || 'unknown').length > 14
          ? `${c.username.slice(0, 12)}…`
          : c.username,
    }))

  if (!chartData.length) {
    return (
      <EmptyChart
        title="Contributor Activity"
        message="No contributor data yet. Re-analyze the repository."
      />
    )
  }

  const chartHeight = Math.max(300, chartData.length * 28 + 80)

  return (
    <ChartShell
      title="Contributor Activity"
      subtitle={`Total PRs (${PALETTE.lime.main}) vs merged (${PALETTE.teal.main})`}
    >
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={chartStyles.gridColor} horizontal={false} />
          <XAxis type="number" stroke={chartStyles.axisColor} allowDecimals={false} tick={{ fontSize: 10, fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            stroke={chartStyles.axisColor}
            width={100}
            tick={{ fontSize: 10, fill: chartStyles.textColor }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={chartStyles.tooltipStyle}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.username || ''}
            formatter={(value: number, name: string) => [`${value} PRs`, name]}
            cursor={{ fill: 'rgba(148, 163, 184, 0.05)' }}
          />
          <Legend wrapperStyle={chartStyles.legendStyle} formatter={renderColorLegend} iconType="circle" iconSize={6} />
          <Bar dataKey="total_prs" fill={CHART.total} name="Total PRs" radius={[0, 4, 4, 0]} />
          <Bar dataKey="merged_prs" fill={CHART.mergedBar} name="Merged" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function ReviewTurnaroundChart({ data }: { data: any[] }) {
  const maxHours = Math.max(...(data || []).map((d) => d.avg_wait_hours || 0), 1)

  return (
    <ChartShell title="Review Turnaround" subtitle="Wait time bands — teal · amber · rose">
      <div className="space-y-3">
        {(data || []).map((item, idx) => {
          const pct = Math.min((item.avg_wait_hours / maxHours) * 100, 100)
          const barStyle =
            item.avg_wait_hours < 24
              ? { background: `linear-gradient(90deg, ${PALETTE.teal.main}, ${PALETTE.teal.text})` }
              : item.avg_wait_hours < 48
                ? { background: `linear-gradient(90deg, ${PALETTE.amber.main}, ${PALETTE.amber.text})` }
                : { background: `linear-gradient(90deg, ${PALETTE.rose.main}, ${PALETTE.rose.text})` }
          return (
            <div key={idx} className="flex items-center gap-3">
              <div className="w-28 truncate text-sm font-semibold text-slate-700 dark:text-slate-300">
                {item.username}
              </div>
              <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, ...barStyle }}
                />
              </div>
              <div
                className={`w-14 text-right text-xs font-bold ${
                  item.avg_wait_hours < 24
                    ? 'text-palette-teal dark:text-teal-400'
                    : item.avg_wait_hours < 48
                      ? 'text-palette-amber dark:text-amber-400'
                      : 'text-palette-rose dark:text-rose-400'
                }`}
              >
                {item.avg_wait_hours < 24
                  ? `${item.avg_wait_hours.toFixed(1)}h`
                  : `${(item.avg_wait_hours / 24).toFixed(1)}d`}
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-5 flex flex-wrap gap-4 text-[11px] font-bold">
        <span className="flex items-center gap-1.5 text-palette-teal dark:text-teal-400">
          <span className="h-2.5 w-2.5 rounded-full bg-palette-teal dark:bg-teal-450" /> &lt;24h
        </span>
        <span className="flex items-center gap-1.5 text-palette-amber dark:text-amber-400">
          <span className="h-2.5 w-2.5 rounded-full bg-palette-amber dark:bg-amber-450" /> 24–48h
        </span>
        <span className="flex items-center gap-1.5 text-palette-rose dark:text-rose-400">
          <span className="h-2.5 w-2.5 rounded-full bg-palette-rose dark:bg-rose-450" /> &gt;48h
        </span>
      </div>
    </ChartShell>
  )
}
