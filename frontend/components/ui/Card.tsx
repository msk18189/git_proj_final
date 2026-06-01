import React from 'react'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const Card: React.FC<CardProps> = ({ children, className = '', ...props }) => {
  return (
    <div
      className={`bg-surface border border-border shadow-card dark:shadow-[0_4px_20px_rgba(0,0,0,0.3)] transition-all duration-300 rounded-2xl p-6 sm:p-8 ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

export default Card
