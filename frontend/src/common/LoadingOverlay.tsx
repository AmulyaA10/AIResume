import React from 'react';

interface LoadingOverlayProps {
  /** Lucide icon shown inside the spinner ring. */
  icon: React.ReactNode;
  /** Status text displayed below the spinner. */
  message: string;
  /** Extra wrapper className (merged with defaults). */
  className?: string;
}

/**
 * Full-panel loading overlay with a spinning border ring + centred icon.
 *
 * ```tsx
 * <LoadingOverlay
 *   icon={<ShieldCheck className="w-10 h-10 text-primary-200" />}
 *   message="Simulating Agent Reasoning..."
 * />
 * ```
 */
const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  icon,
  message,
  className = '',
}) => (
  <div
    className={`flex-1 glass-card flex flex-col items-center justify-center p-12 bg-white/80 border-primary-100 ${className}`}
  >
    <div className="w-24 h-24 relative">
      <div className="absolute inset-0 rounded-2xl border-4 border-primary-100 animate-pulse" />
      <div className="absolute inset-0 rounded-2xl border-t-4 border-primary-500 animate-spin" />
      <div className="absolute inset-0 flex items-center justify-center">{icon}</div>
    </div>
    <p className="mt-8 text-primary-600 font-black uppercase tracking-[0.2em] text-xs">
      {message}
    </p>
  </div>
);

export default LoadingOverlay;
