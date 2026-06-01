import React, { forwardRef } from 'react'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className = '', ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-[10px] font-bold uppercase tracking-wider text-muted mb-1.5">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`w-full bg-background/50 hover:bg-background/80 focus:bg-surface text-primary placeholder:text-muted px-4 py-3 rounded-xl border border-border focus:border-palette-orange focus:ring-4 focus:ring-palette-orange/15 shadow-sm transition-all text-sm outline-none ${
            error ? 'border-red-400 focus:border-red-450 focus:ring-red-200/20' : ''
          } ${className}`}
          {...props}
        />
        {error && <p className="mt-1.5 text-xs text-red-650 font-semibold">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'
export default Input
