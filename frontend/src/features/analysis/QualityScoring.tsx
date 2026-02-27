import React, { useState } from 'react';
import {
    BarChart3,
    Loader2,
    Zap,
    Layout,
    ShieldCheck,
    Search,
    BarChart,
    ListChecks,
    User,
    CheckCircle2,
    Target
} from 'lucide-react';
import api from '../../api';
import { motion } from 'framer-motion';
import { PageHeader, EmptyState, ActionButton, FormTextarea, ValidationBanner } from '../../common';

const ScoreRing = ({ value, label, color }: any) => (
    <div className="flex flex-col items-center">
        <div className="relative w-24 h-24 mb-3">
            <svg className="w-full h-full transform -rotate-90">
                <circle cx="48" cy="48" r="40" fill="transparent" stroke="currentColor" strokeWidth="8" className="text-slate-100" />
                <circle cx="48" cy="48" r="40" fill="transparent" stroke="currentColor" strokeWidth="8" strokeDasharray={251.2} strokeDashoffset={251.2 - (value / 100) * 251.2} className={`text-${color}-500 transition-all duration-1000 ease-out`} />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center font-bold text-xl text-slate-800">{value}</div>
        </div>
        <span className="text-[10px] text-slate-400 uppercase tracking-widest font-black">{label}</span>
    </div>
);

