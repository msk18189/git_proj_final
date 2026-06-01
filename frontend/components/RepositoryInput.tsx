'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Github, Loader, KeyRound, ShieldCheck, Lock, Search, AlertTriangle, AlertCircle } from 'lucide-react'
import { verifyRepositoryAccess, VerifyRepoResponse } from '@/lib/api'

interface RepositoryInputProps {
  githubToken: string
  onGithubTokenChange: (value: string) => void
  onAnalyze: (url: string, githubToken?: string, syncMode?: string) => Promise<void>
  isLoading: boolean
  variant?: 'hero' | 'dashboard'
}

type VerifyState =
  | 'idle'
  | 'verifying'
  | 'verified_anonymous'
  | 'large_repo_detected'
  | 'private_repo_detected'
  | 'pat_input_required'
  | 'validating_pat'
  | 'verified_pat'
  | 'verification_failed'

export default function RepositoryInput({
  githubToken,
  onGithubTokenChange,
  onAnalyze,
  isLoading,
  variant = 'dashboard',
}: RepositoryInputProps) {
  const [url, setUrl] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verifyMessage, setVerifyMessage] = useState<string | null>(null)
  const [estimation, setEstimation] = useState<VerifyRepoResponse | null>(null)
  const [verifyState, setVerifyState] = useState<VerifyState>('idle')
  const [inTokenFlow, setInTokenFlow] = useState(false)

  const tokenForRequest = () => {
    const t = githubToken.trim()
    return t ? t : undefined
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    // If we have already verified successfully, proceed directly to analysis
    if (verifyState === 'verified_anonymous' || verifyState === 'verified_pat') {
      await onAnalyze(url.trim(), tokenForRequest())
      return
    }

    setVerifying(true)
    setVerifyMessage(null)
    setVerifyState('verifying')
    setEstimation(null)
    setInTokenFlow(false)

    try {
      const result = await verifyRepositoryAccess(url.trim(), tokenForRequest())
      
      if (result.pr_count !== undefined) {
        setEstimation(result)
      }

      if (!result.ok) {
        if (result.status === 'LARGE_REPO_PAT_REQUIRED') {
          setVerifyState('large_repo_detected')
          setInTokenFlow(true)
        } else if (result.status === 'PRIVATE_REPO_PAT_REQUIRED') {
          setVerifyState('private_repo_detected')
          setInTokenFlow(true)
        } else if (result.status === 'INVALID_PAT') {
          setVerifyState('verification_failed')
          setVerifyMessage('GitHub Personal Access Token is invalid or expired.')
          setInTokenFlow(true)
        } else {
          setVerifyState('verification_failed')
          setVerifyMessage(result.detail || 'Repository verification failed.')
        }
        return
      }

      if (result.status === 'VERIFIED_PAT') {
        setVerifyState('verified_pat')
        await onAnalyze(url.trim(), tokenForRequest())
      } else {
        // VERIFIED_ANONYMOUS
        setVerifyState('verified_anonymous')
        await onAnalyze(url.trim(), undefined)
      }

    } catch (err) {
      setVerifyState('verification_failed')
      setVerifyMessage('GitHub API access error. Please check your network connection.')
    } finally {
      setVerifying(false)
    }
  }

  const handleLightweightAnalysis = async () => {
    setVerifyMessage(null)
    setVerifyState('verifying')
    try {
      await onAnalyze(url.trim(), undefined, 'lightweight')
    } catch (err) {
      setVerifyState('verification_failed')
      setVerifyMessage('Failed to start lightweight analysis.')
    }
  }

  const handleUsePatForFull = () => {
    setVerifyState('pat_input_required')
    setInTokenFlow(true)
  }

  const handleBackToLargeRepoChoice = () => {
    setVerifyState('large_repo_detected')
    setVerifyMessage(null)
  }

  const handleValidatePat = async () => {
    if (!githubToken.trim()) {
      setVerifyMessage('Please enter a GitHub Personal Access Token.')
      return
    }

    setVerifyMessage(null)
    setVerifyState('validating_pat')

    try {
      const result = await verifyRepositoryAccess(url.trim(), tokenForRequest())
      
      if (result.pr_count !== undefined) {
        setEstimation(result)
      }

      if (!result.ok) {
        setVerifyState('verification_failed')
        if (result.status === 'INVALID_PAT') {
          setVerifyMessage('GitHub Personal Access Token is invalid or expired.')
        } else {
          setVerifyMessage(result.detail || 'Token validation failed.')
        }
        return
      }

      if (result.status === 'VERIFIED_PAT') {
        setVerifyState('verified_pat')
        await onAnalyze(url.trim(), tokenForRequest())
      } else {
        setVerifyState('verified_anonymous')
        await onAnalyze(url.trim(), undefined)
      }

    } catch (err) {
      setVerifyState('verification_failed')
      setVerifyMessage('GitHub API access error or invalid token. Please check connection and try again.')
    }
  }

  const isHero = variant === 'hero'
  const isVerifyingOrLoading = verifying || isLoading

  return (
    <motion.form
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={handleSubmit}
      className={isHero ? 'p-12 sm:p-16 lg:p-24' : 'card card-hover'}
    >
      {!isHero && (
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-palette-emerald-light">
            <Search className="h-5 w-5 text-palette-emerald" />
          </div>
          <div>
            <h2 className="text-base font-bold text-primary">Change repository</h2>
            <p className="text-xs text-muted">Run a new analysis</p>
          </div>
        </div>
      )}

      {isHero && (
        <div className="mb-8 text-center space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-primary sm:text-3xl">Analyze repository</h2>
          <p className="text-base text-secondary">Paste a GitHub URL to start the repository analytics workflow</p>
        </div>
      )}

      <div className={isHero ? 'space-y-6 sm:space-y-8' : 'space-y-4'}>
        <div>
          <label className={`mb-2 block font-semibold uppercase tracking-wider text-secondary ${isHero ? 'text-xs sm:text-sm' : 'text-[10px]'}`}>
            Repository URL
          </label>
          <div className="relative">
            <Github className={`absolute top-1/2 -translate-y-1/2 text-muted ${isHero ? 'h-6 w-6 left-5' : 'h-4 w-4 left-3.5'}`} />
            <input
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                setVerifyMessage(null)
                setVerifyState('idle')
                setEstimation(null)
                setInTokenFlow(false)
              }}
              placeholder="github.com/owner/repo"
              className={`input-field ${isHero ? 'h-14 pr-5 !rounded-2xl text-lg' : 'pr-4 text-sm'}`}
              style={{ paddingLeft: isHero ? '4rem' : '3rem' }}
              disabled={isVerifyingOrLoading}
            />
          </div>
        </div>

        {/* Dedicated Verification Cards Container */}
        <AnimatePresence mode="wait">
          {/* 1. Loader / Verifying state */}
          {verifyState === 'verifying' && (
            <motion.div
              key="verifying"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-warm-200 bg-warm-50/50 p-5 flex items-center gap-3 shadow-sm"
            >
              <Loader className="h-5 w-5 animate-spin text-palette-emerald shrink-0" />
              <p className="text-sm font-medium text-secondary">Verifying repository access...</p>
            </motion.div>
          )}

          {/* 2. Large repository detected card (Step 2A) */}
          {verifyState === 'large_repo_detected' && (
            <motion.div
              key="large_repo"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-palette-amber/20 bg-palette-amber-light/10 p-5 space-y-4 shadow-sm"
            >
              <div className="flex gap-3">
                <AlertTriangle className="h-5 w-5 text-palette-amber shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-primary">Large repository detected</h3>
                  <p className="text-xs text-secondary mt-1">
                    Full analytics requires a GitHub Personal Access Token.
                  </p>
                  <p className="text-xs text-muted mt-2">
                    You can either:
                    <br />• continue with limited lightweight analysis
                    <br />• or provide a PAT for complete analytics
                  </p>
                </div>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleLightweightAnalysis}
                  className="btn-secondary text-xs flex-1 justify-center py-2 h-10"
                >
                  Continue Lightweight Analysis
                </button>
                <button
                  type="button"
                  onClick={handleUsePatForFull}
                  className="btn-primary text-xs flex-1 justify-center py-2 h-10"
                >
                  Use PAT for Full Analysis
                </button>
              </div>
            </motion.div>
          )}

          {/* 3. PAT input for large repository flow */}
          {verifyState === 'pat_input_required' && (
            <motion.div
              key="pat_input"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-warm-200 bg-white/60 p-5 space-y-4 shadow-sm"
            >
              <div className="flex gap-3">
                <KeyRound className="h-5 w-5 text-palette-emerald shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-primary">Use PAT for Full Analysis</h3>
                  <p className="text-xs text-secondary mt-1">
                    Please provide a GitHub Personal Access Token for complete analytics.
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <input
                  type="password"
                  autoComplete="off"
                  value={githubToken}
                  onChange={(e) => onGithubTokenChange(e.target.value)}
                  placeholder="ghp_…"
                  className="input-field font-mono text-sm h-10"
                />

                <div className="flex gap-2 rounded-xl border border-palette-amber/15 bg-palette-amber-light/10 p-3 text-[11px]">
                  <Lock className="h-3.5 w-3.5 text-palette-amber shrink-0 mt-0.5" />
                  <p className="text-secondary leading-relaxed">
                    Note: Private or large repos need a{' '}
                    <a
                      href="https://github.com/settings/tokens"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-palette-emerald hover:underline"
                    >
                      PAT
                    </a>{' '}
                    with <span className="font-medium text-primary">repo</span> scope.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleBackToLargeRepoChoice}
                  className="btn-secondary text-xs px-3 py-1.5 h-9"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleValidatePat}
                  disabled={!githubToken.trim()}
                  className="btn-primary text-xs px-4 py-1.5 h-9"
                >
                  Validate & Continue
                </button>
              </div>
            </motion.div>
          )}

          {/* 4. Private repository detected card (Step 2B) */}
          {verifyState === 'private_repo_detected' && (
            <motion.div
              key="private_repo"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-rose-200 bg-rose-50/30 p-5 space-y-4 shadow-sm"
            >
              <div className="flex gap-3">
                <Lock className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-rose-900">Private repository detected</h3>
                  <p className="text-xs text-rose-800 mt-1">
                    A GitHub Personal Access Token is required to access this repository.
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <input
                  type="password"
                  autoComplete="off"
                  value={githubToken}
                  onChange={(e) => onGithubTokenChange(e.target.value)}
                  placeholder="ghp_…"
                  className="input-field font-mono text-sm h-10"
                />

                <div className="flex gap-2 rounded-xl border border-palette-amber/15 bg-palette-amber-light/10 p-3 text-[11px]">
                  <Lock className="h-3.5 w-3.5 text-palette-amber shrink-0 mt-0.5" />
                  <p className="text-secondary leading-relaxed">
                    Note: Private repos require a{' '}
                    <a
                      href="https://github.com/settings/tokens"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-palette-emerald hover:underline"
                    >
                      PAT
                    </a>{' '}
                    with <span className="font-medium text-primary">repo</span> scope.
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleValidatePat}
                  disabled={!githubToken.trim()}
                  className="btn-primary text-xs px-4 py-1.5 h-9"
                >
                  Validate & Continue
                </button>
              </div>
            </motion.div>
          )}

          {/* 5. Validating PAT state card */}
          {verifyState === 'validating_pat' && (
            <motion.div
              key="validating_pat"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-warm-200 bg-warm-50/50 p-5 flex items-center gap-3 shadow-sm"
            >
              <Loader className="h-5 w-5 animate-spin text-palette-emerald shrink-0" />
              <p className="text-sm font-medium text-secondary">Validating Personal Access Token...</p>
            </motion.div>
          )}

          {/* 6. Verification Failed state card (Inside Token Flow) */}
          {verifyState === 'verification_failed' && inTokenFlow && (
            <motion.div
              key="token_failed"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-rose-200 bg-rose-50/30 p-5 space-y-4 shadow-sm"
            >
              <div className="flex gap-3">
                <AlertCircle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-rose-900 font-bold">Token validation failed</h3>
                  {verifyMessage && (
                    <p className="text-xs text-rose-800 mt-1 leading-relaxed">{verifyMessage}</p>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <input
                  type="password"
                  autoComplete="off"
                  value={githubToken}
                  onChange={(e) => onGithubTokenChange(e.target.value)}
                  placeholder="ghp_…"
                  className="input-field font-mono text-sm h-10"
                />
              </div>

              <div className="flex justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleValidatePat}
                  disabled={!githubToken.trim()}
                  className="btn-primary text-xs px-4 py-1.5 h-9"
                >
                  Validate & Retry
                </button>
              </div>
            </motion.div>
          )}

          {/* 7. Verification Failed (General URL/Network Error, NOT in Token Flow) */}
          {verifyState === 'verification_failed' && !inTokenFlow && (
            <motion.div
              key="general_failed"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-rose-200 bg-rose-50/30 p-4 text-rose-800 text-xs flex gap-2 shadow-sm"
            >
              <AlertCircle className="h-5 w-5 shrink-0 text-rose-500 mt-0.5" />
              <div>
                <span className="font-bold block mb-0.5">Verification failed</span>
                {verifyMessage || 'Repository verification failed.'}
              </div>
            </motion.div>
          )}

          {/* 8. Success validation loader */}
          {(verifyState === 'verified_anonymous' || verifyState === 'verified_pat') && (
            <motion.div
              key="success"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="rounded-2xl border border-palette-emerald/20 bg-palette-emerald-light/10 p-5 flex items-center gap-3 shadow-sm"
            >
              <ShieldCheck className="h-5 w-5 text-palette-emerald shrink-0 animate-bounce" />
              <p className="text-sm font-medium text-palette-emerald">Access verified! Starting analysis...</p>
            </motion.div>
          )}
        </AnimatePresence>

        {estimation && (verifyState === 'verified_anonymous' || verifyState === 'verified_pat') && (
          <div className="rounded-2xl border border-warm-200 bg-white/50 p-5 space-y-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-secondary">
              Expected API Requests & Repository Details
            </h3>
            
            <div className="grid grid-cols-2 gap-4 text-xs sm:grid-cols-3">
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Pull Requests</span>
                <span className="text-sm font-bold text-primary">{estimation.pr_count}</span>
              </div>
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Issues</span>
                <span className="text-sm font-bold text-primary">{estimation.issues_count}</span>
              </div>
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Forks</span>
                <span className="text-sm font-bold text-primary">{estimation.forks_count}</span>
              </div>
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Contributors</span>
                <span className="text-sm font-bold text-primary">{estimation.contributors_count}</span>
              </div>
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Workflows</span>
                <span className="text-sm font-bold text-primary">{estimation.workflows_count}</span>
              </div>
              <div className="rounded-xl bg-warm-50 p-3">
                <span className="block text-muted">Discussions</span>
                <span className="text-sm font-bold text-primary">{estimation.discussions_count}</span>
              </div>
            </div>

            <div className="rounded-xl bg-warm-50 p-3 flex justify-between items-center text-xs">
              <span className="text-muted">Estimated API Requests:</span>
              <span className="text-sm font-bold text-palette-orange">
                ~{estimation.estimated_requests} calls
              </span>
            </div>
          </div>
        )}

        {/* Initial Form Action Block */}
        <div className="flex flex-col gap-4 pt-2 sm:flex-row">
          <button
            type="submit"
            disabled={isVerifyingOrLoading}
            className={`btn-primary flex flex-1 items-center justify-center gap-2.5 transition-all duration-300 ${isHero ? 'text-lg h-14 !rounded-2xl font-bold shadow-lg hover:shadow-xl' : 'text-sm'}`}
          >
            {isVerifyingOrLoading ? (
              <>
                <Loader className={isHero ? 'h-6 w-6 animate-spin' : 'h-4 w-4 animate-spin'} />
                <span>Analyzing…</span>
              </>
            ) : (
              <span>Analyze</span>
            )}
          </button>
        </div>
      </div>
    </motion.form>
  )
}
