'use client'

import React, { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { HelpCircle } from 'lucide-react'

export interface TooltipProps {
  /**
   * Content to show in the tooltip (title + message + calculation)
   */
  content: {
    title: string
    message: string
    calculation?: string
  }
  /**
   * Position of the tooltip
   */
  position?: 'top' | 'bottom' | 'left' | 'right'
  /**
   * Optional custom icon — defaults to HelpCircle
   */
  icon?: React.ReactNode
  /**
   * Optional className for the trigger wrapper
   */
  className?: string
  /**
   * Whether to show the help icon inline or just trigger on hover of children
   */
  showIcon?: boolean
  /**
   * Children to trigger the tooltip
   */
  children?: React.ReactNode
}

export const Tooltip: React.FC<TooltipProps> = ({
  content,
  position = 'top',
  icon,
  className = '',
  showIcon = true,
  children,
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isFocused, setIsFocused] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 })

  // Calculate tooltip position
  useEffect(() => {
    if (!isOpen || !triggerRef.current || !tooltipRef.current) return

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    const gap = 8

    let top = 0
    let left = 0

    switch (position) {
      case 'top':
        top = triggerRect.top - tooltipRect.height - gap
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'bottom':
        top = triggerRect.bottom + gap
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'left':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.left - tooltipRect.width - gap
        break
      case 'right':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.right + gap
        break
    }

    // Keep tooltip within viewport
    const padding = 12
    if (left < padding) left = padding
    if (left + tooltipRect.width > window.innerWidth - padding) {
      left = window.innerWidth - tooltipRect.width - padding
    }
    if (top < padding) top = padding
    if (top + tooltipRect.height > window.innerHeight - padding) {
      top = window.innerHeight - tooltipRect.height - padding
    }

    setTooltipPosition({ top, left })
  }, [isOpen, position])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setIsOpen(false)
      setIsFocused(false)
    }
  }

  // Recalculate on window resize
  useEffect(() => {
    if (!isOpen) return
    
    const handleResize = () => {
      if (triggerRef.current && tooltipRef.current) {
        const triggerRect = triggerRef.current.getBoundingClientRect()
        const tooltipRect = tooltipRef.current.getBoundingClientRect()
        const gap = 8

        let top = 0
        let left = 0

        switch (position) {
          case 'top':
            top = triggerRect.top - tooltipRect.height - gap
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
          case 'bottom':
            top = triggerRect.bottom + gap
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
          case 'left':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.left - tooltipRect.width - gap
            break
          case 'right':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.right + gap
            break
        }

        const padding = 12
        if (left < padding) left = padding
        if (left + tooltipRect.width > window.innerWidth - padding) {
          left = window.innerWidth - tooltipRect.width - padding
        }
        if (top < padding) top = padding
        if (top + tooltipRect.height > window.innerHeight - padding) {
          top = window.innerHeight - tooltipRect.height - padding
        }

        setTooltipPosition({ top, left })
      }
    }

    window.addEventListener('resize', handleResize)
    window.addEventListener('scroll', handleResize, true)
    
    return () => {
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('scroll', handleResize, true)
    }
  }, [isOpen, position])

  return (
    <div
      ref={triggerRef}
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      onKeyDown={handleKeyDown}
      role="region"
      aria-label={`Tooltip: ${content.title}`}
    >
      {children}
      
      {showIcon && (
        <button
          type="button"
          onClick={() => {
            setIsOpen(!isOpen)
            setIsFocused(!isFocused)
          }}
          className="inline-flex items-center justify-center p-1 ml-1 rounded-lg transition-colors hover:bg-slate-100 dark:hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400"
          aria-label={`More info: ${content.title}`}
          tabIndex={0}
        >
          {icon || <HelpCircle className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-400" />}
        </button>
      )}

      {/* Portal-like tooltip */}
      <AnimatePresence>
        {(isOpen || isFocused) && (
          <motion.div
            ref={tooltipRef}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="fixed z-[9999] pointer-events-none"
            style={{
              top: `${tooltipPosition.top}px`,
              left: `${tooltipPosition.left}px`,
            }}
          >
            <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 shadow-lg dark:shadow-2xl p-3.5 max-w-xs pointer-events-auto">
              {/* Title */}
              <p className="text-xs font-bold text-slate-900 dark:text-white mb-1.5">
                {content.title}
              </p>

              {/* Message */}
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed mb-2.5">
                {content.message}
              </p>

              {/* Calculation (if provided) */}
              {content.calculation && (
                <div className="pt-2.5 border-t border-slate-200 dark:border-slate-700">
                  <p className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1.5">
                    How it's calculated
                  </p>
                  <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed font-mono bg-slate-50 dark:bg-slate-800/50 p-2 rounded border border-slate-100 dark:border-slate-700/50">
                    {content.calculation}
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/**
 * Compact tooltip wrapper for use on metric icons only
 */
export const MetricTooltip: React.FC<{ content: TooltipProps['content'] } & Omit<TooltipProps, 'content'>> = ({
  content,
  ...props
}) => (
  <Tooltip content={content} showIcon position="right" {...props} />
)

export default Tooltip
