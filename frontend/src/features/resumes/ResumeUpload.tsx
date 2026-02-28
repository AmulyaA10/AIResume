import React, { useState } from 'react';
import { Upload, File, FileText, CheckCircle2, AlertCircle, Loader2, Sparkles, Shield, AlertTriangle, BarChart3, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';
import { PageHeader } from '../../common';

const classificationConfig: Record<string, { label: string; color: string; bg: string; border: string }> = {
    not_resume: { label: 'Not a Resume', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
    resume_invalid_or_incomplete: { label: 'Invalid / Incomplete', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
    resume_valid_but_weak: { label: 'Weak Resume', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
    resume_valid_good: { label: 'Good Resume', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
    resume_valid_strong: { label: 'Strong Resume', color: 'text-emerald-800', bg: 'bg-emerald-50', border: 'border-emerald-100' },
};

const scoreLabels: Record<string, string> = {
    document_type_validity: 'Doc Type',
    completeness: 'Complete',
    structure_readability: 'Structure',
    achievement_quality: 'Achievements',
    credibility_consistency: 'Credibility',
    ats_friendliness: 'ATS Ready',
};

const ScoreChip = ({ label, value }: { label: string; value: number }) => {
    const pct = (value / 5) * 100;
    const color = value >= 4 ? 'bg-emerald-500' : value >= 3 ? 'bg-amber-400' : 'bg-red-400';
    return (
        <div className="flex flex-col gap-1">
            <div className="flex justify-between items-center">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{label}</span>
                <span className="text-xs font-bold text-slate-600">{value}/5</span>
            </div>
            <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200">
                <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
            </div>
        </div>
    );
};

const ValidationCard = ({ validation, filename }: { validation: any; filename: string }) => {
    const [expanded, setExpanded] = useState(false);

    if (!validation || validation.error) {
        return (
            <div className="flex items-center gap-4 p-4 glass-card border-emerald-100 bg-emerald-50/50">
                <CheckCircle2 className="text-emerald-500 w-5 h-5 flex-shrink-0" />
                <div className="flex-1">
                    <p className="text-sm font-bold text-slate-800">{filename}</p>
                    <p className="text-xs text-emerald-600 font-medium">Successfully parsed and stored in LanceDB</p>
                    {validation?.error && (
                        <p className="text-xs text-amber-500 font-medium mt-1">Validation skipped: {validation.error}</p>
                    )}
                </div>
            </div>
        );
    }

    const config = classificationConfig[validation.classification] || classificationConfig.resume_valid_good;
    const totalPct = Math.round((validation.total_score / 30) * 100);
    const totalBarColor = validation.total_score >= 25 ? 'bg-emerald-500'
        : validation.total_score >= 18 ? 'bg-emerald-400'
        : validation.total_score >= 11 ? 'bg-amber-400'
        : 'bg-red-400';

    return (
        <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`glass-card ${config.border} overflow-hidden`}
        >
            {/* Header */}
            <div className={`p-4 flex items-center justify-between ${config.bg}`}>
                <div className="flex items-center gap-3">
                    <Shield className={`w-5 h-5 ${config.color}`} />
                    <div>
                        <p className="text-sm font-bold text-slate-800">{filename}</p>
                        <p className="text-xs text-slate-500 font-medium">Stored in LanceDB</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded border ${config.color} ${config.bg} ${config.border}`}>
                        {config.label}
                    </span>
                    <span className="text-sm font-black text-slate-700">{validation.total_score}/30</span>
                </div>
            </div>

            {/* Score bar */}
            <div className="px-4 pt-3 pb-2">
                <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200 shadow-inner">
                    <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${totalPct}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut' }}
                        className={`h-full rounded-full ${totalBarColor}`}
                    />
                </div>
            </div>

            {/* Individual scores */}
            <div className="px-4 py-3 grid grid-cols-3 gap-3">
                {Object.entries(validation.scores || {}).map(([key, val]) => (
                    <ScoreChip key={key} label={scoreLabels[key] || key} value={val as number} />
                ))}
            </div>

            {/* Summary */}
            {validation.summary && (
                <div className="px-4 pb-3">
                    <p className="text-sm text-slate-600 font-medium leading-relaxed">{validation.summary}</p>
                </div>
            )}

            {/* Expandable details */}
            <div className="border-t border-slate-100">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-widest hover:bg-slate-50 transition-colors"
                >
                    <span>Detailed Feedback</span>
                    {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                <AnimatePresence>
                    {expanded && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                        >
                            <div className="px-4 pb-4 space-y-4">
                                {/* Top Issues */}
                                {validation.top_issues?.length > 0 && (
                                    <div>
                                        <h5 className="text-[10px] font-black text-red-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                            <AlertTriangle className="w-3 h-3" /> Issues Found
                                        </h5>
                                        <ul className="space-y-1">
                                            {validation.top_issues.map((issue: string, idx: number) => (
                                                <li key={idx} className="text-xs text-slate-600 font-medium flex items-start gap-2">
                                                    <span className="text-red-300 mt-0.5">&#8226;</span> {issue}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Suggested Improvements */}
                                {validation.suggested_improvements?.length > 0 && (
                                    <div>
                                        <h5 className="text-[10px] font-black text-primary-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                                            <BarChart3 className="w-3 h-3" /> Suggested Improvements
                                        </h5>
                                        <ul className="space-y-1">
                                            {validation.suggested_improvements.map((item: string, idx: number) => (
                                                <li key={idx} className="text-xs text-slate-600 font-medium flex items-start gap-2">
                                                    <span className="text-primary-300 mt-0.5">&#8226;</span> {item}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* Missing Fields */}
                                {validation.missing_fields?.length > 0 && (
                                    <div>
                                        <h5 className="text-[10px] font-black text-amber-400 uppercase tracking-widest mb-2">Missing Fields</h5>
                                        <div className="flex flex-wrap gap-1.5">
                                            {validation.missing_fields.map((field: string, idx: number) => (
                                                <span key={idx} className="text-[10px] font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                                    {field}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Follow-up Questions */}
                                {validation.followup_verification_questions?.length > 0 && (
                                    <div>
                                        <h5 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2">Verification Questions</h5>
                                        <ul className="space-y-1">
                                            {validation.followup_verification_questions.map((q: string, idx: number) => (
                                                <li key={idx} className="text-xs text-slate-500 font-medium flex items-start gap-2">
                                                    <span className="text-slate-300 mt-0.5">{idx + 1}.</span> {q}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </motion.div>
    );
};

const ResumeUpload = () => {
    const [files, setFiles] = useState<any[]>([]);
    const [uploading, setUploading] = useState(false);
    const [results, setResults] = useState<any[]>([]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const newFiles = Array.from(e.target.files).map(file => ({
                file,
                name: file.name,
                status: 'pending'
            }));
            setFiles(newFiles);
        }
    };

    const handleUpload = async () => {
        console.log("handleUpload triggered", files);
        if (files.length === 0) return;
        setUploading(true);
        setResults([]);

        const formData = new FormData();
        files.forEach(f => formData.append('files', f.file));
        formData.append('store_db', 'true');
        formData.append('run_validation', 'true');

        try {
            console.log("Sending request to /resumes/upload");
            const response = await api.post('/resumes/upload', formData);
            console.log("Upload response:", response.data);
            setResults(response.data.processed);
            setFiles(prev => prev.map(f => ({ ...f, status: 'indexed' })));
        } catch (err: any) {
            console.error("Upload error details:", err.response?.data || err.message);
            setFiles(prev => prev.map(f => ({ ...f, status: 'error' })));
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-8">
            <PageHeader
                title="Resume Manager"
                subtitle="Upload candidate resumes to your private vector search database."
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                    <div className="glass-card p-16 border-2 border-dashed border-slate-200 hover:border-primary-300 hover:bg-slate-50/50 transition-all cursor-pointer flex flex-col items-center justify-center text-center relative group">
                        <input
                            type="file"
                            multiple
                            onChange={handleFileChange}
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            accept=".pdf,.docx"
                        />
                        <div className="w-16 h-16 bg-primary-50 rounded-2xl flex items-center justify-center mb-4 border border-primary-100 shadow-sm group-hover:scale-110 transition-transform">
                            <Upload className="text-primary-600 w-8 h-8" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Click or drag resumes here</h3>
                        <p className="text-slate-500 max-w-xs mx-auto text-sm font-medium">Supports PDF and DOCX files. Files are validated by AI and indexed for semantic search.</p>

                        {files.length > 0 && !uploading && (
                            <button
                                onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                                className="mt-6 bg-primary-600 hover:bg-primary-500 text-white px-6 py-3 rounded-lg text-base font-bold flex items-center gap-2 shadow-lg shadow-primary-500/20 transition-all relative z-20"
                            >
                                <Upload className="w-5 h-5" />
                                Process {files.length} Files
                            </button>
                        )}
                        {uploading && (
                            <div className="mt-6 flex items-center gap-3 text-primary-600 font-bold bg-primary-50 px-6 py-3 rounded-lg border border-primary-100">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Validating & Indexing...
                            </div>
                        )}
                    </div>

                    <div className="glass-card">
                        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-white">
                            <h3 className="font-bold flex items-center gap-2 text-slate-800">
                                <File className="w-4 h-4 text-primary-500" />
                                Processing Queue
                            </h3>
                            <span className="text-[10px] font-black text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-200 tracking-widest">{files.length} FILES</span>
                        </div>
                        <div className="divide-y divide-slate-100">
                            {files.length === 0 && (
                                <div className="p-12 text-center text-slate-300 italic font-medium">
                                    Queue is empty. Select files to see progress.
                                </div>
                            )}
                            {files.map((file, i) => (
                                <div key={i} className="p-4 flex items-center gap-4 hover:bg-slate-50/50 transition-colors">
                                    <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center border border-slate-200">
                                        <FileText className="w-4 h-4 text-slate-400" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex justify-between items-center mb-1">
                                            <span className="text-sm font-bold text-slate-700">{file.name}</span>
                                            <span className={`text-[10px] font-black uppercase tracking-widest ${file.status === 'indexed' ? 'text-emerald-600' :
                                                file.status === 'error' ? 'text-red-600' : 'text-primary-600'
                                                }`}>{file.status}</span>
                                        </div>
                                        <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200 shadow-inner">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: file.status === 'indexed' ? '100%' : uploading ? '60%' : '0%' }}
                                                className={`h-full ${file.status === 'indexed' ? 'bg-emerald-500' : 'bg-primary-500'}`}
                                            />
                                        </div>
                                    </div>
                                    {file.status === 'indexed' && <CheckCircle2 className="text-emerald-500 w-5 h-5 flex-shrink-0" />}
                                    {file.status === 'error' && <AlertCircle className="text-red-500 w-5 h-5 flex-shrink-0" />}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="glass-card p-6 bg-primary-600 text-white shadow-lg shadow-primary-500/20">
                        <h4 className="font-bold mb-4 flex items-center gap-2 text-primary-50">
                            <Sparkles className="w-4 h-4" />
                            AI Validation Active
                        </h4>
                        <p className="text-sm text-primary-100 leading-relaxed mb-6 font-medium">
                            Our system validates documents, scores resume quality, and indexes embeddings into your vector store for sub-second semantic retrieval.
                        </p>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3 text-xs font-bold bg-white/10 p-2 rounded border border-white/10">
                                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                Resume Validation: ON
                            </div>
                            <div className="flex items-center gap-3 text-xs font-bold bg-white/10 p-2 rounded border border-white/10">
                                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                Vector Embeddings: ON
                            </div>
                            <div className="flex items-center gap-3 text-xs font-bold bg-white/10 p-2 rounded border border-white/10">
                                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                ATS Compatibility Check
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <AnimatePresence>
                {results.length > 0 && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                        <h3 className="font-bold text-slate-400 uppercase tracking-widest text-[10px]">Validation Results</h3>
                        {results.map((res, i) => (
                            <ValidationCard key={i} validation={res.validation} filename={res.filename} />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default ResumeUpload;
