import axios, { isAxiosError } from 'axios'
import type { DashboardFiltersState } from '@/components/DashboardFilters'

import { getAuthToken } from './auth'

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

function filterParams(filters?: DashboardFiltersState) {
  if (!filters) return {}
  const params: Record<string, string | number> = {}
  if (filters.days) params.days = filters.days
  if (filters.author && filters.author !== 'all') params.author = filters.author
  if (filters.state && filters.state !== 'ALL') params.state = filters.state
  if (filters.startDate) params.start_date = filters.startDate
  if (filters.endDate) params.end_date = filters.endDate
  return params
}

export function formatApiError(err: unknown): string {
  if (!isAxiosError(err)) {
    return err instanceof Error ? err.message : 'An unexpected error occurred'
  }
  if (err.code === 'ERR_NETWORK') {
    return `Cannot reach the API at ${API_BASE}. Please ensure the backend is running.`
  }
  
  const data = err.response?.data
  if (data) {
    // 1. Detail is a string
    if (typeof data.detail === 'string') {
      return data.detail
    }
    
    // 2. Detail is an array of objects (e.g. Pydantic validation errors)
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d: any) => {
          if (typeof d === 'string') return d
          if (d && typeof d === 'object') {
            const loc = Array.isArray(d.loc) ? d.loc.filter((x: any) => x !== 'body').join('.') : ''
            const prefix = loc ? `${loc}: ` : ''
            const msg = d.msg || d.message || JSON.stringify(d)
            return `${prefix}${msg}`
          }
          return String(d)
        })
        .join(' | ')
    }
    
    // 3. Detail is a single object
    if (data.detail && typeof data.detail === 'object') {
      return data.detail.msg || data.detail.message || JSON.stringify(data.detail)
    }

    // 4. Message or error keys in response body
    if (typeof data.message === 'string') {
      return data.message
    }
    if (typeof data.error === 'string') {
      return data.error
    }
  }
  
  return err.message || 'Failed to complete request'
}

// ─── Repository Management ────────────────────────────────────────────────

export interface VerifyRepoResponse {
  ok: boolean
  status: 'VERIFIED_ANONYMOUS' | 'LARGE_REPO_PAT_REQUIRED' | 'PRIVATE_REPO_PAT_REQUIRED' | 'INVALID_PAT' | 'VERIFIED_PAT'
  owner?: string
  repo?: string
  is_private?: boolean
  url?: string
  has_token?: boolean
  token_source?: 'user' | 'env' | 'none'
  stars?: number
  language?: string
  description?: string
  pr_count?: number
  issues_count?: number
  forks_count?: number
  contributors_count?: number
  workflows_count?: number
  discussions_count?: number
  estimated_requests?: number
  above_limit?: boolean
  detail?: string
}

export const verifyRepositoryAccess = async (url: string, githubToken?: string): Promise<VerifyRepoResponse> => {
  const response = await api.post('/api/verify-repo', { url, github_token: githubToken || null })
  return response.data
}

export const analyzeRepository = async (url: string, githubToken?: string, syncMode?: string) => {
  const response = await api.post('/api/analyze', { url, github_token: githubToken || null, sync_mode: syncMode || null })
  return response.data
}

export const getSyncStatus = async (repoId: number) => {
  const response = await api.get(`/api/sync-status/${repoId}`)
  return response.data as {
    id: number; owner: string; name: string; full_name: string
    sync_status: 'IDLE' | 'PENDING' | 'VERIFYING' | 'SYNCING' | 'COMPLETED' | 'FAILED' | 'PARTIAL' | 'RATE_LIMITED'
    sync_mode?: 'full' | 'lightweight' | 'partial'
    sync_progress: string | null; sync_duration: number | null
    sync_started_at?: string | null
    initial_sync_completed: boolean
    last_synced_at: string | null; last_successful_sync: string | null
    next_sync_at: string | null
    error_message: string | null
    total_prs: number; total_issues: number; total_branches: number
    total_forks: number; total_workflow_runs: number; total_discussions: number
    total_projects: number
    rate_limit_remaining: number | null; rate_limit_limit: number | null; rate_limit_reset: string | null
    expected_prs?: number; expected_issues?: number; expected_forks?: number; expected_workflows?: number
    synced_prs?: number; synced_issues?: number; synced_forks?: number; synced_workflows?: number
  }
}

export interface AnalyzedRepo {
  id: number; owner: string; name: string; full_name: string; url: string
  description?: string; language?: string; stars?: number; visibility?: string
  sync_status?: string; initial_sync_completed?: boolean; last_synced_at?: string
  total_prs?: number; total_issues?: number; total_branches?: number
  total_forks?: number; total_workflow_runs?: number; total_discussions?: number
  total_projects?: number
  expected_prs?: number; expected_issues?: number; expected_forks?: number; expected_workflows?: number
  synced_prs?: number; synced_issues?: number; synced_forks?: number; synced_workflows?: number
}

export async function getRepositories(): Promise<AnalyzedRepo[]> {
  const response = await api.get('/api/repositories')
  return response.data
}

// ─── Module 1: Pull Requests ──────────────────────────────────────────────

export const getKPI = async (repoId: number, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/kpi/${repoId}`, { params: filterParams(filters) })
  return response.data
}

export const getOldestPRs = async (repoId: number, page = 1, limit = 10, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/oldest-prs/${repoId}`, { params: { page, limit, ...filterParams(filters) } })
  return response.data
}

export const getSlowestPRs = async (repoId: number, page = 1, limit = 10, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/slowest-prs/${repoId}`, { params: { page, limit, ...filterParams(filters) } })
  return response.data
}

export const getContributorActivity = async (repoId: number, page = 1, limit = 10, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/contributor-activity/${repoId}`, { params: { page, limit, ...filterParams(filters) } })
  return response.data
}

