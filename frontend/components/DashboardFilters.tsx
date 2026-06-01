'use client'

import { motion } from 'framer-motion'
import { SlidersHorizontal } from 'lucide-react'

export interface DashboardFiltersState {
  days: number | null
  author: string
  state: string
  startDate?: string | null
  endDate?: string | null
}

interface DashboardFiltersProps {
  authors: string[]
  filters: DashboardFiltersState
  onChange: (filters: DashboardFiltersState) => void
  onApply: () => void
}

export default function DashboardFilters({
  authors,
  filters,
  onChange,
  onApply,
}: DashboardFiltersProps) {
  const presets = [null, 30, 90, 180]
  const isCustomDays = filters.days !== null && !presets.includes(filters.days) && !filters.startDate
  const isCustomRange = filters.startDate !== undefined && filters.startDate !== null

  const handleSelectChange = (val: string) => {
    if (val === 'custom-days') {
      onChange({
        ...filters,
        days: 45,
        startDate: null,
        endDate: null,
      })
    } else if (val === 'custom-range') {
      const end = new Date().toISOString().split('T')[0]
      const start = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().split('T')[0]
      onChange({
        ...filters,
        days: null,
        startDate: start,
        endDate: end,
      })
    } else {
      onChange({
        ...filters,
        days: val ? Number(val) : null,
        startDate: null,
        endDate: null,
      })
    }
  }

  const selectCls = [
    'w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0f1422] px-3 py-2.5',
    'text-sm font-medium text-slate-800 dark:text-slate-200',
    'transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:focus:ring-indigo-550/10',
    'hover:border-slate-300 dark:hover:border-slate-700',
    'appearance-none cursor-pointer',
  ].join(' ')

  const inputCls = [
    'rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0f1422] px-3 py-2.5',
    'text-sm font-medium text-slate-800 dark:text-slate-200',
    'transition focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:focus:ring-indigo-550/10',
  ].join(' ')

  const labelCls = 'mb-1.5 block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400'

  return (
    <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-[#0f1422] p-5 shadow-sm mb-6"
    >
      <div className="mb-4 flex items-center gap-2">
        <div className="p-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/30">
          <SlidersHorizontal className="h-4 w-4 text-indigo-600 dark:text-indigo-400" />
        </div>
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Filters</h3>
      </div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end flex-wrap">
        <div className="flex-1 min-w-[280px]">
          <label className={labelCls}>Date range</label>
          <div className="flex flex-wrap gap-2 items-center">
            <div className="relative flex-1 min-w-[140px]">
              <select
                value={isCustomRange ? 'custom-range' : (isCustomDays ? 'custom-days' : (filters.days ?? ''))}
                onChange={(e) => handleSelectChange(e.target.value)}
                className={selectCls}
              >
                <option value="">All time</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
                <option value="180">Last 180 days</option>
                <option value="custom-days">Custom days...</option>
                <option value="custom-range">Customize Date...</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
            {isCustomDays && (
              <input
                type="number"
                min="1"
                value={filters.days ?? 45}
                onChange={(e) => {
                  const val = e.target.value ? Math.max(1, Number(e.target.value)) : 1
                  onChange({ ...filters, days: val })
                }}
                className={`${inputCls} w-20 text-center`}
                placeholder="Days"
              />
            )}
            {isCustomRange && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <input
                  type="date"
                  value={filters.startDate || ''}
                  onChange={(e) => {
                    onChange({ ...filters, startDate: e.target.value })
                  }}
                  className={`${inputCls} px-2.5 py-2 w-[145px]`}
                />
                <span className="text-xs text-slate-500 font-medium">to</span>
                <input
                  type="date"
                  value={filters.endDate || ''}
                  onChange={(e) => {
                    onChange({ ...filters, endDate: e.target.value })
                  }}
                  className={`${inputCls} px-2.5 py-2 w-[145px]`}
                />
              </div>
            )}
          </div>
        </div>
        <div className="w-full lg:w-auto lg:min-w-[180px]">
          <label className={labelCls}>Author</label>
          <div className="relative">
            <select
              value={filters.author}
              onChange={(e) => onChange({ ...filters, author: e.target.value })}
              className={selectCls}
            >
              <option value="all">All authors</option>
              {authors.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
              <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
        <div className="w-full lg:w-auto lg:min-w-[180px]">
          <label className={labelCls}>PR state</label>
          <div className="relative">
            <select
              value={filters.state}
              onChange={(e) => onChange({ ...filters, state: e.target.value })}
              className={selectCls}
            >
              <option value="ALL">All states</option>
              <option value="OPEN">Open</option>
              <option value="MERGED">Merged</option>
              <option value="CLOSED">Closed</option>
              <option value="STALE">Stale (&gt;30d)</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
              <svg className="h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </div>
        <div className="w-full lg:w-auto lg:flex-initial">
          <button
            type="button"
            onClick={onApply}
            className="w-full lg:px-8 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition-all duration-200 hover:bg-indigo-700 hover:shadow-md dark:shadow-[0_4px_12px_rgba(99,102,241,0.2)] dark:hover:shadow-[0_6px_20px_rgba(99,102,241,0.3)]"
          >
            Apply filters
          </button>
        </div>
      </div>
    </motion.div>
  )
}
