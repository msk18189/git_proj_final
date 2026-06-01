'use client'

import { useState, useEffect } from 'react'
import {
  LayoutDashboard,
  GitPullRequest,
  CircleDot,
  GitBranch,
  Zap,
  GitFork,
  Kanban,
  MessageCircle,
  Heart,
  Settings,
  Plus,
  Bell,
  ChevronRight,
  ChevronLeft,
  LogOut,
  Star,
  Calendar,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { signOut } from '@/lib/auth'

export type NavSection =
  | 'analyze'
  | 'overview'
  | 'pull_requests'
  | 'issues'
  | 'branches'
  | 'cicd'
  | 'forks'
  | 'projects'
  | 'discussions'
  | 'repo_health'
  | 'settings'

interface NavItem {
  id: NavSection
  label: string
  icon: React.ReactNode
  requiresData?: boolean
  badge?: number | string | null
}

interface SyncStatus {
  sync_status: 'IDLE' | 'PENDING' | 'VERIFYING' | 'SYNCING' | 'COMPLETED' | 'FAILED' | 'PARTIAL' | 'RATE_LIMITED'
  sync_progress: string | null
  sync_duration: number | null
  initial_sync_completed: boolean
  last_synced_at: string | null
  last_successful_sync: string | null
  error_message: string | null
  total_prs: number
  total_issues: number
  total_branches: number
  total_forks: number
  total_workflow_runs: number
  total_discussions: number
  total_projects: number
  rate_limit_remaining: number | null
  rate_limit_limit: number | null
}

interface AppShellProps {
  children: React.ReactNode
  hasData: boolean
  repoLabel?: string
  headerActions?: React.ReactNode
  /** Authenticated user's username/display name — comes from JWT or /me endpoint */
  userName?: string
  /** Authenticated user's email — comes from JWT or /me endpoint */
  userEmail?: string
  activeSection?: NavSection
  onNavigate?: (section: NavSection) => void
  syncCounts?: {
    total_prs?: number
    total_issues?: number
    total_branches?: number
    total_forks?: number
    total_workflow_runs?: number
    total_discussions?: number
    total_projects?: number
  }
  syncStatus?: SyncStatus | null
  onSync?: () => void
  isSyncing?: boolean
}

export default function AppShell({
  children,
  hasData,
  repoLabel,
  headerActions,
  userName,
  userEmail,
  activeSection = 'analyze',
  onNavigate,
  syncCounts,
  syncStatus,
  onSync,
  isSyncing,
}: AppShellProps) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isCollapsed, setIsCollapsed] = useState(false)
  // Track whether auth props have been resolved from parent
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    // Mark auth as resolved once we've had at least one render cycle
    // This prevents flashing while the parent loads auth data
    const t = setTimeout(() => setAuthReady(true), 300)
    return () => clearTimeout(t)
  }, [])

  const handleSignOut = async () => {
    await signOut()
    router.replace('/login')
  }

  const currentRepoId = searchParams.get('repoId') || (typeof window !== 'undefined' ? localStorage.getItem('prism_repo_id') : null)

  const NAV: NavItem[] = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="h-4 w-4 shrink-0" />, requiresData: true },
    {
      id: 'pull_requests', label: 'Pull Requests', icon: <GitPullRequest className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_prs,
    },
    {
      id: 'issues', label: 'Issues', icon: <CircleDot className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_issues,
    },
    {
      id: 'branches', label: 'Branches', icon: <GitBranch className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_branches,
    },
    {
      id: 'cicd', label: 'CI/CD', icon: <Zap className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_workflow_runs,
    },
    {
      id: 'forks', label: 'Forks', icon: <GitFork className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_forks,
    },
    {
      id: 'projects', label: 'Projects', icon: <Kanban className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_projects,
    },
    {
      id: 'discussions', label: 'Discussions', icon: <MessageCircle className="h-4 w-4 shrink-0" />,
      requiresData: true, badge: syncCounts?.total_discussions,
    },
    { id: 'repo_health', label: 'Repo Health', icon: <Heart className="h-4 w-4 shrink-0" />, requiresData: true },
    { id: 'settings', label: 'Settings', icon: <Settings className="h-4 w-4 shrink-0" />, requiresData: false },
  ]

  const navigate = (id: NavSection) => {
    onNavigate?.(id)
    if (id === 'analyze') {
      localStorage.removeItem('prism_repo_id')
      localStorage.removeItem('prism_repo_label')
      localStorage.removeItem('prism_active_section')
      localStorage.removeItem('prism_dashboard_route')
      router.push('/analyze')
    } else {
      const repoId = currentRepoId
      if (repoId) {
        router.push(`/dashboard?repoId=${repoId}&section=${id}`)
      } else {
        router.push(`/dashboard?section=${id}`)
      }
    }
  }

  const formatBadge = (n?: number | string | null): string | null => {
    if (!n) return null
    const num = typeof n === 'string' ? parseInt(n) : n
    if (isNaN(num) || num === 0) return null
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
    return String(num)
  }

  // Derive display values strictly from auth props — no hardcoded fallbacks
  const displayName = userName || null
  const displayEmail = userEmail || null
  const displayInitials = displayName
    ? displayName
        .split(/[\s._-]+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join('')
    : null

  /* Landing — no sidebar */
  if (!hasData) {
    return (
      <div className="landing-center relative bg-slate-50">
        {/* Top-right auth badge — only if we have real user data */}
        {displayName && (
          <div className="absolute top-6 right-6 flex items-center gap-2.5 z-20 bg-white border border-slate-200 px-3.5 py-2 rounded-xl shadow-sm">
            <div className="h-6 w-6 rounded-full bg-[#fdf2ec] dark:bg-orange-950/20 text-[#c2410c] dark:text-orange-400 flex items-center justify-center font-bold text-[10px] border border-[#fce6d8] dark:border-orange-950/30 shrink-0">
              {displayInitials}
            </div>
            <span className="text-xs font-semibold text-slate-700">{displayName}</span>
            <span className="h-3.5 w-px bg-slate-200"></span>
            <button
              onClick={handleSignOut}
              className="text-xs text-rose-600 hover:text-rose-700 font-semibold flex items-center gap-1.5 transition"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign Out
            </button>
          </div>
        )}
        <div className="w-full max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="landing-hero-title mb-10 space-y-4">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-indigo-50 border border-indigo-100 shadow-sm">
              <GitBranch className="h-8 w-8 text-indigo-600" />
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">PRISM</h1>
            <p className="mx-auto mt-2 max-w-xl text-base text-slate-500 sm:text-lg">
              Enterprise GitHub Engineering Intelligence Platform
            </p>
          </div>
          {children}
        </div>
      </div>
    )
  }

  const activeNavItem = NAV.find(n => n.id === activeSection)

  return (
    <div className="flex h-screen overflow-hidden bg-background p-0 text-secondary transition-colors duration-200">

      {/* ── Sidebar ── */}
      <aside
        className={`hidden shrink-0 flex-col bg-surface border-r border-border p-4 text-secondary transition-all duration-300 lg:flex ${isCollapsed ? 'w-[76px]' : 'w-[260px]'
          }`}
      >
        {/* Logo and toggle */}
        <div className="mb-6 flex items-center justify-between px-1">
          {!isCollapsed && (
            <button
              type="button"
              onClick={() => navigate('analyze')}
              className="flex items-center gap-2.5 hover:opacity-85 transition text-left"
              title="Analyze new repository"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-sm text-white">
                <GitBranch className="h-4.5 w-4.5" />
              </div>
              <div>
                <span className="text-base font-bold tracking-tight text-primary">PRISM</span>
                <p className="text-[9px] font-bold uppercase tracking-wider text-muted">Engineering Intelligence</p>
              </div>
            </button>
          )}
          {isCollapsed && (
            <button
              type="button"
              onClick={() => navigate('analyze')}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-sm text-white mx-auto hover:opacity-85 transition"
              title="Analyze new repository"
            >
              <GitBranch className="h-4.5 w-4.5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1 rounded-lg hover:bg-bg-hover text-muted hover:text-primary hidden lg:block"
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        {/* Compact Repository selector */}
        {repoLabel && !isCollapsed && (
          <div className="mb-4 rounded-xl bg-surface-soft border border-border px-3 py-2 flex items-center justify-between">
            <div className="min-w-0 flex-1">
              <p className="text-[9px] font-bold uppercase tracking-wider text-muted">Workspace</p>
              <p className="truncate text-xs font-semibold text-primary" title={repoLabel}>{repoLabel}</p>
            </div>
            <div className="flex items-center gap-1 shrink-0 ml-1.5">
              <button
                type="button"
                onClick={() => navigate('analyze')}
                className="p-1 rounded-lg hover:bg-surface border border-border text-muted hover:text-primary transition"
                title="Analyze new repository"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
              <div className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {NAV.map((item) => {
            const active = activeSection === item.id
            const badge = formatBadge(item.badge)
            return (
              <button
                key={item.id}
                type="button"
                id={`nav-${item.id}`}
                onClick={() => navigate(item.id)}
                className={`group flex items-center rounded-xl px-3 py-2.5 text-xs font-semibold transition-all relative ${active
                  ? 'bg-orange-50 dark:bg-orange-950/20 text-[#c2410c] dark:text-orange-400'
                  : 'text-secondary hover:bg-bg-hover hover:text-primary'
                  } ${isCollapsed ? 'justify-center' : 'gap-3'}`}
                title={isCollapsed ? item.label : undefined}
              >
                <span className={active ? 'text-[#c2410c] dark:text-orange-400' : 'text-muted group-hover:text-secondary'}>
                  {item.icon}
                </span>
                {!isCollapsed && <span className="flex-1 text-left">{item.label}</span>}
                {!isCollapsed && badge && (
                  <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold ${active
                    ? 'bg-orange-100 dark:bg-orange-950/40 text-[#c2410c] dark:text-orange-400'
                    : 'bg-surface-soft text-muted'
                    }`}>
                    {badge}
                  </span>
                )}
                {active && !isCollapsed && <ChevronRight className="h-3 w-3 text-[#c2410c] dark:text-orange-400 shrink-0" />}
              </button>
            )
          })}
        </nav>

        {/* Floating Sync Status Card */}
        {!isCollapsed && syncStatus && (
          <div className="mb-4 mt-4 rounded-xl border border-border bg-surface-soft p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[9px] font-bold uppercase tracking-wider text-muted">Sync Status</span>
              <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${syncStatus.sync_status === 'COMPLETED'
                ? 'bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400'
                : 'bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400'
                }`}>
                {syncStatus.sync_status === 'COMPLETED' ? 'Completed' : syncStatus.sync_status}
              </span>
            </div>
            <div className="flex flex-col gap-0.5 text-[10px] text-secondary">
              <div className="flex justify-between">
                <span>Last sync</span>
                <span className="font-semibold text-primary">
                  {syncStatus.last_successful_sync
                    ? (() => {
                        // Ensure ISO string has 'Z' suffix for UTC parsing
                        let isoStr = syncStatus.last_successful_sync
                        if (!isoStr.endsWith('Z') && !isoStr.includes('+')) {
                          isoStr += 'Z'
                        }
                        
                        const lastSync = new Date(isoStr)
                        const now = new Date()
                        const diffMs = now.getTime() - lastSync.getTime()
                        const diffMinutes = Math.floor(diffMs / 60000)
                        const diffHours = Math.floor(diffMinutes / 60)
                        const diffDays = Math.floor(diffHours / 24)
                        
                        // Format in local timezone using toLocaleString
                        const timeStr = lastSync.toLocaleString('en-US', {
                          hour: 'numeric',
                          minute: '2-digit',
                          second: '2-digit',
                          hour12: true
                        })
                        
                        let relativeStr = ''
                        if (diffMinutes < 1) {
                          relativeStr = 'just now'
                        } else if (diffMinutes < 60) {
                          relativeStr = `${diffMinutes}m ago`
                        } else if (diffHours < 24) {
                          relativeStr = `${diffHours}h ago`
                        } else if (diffDays < 7) {
                          relativeStr = `${diffDays}d ago`
                        } else {
                          relativeStr = lastSync.toLocaleDateString('en-US')
                        }
                        
                        return `${timeStr} (${relativeStr})`
                      })()
                    : 'Never'}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Next Sync</span>
                <span className="font-semibold text-primary">
                  {syncStatus.next_sync_at
                    ? (() => {
                        // Ensure ISO string has 'Z' suffix for UTC parsing
                        let isoStr = syncStatus.next_sync_at
                        if (!isoStr.endsWith('Z') && !isoStr.includes('+')) {
                          isoStr += 'Z'
                        }
                        
                        const nextSync = new Date(isoStr)
                        const now = new Date()
                        const diffMs = nextSync.getTime() - now.getTime()
                        
                        if (diffMs <= 0) {
                          return 'In progress'
                        }
                        
                        const diffMinutes = Math.floor(diffMs / 60000)
                        const diffHours = Math.floor(diffMinutes / 60)
                        
                        if (diffHours >= 1) {
                          return `In ${diffHours}h ${diffMinutes % 60}m`
                        }
                        return `In ${diffMinutes}m`
                      })()
                    : 'Not scheduled'}
                </span>
              </div>
            </div>
            {onSync && (
              <button
                type="button"
                onClick={onSync}
                disabled={isSyncing}
                className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-border bg-surface py-1.5 text-[11px] font-semibold text-secondary hover:bg-bg-hover transition disabled:opacity-50"
              >
                <RefreshCw className={`h-3 w-3 ${isSyncing ? 'animate-spin' : ''}`} />
                Sync Now
              </button>
            )}
          </div>
        )}

        {/* Sidebar Footer — User profile block (fully dynamic, no hardcoded fallbacks) */}
        <div
          className={`mt-auto border-t border-border pt-3 flex items-center ${isCollapsed ? 'justify-center' : 'gap-2.5'} px-1`}
          role="region"
          aria-label="User profile"
        >
          {/* Loading skeleton — shown while auth data is resolving */}
          {!authReady && !displayName && (
            <>
              <div className="h-8 w-8 shrink-0 rounded-full bg-surface-soft animate-pulse" />
              {!isCollapsed && (
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="h-2.5 w-24 rounded bg-surface-soft animate-pulse" />
                  <div className="h-2 w-32 rounded bg-surface-soft animate-pulse" />
                </div>
              )}
            </>
          )}

          {/* Authenticated user profile */}
          {(authReady || displayName) && (
            <>
              {/* Avatar circle with dynamic initials */}
              <div
                className="h-8 w-8 shrink-0 rounded-full bg-orange-50 dark:bg-orange-950/25 text-[#c2410c] dark:text-orange-400 flex items-center justify-center font-bold text-xs border border-orange-200 dark:border-orange-900/20 select-none"
                aria-hidden="true"
                title={displayName ?? 'User'}
              >
                {displayInitials ?? '?'}
              </div>

              {!isCollapsed && (
                <div className="flex-1 min-w-0">
                  {displayName ? (
                    <p
                      className="text-[11px] font-bold text-primary truncate leading-tight"
                      title={displayName}
                    >
                      {displayName}
                    </p>
                  ) : (
                    <p className="text-[11px] text-muted italic">Loading…</p>
                  )}
                  {displayEmail ? (
                    <p
                      className="text-[9px] text-muted truncate mt-0.5 leading-tight"
                      title={displayEmail}
                    >
                      {displayEmail}
                    </p>
                  ) : null}
                </div>
              )}

              {!isCollapsed && (
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="ml-auto text-muted hover:text-rose-600 transition p-1 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/20"
                  title="Sign Out"
                  aria-label="Sign out"
                >
                  <LogOut className="h-3.5 w-3.5" />
                </button>
              )}
            </>
          )}
        </div>
      </aside>

      {/* ── Main Panel ── */}
      <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-background">

        {/* Sticky Top Navbar */}
        <header className="flex items-center justify-between border-b border-border bg-surface px-5 py-3 sticky top-0 z-10 shrink-0">
          <div className="flex items-center gap-3">
            {/* Repo selector and display */}
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-surface-soft text-secondary border border-border">
                <GitBranch className="h-4 w-4" />
              </div>
              <span className="text-sm font-bold text-primary">{repoLabel || 'OpenBMB / MiniCPM-V'}</span>
              <button type="button" className="text-muted hover:text-amber-500 transition">
                <Star className="h-3.5 w-3.5 fill-current" />
              </button>
            </div>

            {/* Sync Status badge */}
            {syncStatus && (
              <span className={`hidden rounded-full border px-2 py-0.5 text-[10px] font-semibold sm:inline-block ${
                syncStatus.sync_status === 'COMPLETED'
                  ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-250 dark:border-emerald-850 text-emerald-700 dark:text-emerald-400'
                  : syncStatus.sync_status === 'FAILED'
                  ? 'bg-rose-50 dark:bg-rose-950/20 border-rose-250 dark:border-rose-850 text-rose-700 dark:text-rose-400'
                  : syncStatus.sync_status === 'PARTIAL' || syncStatus.sync_status === 'RATE_LIMITED'
                  ? 'bg-amber-50 dark:bg-amber-950/20 border-amber-250 dark:border-amber-850 text-amber-700 dark:text-amber-400'
                  : syncStatus.sync_status === 'SYNCING' || syncStatus.sync_status === 'PENDING'
                  ? 'bg-blue-50 dark:bg-blue-950/20 border-blue-250 dark:border-blue-850 text-blue-700 dark:text-blue-400'
                  : 'bg-slate-50 dark:bg-slate-950/20 border-slate-250 dark:border-slate-850 text-slate-700 dark:text-slate-400'
              }`}>
                {syncStatus.sync_status === 'COMPLETED' 
                  ? 'Completed' 
                  : syncStatus.sync_status === 'SYNCING' 
                  ? 'Syncing...' 
                  : syncStatus.sync_status === 'PENDING'
                  ? 'Pending'
                  : syncStatus.sync_status === 'VERIFYING'
                  ? 'Verifying'
                  : syncStatus.sync_status === 'PARTIAL'
                  ? 'Partial'
                  : syncStatus.sync_status === 'RATE_LIMITED'
                  ? 'Rate Limited'
                  : syncStatus.sync_status === 'FAILED'
                  ? 'Failed'
                  : syncStatus.sync_status}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Bell/Notifications */}
            <button
              type="button"
              className="rounded-lg p-1.5 border border-border hover:bg-bg-hover text-secondary transition"
              aria-label="Notifications"
            >
              <Bell className="h-4 w-4" />
            </button>

            {/* Header Actions */}
            {headerActions && (
              <div className="flex items-center gap-1.5">
                {headerActions}
              </div>
            )}
          </div>
        </header>

        {/* Mobile Navigation bar */}
        <nav className="flex gap-1.5 overflow-x-auto border-b border-border bg-surface px-4 py-2 lg:hidden scrollbar-none">
          {NAV.map((item) => {
            const active = activeSection === item.id
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => navigate(item.id)}
                className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all ${active
                  ? 'bg-orange-50 dark:bg-orange-950/20 text-[#c2410c] dark:text-orange-400 border border-orange-200 dark:border-orange-900/25'
                  : 'bg-surface-soft border border-border text-secondary hover:bg-bg-hover'
                  }`}
              >
                {item.icon}
                {item.label}
              </button>
            )
          })}
        </nav>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 max-w-7xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  )
}
