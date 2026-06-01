'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { loginUser, formatApiError } from '@/lib/api'
import { saveAuthToken } from '@/lib/auth'
import Input from '../ui/Input'
import Button from '../ui/Button'
import Card from '../ui/Card'
import { AlertCircle, Lock, Mail, Eye, EyeOff } from 'lucide-react'

export default function LoginForm() {
  const router = useRouter()
  const [ident, setIdent] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      if (params.get('signup_success') === 'true') {
        setSuccessMessage('Account created successfully. Please sign in.')
      }
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const data = await loginUser({
        username_or_email: ident,
        password: password,
      })
      saveAuthToken(data.access_token)
      router.push('/dashboard')
    } catch (err: any) {
      const msg = formatApiError(err)
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-[420px]">
      <div className="mb-6 text-center">
        <h2 className="text-xl font-bold text-primary tracking-tight">Welcome Back</h2>
        <p className="text-xs text-muted mt-1.5 leading-normal">
          Login to access engineering workflow intelligence.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {successMessage && (
          <div className="flex items-start gap-2.5 rounded-xl border border-palette-emerald/20 bg-palette-emerald/5 p-3.5 text-xs font-semibold leading-normal text-palette-emerald-text">
            <span>{successMessage}</span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs font-semibold leading-normal text-red-800">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-550 mt-0.5" />
            <span>{typeof error === 'string' ? error : String(error)}</span>
          </div>
        )}

        <div className="relative">
          <Input
            label="Username or Email"
            type="text"
            placeholder="Username or email"
            value={ident}
            onChange={(e) => setIdent(e.target.value)}
            disabled={loading}
            required
            className="pl-10"
          />
          <Mail className="absolute left-3.5 top-[38px] h-4 w-4 text-muted pointer-events-none" />
        </div>

        <div className="relative">
          <Input
            label="Password"
            type={showPassword ? "text" : "password"}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={loading}
            required
            className="pl-10 pr-10"
          />
          <Lock className="absolute left-3.5 top-[38px] h-4 w-4 text-muted pointer-events-none" />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3.5 top-[38px] text-muted hover:text-primary transition-colors flex items-center justify-center cursor-pointer"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        <Button type="submit" loading={loading} className="w-full mt-6">
          Sign In
        </Button>
      </form>

      <div className="mt-6 text-center text-xs text-muted">
        Don&apos;t have an account?{' '}
        <Link href="/signup" className="font-semibold text-palette-orange hover:text-palette-orange-dark">
          Create Account
        </Link>
      </div>
    </Card>
  )
}
