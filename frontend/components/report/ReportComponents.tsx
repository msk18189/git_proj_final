'use client'

import React, { useEffect } from 'react';
import { 
  Database, 
  Activity, 
  AlertCircle, 
  FolderGit2, 
  GitMerge, 
  Clock, 
  Timer, 
  Eye, 
  MessageSquare, 
  AlertOctagon, 
  CheckCircle, 
  Zap,
  Star,
  GitFork,
  GitBranch,
  Shield
} from 'lucide-react';
import dynamic from 'next/dynamic';
import { PieChart, Pie, Cell, Legend, LineChart, Line, XAxis, YAxis, CartesianGrid, AreaChart, Area, BarChart, Bar, RadarChart, Radar, PolarGrid, PolarAngleAxis } from 'recharts';

const MonthlyFlowChart = dynamic(() => import('@/components/Charts').then(m => m.MonthlyFlowChart), { ssr: false });
const ThroughputChart = dynamic(() => import('@/components/Charts').then(m => m.ThroughputChart), { ssr: false });

export function ReportReadyTrigger() {
  useEffect(() => {
    // Wait a solid 2.5 seconds to let data render and charts finish load animations
    const timer = setTimeout(() => {
      document.documentElement.setAttribute('data-pdf-ready', 'true');
      console.log('[ReportReadyTrigger] Set data-pdf-ready=true');
    }, 2500);
    return () => clearTimeout(timer);
  }, []);
  return null;
}

import { formatTelemetry, formatDurationFromDays } from '@/lib/format';

function renderDuration(dur: { value: string | number; unit: string }): string {
  if (typeof dur.value === 'string' && ['Limited', 'Unavailable', 'Partial', 'none'].includes(dur.value)) {
    return dur.value;
  }
  return `${dur.value} ${dur.unit}`.trim();
}

function MetricCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="text-[9px] uppercase tracking-wider text-muted font-extrabold">{label}</p>
      <p className="text-sm font-black text-primary">{typeof value === 'number' ? value.toLocaleString() : value}</p>
    </div>
  );
}

