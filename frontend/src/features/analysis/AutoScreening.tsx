import React, { useState, useEffect } from 'react';
import { ShieldCheck, Loader2, UserCheck, UserX, Info, Target, AlertCircle, ChevronDown } from 'lucide-react';
import api, { jobsApi } from '../../api';
import { motion } from 'framer-motion';
import { PageHeader, EmptyState, LoadingOverlay, ActionButton, FormTextarea, ValidationBanner } from '../../common';

const AutoScreening = () => {
    const [resumeText, setResumeText] = useState('');
    const [jdText, setJdText] = useState('');
    const [threshold, setThreshold] = useState(75);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [validationError, setValidationError] = useState<any>(null);
    const [validationWarning, setValidationWarning] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);
    const [resumes, setResumes] = useState<string[]>([]);
    const [selectedResume, setSelectedResume] = useState('');
    const [loadingResume, setLoadingResume] = useState(false);
    const [jobs, setJobs] = useState<any[]>([]);
    const [selectedJob, setSelectedJob] = useState('');
    const [loadingJob, setLoadingJob] = useState(false);

    useEffect(() => {
        api.get('/resumes').then(r => setResumes(r.data.resumes || [])).catch(() => {});
        jobsApi.list({ limit: 100 }).then(r => setJobs(r.data || [])).catch(() => {});
    }, []);

    const handleJobSelect = async (jobId: string) => {
        setSelectedJob(jobId);
        if (!jobId) { setJdText(''); return; }
        setLoadingJob(true);
        try {
            const r = await jobsApi.get(jobId);
            const job = r.data;
            const details = [
                job.title && `Job Title: ${job.title}`,
                job.employer_name && `Company: ${job.employer_name}`,
                job.location_name && `Location: ${job.location_name}`,
                job.employment_type && `Employment Type: ${job.employment_type}`,
                job.job_level && `Level: ${job.job_level}`,
                job.skills_required?.length && `Required Skills: ${job.skills_required.join(', ')}`,
                job.description && `\n${job.description}`,
            ].filter(Boolean).join('\n');
            setJdText(details);
        } catch {
            setJdText('');
        } finally {
            setLoadingJob(false);
        }
    };

    const handleResumeSelect = async (filename: string) => {
        setSelectedResume(filename);
        if (!filename) { setResumeText(''); return; }
        setLoadingResume(true);
        try {
            const r = await api.get(`/resumes/${encodeURIComponent(filename)}/text`);
            setResumeText(r.data.text || '');
        } catch {
            setResumeText('');
        } finally {
            setLoadingResume(false);
        }
    };

    const handleScreen = async () => {
        if (!resumeText.trim() || !jdText.trim()) return;
        setLoading(true);
        setResult(null);
        setValidationError(null);
        setValidationWarning(null);
        setError(null);
        try {
            const response = await api.post('/analyze/screen', {
                resume_text: resumeText,
                jd_text: jdText,
                threshold: threshold
            });
            setResult(response.data);
            if (response.data.validation_warning) {
                setValidationWarning(response.data.validation_warning);
            }
        } catch (err: any) {
            if (err.response?.status === 422 && err.response?.data?.detail?.error === 'not_a_resume') {
                setValidationError(err.response.data.detail.validation);
            } else {
                const msg = err.response?.data?.detail || err.message || 'Screening failed. Please try again.';
                setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <PageHeader
                title="Auto Screening Decisions"
                subtitle="Automated candidate matching against custom thresholds and JD requirements."
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-6">
                    <div className="glass-card p-8 space-y-6 bg-white/70 border-slate-100 shadow-sm">
                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">
                                Select Resume from Database
                            </label>
                            <div className="relative">
                                <select
                                    value={selectedResume}
                                    onChange={e => handleResumeSelect(e.target.value)}
                                    disabled={loadingResume}
                                    className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 pr-10 focus:ring-2 focus:ring-blue-500 outline-none transition-all disabled:opacity-60"
                                >
                                    <option value="">— choose a resume —</option>
                                    {resumes.map(fn => (
                                        <option key={fn} value={fn}>{fn}</option>
                                    ))}
                                </select>
                                <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                                    {loadingResume
                                        ? <Loader2 size={16} className="text-slate-400 animate-spin" />
                                        : <ChevronDown size={16} className="text-slate-400" />
                                    }
                                </div>
                            </div>
                        </div>
                        <FormTextarea
                            label="Candidate Resume"
                            value={resumeText}
                            onChange={setResumeText}
                            placeholder="Candidate resume..."
                            height="h-40"
                        />
                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">
                                Select Job from Database
                            </label>
                            <div className="relative">
                                <select
                                    value={selectedJob}
                                    onChange={e => handleJobSelect(e.target.value)}
                                    disabled={loadingJob}
                                    className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 pr-10 focus:ring-2 focus:ring-blue-500 outline-none transition-all disabled:opacity-60"
                                >
                                    <option value="">— choose a job —</option>
                                    {jobs.map(j => (
                                        <option key={j.job_id} value={j.job_id}>
                                            {j.title}{j.employer_name ? ` — ${j.employer_name}` : ''}
                                        </option>
                                    ))}
                                </select>
                                <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
                                    {loadingJob
                                        ? <Loader2 size={16} className="text-slate-400 animate-spin" />
                                        : <ChevronDown size={16} className="text-slate-400" />
                                    }
                                </div>
                            </div>
                        </div>
                        <FormTextarea
                            label="Target Job Description"
                            value={jdText}
                            onChange={setJdText}
                            placeholder="Job description..."
                            height="h-40"
                        />
                    </div>

                    <div className="glass-card p-8 bg-white/50 border-slate-100 shadow-sm">
                        <div className="flex justify-between items-center mb-6">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Selection Threshold</span>
                            <span className="text-primary-600 font-black bg-primary-50 px-2 py-0.5 rounded border border-primary-100 shadow-sm">{threshold}%</span>
                        </div>
                        <input
                            type="range"
                            min="50" max="90"
                            value={threshold}
                            onChange={(e) => setThreshold(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary-600 border border-slate-200"
                        />
                        <div className="flex justify-between text-[10px] text-slate-400 mt-2 font-black uppercase tracking-tight">
                            <span>Standard (50%)</span>
                            <span>Strict (75%)</span>
                            <span>Elite (90%)</span>
                        </div>
                    </div>

                    <ActionButton
                        onClick={handleScreen}
                        loading={loading}
                        disabled={!resumeText.trim() || !jdText.trim()}
                        icon={<ShieldCheck className="w-5 h-5" />}
                        label="Execute Screening Decision"
                        loadingLabel="Executing Agentic Flow..."
                        className="py-5"
                    />
                </div>

                <div className="flex flex-col min-h-[500px]">
                    {validationError && (
                        <div className="mb-4">
                            <ValidationBanner validation={validationError} type="error" />
                        </div>
                    )}

                    {validationWarning && !validationError && (
                        <div className="mb-4">
                            <ValidationBanner
                                validation={validationWarning}
                                type="warning"
                                onDismiss={() => setValidationWarning(null)}
                            />
                        </div>
                    )}

                    {error && !validationError && (
                        <div className="mb-4">
                            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 font-medium">
                                <div className="flex items-center gap-2 mb-1 font-black text-[10px] uppercase tracking-widest text-red-500">
                                    <AlertCircle className="w-3.5 h-3.5" /> Screening Error
                                </div>
                                {error}
                            </div>
                        </div>
                    )}

                    {!result && !loading && !validationError && !error && (
                        <EmptyState
                            icon={<ShieldCheck className="w-10 h-10" />}
                            heading="Decision Engine Standby"
                            description="Provide resume and JD data to trigger the AI-agentic screening flow."
                        />
                    )}

                    {loading && (
                        <LoadingOverlay
                            icon={<ShieldCheck className="w-10 h-10 text-primary-200" />}
                            message="Simulating Agent Reasoning..."
                        />
                    )}

                    {result && (
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex-1 flex flex-col shadow-lg rounded-xl overflow-hidden">
                            <div className={`p-10 rounded-t-xl border-x border-t flex flex-col items-center text-center ${result.decision.selected ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'
                                }`}>
                                <div className={`w-20 h-20 rounded-2xl shadow-sm flex items-center justify-center mb-6 ${result.decision.selected ? 'bg-white border border-emerald-200' : 'bg-white border border-red-200'
                                    }`}>
                                    {result.decision.selected ? <UserCheck className="text-emerald-500 w-10 h-10" /> : <UserX className="text-red-500 w-10 h-10" />}
                                </div>
                                <h2 className={`text-2xl font-black uppercase tracking-widest ${result.decision.selected ? 'text-emerald-700' : 'text-red-700'
                                    }`}>
                                    {result.decision.selected ? 'Candidate Selected' : 'Candidate Rejected'}
                                </h2>
                                <div className="mt-6 flex items-baseline gap-2">
                                    <span className="text-6xl font-black text-slate-900 tracking-tighter">{result.score.overall}%</span>
                                    <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Alignment Score</span>
                                </div>
                            </div>

                            <div className="flex-1 glass-card border-t-0 rounded-t-none p-10 space-y-8 bg-white/90">
                                <div className="space-y-3">
                                    <h4 className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                                        <Info className="w-3.5 h-3.5" /> Logical Reasoning Path
                                    </h4>
                                    <p className="text-sm leading-relaxed text-slate-600 bg-slate-50 p-6 rounded-xl border border-slate-100 font-medium italic shadow-inner">
                                        "{result.decision.reason}"
                                    </p>
                                </div>

                                <div className="pt-8 border-t border-slate-100">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">
                                        <Target className="w-3.5 h-3.5" /> KPI Benchmarks
                                    </div>
                                    <div className="space-y-4">
                                        <div className="flex justify-between items-center text-sm">
                                            <span className="text-slate-500 font-bold">Required Score Threshold</span>
                                            <span className="font-mono bg-slate-50 px-2 py-0.5 rounded border border-slate-200 font-black text-slate-700">{threshold}%</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                            <span className="text-slate-500 font-bold">Actual Calculated Score</span>
                                            <span className={`font-mono font-black px-2 py-0.5 rounded border ${result.score.overall >= threshold ? 'text-emerald-700 bg-emerald-50 border-emerald-100' : 'text-red-700 bg-red-50 border-red-100'}`}>
                                                {result.score.overall}%
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default AutoScreening;
