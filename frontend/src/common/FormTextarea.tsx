import React from 'react';

interface FormTextareaProps {
  /** Uppercase label displayed above the textarea. */
  label: string;
  /** Current textarea value. */
  value: string;
  /** Change handler. */
  onChange: (value: string) => void;
  /** Placeholder text. */
  placeholder?: string;
  /** Tailwind height class (e.g. "h-48", "h-80"). Defaults to "h-48". */
  height?: string;
  /** Optional extra info shown on the right side of the label row. */
  extra?: React.ReactNode;
}

/**
 * Labelled textarea matching the project's design system.
 *
 * ```tsx
 * <FormTextarea
 *   label="Candidate Profile"
 *   value={resumeText}
 *   onChange={setResumeText}
 *   placeholder="Paste resume text here..."
 *   height="h-80"
 * />
 * ```
 */
const FormTextarea: React.FC<FormTextareaProps> = ({
  label,
  value,
  onChange,
  placeholder = '',
  height = 'h-48',
  extra,
}) => (
  <div className="flex flex-col gap-2">
    <div className="flex justify-between items-center">
      <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">
        {label}
      </span>
      {extra}
    </div>
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full ${height} bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm font-medium text-slate-800 shadow-inner`}
      placeholder={placeholder}
    />
  </div>
);

export default FormTextarea;
