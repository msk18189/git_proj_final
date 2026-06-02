'use client'

import { useState } from 'react'
import { Download, FileText, Loader2 } from 'lucide-react'
import { getExportCsvUrl, getExportPdfUrl } from '@/lib/api'
import type { DashboardFiltersState } from '@/components/DashboardFilters'

interface ExportButtonProps {
  repoId: number
  filters: DashboardFiltersState
}

export default function ExportButton({ repoId, filters }: ExportButtonProps) {
  const [pdfLoading, setPdfLoading] = useState(false)
  const [csvLoading, setCsvLoading] = useState(false)

  const downloadBlob = (blob: Blob, filename: string) => {
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(objectUrl)
  }

  const handleExport = async (kind: 'csv' | 'pdf') => {
    const isPdf = kind === 'pdf'
    if ((isPdf && pdfLoading) || (!isPdf && csvLoading)) return
    isPdf ? setPdfLoading(true) : setCsvLoading(true)
    try {
      const url = isPdf ? getExportPdfUrl(repoId, filters) : getExportCsvUrl(repoId, filters)
      const res = await fetch(url, { credentials: 'include' })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        alert(`${isPdf ? 'PDF' : 'CSV'} export failed: ${err.detail || res.statusText}`)
        return
      }
      const blob = await res.blob()
      downloadBlob(blob, `prism_report_${repoId}.${kind}`)
    } catch (e: any) {
      alert(`${isPdf ? 'PDF' : 'CSV'} export error: ${e.message}`)
    } finally {
      isPdf ? setPdfLoading(false) : setCsvLoading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => handleExport('csv')}
        disabled={csvLoading}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold shadow-sm transition-all duration-200 hover:border-emerald-400 hover:bg-emerald-50 hover:shadow-md"
        style={{ color: '#1e293b' }}
      >
        {csvLoading
          ? <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
          : <Download className="h-4 w-4 text-emerald-600" />
        }
        <span style={{ color: '#1e293b' }}>{csvLoading ? 'Exporting CSV...' : 'Export CSV'}</span>
      </button>
      <button
        type="button"
        onClick={() => handleExport('pdf')}
        disabled={pdfLoading}
        className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:bg-indigo-700 hover:shadow-md disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {pdfLoading
          ? <Loader2 className="h-4 w-4 animate-spin" />
          : <FileText className="h-4 w-4" />
        }
        {pdfLoading ? 'Generating PDF...' : 'Export PDF'}
      </button>
    </div>
  )
}
