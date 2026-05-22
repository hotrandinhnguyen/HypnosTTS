import * as React from 'react'
import { cn } from '@/lib/utils'

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-xl border border-white/10 bg-[rgba(12,18,38,0.75)] px-4 py-2 text-sm text-slate-200 placeholder:text-[#2d3a52] backdrop-blur-xl outline-none transition-all duration-200',
          'focus:border-violet-500 focus:bg-[rgba(16,24,50,0.85)] focus:shadow-[0_0_0_3px_rgba(139,92,246,.15),0_0_20px_rgba(139,92,246,.1)]',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        ref={ref}
        {...props}
      />
    )
  },
)
Input.displayName = 'Input'

export { Input }
