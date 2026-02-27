import React, { useState } from 'react';
import { AlertTriangle, XCircle, ChevronDown, ChevronUp, Shield } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ValidationBannerProps {
    validation: any;
    type: 'error' | 'warning';
    onDismiss?: () => void;
}

const classificationConfig: Record<string, { label: string; color: string; bg: string; border: string }> = {
    not_resume:                   { label: 'Not a Resume',         color: 'text-red-700',     bg: 'bg-red-50',     border: 'border-red-200' },
    resume_invalid_or_incomplete: { label: 'Invalid / Incomplete', color: 'text-red-600',     bg: 'bg-red-50',     border: 'border-red-200' },
    resume_valid_but_weak:        { label: 'Weak Resume',          color: 'text-amber-700',   bg: 'bg-amber-50',   border: 'border-amber-200' },
    resume_valid_good:            { label: 'Good Resume',          color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
    resume_valid_strong:          { label: 'Strong Resume',        color: 'text-emerald-800', bg: 'bg-emerald-50', border: 'border-emerald-100' },
};

const scoreLabels: Record<string, string> = {
    document_type_validity: 'Doc Type',
    completeness: 'Complete',
    structure_readability: 'Structure',
    achievement_quality: 'Achievements',
    credibility_consistency: 'Credibility',
    ats_friendliness: 'ATS Ready',
};

const ValidationBanner: React.FC<ValidationBannerProps> = ({ validation, type, onDismiss }) => {
    const [expanded, setExpanded] = useState(false);
    const config = classificationConfig[validation?.classification] || classificationConfig.not_resume;
    const isError = type === 'error';

    return (
        <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-xl border ${config.border} ${config.bg} overflow-hidden`}
        >
            <div className="p-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                    {isError
                        ? <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
                        : <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0" />}
                    <div className="min-w-0">
                        <p className={`text-sm font-bold ${config.color}`}>
                            {isError ? 'Input Rejected — Not a Resume' : 'Resume Quality Warning'}
                        </p>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">
                            {validation?.summary || 'See details below.'}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded border ${config.color} ${config.bg} ${config.border}`}>
                        {config.label}
                    </span>
                    <span className="text-sm font-black text-slate-700">{validation?.total_score ?? 0}/30</span>
                    <button onClick={() => setExpanded(!expanded)} className="ml-1 text-slate-400 hover:text-slate-600 transition-colors">
                        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                    {onDismiss && (
                        <button onClick={onDismiss} className="ml-1 text-slate-300 hover:text-slate-500 text-[10px] font-bold uppercase tracking-widest transition-colors">
                            Dismiss
                        </button>
                    )}
                </div>
            </div>

            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        <div className="p-4 pt-0 space-y-4 border-t border-slate-100/50">
                            {/* Score chips */}
                            {validation?.scores && (
                                <div className="grid grid-cols-3 gap-2 pt-3">
                                    {Object.entries(validation.scores).map(([key, val]) => (
                                        <div key={key} className="flex items-center gap-1.5 text-xs">
                                            <span className="text-slate-400 font-bold">{scoreLabels[key] || key}:</span>
                                            <span className="font-black text-slate-700">{val as number}/5</span>
                                            <div className="flex-1 h-1 bg-slate-200 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all ${
                                                        (val as number) >= 4 ? 'bg-emerald-500' :
                                                        (val as number) >= 3 ? 'bg-amber-400' : 'bg-red-400'
                                                    }`}
                                                    style={{ width: `${((val as number) / 5) * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Top issues */}
                            {validation?.top_issues?.length > 0 && (
                                <div>
                                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Issues Found</p>
                                    <ul className="space-y-1">
                                        {validation.top_issues.map((issue: string, i: number) => (
                                            <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                                                <span className="text-red-300 mt-0.5">&#8226;</span> {issue}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Improvements */}
                            {validation?.suggested_improvements?.length > 0 && (
                                <div>
                                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Suggested Improvements</p>
                                    <ul className="space-y-1">
                                        {validation.suggested_improvements.map((item: string, i: number) => (
                                            <li key={i} className="text-xs text-slate-600 flex items-start gap-2">
                                                <span className="text-emerald-400 mt-0.5">&#8226;</span> {item}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
};

export default ValidationBanner;
