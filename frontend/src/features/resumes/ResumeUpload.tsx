import React, { useState, useEffect } from 'react';
import { Upload, File, FileText, CheckCircle2, AlertCircle, Loader2, Sparkles, Shield, AlertTriangle, BarChart3, ChevronDown, ChevronUp, Download, Trash2 } from 'lucide-react';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';

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
    const { persona } = useAuth();
    const isRecruiter = persona === 'recruiter';
    const [files, setFiles] = useState<any[]>([]);
    const [uploading, setUploading] = useState(false);
    const [results, setResults] = useState<any[]>([]);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [myResumes, setMyResumes] = useState<{ filename: string; validation: any }[]>([]);

    const fetchMyResumes = async () => {
        try {
            const response = await api.get('/resumes/list');
            setMyResumes(response.data.resumes || []);
        } catch (err) {
            console.error('Failed to fetch resumes:', err);
        }
    };

    useEffect(() => {
        fetchMyResumes();
    }, []);

    const handleDelete = async (filename: string) => {
        if (!window.confirm(`Delete "${filename}"?`)) return;
        try {
            await api.delete(`/resumes/${encodeURIComponent(filename)}`);
            fetchMyResumes();
        } catch (err) {
            console.error('Delete failed:', err);
        }
    };

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
        setUploadError(null);

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
            fetchMyResumes();
        } catch (err: any) {
            const msg = err.response?.data?.detail || err.message || 'Upload failed. Please try again.';
            setUploadError(typeof msg === 'string' ? msg : JSON.stringify(msg));
            console.error("Upload error details:", err.response?.data || err.message);
            setFiles(prev => prev.map(f => ({ ...f, status: 'error' })));
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* ── Page Header ── */}
            <div className="flex items-center justify-between gap-6 pb-5 border-b border-slate-100">
                <div>
                    <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                        {isRecruiter ? 'Resume Manager' : 'My Documents'}
                    </h1>
                    <p className="text-slate-400 text-sm font-medium mt-0.5">
                        {isRecruiter
                            ? 'Upload candidate resumes to your private vector search database.'
                            : 'Upload, manage, and index your resumes for AI-powered job matching.'}
                    </p>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0 bg-gradient-to-br from-slate-900 to-slate-800 border border-slate-700/60 rounded-2xl px-4 py-2.5 shadow-xl shadow-slate-900/20">
                    <Sparkles className="w-3.5 h-3.5 text-primary-400 mr-1" />
                    {['Validation', 'Embeddings', 'ATS Check'].map((label) => (
                        <div key={label} className="flex items-center gap-1.5 bg-white/5 border border-white/10 px-2.5 py-1 rounded-lg">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span className="text-[10px] font-bold text-slate-300 whitespace-nowrap">{label}</span>
                        </div>
                    ))}
                </div>
            </div>

            {uploadError && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 font-medium flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
                    <div>
                        <p className="font-bold text-xs uppercase tracking-wider text-red-500 mb-1">Upload Error</p>
                        {uploadError}
                    </div>
                </div>
            )}

            {/* ── Main Grid ── */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Left — Upload + Queue */}
                <div className="lg:col-span-2 space-y-5">

                    {/* Drop zone */}
                    <div className="relative rounded-2xl border-2 border-dashed border-slate-200 bg-gradient-to-br from-slate-50 to-white hover:border-primary-300 hover:from-primary-50/40 hover:to-white transition-all duration-300 cursor-pointer group overflow-hidden">
                        <input
                            type="file"
                            multiple
                            onChange={handleFileChange}
                            className="absolute inset-0 opacity-0 cursor-pointer z-10"
                            accept=".pdf,.docx"
                        />
                        {/* Decorative glow */}
                        <div className="absolute -top-10 -right-10 w-40 h-40 bg-primary-100 rounded-full blur-3xl opacity-0 group-hover:opacity-60 transition-opacity duration-500 pointer-events-none" />

                        <div className="flex flex-col items-center justify-center text-center py-14 px-8">
                            <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center mb-5 border border-slate-200 shadow-md shadow-slate-100 group-hover:shadow-primary-100 group-hover:border-primary-200 group-hover:scale-105 transition-all duration-300">
                                <Upload className="text-primary-500 w-7 h-7" />
                            </div>
                            <h3 className="text-base font-bold text-slate-800 mb-1">Drop resumes here or click to browse</h3>
                            <p className="text-slate-400 text-xs font-medium max-w-xs">
                                PDF & DOCX supported · AI validation · Vector indexed
                            </p>

                            {files.length > 0 && !uploading && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                                    className="mt-6 relative z-20 bg-primary-600 hover:bg-primary-500 active:scale-95 text-white px-7 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg shadow-primary-500/25 transition-all"
                                >
                                    <Upload className="w-4 h-4" />
                                    Process {files.length} {files.length === 1 ? 'File' : 'Files'}
                                </button>
                            )}
                            {uploading && (
                                <div className="mt-6 flex items-center gap-2.5 text-primary-600 font-bold bg-primary-50 px-5 py-2.5 rounded-xl border border-primary-100 text-sm">
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Validating & Indexing…
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Processing Queue */}
                    <div className="rounded-2xl border border-slate-100 bg-white shadow-sm overflow-hidden">
                        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
                            <h3 className="font-bold text-sm flex items-center gap-2 text-slate-700">
                                <File className="w-4 h-4 text-primary-400" />
                                Processing Queue
                            </h3>
                            <span className="text-[10px] font-black text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-200 tracking-widest">
                                {files.length} FILES
                            </span>
                        </div>
                        <div className="divide-y divide-slate-50">
                            {files.length === 0 ? (
                                <div className="py-12 text-center text-slate-300 text-sm font-medium">
                                    Queue is empty — select files above to begin.
                                </div>
                            ) : files.map((file, i) => (
                                <div key={i} className="px-5 py-3.5 flex items-center gap-4 hover:bg-slate-50/60 transition-colors">
                                    <div className="w-9 h-9 rounded-xl bg-slate-50 flex items-center justify-center border border-slate-100 flex-shrink-0">
                                        <FileText className="w-4 h-4 text-slate-400" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex justify-between items-center mb-1.5">
                                            <span className="text-sm font-semibold text-slate-700 truncate pr-2">{file.name}</span>
                                            <span className={`text-[10px] font-black uppercase tracking-widest flex-shrink-0 ${
                                                file.status === 'indexed' ? 'text-emerald-500' :
                                                file.status === 'error' ? 'text-red-500' : 'text-primary-500'
                                            }`}>{file.status}</span>
                                        </div>
                                        <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: file.status === 'indexed' ? '100%' : uploading ? '65%' : '0%' }}
                                                transition={{ duration: 0.6, ease: 'easeOut' }}
                                                className={`h-full rounded-full ${file.status === 'indexed' ? 'bg-emerald-400' : 'bg-primary-400'}`}
                                            />
                                        </div>
                                    </div>
                                    {file.status === 'indexed' && <CheckCircle2 className="text-emerald-400 w-5 h-5 flex-shrink-0" />}
                                    {file.status === 'error' && <AlertCircle className="text-red-400 w-5 h-5 flex-shrink-0" />}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Right — My Documents */}
                <div>
                    <div className="rounded-2xl border border-slate-100 bg-white shadow-sm overflow-hidden h-full">
                        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
                            <h3 className="font-bold text-sm flex items-center gap-2 text-slate-700">
                                <FileText className="w-4 h-4 text-primary-400" />
                                My Documents
                            </h3>
                            <span className="text-[10px] font-black text-white bg-primary-500 px-2 py-0.5 rounded-full tracking-widest">
                                {myResumes.length}
                            </span>
                        </div>
                        <div className="divide-y divide-slate-50">
                            {myResumes.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                                    <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center mb-3">
                                        <FileText className="w-5 h-5 text-slate-300" />
                                    </div>
                                    <p className="text-sm font-semibold text-slate-300">No resumes yet</p>
                                    <p className="text-xs text-slate-300 mt-0.5">Upload a file to get started</p>
                                </div>
                            ) : myResumes.map(({ filename, validation }, i) => {
                                const ext = filename.split('.').pop()?.toUpperCase() || '';
                                const totalScore: number | null = validation?.total_score ?? null;
                                const classification: string | null = validation?.classification ?? null;
                                const atsScore: number | null = validation?.scores?.ats_friendliness ?? null;
                                const qualityScore: number | null = validation?.scores?.achievement_quality ?? null;
                                const scorePct = totalScore !== null ? Math.round((totalScore / 30) * 100) : null;
                                const classConfig = classification ? (classificationConfig[classification] || classificationConfig.resume_valid_good) : null;
                                const barColor = scorePct !== null
                                    ? scorePct >= 83 ? 'bg-emerald-400' : scorePct >= 60 ? 'bg-amber-400' : 'bg-red-400'
                                    : 'bg-slate-200';

                                return (
                                    <motion.div
                                        key={i}
                                        initial={{ opacity: 0, x: 8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: i * 0.04 }}
                                        className="px-4 py-3.5 hover:bg-slate-50/70 transition-colors group/row"
                                    >
                                        {/* Top row: icon + name + actions */}
                                        <div className="flex items-center gap-3">
                                            <div className="w-9 h-9 rounded-xl bg-primary-50 border border-primary-100 flex items-center justify-center flex-shrink-0">
                                                <FileText className="w-4 h-4 text-primary-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-semibold text-slate-700 truncate">{filename}</p>
                                                <div className="flex items-center gap-2 mt-0.5">
                                                    <span className="text-[10px] font-black text-slate-400 tracking-widest">{ext}</span>
                                                    {classConfig && (
                                                        <span className={`text-[9px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border ${classConfig.color} ${classConfig.bg} ${classConfig.border}`}>
                                                            {classConfig.label}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1 opacity-0 group-hover/row:opacity-100 transition-opacity flex-shrink-0">
                                                <a
                                                    href={`${api.defaults.baseURL}/resumes/download/${encodeURIComponent(filename)}`}
                                                    download={filename}
                                                    className="w-7 h-7 rounded-lg hover:bg-primary-50 flex items-center justify-center text-slate-400 hover:text-primary-600 transition-colors"
                                                    title="Download"
                                                >
                                                    <Download className="w-3.5 h-3.5" />
                                                </a>
                                                <button
                                                    onClick={() => handleDelete(filename)}
                                                    className="w-7 h-7 rounded-lg hover:bg-red-50 flex items-center justify-center text-slate-400 hover:text-red-500 transition-colors"
                                                    title="Delete"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Score row */}
                                        {totalScore !== null && (
                                            <div className="mt-2.5 ml-12 space-y-2">
                                                {/* Overall score bar */}
                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1 h-1 bg-slate-100 rounded-full overflow-hidden">
                                                        <motion.div
                                                            initial={{ width: 0 }}
                                                            animate={{ width: `${scorePct}%` }}
                                                            transition={{ duration: 0.7, ease: 'easeOut' }}
                                                            className={`h-full rounded-full ${barColor}`}
                                                        />
                                                    </div>
                                                    <span className="text-[10px] font-black text-slate-500 flex-shrink-0">{totalScore}/30</span>
                                                </div>
                                                {/* Key metric chips */}
                                                <div className="flex gap-1.5 flex-wrap">
                                                    {atsScore !== null && (
                                                        <div className="flex items-center gap-1 bg-slate-50 border border-slate-100 rounded-md px-1.5 py-0.5">
                                                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">ATS</span>
                                                            <span className={`text-[10px] font-black ${atsScore >= 4 ? 'text-emerald-500' : atsScore >= 3 ? 'text-amber-500' : 'text-red-400'}`}>{atsScore}/5</span>
                                                        </div>
                                                    )}
                                                    {qualityScore !== null && (
                                                        <div className="flex items-center gap-1 bg-slate-50 border border-slate-100 rounded-md px-1.5 py-0.5">
                                                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Quality</span>
                                                            <span className={`text-[10px] font-black ${qualityScore >= 4 ? 'text-emerald-500' : qualityScore >= 3 ? 'text-amber-500' : 'text-red-400'}`}>{qualityScore}/5</span>
                                                        </div>
                                                    )}
                                                    {validation?.scores?.completeness != null && (
                                                        <div className="flex items-center gap-1 bg-slate-50 border border-slate-100 rounded-md px-1.5 py-0.5">
                                                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Complete</span>
                                                            <span className={`text-[10px] font-black ${validation.scores.completeness >= 4 ? 'text-emerald-500' : validation.scores.completeness >= 3 ? 'text-amber-500' : 'text-red-400'}`}>{validation.scores.completeness}/5</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )}
                                        {totalScore === null && (
                                            <p className="mt-1.5 ml-12 text-[10px] text-slate-300 italic">No validation data</p>
                                        )}
                                    </motion.div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Validation Results ── */}
            <AnimatePresence>
                {results.length > 0 && (
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                        <div className="flex items-center gap-3">
                            <div className="h-px flex-1 bg-slate-100" />
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Validation Results</span>
                            <div className="h-px flex-1 bg-slate-100" />
                        </div>
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
