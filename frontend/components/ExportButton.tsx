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

  const handlePdfExport = async () => {
    if (pdfLoading) return
    setPdfLoading(true)
    try {
      const url = getExportPdfUrl(repoId, filters)
      const res = await fetch(url)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        alert(`PDF export failed: ${err.detail || res.statusText}`)
        return
      }
      const blob = await res.blob()
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objectUrl
      a.download = `prism_report_${repoId}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(objectUrl)
    } catch (e: any) {
      alert(`PDF export error: ${e.message}`)
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => window.open(getExportCsvUrl(repoId, filters), '_blank')}
        className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold shadow-sm transition-all duration-200 hover:border-emerald-400 hover:bg-emerald-50 hover:shadow-md"
        style={{ color: '#1e293b' }}
      >
        <Download className="h-4 w-4 text-emerald-600" />
        <span style={{ color: '#1e293b' }}>Export CSV</span>
      </button>
      <button
        type="button"
        onClick={handlePdfExport}
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
