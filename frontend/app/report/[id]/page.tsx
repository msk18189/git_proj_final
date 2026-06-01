import React from 'react'
import {
  ExecutiveSummaryReport,
  KPIGridReport,
  ThroughputReport,
  ContributorAnalyticsReport,
  StalePRTableReport,
  BottleneckPRReport,
  AIInsightsReport
} from '@/components/report/ReportComponents'

// Define the shape of search params
interface PageProps {
  params: { id: string }
  searchParams: { [key: string]: string | string[] | undefined }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Helper function to build query string
function buildQueryString(searchParams: { [key: string]: string | string[] | undefined }) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(searchParams)) {
    if (value && typeof value === 'string') {
      params.append(key, value)
    }
  }
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export default async function ReportPage({ params, searchParams }: PageProps) {
  const id = Number(params.id)
  
  if (!id) {
    return <div className="p-10 text-center text-rose-500">Invalid Repository ID</div>
  }

  const token = typeof searchParams.token === 'string' ? searchParams.token : ''
  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const fetchApi = async (path: string, extraParams: Record<string, any> = {}) => {
    // Merge searchParams and extraParams
    const qsObj = { ...searchParams, ...extraParams }
    delete qsObj.token // don't send token in query string to backend if possible, or it's fine
    
    const url = `${API_BASE}${path}${buildQueryString(qsObj)}`
    const res = await fetch(url, { headers, cache: 'no-store' })
    if (!res.ok) {
      // If it fails, return null or handle gracefully so the report can still partially render
      console.error(`Failed to fetch ${url}: ${res.status} ${res.statusText}`)
      return null
    }
    return res.json()
  }

  try {
    // Fetch all data in parallel
    const [
      status, kpi, flowRes, throughputRes, contributorsRes,
      staleRes, slowestRes, risksRes
    ] = await Promise.all([
      fetchApi(`/api/sync-status/${id}`),
      fetchApi(`/api/kpi/${id}`),
      fetchApi(`/api/monthly-flow/${id}`, { months: 6 }),
      fetchApi(`/api/throughput/${id}`, { weeks: 8 }),
      fetchApi(`/api/contributor-activity/${id}`, { page: 1, limit: 15 }),
      fetchApi(`/api/stale-alerts/${id}`, { page: 1, limit: 10 }),
      fetchApi(`/api/slowest-prs/${id}`, { page: 1, limit: 10 }),
      fetchApi(`/api/pr-risk/${id}`, { page: 1, limit: 15 })
    ])

    const flow = flowRes
    const throughput = throughputRes
    const contributors = contributorsRes?.data || []
    const stale = staleRes?.data || []
    const slowest = slowestRes?.data || []

    return (
      <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-8 md:p-12 max-w-5xl mx-auto printable-report">
        
        {/* PAGE 1: Executive Summary & KPIs */}
        <div className="report-page">
          <ExecutiveSummaryReport status={status} />
          <KPIGridReport kpi={kpi} />
        </div>

        {/* PAGE 2: Flow & Contributor Analytics */}
        <div className="report-page">
          <ThroughputReport flow={flow} throughput={throughput} />
          <ContributorAnalyticsReport contributors={contributors} />
        </div>

        {/* PAGE 3: Operational Tables (Oldest/Stale/Bottleneck) */}
        <div className="report-page mt-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <StalePRTableReport stale={stale} />
            <BottleneckPRReport slowest={slowest} />
          </div>
        </div>

        {/* PAGE 4: AI Insights & Risks */}
        <div className="report-page">
          <AIInsightsReport kpi={kpi} stale={stale} />
        </div>

      </div>
    )
  } catch (err: any) {
    return (
      <div className="p-10 text-center font-mono text-sm text-rose-500">
        Error generating report: {err.message}
      </div>
    )
  }
}
