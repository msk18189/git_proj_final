'use client'

import React from 'react';
import { Database, Activity, AlertCircle } from 'lucide-react';
import dynamic from 'next/dynamic';

const MonthlyFlowChart = dynamic(() => import('@/components/Charts').then(m => m.MonthlyFlowChart), { ssr: false });
const ThroughputChart = dynamic(() => import('@/components/Charts').then(m => m.ThroughputChart), { ssr: false });

export function ExecutiveSummaryReport({ status }: { status: any }) {
  return (
    <header className="mb-10 pb-6 border-b border-slate-200 avoid-break">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 mb-2">
            Engineering Intelligence Report
          </h1>
          <div className="flex items-center gap-2 text-slate-500 font-medium">
            <Database className="w-4 h-4" />
            <span>{status?.owner}/{status?.name}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-slate-400 mb-1">Generated On</div>
          <div className="text-sm text-slate-600 font-mono">
            {new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })}
          </div>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-500 uppercase tracking-widest font-semibold">
        Cycle Time · Review Turnaround · Throughput · Bottlenecks
      </p>
    </header>
  );
}

export function KPIGridReport({ kpi }: { kpi: any }) {
  return (
    <section className="mb-12 avoid-break">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Key Performance Indicators</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Open PRs" value={kpi?.open_prs} />
        <KpiCard label="Stale PRs" value={kpi?.stale_prs} alert={kpi?.stale_prs > 5} />
        <KpiCard label="Merge Rate" value={`${kpi?.merge_rate || 0}%`} />
        <KpiCard label="Avg Cycle Time" value={kpi?.avg_cycle_time_display?.value} unit={kpi?.avg_cycle_time_display?.unit} />
        <KpiCard label="Median Cycle Time" value={kpi?.median_cycle_time_display?.value} unit={kpi?.median_cycle_time_display?.unit} />
        <KpiCard label="Avg Wait For Review" value={kpi?.avg_wait_for_review_display?.value} unit={kpi?.avg_wait_for_review_display?.unit} />
        <KpiCard label="Avg Review Duration" value={kpi?.avg_review_duration_display?.value} unit={kpi?.avg_review_duration_display?.unit} />
        <KpiCard label="Avg Reviews / PR" value={kpi?.avg_reviews_per_pr} />
      </div>
    </section>
  );
}

