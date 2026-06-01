'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { signupUser, formatApiError } from '@/lib/api'
import { saveAuthToken } from '@/lib/auth'
import Input from '../ui/Input'
import Button from '../ui/Button'
import Card from '../ui/Card'
import { AlertCircle, Lock, Mail, User, Eye, EyeOff } from 'lucide-react'

export default function SignupForm() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const passwordsMatch = password === confirmPassword
  const canSubmit = username.trim() !== '' && email.trim() !== '' && password !== '' && confirmPassword !== '' && passwordsMatch

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!passwordsMatch) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)

    try {
      await signupUser({
        username: username.trim(),
        email: email.trim(),
        password: password,
        confirm_password: confirmPassword,
      })
      router.push('/login?signup_success=true')
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
        <h2 className="text-xl font-bold text-primary tracking-tight">Create Workspace</h2>
        <p className="text-xs text-muted mt-1.5 leading-normal">
          Sign up to analyze repository cycle time & risk factors.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs font-semibold leading-normal text-red-800">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-550 mt-0.5" />
            <span>{typeof error === 'string' ? error : String(error)}</span>
          </div>
        )}

        <div className="relative">
          <Input
            label="Username"
            type="text"
            placeholder="Username or E-mail"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={loading}
            required
            className="pl-10"
          />
          <User className="absolute left-3.5 top-[38px] h-4 w-4 text-muted pointer-events-none" />
        </div>

        <div className="relative">
          <Input
            label="Email Address"
            type="email"
            placeholder="E-mail address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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

        <div className="relative">
          <Input
            label="Confirm Password"
            type={showConfirmPassword ? "text" : "password"}
            placeholder="Confirm Password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={loading}
            required
            error={confirmPassword && !passwordsMatch ? "Passwords do not match" : undefined}
            className="pl-10 pr-10"
          />
          <Lock className="absolute left-3.5 top-[38px] h-4 w-4 text-muted pointer-events-none" />
          <button
            type="button"
            onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            className="absolute right-3.5 top-[38px] text-muted hover:text-primary transition-colors flex items-center justify-center cursor-pointer"
            aria-label={showConfirmPassword ? "Hide password" : "Show password"}
          >
            {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        <Button type="submit" loading={loading} disabled={!canSubmit} className="w-full mt-6">
          Create Account
        </Button>
      </form>

      <div className="mt-6 text-center text-xs text-muted">
        Already have an account?{' '}
        <Link href="/login" className="font-semibold text-palette-orange hover:text-palette-orange-dark">
          Sign In
        </Link>
      </div>
    </Card>
  )
}
