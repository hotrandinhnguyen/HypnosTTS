import * as React from 'react'
import { cn } from '@/lib/utils'

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative rounded-2xl border border-white/10 bg-[rgba(12,18,38,0.75)] backdrop-blur-[24px] [backdrop-filter:blur(24px)_saturate(180%)]',
        'shadow-[0_0_0_1px_rgba(139,92,246,.04),0_20px_60px_rgba(0,0,0,.5),inset_0_1px_0_rgba(255,255,255,.04)]',
        'hover:shadow-[0_0_0_1px_rgba(139,92,246,.1),0_24px_80px_rgba(0,0,0,.6),0_0_60px_rgba(139,92,246,.06),inset_0_1px_0_rgba(255,255,255,.05)]',
        'transition-shadow duration-400',
        className,
      )}
      {...props}
    />
  ),
)
Card.displayName = 'Card'

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex items-center justify-between px-5 py-3.5 border-b border-white/10 flex-shrink-0', className)}
      {...props}
    />
  ),
)
CardHeader.displayName = 'CardHeader'

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn('text-[11px] font-semibold uppercase tracking-[.12em] text-[#64748b]', className)}
      {...props}
    />
  ),
)
CardTitle.displayName = 'CardTitle'

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-6', className)} {...props} />
  ),
)
CardContent.displayName = 'CardContent'

export { Card, CardHeader, CardTitle, CardContent }
