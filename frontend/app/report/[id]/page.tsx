import React from 'react'
import {
  ReportReadyTrigger,
  ExecutiveSummaryReport,
  KPIGridReport,
  ThroughputReport,
  ContributorAnalyticsReport,
  StalePRTableReport,
  BottleneckPRReport,
  AIInsightsReport,
  IssuesReportSection,
  BranchesAndCICDSection,
  ForksAndDiscussionsSection,
  ProjectsAndHealthSection,
  OldestPRsTable,
  PRRiskTable,
  IssuesListTable,
  BranchesListTable,
  WorkflowRunsListTable,
  ForksListTable,
  DiscussionsListTable,
  ProjectsListTable,
} from '@/components/report/ReportComponents'

interface PageProps {
  params: { id: string }
  searchParams: { [key: string]: string | string[] | undefined }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function qs(obj: Record<string, any>) {
  const p = new URLSearchParams()
  Object.entries(obj).forEach(([k, v]) => { if (v != null) p.set(k, String(v)) })
  const s = p.toString()
  return s ? `?${s}` : ''
}

export default async function ReportPage({ params, searchParams }: PageProps) {
  const id = Number(params.id)
  if (!id) return <div className="p-10 text-rose-500">Invalid Repository ID</div>

  const token = typeof searchParams.token === 'string' ? searchParams.token : ''
  const headers: HeadersInit = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const get = async (path: string, extra: Record<string, any> = {}) => {
    const qsObj: Record<string, any> = {}
    for (const [k, v] of Object.entries(searchParams)) {
      if (k !== 'token' && typeof v === 'string') qsObj[k] = v
    }
    Object.assign(qsObj, extra)
    try {
      const res = await fetch(`${API_BASE}${path}${qs(qsObj)}`, { headers, cache: 'no-store' })
      if (!res.ok) return null
      return res.json()
    } catch { return null }
  }

  const [
    status, kpi, flow, throughput, contributors,
    stale, slowest, prRisk, oldestPRs,
    issueAnalytics, staleIssues,
    branchAnalytics,
    cicdAnalytics,
    forksAnalytics,
    discussionAnalytics,
    discussionTimeline,
    projectsAnalytics,
    repoHealth,
    issuesListRaw,
    branchesListRaw,
    workflowRunsListRaw,
    forksListRaw,
    discussionsListRaw,
    projectsListRaw,
  ] = await Promise.all([
    get(`/api/sync-status/${id}`),
    get(`/api/kpi/${id}`),
    get(`/api/monthly-flow/${id}`, { months: 6 }),
    get(`/api/throughput/${id}`, { weeks: 8 }),
    get(`/api/contributor-activity/${id}`, { page: 1, limit: 20 }),
    get(`/api/stale-alerts/${id}`, { page: 1, limit: 15 }),
    get(`/api/slowest-prs/${id}`, { page: 1, limit: 15 }),
    get(`/api/pr-risk/${id}`, { page: 1, limit: 20 }),
    get(`/api/oldest-prs/${id}`, { page: 1, limit: 15 }),
    get(`/api/issues/analytics/${id}`),
    get(`/api/issues/stale/${id}`, { page: 1, limit: 15 }),
    get(`/api/branches/analytics/${id}`),
    get(`/api/cicd/analytics/${id}`),
    get(`/api/forks/analytics/${id}`),
    get(`/api/discussions/analytics/${id}`),
    get(`/api/discussions/timeline/${id}`),
    get(`/api/projects/analytics/${id}`),
    get(`/api/repo-health/${id}`),
    get(`/api/issues/${id}`, { page: 1, limit: 15 }),
    get(`/api/branches/${id}`, { page: 1, limit: 15 }),
    get(`/api/workflow-runs/${id}`, { page: 1, limit: 15 }),
    get(`/api/forks/${id}`, { page: 1, limit: 15 }),
    get(`/api/discussions/${id}`, { page: 1, limit: 15 }),
    get(`/api/projects/${id}`, { page: 1, limit: 15 }),
  ])

  const contribList = contributors?.data || []
  const staleList = stale?.data || []
  const slowestList = slowest?.data || []
  const staleIssueList = staleIssues?.data || []
  const riskList = prRisk?.data || []
  const oldestList = oldestPRs?.data || []
  const issuesList = issuesListRaw?.data || []
  const branchesList = branchesListRaw?.data || []
  const workflowRunsList = workflowRunsListRaw?.data || []
  const forksList = forksListRaw?.data || []
  const discussionsList = discussionsListRaw?.data || []
  const projectsList = projectsListRaw?.data || []

  return (
    <div className="printable-report min-h-screen bg-[#ffffff] text-[#1e293b] p-8 font-sans relative">
      
      {/* PAGE 1: Overview & Executive Summary */}
      <div className="report-page py-6">
        <ExecutiveSummaryReport status={status} kpi={kpi} repoHealth={repoHealth} />
        <KPIGridReport kpi={kpi} />
      </div>

      {/* PAGE 2: Throughput & Contributor Analytics */}
      <div className="report-page py-6">
        <h2 className="text-xl font-black text-primary mb-6">Throughput & Contributor Analytics</h2>
        <ThroughputReport flow={flow} throughput={throughput} />
        <ContributorAnalyticsReport contributors={contribList} />
      </div>

      {/* PAGE 3: Pull Request Backlog & Insights */}
      <div className="report-page py-6">
        <h2 className="text-xl font-black text-primary mb-6">Pull Request Analysis</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <StalePRTableReport stale={staleList} />
          <BottleneckPRReport slowest={slowestList} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <OldestPRsTable oldestList={oldestList} />
          <PRRiskTable riskList={riskList} />
        </div>
        <AIInsightsReport kpi={kpi} stale={staleList} />
      </div>

      {/* PAGE 4: Issues Analytics */}
      <div className="report-page py-6">
        <IssuesReportSection issueAnalytics={issueAnalytics} staleIssueList={staleIssueList} status={status} />
        <div className="mt-8">
          <IssuesListTable issuesList={issuesList} />
        </div>
      </div>

      {/* PAGE 5: Branches & CI/CD Analytics */}
      <div className="report-page py-6 space-y-6">
        <BranchesAndCICDSection branchAnalytics={branchAnalytics} cicdAnalytics={cicdAnalytics} status={status} />
        <BranchesListTable branchesList={branchesList} />
        <WorkflowRunsListTable workflowRunsList={workflowRunsList} />
      </div>

      {/* PAGE 6: Forks & Discussions */}
      <div className="report-page py-6 space-y-6">
        <ForksAndDiscussionsSection forksAnalytics={forksAnalytics} discussionAnalytics={discussionAnalytics} discussionTimeline={discussionTimeline} status={status} />
        <ForksListTable forksList={forksList} />
        <DiscussionsListTable discussionsList={discussionsList} />
      </div>

      {/* PAGE 7: Projects & Repository Health */}
      <div className="report-page py-6">
        <ProjectsAndHealthSection projectsAnalytics={projectsAnalytics} repoHealth={repoHealth} status={status} />
        <div className="mt-8">
          <ProjectsListTable projectsList={projectsList} />
        </div>
      </div>

      <ReportReadyTrigger />
    </div>
  )
}
