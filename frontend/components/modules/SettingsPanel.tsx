'use client'
 
import { useState } from 'react'
import { Settings, Key, Database, Info, RefreshCw, Save, Sun, Moon, Laptop } from 'lucide-react'
import { useTheme } from '@/components/ThemeProvider'
 
interface Props {
  repoLabel?: string
  onTokenChange?: (token: string) => void
}
 
export default function SettingsPanel({ repoLabel, onTokenChange }: Props) {
  const { theme, setTheme } = useTheme()
  const [token, setToken] = useState('')
  const [saved, setSaved] = useState(false)

  const [backgroundSync, setBackgroundSync] = useState(false)
  const [rateLimitRecover, setRateLimitRecover] = useState(true)

  const handleSave = () => {
    onTokenChange?.(token)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }
 
  const themesList = [
    { id: 'light', name: 'Light Mode', icon: Sun, desc: 'Clean, high-contrast cool white workspace' },
    { id: 'dark', name: 'Dark Mode', icon: Moon, desc: 'Sleek, Linear-inspired deep blue canvas' },
    { id: 'system', name: 'System Sync', icon: Laptop, desc: 'Auto-syncs with your operating system' },
  ] as const
 
  return (
    <div className="space-y-8 max-w-4xl">
 
      {/* Appearance Settings */}
      <div className="rounded-2xl border border-border bg-surface p-6 space-y-6 shadow-sm">
        <div>
          <h3 className="text-sm font-bold text-primary flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100/10 dark:border-indigo-900/20 text-indigo-600 dark:text-indigo-400">
              <Settings className="h-4 w-4" />
            </span>
            Appearance Preferences
          </h3>
          <p className="text-xs text-muted mt-1">Configure your theme options to switch between light and dark visual aesthetics</p>
        </div>
 
        {/* Live Preview Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {themesList.map((t) => {
            const Icon = t.icon
            const active = theme === t.id
            return (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`text-left rounded-xl border p-4 transition-all duration-200 flex flex-col justify-between h-32 ${
                  active
                    ? 'border-indigo-500 ring-2 ring-indigo-500/10 bg-indigo-50/10 dark:bg-indigo-950/10'
                    : 'border-border bg-surface hover:border-border/80 hover:bg-bg-hover'
                }`}
              >
                <div className="flex items-center justify-between w-full">
                  <span className={`p-2 rounded-lg ${
                    active 
                      ? 'bg-indigo-500 text-white' 
                      : 'bg-surface-soft text-muted'
                  }`}>
                    <Icon className="h-4.5 w-4.5" />
                  </span>
                  <div className={`h-2.5 w-2.5 rounded-full ${active ? 'bg-indigo-500' : 'bg-transparent'}`} />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-primary">{t.name}</h4>
                  <p className="text-[10px] text-muted mt-0.5 leading-relaxed">{t.desc}</p>
                </div>
              </button>
            )
          })}
        </div>
      </div>
 
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* GitHub Token configuration */}
        <div className="rounded-2xl border border-border bg-surface p-5 space-y-4 shadow-sm flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100/15 dark:border-indigo-900/20 text-indigo-600 dark:text-indigo-400 shrink-0">
                <Key className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-primary">GitHub Access Token</h3>
                <p className="text-[10px] text-muted font-semibold">Higher rate limits (5,000 requests/hr)</p>
              </div>
            </div>
 
            <div className="rounded-xl border border-indigo-100 dark:border-indigo-900/30 bg-indigo-50/20 dark:bg-indigo-950/10 p-3 text-indigo-950 dark:text-indigo-300 text-xs flex gap-2 leading-relaxed">
              <Info className="h-3.5 w-3.5 shrink-0 mt-0.5 text-indigo-500 dark:text-indigo-400" />
              <span>Token is temporary and only used for the current analysis session. It is never stored or persisted.</span>
            </div>
 
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted block">Personal Access Token</label>
              <input
                type="password"
                value={token}
                onChange={e => setToken(e.target.value)}
                placeholder="github_pat_..."
                className="w-full rounded-xl bg-background dark:bg-background/50 border border-border px-3.5 py-2.5 text-xs text-primary dark:text-primary placeholder:text-muted focus:outline-none focus:border-indigo-500 font-mono transition"
              />
              <p className="text-[9px] text-muted font-semibold">
                Required scopes: <code className="font-bold text-secondary">public_repo</code> or <code className="font-bold text-secondary">repo</code> (private), <code className="font-bold text-secondary">read:project</code>
              </p>
            </div>
          </div>
 
          <button onClick={handleSave}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-sm transition flex items-center justify-center gap-1.5 mt-4">
            <Save className="h-3.5 w-3.5" />
            {saved ? '✓ Token Applied' : 'Apply Token'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
 
        {/* Sync Settings */}
        <div className="rounded-2xl border border-border bg-surface p-5 space-y-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50/50 dark:bg-amber-950/20 border border-amber-100/15 dark:border-amber-900/20 text-amber-600 dark:text-amber-400 shrink-0">
              <RefreshCw className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-primary">Ingestion & Sync Configuration</h3>
              <p className="text-[10px] text-muted font-semibold">Database updates and rate limit throttling</p>
            </div>
          </div>
 
          <div className="space-y-3 pt-2">
            {[
              { id: 'bg-sync', label: 'Background Incremental Syncing', desc: 'Sync database records in background every 1 hour', value: backgroundSync, onChange: setBackgroundSync },
              { id: 'rate-limit', label: 'Automatic Rate-Limiting Recovery', desc: 'Sleeps and auto-resumes ingestion when PAT budget ends', value: rateLimitRecover, onChange: setRateLimitRecover },
            ].map((cfg) => (
              <div key={cfg.id} className="flex items-start justify-between gap-4">
                <div className="space-y-0.5">
                  <label htmlFor={cfg.id} className="text-xs font-bold text-primary block cursor-pointer">{cfg.label}</label>
                  <p className="text-[10px] text-muted font-semibold">{cfg.desc}</p>
                </div>
                <button
                  type="button"
                  id={cfg.id}
                  onClick={() => cfg.onChange(!cfg.value)}
                  className={`w-9 h-5 rounded-full shrink-0 relative transition-all duration-200 border ${
                    cfg.value 
                      ? 'bg-indigo-600 border-indigo-600 dark:bg-indigo-500 dark:border-indigo-500' 
                      : 'bg-surface-soft border-border dark:border-slate-700'
                  }`}
                >
                  <div className={`h-3.5 w-3.5 bg-white dark:bg-slate-200 rounded-full shadow absolute top-0.5 transition-all duration-200 ${
                    cfg.value ? 'left-4.5' : 'left-0.5'
                  }`} />
                </button>
              </div>
            ))}
          </div>
        </div>
 
        {/* Platform Info card */}
        <div className="rounded-2xl border border-border bg-surface p-5 space-y-4 shadow-sm flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface-soft border border-border text-secondary shrink-0">
                <Database className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-primary">Platform Specifications</h3>
                <p className="text-[10px] text-muted font-semibold">PRISM Enterprise v2.0</p>
              </div>
            </div>
 
            <div className="grid grid-cols-2 gap-2 text-[11px] font-semibold">
              {[
                ['Database Schema', 'MySQL Ingestion'],
                ['GraphQL Engine', 'Projects v2 (GH API)'],
                ['Sync Intervals', 'On-Demand + Cron'],
                ['Selected Repo', repoLabel ?? 'None'],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-surface-soft dark:bg-slate-900/60 border border-border/80 p-3 space-y-0.5">
                  <p className="text-[9px] font-bold text-muted uppercase tracking-wider">{k}</p>
                  <p className="text-primary truncate" title={v}>{v}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
 
      </div>
 
    </div>
  )
}