export function ExecutiveSummaryReport({ status, kpi, repoHealth }: { status: any, kpi: any, repoHealth?: any }) {
  const openCount = kpi?.open_prs ?? 0;
  const staleCount = kpi?.stale_prs ?? 0;
  const mergeRate = kpi?.merge_rate ?? 0;

  return (
    <header className="mb-10 pb-6 border-b border-border avoid-break">
      <div className="pt-2 pb-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-primary mb-2">
            PR-Analytics
          </h1>
          <div className="flex items-center gap-2 text-muted font-bold text-xs uppercase tracking-wider">
            <Database className="w-4 h-4 text-indigo-600" />
            <span>Workspace: {status?.owner}/{status?.name}</span>
          </div>
        </div>
        <div className="text-right flex flex-col items-end gap-1.5">
          <div className="text-[10px] font-bold text-muted uppercase tracking-wider mb-1">Generated On</div>
          <div className="text-xs text-primary font-mono bg-surface-soft border border-border px-2.5 py-1 rounded-lg">
            {new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}
          </div>
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[9px] font-extrabold uppercase bg-emerald-50 text-emerald-700 border border-emerald-200">
            ● Executive Audit Grade A
          </span>
        </div>
      </div>

      {/* Sync Status Header Bar */}
      {status && (
        <div className="mb-4 p-2.5 rounded-xl border border-border bg-surface-soft shadow-sm">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Database className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
            <span className="text-xs font-bold text-primary">{status.owner}/{status.name}</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-250">
              ✓ COMPLETED
            </span>
            {status.initial_sync_completed && (
              <span className="text-[9px] bg-slate-100 text-secondary border border-slate-200 px-1.5 py-0.5 rounded-full font-semibold">
                Initial Sync Complete
              </span>
            )}
            <span className="text-[9px] text-muted font-semibold italic ml-auto">Sync progress completes</span>
          </div>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-3 pt-1.5 border-t border-border">
            <MetricCell label="PRs" value={formatTelemetry(status.synced_prs || status.total_prs, status.expected_prs)} />
            <MetricCell label="Issues" value={formatTelemetry(status.synced_issues || status.total_issues, status.expected_issues)} />
            <MetricCell label="Branches" value={status.total_branches ?? 0} />
            <MetricCell label="Forks" value={formatTelemetry(status.synced_forks || status.total_forks, status.expected_forks)} />
            <MetricCell label="CI Runs" value={formatTelemetry(status.synced_workflows || status.total_workflow_runs, status.expected_workflows)} />
            <MetricCell label="Discussions" value={formatTelemetry(status.total_discussions, 0)} />
            <MetricCell label="Projects" value={formatTelemetry(status.total_projects, 0)} />
            <MetricCell label="Contributors" value={formatTelemetry(status.total_contributors ?? 0, 0)} />
          </div>
        </div>
      )}

      {status?.description && (
        <p className="mt-4 text-xs text-secondary italic max-w-2xl leading-relaxed">
          {status.description}
        </p>
      )}
      
      {/* Executive Summary Hero Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
        <div className="md:col-span-2 rounded-2xl border border-border bg-surface p-5 flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="absolute right-0 top-0 h-40 w-40 bg-gradient-to-bl from-indigo-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400">
                <Activity className="h-4 w-4" />
              </span>
              <h3 className="text-sm font-bold text-primary">Executive Summary</h3>
            </div>
            
            <div className="space-y-3">
              {kpi ? (
                <>
                  <p className="text-secondary text-sm leading-relaxed font-medium">
                    {mergeRate >= 75 ? (
                      <>
                        <span className="text-emerald-600 dark:text-emerald-400 font-bold flex items-center gap-1 mb-1">
                          <CheckCircle className="h-4 w-4" /> Strong merging
                        </span>
                        With a <span className="font-bold">{mergeRate}% merge rate</span>, your team is closing PRs efficiently. Average cycle time of <span className="font-bold">{kpi.avg_cycle_time_display?.value} {kpi.avg_cycle_time_display?.unit}</span> shows good momentum.
                      </>
                    ) : (
                      <>
                        <span className="text-orange-600 dark:text-orange-400 font-bold flex items-center gap-1 mb-1">
                          <AlertCircle className="h-4 w-4" /> Merge rate below target
                        </span>
                        Current merge rate of <span className="font-bold">{mergeRate}%</span> suggests review bottlenecks or declining PRs. Review wait time is <span className="font-bold">{kpi.avg_wait_for_review_display?.value} {kpi.avg_wait_for_review_display?.unit}</span>.
                      </>
                    )}
                  </p>

                  <div className="flex flex-wrap gap-2">
                    {staleCount > 0 && (
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-900/30 text-orange-700 dark:text-orange-400 text-xs font-semibold">
                        <AlertOctagon className="h-3.5 w-3.5" />
                        {staleCount} stale PR{staleCount !== 1 ? 's' : ''} blocking progress
                      </div>
                    )}
                    {openCount > 5 && (
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/30 text-amber-700 dark:text-amber-400 text-xs font-semibold">
                        <Clock className="h-3.5 w-3.5" />
                        {openCount} open PRs awaiting review
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <span className="text-muted italic">Sync repository to see executive insights.</span>
              )}
            </div>
          </div>
        </div>

        {/* PR Distribution Pie Chart Column */}
        <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm flex flex-col justify-between items-center relative overflow-hidden">
          <h3 className="text-sm font-bold text-primary mb-2 self-start">PR Distribution</h3>
          <div className="flex justify-center items-center h-32 w-full">
            <PieChart width={140} height={120}>
              <Pie
                data={[
                  { name: 'Open', value: kpi?.open_prs ?? 0 },
                  { name: 'Merged', value: kpi?.merged_prs ?? 0 },
                  { name: 'Closed', value: kpi?.closed_not_merged_prs ?? 0 }
                ]}
                cx="50%"
                cy="50%"
                innerRadius={30}
                outerRadius={45}
                paddingAngle={4}
                dataKey="value"
                isAnimationActive={false}
              >
                <Cell fill="#D4A054" /> {/* Open: Amber */}
                <Cell fill="#6B8F7A" /> {/* Merged: Teal */}
                <Cell fill="#C75D5D" /> {/* Closed: Rose */}
              </Pie>
            </PieChart>
          </div>
          <div className="flex gap-3 text-[9px] font-bold mt-2">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-400" /> Open ({kpi?.open_prs ?? 0})</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-teal-500" /> Merged ({kpi?.merged_prs ?? 0})</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500" /> Closed ({kpi?.closed_not_merged_prs ?? 0})</span>
          </div>
        </div>
      </div>

      {/* Needs Attention Row */}
      <div className="mt-6 rounded-2xl border border-border bg-surface p-5 shadow-sm relative overflow-hidden">
        <div className="absolute right-0 bottom-0 h-32 w-32 bg-gradient-to-tl from-rose-500/5 to-transparent rounded-full blur-3xl pointer-events-none" />
        <div className="flex items-center gap-2 mb-4">
          <span className="p-1 rounded-lg bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400">
            <AlertCircle className="h-4 w-4" />
          </span>
          <h3 className="text-sm font-bold text-primary">Needs Attention</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {/* Stale PRs */}
          <div className="rounded-xl border border-rose-200 bg-rose-50/40 p-3 flex items-start gap-2.5">
            <AlertCircle className="h-4.5 w-4.5 text-rose-500 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-rose-900">
                {kpi?.stale_prs != null ? `${kpi.stale_prs} Stale PR${kpi.stale_prs !== 1 ? 's' : ''}` : 'Stale PRs'}
              </p>
              <p className="text-[10px] text-rose-600">
                {kpi?.stale_prs != null ? (kpi.stale_prs === 0 ? 'None stale' : '> 30 days old') : 'Loading...'}
              </p>
            </div>
          </div>

          {/* Open PRs */}
          <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 flex items-start gap-2.5">
            <Clock className="h-4.5 w-4.5 text-amber-500 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-amber-900">
                {kpi?.open_prs != null ? `${kpi.open_prs} Open PR${kpi.open_prs !== 1 ? 's' : ''}` : 'Open PRs'}
              </p>
              <p className="text-[10px] text-amber-600">
                {kpi?.open_prs != null ? `${kpi.open_prs} awaiting merge` : 'Loading...'}
              </p>
            </div>
          </div>

          {/* CI/CD Health */}
          <div className="rounded-xl border border-red-200 bg-red-50/40 p-3 flex items-start gap-2.5">
            <AlertCircle className="h-4.5 w-4.5 text-red-500 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-red-900">CI/CD Health</p>
              <p className="text-[10px] text-red-600">
                {repoHealth?.components?.ci_cd != null
                  ? `${Math.round((repoHealth.components.ci_cd / 25) * 100)}% reliability`
                  : 'No data yet'}
              </p>
            </div>
          </div>

          {/* Avg Cycle Time */}
          <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3 flex items-start gap-2.5">
            <Clock className="h-4.5 w-4.5 text-indigo-500 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-indigo-900">Avg Cycle Time</p>
              <p className="text-[10px] text-indigo-600">
                {kpi?.avg_cycle_time != null
                  ? renderDuration(formatDurationFromDays(kpi.avg_cycle_time))
                  : 'Loading...'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export function KPIGridReport({ kpi }: { kpi: any }) {
  return (
    <section className="mb-12 avoid-break">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted mb-4">Key Performance Indicators</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard 
          label="Open PRs" 
          value={kpi?.open_prs} 
          icon={<FolderGit2 className="h-4 w-4" />}
          sub="Active backlog"
        />
        <KpiCard 
          label="Stale PRs" 
          value={kpi?.stale_prs} 
          alert={kpi?.stale_prs > 5} 
          icon={<AlertOctagon className="h-4 w-4 text-rose-550" />}
          sub="&gt; 30 days old"
        />
        <KpiCard 
          label="Merge Rate" 
          value={`${kpi?.merge_rate || 0}%`} 
          icon={<GitMerge className="h-4 w-4" />}
          sub="of closed PRs"
        />
        <KpiCard 
          label="Avg Cycle Time" 
          value={kpi?.avg_cycle_time_display?.value} 
          unit={kpi?.avg_cycle_time_display?.unit} 
          icon={<Clock className="h-4 w-4" />}
          sub="Creation to merge"
        />
        <KpiCard 
          label="Median Cycle Time" 
          value={kpi?.median_cycle_time_display?.value} 
          unit={kpi?.median_cycle_time_display?.unit} 
          icon={<Timer className="h-4 w-4" />}
          sub="Typical turnaround"
        />
        <KpiCard 
          label="Avg Wait For Review" 
          value={kpi?.avg_wait_for_review_display?.value} 
          unit={kpi?.avg_wait_for_review_display?.unit} 
          icon={<Eye className="h-4 w-4" />}
          sub="Time to first review"
        />
        <KpiCard 
          label="Avg Review Duration" 
          value={kpi?.avg_review_duration_display?.value} 
          unit={kpi?.avg_review_duration_display?.unit} 
          icon={<MessageSquare className="h-4 w-4" />}
          sub="Active review cycle"
        />
        <KpiCard 
          label="Avg Reviews / PR" 
          value={kpi?.avg_reviews_per_pr} 
          icon={<Activity className="h-4 w-4" />}
          sub="Feedback depth"
        />
      </div>
    </section>
  );
}

function KpiCard({ label, value, unit, alert, icon, sub }: { label: string, value: string | number, unit?: string, alert?: boolean, icon?: React.ReactNode, sub?: string }) {
  return (
    <div className={`bg-surface p-4 rounded-2xl border border-border shadow-sm flex flex-col justify-between gap-3 relative overflow-hidden page-break-inside-avoid ${alert ? 'border-rose-200 bg-rose-50/10' : ''}`}>
      <div className="flex items-center justify-between w-full">
        <span className="text-[10px] font-bold text-muted uppercase tracking-wider">{label}</span>
        {icon && (
          <div className="p-1.5 rounded-lg bg-surface-soft border border-border text-muted">
            {icon}
          </div>
        )}
      </div>
      <div className="space-y-0.5">
        <div className={`text-2xl font-black tracking-tight leading-none ${alert ? 'text-rose-600' : 'text-primary'}`}>
          {value !== undefined && value !== null ? value : '—'} {unit && value !== undefined && <span className="text-sm font-medium text-muted">{unit}</span>}
        </div>
        {sub && <p className="text-[10px] font-semibold text-muted mt-1">{sub}</p>}
      </div>
    </div>
  );
}

export function ThroughputReport({ flow, throughput }: { flow: any, throughput: any }) {
  return (
    <section className="mb-12 grid grid-cols-1 md:grid-cols-2 gap-8 avoid-break page-break-inside-avoid">
      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm page-break-inside-avoid">
        <h2 className="text-sm font-bold text-primary mb-1">PR Flow</h2>
        <p className="text-[10px] text-muted font-semibold mb-4">Created · Merged · Closed (not merged)</p>
        <div className="h-80">
          <MonthlyFlowChart data={flow} isAnimationActive={false} isPrint={true} />
        </div>
      </div>
      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm page-break-inside-avoid">
        <h2 className="text-sm font-bold text-primary mb-1">Weekly Throughput</h2>
        <p className="text-[10px] text-muted font-semibold mb-4">PRs merged per week</p>
        <div className="h-80">
          <ThroughputChart data={throughput} isAnimationActive={false} isPrint={true} />
        </div>
      </div>
    </section>
  );
}

export function ContributorAnalyticsReport({ contributors }: { contributors: any[] }) {
  return (
    <section className="mb-12 avoid-break page-break-inside-avoid">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted mb-4">Top Contributors</h2>
      <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-5 py-3.5">Contributor</th>
              <th className="px-5 py-3.5 text-right">Total PRs</th>
              <th className="px-5 py-3.5 text-right">Merged</th>
              <th className="px-5 py-3.5 text-right">Merge Rate</th>
              <th className="px-5 py-3.5 text-right">Avg Cycle Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {contributors?.slice(0, 8).map((c: any) => (
              <tr key={c.username} className="hover:bg-bg-hover transition-colors">
                <td className="px-5 py-4 flex items-center gap-3">
                  <div className="h-6 w-6 rounded-full bg-orange-50 text-orange-700 flex items-center justify-center font-bold text-[10px] border border-orange-200 shrink-0">
                    {c.username.slice(0, 1).toUpperCase()}
                  </div>
                  <span className="font-bold text-primary truncate max-w-[150px]">{c.username}</span>
                </td>
                <td className="px-5 py-4 text-right text-primary font-bold">{c.total_prs}</td>
                <td className="px-5 py-4 text-right">{c.merged_prs}</td>
                <td className="px-5 py-4 text-right font-semibold text-emerald-600">{c.merge_rate}%</td>
                <td className="px-5 py-4 text-right font-mono text-xs">
                  {c.avg_cycle_time_display?.value} {c.avg_cycle_time_display?.unit}
                </td>
              </tr>
            ))}
            {(!contributors || contributors.length === 0) && (
              <tr><td colSpan={5} className="px-5 py-6 text-center text-muted italic">No contributor data available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function StalePRTableReport({ stale }: { stale: any[] }) {
  return (
    <div className="page-break-inside-avoid bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5">
      <h2 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <AlertOctagon className="w-4 h-4 text-rose-500" /> Stale PR Alerts
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3 text-right">Age</th>
              <th className="px-4 py-3">Author</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {stale?.slice(0, 8).map((s: any) => (
              <tr key={s.number} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[180px]">#{s.number} {s.title}</td>
                <td className="px-4 py-3.5 text-right text-rose-600 font-bold">{s.age_days}d</td>
                <td className="px-4 py-3.5 text-muted">{s.author}</td>
              </tr>
            ))}
            {(!stale || stale.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-muted italic">No stale PRs detected</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BottleneckPRReport({ slowest }: { slowest: any[] }) {
  return (
    <div className="page-break-inside-avoid bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5">
      <h2 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4 text-amber-500" /> Slowest Merged PRs
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3 text-right">Cycle Time</th>
              <th className="px-4 py-3">Author</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {slowest?.slice(0, 8).map((s: any) => (
              <tr key={s.number} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[180px]">#{s.number} {s.title}</td>
                <td className="px-4 py-3.5 text-right font-mono text-xs text-primary">{s.cycle_time_display?.value}{s.cycle_time_display?.unit}</td>
                <td className="px-4 py-3.5 text-muted">{s.author}</td>
              </tr>
            ))}
            {(!slowest || slowest.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-muted italic">No merged PRs available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AIInsightsReport({ kpi, stale }: { kpi: any, stale: any[] }) {
  const avgCycleTime = kpi?.avg_cycle_time || 0;
  const mergeRate = kpi?.merge_rate || 0;
  const staleCount = stale?.length || 0;

  return (
    <section className="avoid-break page-break-inside-avoid mb-8 mt-12">
      <h2 className="text-xs font-bold uppercase tracking-wider text-muted mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4 text-indigo-500" /> Operational Insights & Recommendations
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InsightCard 
          title="Cycle Time Health" 
          metric={kpi?.avg_cycle_time_display?.value ? kpi.avg_cycle_time_display.value + kpi.avg_cycle_time_display.unit : 'N/A'}
          good={avgCycleTime < 72}
          desc={avgCycleTime < 72 ? "Cycle time is healthy. Development velocity matches best-practice baselines." : "Elevated cycle times detected. Consider breaking PRs into smaller increments."}
        />
        <InsightCard 
          title="Merge Efficiency" 
          metric={`${mergeRate}%`}
          good={mergeRate > 75}
          desc={mergeRate > 75 ? "Strong merge rate indicates high quality submissions and effective alignment." : "Low merge rate suggests high PR churn or review bottlenecks."}
        />
        <InsightCard 
          title="Stale Backlog" 
          metric={`${staleCount} PRs`}
          good={staleCount < 5}
          desc={staleCount < 5 ? "Minimal backlog clutter. Team is keeping active items clean and moving." : "High volume of stale PRs requires backlog grooming and archiving of stale code."}
        />
      </div>
    </section>
  );
}

function InsightCard({ title, metric, desc, good }: { title: string, metric: string, desc: string, good: boolean }) {
  return (
    <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm page-break-inside-avoid">
      <div className="flex items-center justify-between mb-3">
        <div className="text-[10px] font-bold text-muted uppercase tracking-wider">{title}</div>
        <div className={`px-2.5 py-0.5 rounded text-xs font-bold ${good ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
          {metric}
        </div>
      </div>
      <p className="text-xs text-secondary leading-relaxed font-medium">{desc}</p>
    </div>
  );
}

export function IssuesReportSection({ issueAnalytics, staleIssueList, status }: { issueAnalytics: any, staleIssueList: any[], status: any }) {
  const fmt = (v: any, unit?: string) => v != null ? `${v}${unit ? ' ' + unit : ''}` : '—';
  const summary = issueAnalytics?.summary;
  return (
    <div className="space-y-8 avoid-break">
      <div className="border-b border-border pb-4 mb-6">
        <h2 className="text-2xl font-extrabold text-primary">Issues Report</h2>
        <p className="text-xs text-muted font-semibold mt-1">{status?.owner}/{status?.name}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total Issues" value={fmt(summary?.total_issues)} icon={<AlertCircle className="h-4 w-4" />} />
        <KpiCard label="Open Issues" value={fmt(summary?.open_issues)} icon={<AlertCircle className="h-4 w-4 text-orange-500" />} />
        <KpiCard label="Closed Issues" value={fmt(summary?.closed_issues)} icon={<CheckCircle className="h-4 w-4 text-emerald-500" />} />
        <KpiCard label="Stale Issues" value={fmt(summary?.stale_issues)} icon={<AlertOctagon className="h-4 w-4 text-rose-500" />} />
      </div>

      {/* Dynamic Issues Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 page-break-inside-avoid">
        <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-1">Issue Trend</h3>
          <p className="text-[10px] text-muted font-semibold mb-4">Backlog growth: Opened vs Closed issues</p>
          <div className="h-64 w-full flex justify-center">
            {issueAnalytics?.velocity?.length > 0 ? (
              <LineChart data={issueAnalytics.velocity} width={340} height={220} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" vertical={false} />
                <XAxis dataKey="month" stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Legend verticalAlign="top" height={36} iconSize={8} wrapperStyle={{ fontSize: 9, fontWeight: 700, color: '#94a3b8' }} />
                <Line type="monotone" dataKey="opened" name="Opened" stroke="#f97316" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                <Line type="monotone" dataKey="closed" name="Closed" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
              </LineChart>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-xs text-muted">No trend data available</div>
            )}
          </div>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-primary mb-1">Issues by Priority</h3>
            <p className="text-[10px] text-muted font-semibold mb-4">Priority distribution for open issues</p>
          </div>
          <div className="flex items-center justify-between gap-4 py-2">
            <div className="w-1/2 flex justify-center">
              <PieChart width={120} height={120}>
                <Pie
                  data={issueAnalytics?.priority || [
                    { name: 'Critical', value: 0, color: '#ef4444' },
                    { name: 'High', value: 0, color: '#f97316' },
                    { name: 'Medium', value: 0, color: '#f59e0b' },
                    { name: 'Low', value: 0, color: '#10b981' },
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={30}
                  outerRadius={45}
                  paddingAngle={3}
                  dataKey="value"
                  isAnimationActive={false}
                >
                  {(issueAnalytics?.priority || [
                    { name: 'Critical', value: 0, color: '#ef4444' },
                    { name: 'High', value: 0, color: '#f97316' },
                    { name: 'Medium', value: 0, color: '#f59e0b' },
                    { name: 'Low', value: 0, color: '#10b981' },
                  ]).map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </div>
            <div className="flex-1 space-y-1 text-[11px] font-semibold text-secondary">
              {(issueAnalytics?.priority || [
                { name: 'Critical', value: 0, color: '#ef4444' },
                { name: 'High', value: 0, color: '#f97316' },
                { name: 'Medium', value: 0, color: '#f59e0b' },
                { name: 'Low', value: 0, color: '#10b981' },
              ]).map((item: any) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                    <span>{item.name}</span>
                  </div>
                  <span className="font-bold text-primary">{item.value ?? 0}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {issueAnalytics?.top_labels?.length > 0 && (
        <div className="page-break-inside-avoid bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-4">Top Labels</h3>
          <div className="flex flex-wrap gap-2">
            {issueAnalytics.top_labels.slice(0, 15).map((l: any) => (
              <span key={l.name} style={{ backgroundColor: `#${l.color || 'e2e8f0'}20`, borderColor: `#${l.color || 'e2e8f0'}80`, color: `#${l.color || '475569'}` }} className="px-2.5 py-1 rounded-full text-xs font-semibold border">
                {l.name} ({l.count})
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="page-break-inside-avoid bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5">
        <h3 className="text-sm font-bold text-primary mb-4">Stale Issues (&gt;30 days without activity)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
              <tr>
                <th className="px-4 py-3">Issue</th>
                <th className="px-4 py-3 text-right">Age</th>
                <th className="px-4 py-3">Author</th>
                <th className="px-4 py-3 text-right">Comments</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border text-secondary font-medium">
              {staleIssueList?.slice(0, 8).map((i: any) => (
                <tr key={i.number} className="hover:bg-bg-hover transition-colors">
                  <td className="px-4 py-3 font-bold text-primary truncate max-w-[200px]">#{i.number} {i.title}</td>
                  <td className="px-4 py-3 text-right text-rose-600 font-bold">{i.age_days}d</td>
                  <td className="px-4 py-3 text-muted">{i.author}</td>
                  <td className="px-4 py-3 text-right">{i.comments_count ?? 0}</td>
                </tr>
              ))}
              {(!staleIssueList || staleIssueList.length === 0) && (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-muted italic">No stale issues detected</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export function BranchesAndCICDSection({ branchAnalytics, cicdAnalytics, status }: { branchAnalytics: any, cicdAnalytics: any, status: any }) {
  const fmt = (v: any, unit?: string) => v != null ? `${v}${unit ? ' ' + unit : ''}` : '—';
  const cicdSummary = cicdAnalytics?.summary;
  const workflowBreakdown = cicdAnalytics?.workflow_breakdown || [];

  const branchChartData = branchAnalytics ? [
    { name: 'Active', value: branchAnalytics.active_branches || 0, color: '#10b981' },
    { name: 'Inactive', value: Math.max(0, (branchAnalytics.total_branches || 0) - (branchAnalytics.active_branches || 0) - (branchAnalytics.stale_branches || 0)), color: '#64748b' },
    { name: 'Stale', value: branchAnalytics.stale_branches || 0, color: '#ef4444' }
  ] : [];

  return (
    <div className="space-y-8 avoid-break">
      <div className="border-b border-border pb-4 mb-6">
        <h2 className="text-2xl font-extrabold text-primary">Branches & CI/CD</h2>
        <p className="text-xs text-muted font-semibold mt-1">{status?.owner}/{status?.name}</p>
      </div>

      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
        <h3 className="text-sm font-bold text-primary mb-4">Branch Analytics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Branches" value={fmt(branchAnalytics?.total_branches)} icon={<FolderGit2 className="h-4 w-4" />} />
          <KpiCard label="Active Branches" value={fmt(branchAnalytics?.active_branches)} icon={<Activity className="h-4 w-4 text-emerald-500" />} />
          <KpiCard label="Stale Branches" value={fmt(branchAnalytics?.stale_branches)} icon={<AlertOctagon className="h-4 w-4 text-rose-500" />} />
          <KpiCard label="Protected Branches" value={fmt(branchAnalytics?.protected_branches)} icon={<CheckCircle className="h-4 w-4 text-indigo-500" />} />
        </div>
      </div>

      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
        <h3 className="text-sm font-bold text-primary mb-4">CI/CD Pipeline Analytics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Runs" value={fmt(cicdSummary?.total_runs)} icon={<Activity className="h-4 w-4" />} />
          <KpiCard label="Success Rate" value={fmt(cicdSummary?.success_rate, '%')} alert={(cicdSummary?.success_rate ?? 100) < 80} icon={<CheckCircle className="h-4 w-4 text-emerald-500" />} />
          <KpiCard label="Failure Rate" value={fmt(cicdSummary?.failure_rate, '%')} icon={<AlertCircle className="h-4 w-4 text-rose-500" />} />
          <KpiCard label="Avg Duration" value={cicdSummary?.avg_duration_minutes != null ? `${cicdSummary.avg_duration_minutes.toFixed(1)} min` : '—'} icon={<Clock className="h-4 w-4 text-indigo-500" />} />
        </div>
      </div>

      {/* Dynamic Branch and CI/CD Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6 page-break-inside-avoid">
        <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-1">Branch Activity Breakdown</h3>
          <p className="text-[10px] text-muted font-semibold mb-4">Active vs Inactive vs Stale branches</p>
          <div className="h-64 w-full flex justify-center">
            {branchChartData.length > 0 ? (
              <BarChart data={branchChartData} width={340} height={220} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" vertical={false} />
                <XAxis dataKey="name" stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Bar dataKey="value" name="Branches" fill="#6366f1" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {branchChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-xs text-muted">No branch data available</div>
            )}
          </div>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-1">CI/CD Pipeline Success Trend</h3>
          <p className="text-[10px] text-muted font-semibold mb-4">Pipeline success rate over time</p>
          <div className="h-64 w-full flex justify-center">
            {cicdAnalytics?.success_trend?.length > 0 ? (
              <AreaChart data={cicdAnalytics.success_trend} width={340} height={220} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="cicdGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" vertical={false} />
                <XAxis dataKey="date" stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Area type="monotone" dataKey="success_rate" name="Success Rate" stroke="#10b981" strokeWidth={2.5} fill="url(#cicdGrad)" isAnimationActive={false} />
              </AreaChart>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-xs text-muted">No trend data available</div>
            )}
          </div>
        </div>
      </div>

      {workflowBreakdown?.length > 0 && (
        <div className="page-break-inside-avoid bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5">
          <h3 className="text-sm font-bold text-primary mb-4">Workflow Performance</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
                <tr>
                  <th className="px-4 py-3">Workflow</th>
                  <th className="px-4 py-3 text-right">Total Runs</th>
                  <th className="px-4 py-3 text-right">Success Rate</th>
                  <th className="px-4 py-3 text-right">Avg Duration</th>
                  <th className="px-4 py-3 text-right">Last Run</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-secondary font-medium">
                {workflowBreakdown.slice(0, 6).map((w: any) => (
                  <tr key={w.name} className="hover:bg-bg-hover transition-colors">
                    <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[200px]">{w.name}</td>
                    <td className="px-4 py-3.5 text-right text-primary font-bold">{w.total_runs}</td>
                    <td className="px-4 py-3.5 text-right font-bold text-emerald-600">{w.success_rate?.toFixed(1)}%</td>
                    <td className="px-4 py-3.5 text-right font-mono text-xs">{w.avg_duration_minutes?.toFixed(1)} min</td>
                    <td className="px-4 py-3.5 text-right text-muted font-mono text-xs">{w.last_run?.slice(0, 10) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export function ForksAndDiscussionsSection({ forksAnalytics, discussionAnalytics, discussionTimeline, status }: { forksAnalytics: any, discussionAnalytics: any, discussionTimeline: any, status: any }) {
  const fmt = (v: any, unit?: string) => v != null ? `${v}${unit ? ' ' + unit : ''}` : '—';
  const forksSummary = forksAnalytics?.summary;
  const growth = forksAnalytics?.growth_trend || [];
  const timelineData = discussionTimeline?.timeline || [];
  return (
    <div className="space-y-8 avoid-break">
      <div className="border-b border-border pb-4 mb-6">
        <h2 className="text-2xl font-extrabold text-primary">Forks & Discussions</h2>
        <p className="text-xs text-muted font-semibold mt-1">{status?.owner}/{status?.name}</p>
      </div>

      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
        <h3 className="text-sm font-bold text-primary mb-4">Fork Analytics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Forks" value={fmt(forksSummary?.total_forks)} icon={<FolderGit2 className="h-4 w-4" />} />
          <KpiCard label="Active Forks" value={fmt(forksSummary?.active_forks)} icon={<Activity className="h-4 w-4 text-emerald-500" />} />
          <KpiCard label="Starred Forks" value={fmt(forksSummary?.starred_forks)} icon={<CheckCircle className="h-4 w-4 text-indigo-500" />} />
          <KpiCard label="Adoption Rate" value={forksSummary?.adoption_rate != null ? `${forksSummary.adoption_rate}%` : '—'} icon={<Clock className="h-4 w-4 text-amber-500" />} />
        </div>
      </div>

      {/* Dynamic Fork Growth Trend Chart */}
      {growth?.length > 0 && (
        <div className="page-break-inside-avoid bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-1">Fork Growth Trend</h3>
          <p className="text-[10px] text-muted font-semibold mb-4">Growth metrics: new forks created per month</p>
          <div className="h-64 w-full flex justify-center">
            <AreaChart data={growth} width={700} height={240} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="forkGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" vertical={false} />
              <XAxis dataKey="month" stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Area type="monotone" dataKey="new_forks" name="New Forks" stroke="#6366f1" strokeWidth={2.5} fill="url(#forkGrad)" isAnimationActive={false} />
            </AreaChart>
          </div>
        </div>
      )}

      <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm">
        <h3 className="text-sm font-bold text-primary mb-4">Discussions Analytics</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Discussions" value={fmt(discussionAnalytics?.total_discussions)} icon={<MessageSquare className="h-4 w-4" />} />
          <KpiCard label="Answer Rate" value={fmt(discussionAnalytics?.answer_rate, '%')} icon={<CheckCircle className="h-4 w-4 text-emerald-500" />} />
          <KpiCard label="Avg Comments" value={fmt(discussionAnalytics?.avg_comments)} icon={<Activity className="h-4 w-4 text-indigo-500" />} />
          <KpiCard label="Recent (30d)" value={fmt(discussionAnalytics?.recent_discussions_30d)} icon={<Clock className="h-4 w-4 text-amber-500" />} />
        </div>
      </div>

      {/* Dynamic Discussion Activity Timeline Chart */}
      {timelineData.length > 0 && (
        <div className="page-break-inside-avoid bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-1">Discussion Activity</h3>
          <p className="text-[10px] text-muted font-semibold mb-4">Active threads timeline over time</p>
          <div className="h-64 w-full flex justify-center">
            <AreaChart data={timelineData} width={700} height={240} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="discGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" vertical={false} />
              <XAxis dataKey="date" stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis stroke="#334155" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <Area type="monotone" dataKey="activity" name="Discussions" stroke="#6366f1" strokeWidth={2.5} fill="url(#discGrad)" isAnimationActive={false} />
            </AreaChart>
          </div>
        </div>
      )}

      {discussionAnalytics?.top_categories?.length > 0 && (
        <div className="page-break-inside-avoid bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5">
          <h3 className="text-sm font-bold text-primary mb-4">Top Discussion Categories</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
                <tr>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3 text-right">Count</th>
                  <th className="px-4 py-3 text-right">Answered</th>
                  <th className="px-4 py-3 text-right">Answer Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border text-secondary font-medium">
                {discussionAnalytics.top_categories.slice(0, 6).map((c: any) => (
                  <tr key={c.name} className="hover:bg-bg-hover transition-colors">
                    <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[200px]">{c.name}</td>
                    <td className="px-4 py-3.5 text-right text-primary font-bold">{c.count}</td>
                    <td className="px-4 py-3.5 text-right">{c.answered ?? 0}</td>
                    <td className="px-4 py-3.5 text-right font-bold text-indigo-600">{c.count > 0 ? Math.round(((c.answered ?? 0) / c.count) * 100) : 0}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export function ProjectsAndHealthSection({ projectsAnalytics, repoHealth, status }: { projectsAnalytics: any, repoHealth: any, status: any }) {
  const fmt = (v: any, unit?: string) => v != null ? `${v}${unit ? ' ' + unit : ''}` : '—';
  const score = repoHealth?.score ?? 0;
  const grade = repoHealth?.grade ?? '—';

  const gradeColors: Record<string, string> = {
    A: 'text-emerald-600',
    B: 'text-indigo-600',
    C: 'text-amber-600',
    D: 'text-orange-600',
    F: 'text-rose-600',
  };

  const gradeRing: Record<string, string> = {
    A: 'border-emerald-200 bg-emerald-50 text-emerald-700',
    B: 'border-indigo-200 bg-indigo-50 text-indigo-700',
    C: 'border-amber-200 bg-amber-50 text-amber-700',
    D: 'border-orange-200 bg-orange-50 text-orange-700',
    F: 'border-rose-200 bg-rose-50 text-rose-700',
  };

  const componentIcons: Record<string, React.ReactNode> = {
    pull_requests: <FolderGit2 className="h-3.5 w-3.5" />,
    ci_cd: <Zap className="h-3.5 w-3.5" />,
    branches: <GitBranch className="h-3.5 w-3.5" />,
    issues: <AlertCircle className="h-3.5 w-3.5" />,
    community: <MessageSquare className="h-3.5 w-3.5" />,
    visibility: <Shield className="h-3.5 w-3.5" />,
  };

  const components = repoHealth?.components ?? {};
  const componentMaxes: Record<string, number> = {
    pull_requests: 20, ci_cd: 25, branches: 15, issues: 20, community: 10, visibility: 10,
  };

  return (
    <div className="space-y-6 avoid-break">
      <div className="border-b border-border pb-4 mb-6">
        <h2 className="text-2xl font-extrabold text-primary">Projects & Repository Health</h2>
        <p className="text-xs text-muted font-semibold mt-1">{status?.owner}/{status?.name}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main Score overview layout mimicking Dashboard */}
        <div className="md:col-span-2 rounded-2xl border border-border bg-surface p-6 flex items-center gap-8 shadow-sm">
          {/* Large Grade Circle */}
          <div className={`flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-4 shadow-sm ${gradeRing[grade] ?? gradeRing.F}`}>
            <div className="text-center">
              <p className={`text-4xl font-black ${gradeColors[grade] ?? 'text-rose-600'}`}>{grade}</p>
              <p className="text-[9px] font-bold text-slate-500 mt-0.5 uppercase tracking-wider">{score}/100 SCORE</p>
            </div>
          </div>

          {/* Detailed stats bars */}
          <div className="flex-1 min-w-0 space-y-3">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-primary uppercase tracking-wider">Repository Health breakdown</h3>
            </div>
            <p className="text-[10px] text-muted font-semibold">{status?.owner}/{status?.name}</p>
            <div className="space-y-2.5">
              {Object.entries(componentMaxes).map(([key, max]) => {
                const val = components[key] ?? 0;
                const pct = max > 0 ? (val / max) * 100 : 0;
                const color = pct >= 80 ? 'bg-emerald-500' : pct >= 55 ? 'bg-indigo-500' : pct >= 35 ? 'bg-amber-500' : 'bg-rose-500';
                return (
                  <div key={key} className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 w-28 shrink-0 text-[10px] font-semibold text-secondary">
                      <span className="text-muted">{componentIcons[key]}</span>
                      <span className="capitalize">{key.replace('_', ' ')}</span>
                    </div>
                    <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-[10px] font-bold text-primary w-12 text-right">{val} / {max}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="bg-surface p-5 rounded-2xl border border-border shadow-sm flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-primary mb-4">Projects Overview</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted font-bold uppercase">Total Projects</span>
                <span className="font-bold text-primary">{fmt(projectsAnalytics?.total_projects)}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted font-bold uppercase">Open Projects</span>
                <span className="font-bold text-primary">{fmt(projectsAnalytics?.open_projects)}</span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted font-bold uppercase">Total Items</span>
                <span className="font-bold text-primary">{fmt(projectsAnalytics?.total_items)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {repoHealth?.recommendations?.length > 0 && (
        <div className="page-break-inside-avoid bg-surface p-5 rounded-2xl border border-border shadow-sm">
          <h3 className="text-sm font-bold text-primary mb-4">Recommendations</h3>
          <div className="space-y-3">
            {repoHealth.recommendations.slice(0, 4).map((r: any, idx: number) => (
              <div key={idx} className="flex gap-3 items-start p-3 bg-surface-soft border border-border rounded-xl text-xs">
                <span className="text-base shrink-0">{r.priority === 'high' ? '🔴' : r.priority === 'medium' ? '🟡' : '🟢'}</span>
                <div>
                  <p className="font-bold text-primary">{r.title || r.message}</p>
                  {r.description && <p className="text-muted mt-1 font-medium">{r.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function OldestPRsTable({ oldestList }: { oldestList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4 text-rose-500" /> Oldest Open PRs
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3 text-right">Age</th>
              <th className="px-4 py-3">Author</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {oldestList?.slice(0, 8).map((p: any) => (
              <tr key={p.number} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[180px]">#{p.number} {p.title}</td>
                <td className="px-4 py-3.5 text-right text-rose-600 font-bold">{p.age_days}d</td>
                <td className="px-4 py-3.5 text-muted">{p.author}</td>
              </tr>
            ))}
            {(!oldestList || oldestList.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-muted italic">No open PRs found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PRRiskTable({ riskList }: { riskList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-orange-500" /> PR Risk Analysis (ML Predictions)
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3 text-center">Risk Level</th>
              <th className="px-4 py-3">Predicted Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {riskList?.slice(0, 8).map((p: any) => (
              <tr key={p.number} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[180px]">#{p.number} {p.title}</td>
                <td className="px-4 py-3.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    p.risk_level === 'HIGH' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                    p.risk_level === 'MEDIUM' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                    'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}>
                    {p.risk_level}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-xs text-muted truncate max-w-[200px]">
                  {p.risk_reasons?.slice(0, 2).join(', ') || 'Low overall risk factors.'}
                </td>
              </tr>
            ))}
            {(!riskList || riskList.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-muted italic">No PR risk predictions available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function IssuesListTable({ issuesList }: { issuesList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <AlertCircle className="w-4 h-4 text-indigo-500" /> Active Issues List
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Issue</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3">Author</th>
              <th className="px-4 py-3 text-right">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {issuesList?.slice(0, 8).map((i: any) => (
              <tr key={i.number} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[220px]">#{i.number} {i.title}</td>
                <td className="px-4 py-3.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    i.state === 'open' ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  }`}>
                    {i.state}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-muted">{i.author}</td>
                <td className="px-4 py-3.5 text-right text-xs text-muted font-mono">{i.created_at?.slice(0, 10) ?? '—'}</td>
              </tr>
            ))}
            {(!issuesList || issuesList.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-muted italic">No issues found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BranchesListTable({ branchesList }: { branchesList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <FolderGit2 className="w-4 h-4 text-indigo-500" /> Repository Branches
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-surface-soft text-muted font-bold text-[10px] uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Branch Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Protected</th>
              <th className="px-4 py-3">Last Commit Message</th>
              <th className="px-4 py-3">Author</th>
              <th className="px-4 py-3 text-right">Days Stale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {branchesList?.slice(0, 8).map((b: any) => (
              <tr key={b.name} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3 font-bold text-primary truncate max-w-[140px]">
                  <div className="flex items-center gap-1.5">
                    <GitBranch className="h-3.5 w-3.5 text-muted shrink-0" />
                    <span>{b.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${
                    b.status === 'active' ? 'bg-emerald-50 text-emerald-700 border-emerald-250 font-bold' :
                    b.status === 'inactive' ? 'bg-amber-50 text-amber-700 border-amber-250 font-bold' :
                    b.status === 'stale' ? 'bg-rose-50 text-rose-700 border-rose-250 font-bold' :
                    'bg-surface-soft border-border text-muted'
                  }`}>
                    {b.status ?? '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {b.protected ? (
                    <span className="inline-flex items-center gap-1 text-[9px] bg-purple-50 text-purple-750 font-bold border border-purple-200 px-2 py-0.5 rounded-full">
                      <Shield className="h-3 w-3 shrink-0" /> Yes
                    </span>
                  ) : <span className="text-muted">—</span>}
                </td>
                <td className="px-4 py-3 text-secondary text-xs max-w-[180px] truncate" title={b.last_commit_message}>{b.last_commit_message || '—'}</td>
                <td className="px-4 py-3 text-secondary text-xs font-semibold">{b.last_commit_author || '—'}</td>
                <td className="px-4 py-3 text-right font-bold">{b.staleness_days ?? '—'}</td>
              </tr>
            ))}
            {(!branchesList || branchesList.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted italic">No branches found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function WorkflowRunsListTable({ workflowRunsList }: { workflowRunsList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-emerald-500" /> Recent CI/CD Workflow Runs
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Run ID / Commit</th>
              <th className="px-4 py-3">Workflow</th>
              <th className="px-4 py-3 text-center">Conclusion</th>
              <th className="px-4 py-3 text-right">Duration</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {workflowRunsList?.slice(0, 8).map((run: any) => (
              <tr key={run.id} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[140px]">
                  #{run.run_number} <span className="text-xs font-normal text-muted font-mono">({run.head_sha?.slice(0, 7)})</span>
                </td>
                <td className="px-4 py-3.5 text-xs font-semibold">{run.name}</td>
                <td className="px-4 py-3.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    run.conclusion === 'success' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                    run.conclusion === 'failure' ? 'bg-rose-50 text-rose-700 border border-rose-200' :
                    'bg-slate-50 text-slate-600 border border-slate-200'
                  }`}>
                    {run.conclusion || 'Running'}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-right text-xs text-muted font-mono">
                  {run.duration_seconds != null ? `${Math.round(run.duration_seconds / 60)} min` : '—'}
                </td>
              </tr>
            ))}
            {(!workflowRunsList || workflowRunsList.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-muted italic">No workflow runs found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ForksListTable({ forksList }: { forksList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <GitMerge className="w-4 h-4 text-amber-500" /> Active Repository Forks
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-surface-soft text-muted font-bold text-[10px] uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Fork Repository</th>
              <th className="px-4 py-3">Owner</th>
              <th className="px-4 py-3">Stars</th>
              <th className="px-4 py-3">Language</th>
              <th className="px-4 py-3">Activity Status</th>
              <th className="px-4 py-3 text-right">Last Push</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {forksList?.slice(0, 8).map((f: any) => (
              <tr key={f.full_name} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3 font-bold text-primary truncate max-w-[200px] flex items-center gap-1.5">
                  <GitFork className="h-3.5 w-3.5 text-muted shrink-0" />
                  <span>{f.full_name}</span>
                </td>
                <td className="px-4 py-3 text-secondary">{f.owner}</td>
                <td className="px-4 py-3 text-secondary font-bold flex items-center gap-1">
                  <Star className="h-3 w-3 text-amber-500 fill-current" />
                  {f.stars ?? 0}
                </td>
                <td className="px-4 py-3 text-secondary">{f.language || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold border ${
                    f.activity === 'active'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                      : 'bg-surface-soft border-border text-muted'
                  }`}>
                    {f.activity ?? 'stale'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-xs text-muted font-mono">
                  {f.pushed_at ? new Date(f.pushed_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
            {(!forksList || forksList.length === 0) && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted italic">No forks found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DiscussionsListTable({ discussionsList }: { discussionsList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <MessageSquare className="w-4 h-4 text-indigo-500" /> Community Discussions
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Discussion Title</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3 text-right">Comments</th>
              <th className="px-4 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {discussionsList?.slice(0, 8).map((d: any) => (
              <tr key={d.id} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[220px]">#{d.number} {d.title}</td>
                <td className="px-4 py-3.5 text-xs text-muted font-semibold">{d.category}</td>
                <td className="px-4 py-3.5 text-right font-mono text-xs">{d.comments_count ?? 0}</td>
                <td className="px-4 py-3.5 text-center">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    d.is_answered ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-50 text-slate-600 border border-slate-200'
                  }`}>
                    {d.is_answered ? 'Answered' : 'Open'}
                  </span>
                </td>
              </tr>
            ))}
            {(!discussionsList || discussionsList.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-muted italic">No discussions found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ProjectsListTable({ projectsList }: { projectsList: any[] }) {
  return (
    <div className="bg-surface rounded-2xl border border-border shadow-sm overflow-hidden p-5 avoid-break page-break-inside-avoid">
      <h3 className="text-sm font-bold text-primary mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4 text-indigo-500" /> Project Boards & Lists
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-surface-soft text-muted font-bold text-xs uppercase tracking-wider border-b border-border">
            <tr>
              <th className="px-4 py-3">Project Title</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3 text-right">Items Count</th>
              <th className="px-4 py-3 text-right">Last Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border text-secondary font-medium">
            {projectsList?.slice(0, 8).map((p: any) => (
              <tr key={p.id} className="hover:bg-bg-hover transition-colors">
                <td className="px-4 py-3.5 font-bold text-primary truncate max-w-[240px]">{p.title}</td>
                <td className="px-4 py-3.5">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    p.state === 'open' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-slate-50 text-slate-600 border border-slate-200'
                  }`}>
                    {p.state}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-right font-mono text-xs">{p.items_count ?? 0}</td>
                <td className="px-4 py-3.5 text-right text-xs text-muted font-mono">{p.updated_at?.slice(0, 10) || '—'}</td>
              </tr>
            ))}
            {(!projectsList || projectsList.length === 0) && (
              <tr><td colSpan={4} className="px-4 py-6 text-center text-muted italic">No projects found</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

