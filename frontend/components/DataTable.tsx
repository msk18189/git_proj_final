'use client'

import { motion } from 'framer-motion'

interface DataTableProps {
  title: string
  icon?: React.ReactNode
  columns: string[]
  data: any[]
  emptyMessage?: string
  page?: number
  pages?: number
  onPageChange?: (newPage: number) => void
  totalResults?: number
  renderRow: (row: any, idx: number) => React.ReactNode
}

export default function DataTable({
  title,
  icon,
  columns,
  data,
  emptyMessage = 'No data available',
  page = 1,
  pages,
  onPageChange,
  totalResults,
  renderRow,
}: DataTableProps) {
  const totalPages = pages

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow flex flex-col h-full">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 gap-2">
        <div className="flex items-center gap-2 text-primary">
          {icon}
          <h3 className="section-title text-primary">{title}</h3>
        </div>
        {totalResults !== undefined && (
          <span className="text-xs text-muted font-medium">
            Total: {totalResults.toLocaleString()} records
          </span>
        )}
      </div>

      {data.length === 0 ? (
        <div className="flex-1 flex flex-col justify-center items-center py-10">
          <p className="text-sm text-muted">{emptyMessage}</p>
        </div>
      ) : (
        <>
          <div className="flex-1 overflow-y-auto overflow-x-auto rounded-xl border border-border" style={{ minHeight: '420px' }}>
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface-soft/50">
                  {columns.map((col) => (
                    <th
                      key={col}
                      className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-secondary"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="align-top">
                {data.map((row, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-border-muted transition hover:bg-bg-hover/40"
                  >
                    {renderRow(row, idx)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages !== undefined && onPageChange && totalPages > 1 && (
            <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
              <button
                onClick={() => onPageChange(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-secondary transition hover:bg-bg-hover hover:text-primary disabled:pointer-events-none disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-xs text-secondary">
                Page <span className="font-semibold text-primary">{page}</span> of{' '}
                <span className="font-semibold text-primary">{totalPages}</span>
              </span>
              <button
                onClick={() => onPageChange(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-secondary transition hover:bg-bg-hover hover:text-primary disabled:pointer-events-none disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </motion.div>
  )
}