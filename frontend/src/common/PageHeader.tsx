import React from 'react';

interface PageHeaderProps {
  title: string;
  subtitle: string;
  /** Optional right-side action (e.g. a button). */
  action?: React.ReactNode;
}

/**
 * Consistent page header used across every page.
 *
 * ```tsx
 * <PageHeader title="Resume Manager" subtitle="Upload candidate resumes..." />
 * ```
 */
const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, action }) => (
  <header className={action ? 'flex justify-between items-center' : undefined}>
    <div>
      <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">{title}</h1>
      <p className="text-slate-500 font-medium">{subtitle}</p>
    </div>
    {action}
  </header>
);

export default PageHeader;