function KpiCard({ label, value, unit, alert }: { label: string, value: string | number, unit?: string, alert?: boolean }) {
  return (
    <div className={`bg-white p-4 rounded-xl border shadow-sm ${alert ? 'border-rose-200' : 'border-slate-200'} page-break-inside-avoid`}>
      <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${alert ? 'text-rose-600' : 'text-slate-800'}`}>
        {value !== undefined ? value : '—'} {unit && value !== undefined && <span className="text-sm font-medium text-slate-500">{unit}</span>}
      </div>
    </div>
  );
}

export function ThroughputReport({ flow, throughput }: { flow: any, throughput: any }) {
  return (
    <section className="mb-12 grid grid-cols-1 md:grid-cols-2 gap-8 avoid-break page-break-inside-avoid">
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm page-break-inside-avoid">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Monthly PR Flow</h2>
        <div className="h-64">
          <MonthlyFlowChart data={flow} isAnimationActive={false} />
        </div>
      </div>
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm page-break-inside-avoid">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Weekly Throughput</h2>
        <div className="h-64">
          <ThroughputChart data={throughput} isAnimationActive={false} />
        </div>
      </div>
    </section>
  );
}

export function ContributorAnalyticsReport({ contributors }: { contributors: any[] }) {
  return (
    <section className="mb-12 avoid-break page-break-inside-avoid">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Top Contributors</h2>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
            <tr>
              <th className="px-4 py-3">Username</th>
              <th className="px-4 py-3 text-right">Total PRs</th>
              <th className="px-4 py-3 text-right">Merged</th>
              <th className="px-4 py-3 text-right">Merge Rate</th>
              <th className="px-4 py-3 text-right">Avg Cycle Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {contributors?.slice(0, 8).map((c: any) => (
              <tr key={c.username}>
                <td className="px-4 py-3 font-medium text-slate-700">{c.username}</td>
                <td className="px-4 py-3 text-right">{c.total_prs}</td>
                <td className="px-4 py-3 text-right">{c.merged_prs}</td>
                <td className="px-4 py-3 text-right">{c.merge_rate}%</td>
                <td className="px-4 py-3 text-right">
                  {c.avg_cycle_time_display?.value} {c.avg_cycle_time_display?.unit}
                </td>
              </tr>
            ))}
            {(!contributors || contributors.length === 0) && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-400">No contributor data available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ReviewTurnaroundReport() {
  // Placeholder for review turnaround specifics if needed beyond KPI grid.
  return null;
}

export function StalePRTableReport({ stale }: { stale: any[] }) {
  return (
    <div className="page-break-inside-avoid">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Stale PR Alerts</h2>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3">Age</th>
              <th className="px-4 py-3">Author</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {stale?.slice(0, 10).map((s: any) => (
              <tr key={s.number}>
                <td className="px-4 py-3 font-medium text-slate-700 truncate max-w-[200px]">#{s.number} {s.title}</td>
                <td className="px-4 py-3 text-rose-600 font-medium">{s.age_days}d</td>
                <td className="px-4 py-3 text-slate-500">{s.author}</td>
              </tr>
            ))}
            {(!stale || stale.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-slate-400">No stale PRs detected</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BottleneckPRReport({ slowest }: { slowest: any[] }) {
  return (
    <div className="page-break-inside-avoid">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">Slowest Merged PRs</h2>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
            <tr>
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3 text-right">Cycle Time</th>
              <th className="px-4 py-3">Author</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {slowest?.slice(0, 10).map((s: any) => (
              <tr key={s.number}>
                <td className="px-4 py-3 font-medium text-slate-700 truncate max-w-[200px]">#{s.number} {s.title}</td>
                <td className="px-4 py-3 text-right">{s.cycle_time_display?.value}{s.cycle_time_display?.unit}</td>
                <td className="px-4 py-3 text-slate-500">{s.author}</td>
              </tr>
            ))}
            {(!slowest || slowest.length === 0) && (
              <tr><td colSpan={3} className="px-4 py-6 text-center text-slate-400">No merged PRs available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function WorkflowAnalyticsReport() {
  // Placeholder. If we have workflow metrics, we'd add them here.
  return null;
}

export function AIInsightsReport({ kpi, stale }: { kpi: any, stale: any[] }) {
  const avgCycleTime = kpi?.avg_cycle_time || 0;
  const mergeRate = kpi?.merge_rate || 0;
  const staleCount = stale?.length || 0;

  return (
    <section className="avoid-break page-break-inside-avoid mb-8 mt-12">
      <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" /> Operational Insights
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InsightCard 
          title="Cycle Time Health" 
          metric={kpi?.avg_cycle_time_display?.value ? kpi.avg_cycle_time_display.value + kpi.avg_cycle_time_display.unit : 'N/A'}
          good={avgCycleTime < 72}
          desc={avgCycleTime < 72 ? "Cycle time is well within healthy operational limits." : "Elevated cycle times detected. Review bottleneck potential."}
        />
        <InsightCard 
          title="Merge Efficiency" 
          metric={`${mergeRate}%`}
          good={mergeRate > 75}
          desc={mergeRate > 75 ? "Strong merge rate indicates high quality submissions." : "Low merge rate suggests high PR churn or abandoned work."}
        />
        <InsightCard 
          title="Stale Accumulation" 
          metric={`${staleCount} PRs`}
          good={staleCount < 5}
          desc={staleCount < 5 ? "Minimal stale PRs in the backlog." : "High volume of stale PRs requires backlog grooming."}
        />
      </div>
    </section>
  );
}

function InsightCard({ title, metric, desc, good }: { title: string, metric: string, desc: string, good: boolean }) {
  return (
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm page-break-inside-avoid">
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">{title}</div>
        <div className={`px-2 py-0.5 rounded text-xs font-bold ${good ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
          {metric}
        </div>
      </div>
      <p className="text-sm text-slate-600 leading-relaxed">{desc}</p>
    </div>
  );
}
