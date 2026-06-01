'use client'

import React, { useState, useEffect, useCallback, Suspense } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated, getAuthUser } from '@/lib/auth'

import { analyzeRepository, formatApiError, getSyncStatus } from '@/lib/api'
import { Loader2 } from 'lucide-react'
import AppShell from '@/components/AppShell'
import RepositoryInput from '@/components/RepositoryInput'

import { loadGithubToken, saveGithubToken } from '@/lib/tokenStorage'

function AnalyzeContent() {
  const router = useRouter()
  const [githubToken, setGithubToken] = useState<string>(() => loadGithubToken())
  const [userName, setUserName] = useState<string | undefined>()
  const [userEmail, setUserEmail] = useState<string | undefined>()
  const [isSyncing, setIsSyncing] = useState(false)
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [isHydrated, setIsHydrated] = useState(false)

  const [activeRepoId, setActiveRepoId] = useState<number | null>(null)
  const [activeRepoLabel, setActiveRepoLabel] = useState<string>('')

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login')
      return
    }

    const savedRepoId = localStorage.getItem('prism_repo_id')
    const savedRepoLabel = localStorage.getItem('prism_repo_label')
    if (savedRepoId) {
      const id = parseInt(savedRepoId, 10)
      if (!isNaN(id)) {
        setActiveRepoId(id)
        if (savedRepoLabel) setActiveRepoLabel(savedRepoLabel)
      }
    }


    setIsHydrated(true)

    const loadUser = async () => {
      try {
        const u = await getAuthUser()
        if (u) {
          setUserName(u.username || undefined)
          setUserEmail(u.email || undefined)
        }
      } catch (err) {
        console.error("Auth load failed", err)
      }
    }
    loadUser()
  }, [router])

  const handleAnalyze = useCallback(async (url: string, token?: string, syncMode?: string) => {
    setGlobalError(null)
    setIsSyncing(true)
    try {
      const result = await analyzeRepository(url, token || githubToken || undefined, syncMode)
      const newRepoId: number = result.repo_id ?? result.id
      const label = result.owner && result.repo ? `${result.owner}/${result.repo}` : url

      // Store in localStorage
      localStorage.setItem('prism_repo_id', String(newRepoId))
      localStorage.setItem('prism_repo_label', label)
      localStorage.setItem('prism_active_section', 'overview')
      localStorage.setItem('prism_dashboard_route', '/dashboard')

      // Redirect to dashboard
      router.push(`/dashboard?repoId=${newRepoId}&section=overview`)

      // Keep PAT for the duration of the session so re-syncs/resumes can use it
      // setGithubToken('')
    } catch (err) {
      setIsSyncing(false)
      setGlobalError(formatApiError(err))
    }
  }, [githubToken, router])

  const handleTokenSave = (t: string) => {
    setGithubToken(t)
    saveGithubToken(t)
  }

  if (!isHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-palette-orange" />
          <p className="text-xs font-bold uppercase tracking-wider text-muted">Loading PRISM...</p>
        </div>
      </div>
    )
  }

  return (
    <AppShell
      hasData={!!activeRepoId}
      repoLabel={activeRepoLabel}
      activeSection="analyze"
      userName={userName}
      userEmail={userEmail}
    >
      <div className="space-y-6">
        {globalError && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-semibold">Error:</span>
              <span>{globalError}</span>
            </div>
          </div>
        )}
        <RepositoryInput
          githubToken={githubToken}
          onGithubTokenChange={handleTokenSave}
          onAnalyze={handleAnalyze}
          isLoading={isSyncing}
          variant="hero"
        />
      </div>
    </AppShell>
  )
}

export default function AnalyzePage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center space-y-3">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-palette-orange" />
          <p className="text-xs font-bold uppercase tracking-wider text-muted">Loading PRISM...</p>
        </div>
      </div>
    }>
      <AnalyzeContent />
    </Suspense>
  )
}
