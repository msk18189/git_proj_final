'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/auth'
import { Loader2 } from 'lucide-react'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated()) {
      const savedRepoId = localStorage.getItem('prism_repo_id')
      if (savedRepoId) {
        router.replace('/dashboard')
      } else {
        router.replace('/analyze')
      }
    } else {
      router.replace('/login')
    }
  }, [router])

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center space-y-3">
        <Loader2 className="h-8 w-8 animate-spin mx-auto text-palette-orange" />
        <p className="text-xs font-bold uppercase tracking-wider text-muted">Loading PRISM...</p>
      </div>
    </div>
  )
}
