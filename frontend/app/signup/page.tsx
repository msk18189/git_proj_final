'use client'

import React, { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/auth'
import SignupForm from '@/components/auth/SignupForm'
import { GitBranch } from 'lucide-react'

export default function SignupPage() {
  const router = useRouter()

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace('/dashboard')
    }
  }, [router])

  return (
    <div className="auth-bg min-h-screen w-full flex flex-col items-center justify-center p-4 sm:p-6 md:p-8">
      {/* Decorative radial gradient meshes */}
      <div className="auth-glow-1"></div>
      <div className="auth-glow-2"></div>

      <div className="relative z-10 w-full max-w-[420px] flex flex-col items-center">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr from-palette-orange to-palette-amber text-white shadow-md shadow-palette-orange/15 mb-3">
            <GitBranch className="h-5.5 w-5.5" />
          </div>

          <h1 className="text-2xl font-extrabold tracking-tight text-primary">PRISM</h1>
          <p className="mt-1 text-xs text-secondary font-semibold max-w-[320px] leading-relaxed">
            AI-Powered GitHub PR Intelligence
          </p>
        </div>

        <SignupForm />
      </div>
    </div>
  )
}
