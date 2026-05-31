import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring-color)] disabled:pointer-events-none disabled:opacity-45 active:translate-y-px',
  {
    variants: {
      variant: {
        default:
          'bg-[linear-gradient(135deg,var(--accent),var(--sage))] text-[var(--accent-contrast)] shadow-[0_16px_34px_rgba(0,0,0,.24),inset_0_1px_0_rgba(255,255,255,.35)] hover:-translate-y-0.5 hover:shadow-[0_22px_46px_rgba(0,0,0,.32),inset_0_1px_0_rgba(255,255,255,.42)]',
        destructive:
          'bg-[linear-gradient(135deg,var(--danger),#b9483e)] text-white shadow-[0_16px_34px_rgba(0,0,0,.22)] hover:-translate-y-0.5',
        outline:
          'border border-[var(--border-strong)] bg-[linear-gradient(180deg,rgba(255,255,255,.05),transparent),var(--surface-raised)] text-[var(--text)] shadow-[0_12px_28px_rgba(0,0,0,.18),inset_0_1px_0_rgba(255,255,255,.05)] hover:-translate-y-0.5 hover:border-[var(--accent-muted)] hover:bg-[var(--surface-hover)]',
        secondary:
          'border border-[var(--border)] bg-[linear-gradient(180deg,rgba(255,255,255,.045),transparent),var(--surface)] text-[var(--text)] shadow-[0_12px_28px_rgba(0,0,0,.16)] hover:-translate-y-0.5 hover:border-[var(--border-strong)] hover:bg-[var(--surface-hover)]',
        ghost:
          'border border-transparent bg-transparent text-[var(--muted)] hover:border-[var(--border)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)]',
        link: 'text-[var(--accent)] underline-offset-4 hover:underline',
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
