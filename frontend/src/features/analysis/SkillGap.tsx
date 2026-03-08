import React, { useState, useEffect } from 'react';
import { BrainCircuit, Loader2, Sparkles, AlertCircle, CheckCircle2, ChevronRight, ChevronDown } from 'lucide-react';
import api, { jobsApi } from '../../api';
import { motion, AnimatePresence } from 'framer-motion';
import { PageHeader, EmptyState, ActionButton, FormTextarea, ValidationBanner } from '../../common';

const SkillGap = () => {
    const [resumeText, setResumeText] = useState('');
    const [jdText, setJdText] = useState('');
    const [analyzing, setAnalyzing] = useState(false);
    const [gaps, setGaps] = useState<any>(null);
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

    const handleAnalyze = async () => {
        if (!resumeText.trim() || !jdText.trim()) return;
        setAnalyzing(true);
        setGaps(null);
        setValidationError(null);
        setValidationWarning(null);
        setError(null);
        try {
            const response = await api.post('/analyze/gap', {
                resume_text: resumeText,
                jd_text: jdText
            });
            setGaps(response.data.gaps);
            if (response.data.validation_warning) {
                setValidationWarning(response.data.validation_warning);
            }
        } catch (err: any) {
            if (err.response?.status === 422 && err.response?.data?.detail?.error === 'not_a_resume') {
                setValidationError(err.response.data.detail.validation);
            } else {
                const msg = err.response?.data?.detail || err.message || 'Skill gap analysis failed. Please try again.';
                setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
        } finally {
            setAnalyzing(false);
        }
    };

    return (
        <div className="space-y-8">
            <PageHeader
                title="Skill Gap Analysis"
                subtitle="Identify missing competencies by comparing candidate resumes against job requirements."
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="glass-card p-8 flex flex-col gap-6 bg-white/70 border-slate-100 shadow-sm">
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
                        label="Candidate Profile"
                        value={resumeText}
                        onChange={setResumeText}
                        placeholder="Paste resume text here..."
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
                        label="Job Description"
                        value={jdText}
                        onChange={setJdText}
                        placeholder="Paste job description here..."
                    />
                    <ActionButton
                        onClick={handleAnalyze}
                        loading={analyzing}
                        disabled={!resumeText.trim() || !jdText.trim()}
                        icon={<BrainCircuit className="w-5 h-5" />}
                        label="Analyze Skill Alignment"
                        loadingLabel="Analyzing..."
                        className="mt-2"
                    />
                </div>

                <div className="flex flex-col h-full min-h-[500px]">
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
                                    <AlertCircle className="w-3.5 h-3.5" /> Analysis Error
                                </div>
                                {error}
                            </div>
                        </div>
                    )}

                    <AnimatePresence mode="wait">
                        {!gaps && !analyzing && !validationError && !error && (
                            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                                <EmptyState
                                    icon={<Sparkles className="w-10 h-10" />}
                                    heading="Ready to Compare"
                                    description="Fill in both inputs to start the AI-powered competency analysis."
                                />
                            </motion.div>
                        )}

                        {analyzing && (
                            <motion.div
                                key="loading"
                                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                className="flex-1 glass-card flex flex-col items-center justify-center p-12 bg-white/80"
                            >
                                <div className="relative">
                                    <BrainCircuit className="w-16 h-16 text-primary-500 animate-pulse" />
                                    <div className="absolute inset-0 w-16 h-16 border-4 border-primary-500 rounded-full animate-ping opacity-10" />
                                </div>
                                <p className="mt-8 text-primary-600 font-black uppercase tracking-[0.2em] text-xs">Deep Mapping Skills...</p>
                            </motion.div>
                        )}

                        {gaps && (
                            <motion.div
                                key="results"
                                initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
                                className="space-y-6"
                            >
                                <div className="glass-card bg-amber-50/50 border-amber-200 p-8 shadow-sm">
                                    <h3 className="flex items-center gap-2 text-amber-700 font-black uppercase tracking-widest text-xs mb-6">
                                        <AlertCircle className="w-5 h-5" /> Missing Skills
                                    </h3>
                                    <div className="flex flex-wrap gap-2">
                                        {gaps.missing_skills.length > 0 ? gaps.missing_skills.map((skill: string, i: number) => (
                                            <span key={i} className="bg-white text-amber-900 px-4 py-2 rounded-xl text-sm font-bold border border-amber-200 shadow-sm">
                                                {skill}
                                            </span>
                                        )) : <p className="text-sm font-bold text-emerald-600 flex items-center gap-2 bg-emerald-50 px-4 py-2 rounded-lg border border-emerald-100">
                                            <CheckCircle2 className="w-4 h-4" /> No major gaps identified.</p>}
                                    </div>
                                </div>

                                <div className="glass-card bg-primary-50/50 border-primary-100 p-8 shadow-sm">
                                    <h3 className="flex items-center gap-2 text-primary-700 font-black uppercase tracking-widest text-xs mb-6">
                                        <CheckCircle2 className="w-5 h-5" /> Recommended Learning
                                    </h3>
                                    <div className="space-y-3">
                                        {gaps.recommended.map((item: string, i: number) => (
                                            <div key={i} className="flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-100 hover:border-primary-200 hover:shadow-md transition-all group">
                                                <div className="w-6 h-6 rounded-full bg-primary-50 flex items-center justify-center group-hover:bg-primary-100 transition-colors">
                                                    <ChevronRight className="w-4 h-4 text-primary-500" />
                                                </div>
                                                <span className="text-sm font-semibold text-slate-700">{item}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    );
};

export default SkillGap;
