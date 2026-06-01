import React from 'react'
import { Loader2 } from 'lucide-react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost'
  loading?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  loading = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-semibold py-3 px-4 rounded-xl text-sm transition-all duration-200 focus:outline-none focus:ring-2 active:scale-[0.99] disabled:opacity-60 disabled:pointer-events-none'
  
  let variantStyles = ''
  if (variant === 'primary') {
    variantStyles = 'bg-palette-orange hover:bg-palette-orange-dark text-white shadow-[0_4px_12px_rgba(198,123,92,0.2)] hover:shadow-[0_6px_20px_rgba(198,123,92,0.3)] focus:ring-palette-orange/20'
  } else if (variant === 'secondary') {
    variantStyles = 'border border-border bg-surface text-primary hover:border-palette-emerald hover:bg-palette-emerald-light dark:hover:bg-emerald-950/20 dark:hover:text-emerald-400 focus:ring-palette-emerald/20'
  } else if (variant === 'outline') {
    variantStyles = 'border border-border bg-transparent text-primary hover:bg-bg-hover focus:ring-border'
  } else if (variant === 'ghost') {
    variantStyles = 'text-secondary hover:bg-bg-hover hover:text-primary focus:ring-bg-hover'
  }

  return (
    <button
      className={`${baseStyles} ${variantStyles} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          <span>Please wait...</span>
        </>
      ) : (
        children
      )}
    </button>
  )
}

export default Button