export const getMonthlyFlow = async (repoId: number, months = 6, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/monthly-flow/${repoId}`, { params: { months, ...filterParams(filters) } })
  return response.data
}

export const getThroughput = async (repoId: number, weeks = 8, filters?: DashboardFiltersState) => {
  const response = await api.get(`/api/throughput/${repoId}`, { params: { weeks, ...filterParams(filters) } })
  return response.data
}

export const getAuthors = async (repoId: number) => {
  const response = await api.get(`/api/authors/${repoId}`)
  return response.data.authors as string[]
}

export const getPRRisk = async (repoId: number, page = 1, limit = 15) => {
  const response = await api.get(`/api/pr-risk/${repoId}`, { params: { page, limit } })
  return response.data
}

export const getStaleAlerts = async (repoId: number, page = 1, limit = 10) => {
  const response = await api.get(`/api/stale-alerts/${repoId}`, { params: { page, limit } })
  return response.data
}

export const getMLStatus = async (repoId: number) => {
  const response = await api.get(`/api/ml-status/${repoId}`)
  return response.data as {
    open_prs: number
    prs_with_predictions: number
    models_exist: boolean
    ready: boolean
    reasons: string[]
  }
}

export const refreshMLPredictions = async (repoId: number) => {
  const response = await api.post(`/api/refresh-ml/${repoId}`)
  return response.data as {
    refreshed: number
    models_exist: boolean
    reason: string
  }
}

// ─── Module 2: Issues ────────────────────────────────────────────────────

export const getIssues = async (repoId: number, page = 1, limit = 20, state = 'all', label?: string, search?: string, sort = 'created_at', sortDir = 'desc') => {
  const response = await api.get(`/api/issues/${repoId}`, { params: { page, limit, state, label, search, sort, sort_dir: sortDir } })
  return response.data
}

export const getIssuesAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/issues/analytics/${repoId}`)
  return response.data
}

export const getStaleIssues = async (repoId: number, stale_days = 30, page = 1, limit = 20, search?: string, sort = 'created_at', sortDir = 'asc') => {
  const response = await api.get(`/api/issues/stale/${repoId}`, { params: { stale_days, page, limit, search, sort, sort_dir: sortDir } })
  return response.data
}

// ─── Module 3: Branches ──────────────────────────────────────────────────

export const getBranches = async (repoId: number, page = 1, limit = 20, filter_type = 'all') => {
  const response = await api.get(`/api/branches/${repoId}`, { params: { page, limit, filter_type } })
  return response.data
}

export const getBranchesAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/branches/analytics/${repoId}`)
  return response.data
}

// ─── Module 5: Forks ─────────────────────────────────────────────────────

export const getForks = async (repoId: number, page = 1, limit = 20, filter_type = 'all') => {
  const response = await api.get(`/api/forks/${repoId}`, { params: { page, limit, filter_type } })
  return response.data
}

export const getForksAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/forks/analytics/${repoId}`)
  return response.data
}

// ─── Module 8: CI/CD ─────────────────────────────────────────────────────

export const getCICDAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/cicd/analytics/${repoId}`)
  return response.data
}

export const getWorkflowRuns = async (repoId: number, page = 1, limit = 20, conclusion?: string, branch?: string) => {
  const response = await api.get(`/api/workflow-runs/${repoId}`, { params: { page, limit, conclusion, branch } })
  return response.data
}

// ─── Module 6: Discussions ────────────────────────────────────────────────

export const getDiscussions = async (repoId: number, page = 1, limit = 20) => {
  const response = await api.get(`/api/discussions/${repoId}`, { params: { page, limit } })
  return response.data
}

export const getDiscussionsAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/discussions/analytics/${repoId}`)
  return response.data
}

export const getDiscussionsTimeline = async (repoId: number) => {
  const response = await api.get(`/api/discussions/timeline/${repoId}`)
  return response.data
}

// ─── Module 7: Projects ──────────────────────────────────────────────────

export const getProjects = async (repoId: number, page = 1, limit = 10) => {
  const response = await api.get(`/api/projects/${repoId}`, { params: { page, limit } })
  return response.data
}

export const getProjectsAnalytics = async (repoId: number) => {
  const response = await api.get(`/api/projects/analytics/${repoId}`)
  return response.data
}

// ─── Repository Health ────────────────────────────────────────────────────

export const getRepoHealth = async (repoId: number) => {
  const response = await api.get(`/api/repo-health/${repoId}`)
  return response.data
}

// ─── ML & Export ─────────────────────────────────────────────────────────

export const compareRepositories = async (urlA: string, urlB: string, githubToken?: string) => {
  const response = await api.get('/api/compare', { params: { url_a: urlA, url_b: urlB, github_token: githubToken } })
  return response.data
}

function exportQueryString(filters?: DashboardFiltersState): string {
  const params = new URLSearchParams()
  const fp = filterParams(filters)
  Object.entries(fp).forEach(([k, v]) => params.set(k, String(v)))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function getExportCsvUrl(repoId: number, filters?: DashboardFiltersState): string {
  return `${API_BASE}/api/export/${repoId}${exportQueryString(filters)}`
}

export function getExportPdfUrl(repoId: number, filters?: DashboardFiltersState): string {
  return `${API_BASE}/api/export-pdf/${repoId}${exportQueryString(filters)}`
}

// ─── Authentication API Calls ────────────────────────────────────────────────

export const loginUser = async (payload: any) => {
  const response = await api.post('/api/auth/login', payload)
  return response.data as { access_token: string; username: string; email: string }
}

export const signupUser = async (payload: any) => {
  const response = await api.post('/api/auth/signup', payload)
  return response.data as { access_token: string; username: string; email: string }
}
