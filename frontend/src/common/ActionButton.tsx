import React from 'react';
import { Loader2 } from 'lucide-react';

interface ActionButtonProps {
  /** Click handler. */
  onClick: () => void;
  /** Whether the action is in progress. */
  loading: boolean;
  /** Disable the button (in addition to loading state). */
  disabled?: boolean;
  /** Icon shown when NOT loading. */
  icon: React.ReactNode;
  /** Label shown when NOT loading. */
  label: string;
  /** Label shown when loading (defaults to "Processing..."). */
  loadingLabel?: string;
  /** Extra className (merged with defaults). */
  className?: string;
}

/**
 * Primary action button with built-in loading spinner swap.
 *
 * ```tsx
 * <ActionButton
 *   onClick={handleGenerate}
 *   loading={generating}
 *   disabled={!profile.trim()}
 *   icon={<Sparkles className="w-5 h-5" />}
 *   label="Generate AI Resume"
 *   loadingLabel="Crafting Professional Content..."
 * />
 * ```
 */
const ActionButton: React.FC<ActionButtonProps> = ({
  onClick,
  loading,
  disabled = false,
  icon,
  label,
  loadingLabel = 'Processing...',
  className = '',
}) => (
  <button
    onClick={onClick}
    disabled={loading || disabled}
    className={`w-full bg-primary-600 hover:bg-primary-500 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-3 shadow-lg shadow-primary-500/20 disabled:opacity-50 transition-all ${className}`}
  >
    {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : icon}
    {loading ? loadingLabel : label}
  </button>
);

export default ActionButton;
