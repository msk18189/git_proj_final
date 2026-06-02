
export function loadGithubToken(): string {
  return ''
}

export async function saveGithubToken(token: string): Promise<void> {
  if (typeof window === 'undefined') return
  sessionStorage.removeItem('prism_github_token')
}
