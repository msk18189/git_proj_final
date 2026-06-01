
export function loadGithubToken(): string {
  if (typeof window === 'undefined') return ''
  return sessionStorage.getItem('prism_github_token') || ''
}

export async function saveGithubToken(token: string): Promise<void> {
  if (typeof window === 'undefined') return
  if (token) {
    sessionStorage.setItem('prism_github_token', token)
  } else {
    sessionStorage.removeItem('prism_github_token')
  }
}
