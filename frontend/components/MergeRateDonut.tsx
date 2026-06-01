'use client'

import { motion } from 'framer-motion'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { CHART } from '@/lib/chartTheme'

interface MergeRateDonutProps {
  mergeRate: number
  openPrs: number
  stalePrs: number
}

export default function MergeRateDonut({ mergeRate, openPrs, stalePrs }: MergeRateDonutProps) {
  const merged = Math.max(0, Math.min(100, mergeRate))
  const data = [
    { name: 'Merged', value: merged },
    { name: 'Remaining', value: Math.max(0, 100 - merged) },
  ]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="card card-hover card-glow h-full">
      <h3 className="section-title text-palette-orange-text">Merge Health</h3>
      <p className="section-subtitle mb-4">Teal = merged portion of closed PRs</p>
      <div className="relative h-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={72}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={CHART.merged} />
              <Cell fill={CHART.pie[5]} />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-palette-teal-dark dark:text-palette-teal">{merged}%</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider text-palette-teal dark:text-palette-teal/80">
            Merge rate
          </span>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-palette-lime/25 bg-palette-lime-light dark:bg-palette-lime-dark/10 dark:border-palette-lime-dark/20 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase text-palette-lime-text dark:text-palette-lime-light">Open</p>
          <p className="text-lg font-bold text-palette-lime">{openPrs}</p>
        </div>
        <div className="rounded-xl border border-palette-amber/25 bg-palette-amber-light dark:bg-palette-amber-dark/10 dark:border-palette-amber-dark/20 px-3 py-2">
          <p className="text-[10px] font-semibold uppercase text-palette-amber-text dark:text-palette-amber-light">Stale</p>
          <p className="text-lg font-bold text-palette-amber">{stalePrs}</p>
        </div>
      </div>
    </motion.div>
  )
}