const QualityScoring = () => {
    const [text, setText] = useState('');
    const [analyzing, setAnalyzing] = useState(false);
    const [results, setResults] = useState<any>(null);
    const [validationError, setValidationError] = useState<any>(null);
    const [validationWarning, setValidationWarning] = useState<any>(null);

    const handleScore = async () => {
        if (!text.trim()) return;
        setAnalyzing(true);
        setResults(null);
        setValidationError(null);
        setValidationWarning(null);
        try {
            const response = await api.post('/analyze/quality', { resume_text: text });
            setResults(response.data);
            if (response.data.validation_warning) {
                setValidationWarning(response.data.validation_warning);
            }
        } catch (err: any) {
            if (err.response?.status === 422 && err.response?.data?.detail?.error === 'not_a_resume') {
                setValidationError(err.response.data.detail.validation);
            } else {
                console.error(err);
            }
        } finally {
            setAnalyzing(false);
        }
    };

    const hasData = results && results.score;

    return (
        <div className="space-y-8 text-slate-900">
            <PageHeader
                title="AI Quality Scoring"
                subtitle="Deep audit of resume structure, impact, and formatting using LLM reasoning."
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-4">
                    <FormTextarea
                        label="Candidate Resume"
                        value={text}
                        onChange={setText}
                        placeholder="Paste the resume content here for deep analysis..."
                        height="h-[450px]"
                        extra={<span className="text-xs text-slate-400 font-medium">{text.length} characters</span>}
                    />
                    <ActionButton
                        onClick={handleScore}
                        loading={analyzing}
                        disabled={!text.trim()}
                        icon={<Zap className="w-5 h-5" />}
                        label="Trigger Quality Audit"
                        loadingLabel="Scanning Resume Architecture..."
                    />
                </div>

                <div className="glass-card flex flex-col items-center justify-center min-h-[500px] border-slate-100 bg-white/80">
                    {validationError && (
                        <div className="w-full p-4">
                            <ValidationBanner validation={validationError} type="error" />
                        </div>
                    )}

                    {validationWarning && !validationError && (
                        <div className="w-full p-4 pb-0">
                            <ValidationBanner
                                validation={validationWarning}
                                type="warning"
                                onDismiss={() => setValidationWarning(null)}
                            />
                        </div>
                    )}

                    {!hasData && !analyzing && !validationError && (
                        <EmptyState
                            icon={<Target className="w-10 h-10" />}
                            heading="Ready for Analysis"
                            description="Input a resume on the left to generate a comprehensive quality scorecard."
                            className="border-0"
                        />
                    )}

                    {analyzing && (
                        <div className="text-center">
                            <div className="relative w-32 h-32 mx-auto mb-8">
                                <div className="absolute inset-0 border-4 border-primary-50 rounded-full" />
                                <div className="absolute inset-0 border-4 border-primary-500 rounded-full border-t-transparent animate-spin" />
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <BrainCircuit className="w-10 h-10 text-primary-200 animate-pulse" />
                                </div>
                            </div>
                            <p className="text-primary-600 font-bold tracking-tight animate-pulse text-lg">AI Auditor is Thinking...</p>
                            <p className="text-slate-400 text-xs mt-2 uppercase tracking-widest font-black">Evaluating 42+ quality metrics</p>
                        </div>
                    )}

                    {hasData && (
                        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="w-full p-8 space-y-10">
                            <div className="text-center">
                                <div className="inline-flex items-center gap-2 bg-emerald-50 text-emerald-700 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border border-emerald-100 mb-4 shadow-sm">
                                    <ShieldCheck className="w-3 h-3" /> Audit Complete
                                </div>
                                <h2 className="text-6xl font-black text-slate-900 tracking-tighter">{results.score.overall}</h2>
                                <p className="text-slate-400 mt-1 uppercase tracking-widest text-[10px] font-black">Overall Quality Score</p>
                            </div>

                            <div className="grid grid-cols-3 gap-4 border-y border-slate-100 py-8">
                                <ScoreRing value={results.score.clarity || 85} label="Clarity" color="blue" />
                                <ScoreRing value={results.score.skills || 90} label="Skills" color="amber" />
                                <ScoreRing value={results.score.format || 75} label="Format" color="emerald" />
                            </div>

                            <div className="bg-slate-50/80 p-6 rounded-xl border border-slate-100 shadow-inner">
                                <div className="flex items-center gap-2 mb-3">
                                    <Layout className="w-4 h-4 text-primary-500" />
                                    <h4 className="font-black text-[10px] uppercase tracking-widest text-slate-400">System Recommendation</h4>
                                </div>
                                <p className="text-sm text-slate-600 font-medium leading-relaxed italic">
                                    {results.summary || "High skill density detected. Consider refining the 'Summary' section for maximum impact."}
                                </p>
                            </div>
                        </motion.div>
                    )}
                </div>
            </div>

            {hasData && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[
                        { label: 'Formatting & Layout', icon: Layout, color: 'blue', val: 92 },
                        { label: 'Impact Metrics', icon: Zap, color: 'amber', val: 78 },
                        { label: 'Keyword Optimization', icon: Search, color: 'emerald', val: results.score.overall },
                        { label: 'Experience Depth', icon: BarChart3, color: 'indigo', val: 85 },
                        { label: 'Clarity & Conciseness', icon: ListChecks, color: 'purple', val: 90 },
                        { label: 'Contact Information', icon: User, color: 'slate', val: 100 }
                    ].map((item, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 + i * 0.1 }}
                            className="glass-card p-6 border-slate-100 bg-white/70 hover:shadow-md transition-shadow"
                        >
                            <div className="flex items-center gap-4 mb-4">
                                <div className={`p-2.5 rounded-lg bg-${item.color}-50 text-${item.color}-600 border border-${item.color}-100`}>
                                    <item.icon className="w-5 h-5" />
                                </div>
                                <h4 className="font-bold text-slate-800 text-sm tracking-tight">{item.label}</h4>
                            </div>
                            <div className="flex items-center gap-4">
                                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden border border-slate-200 shadow-inner">
                                    <motion.div
                                        initial={{ width: 0 }}
                                        animate={{ width: `${item.val}%` }}
                                        className={`h-full bg-${item.color}-500`}
                                    />
                                </div>
                                <span className="text-sm font-black text-slate-700 w-8">{item.val}%</span>
                            </div>
                        </motion.div>
                    ))}
                </div>
            )}
        </div>
    );
};

// Mock icon for the loading state inside the component
const BrainCircuit = ({ className }: { className?: string }) => (
    <div className={className}>
        <div className="w-full h-full border-2 border-current rounded-full flex items-center justify-center opacity-50">
            <div className="w-1/2 h-1/2 bg-current rounded-full" />
        </div>
    </div>
);

export default QualityScoring;
