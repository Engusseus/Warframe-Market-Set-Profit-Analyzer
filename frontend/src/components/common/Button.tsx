import React from 'react';
import { motion } from 'framer-motion';
import type { HTMLMotionProps } from 'framer-motion';
import { cn } from '../../utils/cn';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  isLoading?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'primary',
      size = 'md',
      className,
      icon,
      isLoading,
      loading,
      disabled,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'relative inline-flex items-center justify-center font-medium wf-corner transition-all duration-300 overflow-hidden';

    const variants = {
      primary:
        'bg-[#2ebfcc]/10 text-[#2ebfcc] border border-[#2ebfcc]/50 hover:bg-[#2ebfcc]/20 hover:shadow-[0_0_10px_rgba(46,191,204,0.2)]',
      secondary:
        'bg-[#e5c158]/10 text-[#e5c158] border border-[#e5c158]/50 hover:bg-[#e5c158]/20 hover:shadow-[0_0_10px_rgba(229,193,88,0.2)]',
      ghost:
        'bg-transparent text-gray-300 hover:text-white hover:bg-white/5 border border-transparent',
      danger:
        'bg-[#ff3366]/10 text-[#ff3366] border border-[#ff3366]/50 hover:bg-[#ff3366]/20 hover:shadow-[0_0_10px_rgba(255,51,102,0.2)]',
    };

    const sizes = {
      sm: 'text-sm px-3 py-1.5 gap-1.5',
      md: 'text-sm px-4 py-2 gap-2',
      lg: 'text-base px-6 py-3 gap-2',
    };

    const isButtonLoading = isLoading ?? loading ?? false;
    const isDisabled = disabled || isButtonLoading;

    return (
      <motion.button
        ref={ref}
        whileHover={!isDisabled ? { scale: 1.02 } : {}}
        whileTap={!isDisabled ? { scale: 0.98 } : {}}
        className={cn(
          baseStyles,
          variants[variant],
          sizes[size],
          isDisabled && 'opacity-50 cursor-not-allowed hover:shadow-none hover:bg-transparent',
          className
        )}
        disabled={isDisabled}
        {...props as HTMLMotionProps<"button">}
      >
        {/* Glow sweep effect */}
        {!isDisabled && (
          <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden wf-corner">
            <div className="absolute top-0 -left-[100%] w-1/2 h-full bg-gradient-to-r from-transparent via-white/10 to-transparent skew-x-[45deg] animate-[sweep_3s_ease-in-out_infinite]" />
          </div>
        )}

        <div className="relative z-10 flex items-center gap-2">
          {isButtonLoading ? (
            <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : (
            icon
          )}
          {children}
        </div>
      </motion.button>
    );
  }
);

Button.displayName = 'Button';

const BUTTON_SWEEP_STYLE_ID = 'wfm-button-sweep-keyframes';

// Add the sweep animation once if not provided by Tailwind plugins.
if (typeof document !== 'undefined' && !document.getElementById(BUTTON_SWEEP_STYLE_ID)) {
  const style = document.createElement('style');
  style.id = BUTTON_SWEEP_STYLE_ID;
  style.textContent = `
    @keyframes sweep {
      0% { transform: translateX(-100%); }
      50%, 100% { transform: translateX(300%); }
    }
  `;
  document.head.appendChild(style);
}
