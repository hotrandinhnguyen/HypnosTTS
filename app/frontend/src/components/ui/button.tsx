import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40 active:scale-[.98] active:translate-y-0.5',
  {
    variants: {
      variant: {
        default:
          'bg-gradient-to-br from-violet-500 to-violet-700 text-white shadow-[0_4px_20px_rgba(139,92,246,.35),0_2px_6px_rgba(0,0,0,.3)] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(139,92,246,.35)]',
        destructive:
          'bg-gradient-to-br from-red-400 to-red-600 text-white shadow-[0_4px_20px_rgba(248,113,113,.3)] hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(248,113,113,.3)]',
        outline:
          'border border-white/10 bg-[rgba(12,18,38,0.75)] text-slate-200 backdrop-blur-md shadow-[0_2px_8px_rgba(0,0,0,.2)] hover:bg-[rgba(16,24,50,0.85)] hover:border-[rgba(139,92,246,.3)]',
        secondary:
          'bg-[rgba(12,18,38,0.75)] text-slate-200 border border-white/10 backdrop-blur-md shadow-[0_2px_8px_rgba(0,0,0,.2)] hover:bg-[rgba(16,24,50,0.85)] hover:border-[rgba(139,92,246,.3)]',
        ghost:
          'bg-transparent text-[#64748b] border border-white/10 text-xs hover:bg-[rgba(139,92,246,.15)] hover:text-[#a78bfa] hover:border-[rgba(139,92,246,.3)]',
        link: 'text-[#a78bfa] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-5 py-3',
        sm: 'h-8 px-3.5 py-2 text-xs',
        lg: 'h-12 px-6 py-3 text-base',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
