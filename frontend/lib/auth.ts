import { api } from './api'

export function saveAuthToken(token: string): void {
  // Handled by backend setting the HttpOnly cookie
}

export function getAuthToken(): string | null {
  // Can no longer access token directly since it's HttpOnly
  return null
}

export async function getAuthUser(): Promise<{ username: string; email?: string } | null> {
  if (typeof window === 'undefined') return Promise.resolve(null)
  try {
    const res = await api.get('/api/auth/me')
    if (res.data) {
      return {
        username: res.data.username,
        email: res.data.email,
      }
    }
    return Promise.resolve(null)
  } catch (err) {
    return Promise.resolve(null)
  }
}

export function isAuthenticated(): boolean {
  if (typeof window === 'undefined') return false
  return document.cookie.includes('isAuthenticated=true')
}

export async function signOut(): Promise<void> {
  if (typeof window === 'undefined') return
  try {
    await api.post('/api/auth/logout')
    localStorage.removeItem('prism_repo_id')
    localStorage.removeItem('prism_repo_label')
    localStorage.removeItem('prism_active_section')
    localStorage.removeItem('prism_dashboard_route')
    // We could reload or let the frontend router handle redirects on its own
  } catch (err) {
    console.error('Failed to clear session', err)
  }
}
