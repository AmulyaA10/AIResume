import React from 'react';

interface EmptyStateProps {
  /** Lucide icon component rendered inside the rounded container. */
  icon: React.ReactNode;
  /** Bold heading text. */
  heading: string;
  /** Smaller description below the heading. */
  description: string;
  /** Extra wrapper className (merged with defaults). */
  className?: string;
}

/**
 * Dashed-border empty / standby placeholder shown when no data is loaded.
 *
 * ```tsx
 * <EmptyState
 *   icon={<FileText className="w-10 h-10" />}
 *   heading="Preview Engine Standby"
 *   description="Your AI-generated resume will appear here."
 * />
 * ```
 */
const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  heading,
  description,
  className = '',
}) => (
  <div
    className={`flex-1 glass-card border-dashed border-2 border-slate-200 flex flex-col items-center justify-center p-12 text-center bg-slate-50/30 ${className}`}
  >
    <div className="w-20 h-20 bg-white rounded-3xl flex items-center justify-center mb-6 border border-slate-100 shadow-sm text-slate-200">
      {icon}
    </div>
    <h3 className="text-xl font-bold text-slate-400">{heading}</h3>
    <p className="text-slate-400 text-sm mt-2 max-w-xs font-medium">{description}</p>
  </div>
);

export default EmptyState;
