import React, { useEffect, useState } from 'react';
import { jobsApi, resumesApi } from '../../api';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import ReactDOM from 'react-dom';
import {
    Briefcase, MapPin, Calendar, CheckCircle, ExternalLink, ArrowRight,
    Building2, Clock, Bot, Sparkles, ChevronRight, X, FileText, Loader2,
    Users, Send
} from 'lucide-react';

interface AppliedJob {
    job_id: string;
    title: string;
    company: string;
    location: string;
    posted_date: string;
    resume_id: string;
    applied_at: string;
    applied_status: string;
}

// ── Candidate JD modal ────────────────────────────────────────────────────

interface JDModalProps {
    jobId: string;
    resumeId: string;
    onClose: () => void;
    onApplied: () => void;
}

const CandidateJDModal: React.FC<JDModalProps> = ({ jobId, resumeId, onClose, onApplied }) => {
    const [job, setJob] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [applying, setApplying] = useState(false);
    const [applied, setApplied] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        jobsApi.get(jobId)
            .then(r => setJob(r.data))
            .catch(() => setError('Failed to load job details.'))
            .finally(() => setLoading(false));
    }, [jobId]);

    const handleApply = async () => {
        setApplying(true);
        setError('');
        try {
            await jobsApi.apply(jobId, resumeId);
            setApplied(true);
            onApplied();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Failed to apply. Please try again.');
        } finally {
            setApplying(false);
        }
    };

    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl relative z-10 flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="p-6 border-b border-slate-100 flex items-start justify-between">
                    {loading ? (
                        <div className="flex items-center gap-3 text-slate-400">
                            <Loader2 size={18} className="animate-spin" /> Loading…
                        </div>
                    ) : job ? (
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-violet-50 rounded-xl flex items-center justify-center text-violet-600">
                                <Briefcase size={20} />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-slate-900">{job.title}</h2>
                                <p className="text-sm text-slate-500">{job.employer_name}</p>
                            </div>
                        </div>
                    ) : null}
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors ml-auto">
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="overflow-y-auto flex-1 p-6 space-y-5">
                    {loading && (
                        <div className="flex justify-center py-12">
                            <Loader2 size={28} className="animate-spin text-violet-400" />
                        </div>
                    )}
                    {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3 border border-red-200">{error}</p>}
                    {job && !loading && (
                        <>
                            {/* Matched resume */}
                            <div className="flex items-center gap-2 px-4 py-2.5 bg-violet-50 rounded-xl border border-violet-200 text-sm">
                                <Bot size={14} className="text-violet-600 shrink-0" />
                                <span className="text-violet-700 font-semibold">AI Shortlisted with resume:</span>
                                <span className="font-mono text-xs text-slate-600 truncate">{resumeId}</span>
                            </div>

                            {/* Meta */}
                            <div className="flex flex-wrap gap-3 text-sm text-slate-500">
                                {job.location_name && (
                                    <span className="flex items-center gap-1.5"><MapPin size={13} /> {job.location_name}</span>
                                )}
                                {job.employment_type && (
                                    <span className="flex items-center gap-1.5"><Briefcase size={13} /> {job.employment_type.replace('_', ' ')}</span>
                                )}
                                {job.job_level && (
                                    <span className="bg-slate-100 text-slate-600 text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wider">{job.job_level}</span>
                                )}
                                {job.positions > 1 && (
                                    <span className="flex items-center gap-1 bg-blue-50 text-blue-600 text-xs font-bold px-2 py-0.5 rounded border border-blue-100">
                                        <Users size={11} /> {job.positions} positions
                                    </span>
                                )}
                            </div>

                            {/* Skills */}
                            {job.skills_required?.length > 0 && (
                                <div>
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Required Skills</p>
                                    <div className="flex flex-wrap gap-2">
                                        {job.skills_required.map((s: string) => (
                                            <span key={s} className="bg-slate-100 text-slate-700 text-xs font-medium px-2.5 py-1 rounded-lg">{s}</span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Description */}
                            {job.description && (
                                <div>
                                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Job Description</p>
                                    <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{job.description}</p>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer */}
                {job && !loading && (
                    <div className="p-5 border-t border-slate-100 flex items-center justify-between gap-3">
                        <p className="text-xs text-slate-400">
                            Applying with <span className="font-mono font-semibold text-slate-600">{resumeId}</span>
                        </p>
                        {applied ? (
                            <span className="flex items-center gap-2 text-sm font-bold text-emerald-600">
                                <CheckCircle size={16} /> Applied!
                            </span>
                        ) : (
                            <button
                                onClick={handleApply}
                                disabled={applying}
                                className="flex items-center gap-2 px-5 py-2.5 bg-violet-600 text-white text-sm font-bold rounded-xl hover:bg-violet-700 disabled:opacity-60 transition-all"
                            >
                                {applying ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                                {applying ? 'Applying…' : 'Apply Now'}
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
};

// ── Main page ─────────────────────────────────────────────────────────────

const MyApplications: React.FC = () => {
    const [allRecords, setAllRecords] = useState<AppliedJob[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedShortlist, setSelectedShortlist] = useState<AppliedJob | null>(null);

    useEffect(() => {
        const fetchApplied = async () => {
            try {
                const response = await jobsApi.getAppliedJobs();
                setAllRecords(response.data);
            } catch (err) {
                console.error('Failed to fetch applied jobs', err);
            } finally {
                setLoading(false);
            }
        };
        fetchApplied();
    }, []);

    const appliedJobIds = new Set(
        allRecords.filter(j => j.applied_status !== 'auto_shortlisted').map(j => j.job_id)
    );
    const shortlisted = allRecords.filter(
        j => j.applied_status === 'auto_shortlisted' && !appliedJobIds.has(j.job_id)
    );
    const jobs = allRecords.filter(j => j.applied_status !== 'auto_shortlisted');

    const handleApplied = () => {
        // Re-fetch to reflect the new applied record
        jobsApi.getAppliedJobs().then(r => setAllRecords(r.data)).catch(() => {});
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-96 space-y-4">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <div className="text-slate-500 font-medium animate-pulse">Loading your applications...</div>
            </div>
        );
    }

    if (allRecords.length === 0) {
        return (
            <div className="max-w-xl mx-auto mt-20 text-center space-y-6 p-8 glass-card border-dashed border-slate-200">
                <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mx-auto text-slate-300">
                    <Briefcase size={40} />
                </div>
                <div className="space-y-2">
                    <h2 className="text-3xl font-black text-slate-900">No Applications Yet</h2>
                    <p className="text-slate-500">Explore jobs and apply to start building your application history. Your future career starts here.</p>
                </div>
                <Link
                    to="/search"
                    className="inline-flex items-center gap-2 bg-blue-600 text-white px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 active:scale-95"
                >
                    Find Jobs <ArrowRight size={18} />
                </Link>
            </div>
        );
    }

    return (
        <>
        <div className="max-w-6xl mx-auto p-4 md:p-8 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="space-y-2">
                <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">My <span className="text-blue-600">Applications</span></h1>
                <p className="text-slate-500 font-medium">
                    {jobs.length > 0 && `${jobs.length} application${jobs.length !== 1 ? 's' : ''}`}
                    {jobs.length > 0 && shortlisted.length > 0 && ' · '}
                    {shortlisted.length > 0 && `${shortlisted.length} shortlisted by AI`}
                </p>
            </div>

            {/* ── AI Shortlisted ── */}
            {shortlisted.length > 0 && (
                <div className="space-y-4">
                    <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-violet-100 flex items-center justify-center">
                            <Bot size={14} className="text-violet-600" />
                        </div>
                        <h2 className="text-lg font-bold text-slate-800">Shortlisted for You</h2>
                        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200">
                            {shortlisted.length} match{shortlisted.length !== 1 ? 'es' : ''}
                        </span>
                        <span className="text-xs text-slate-400 font-medium ml-1">— discovered by the AI Recruiter</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {shortlisted.map((job, idx) => (
                            <motion.div
                                key={`${job.job_id}-${idx}`}
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: idx * 0.06 }}
                                className="relative bg-gradient-to-br from-violet-50 to-white border border-violet-200 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-violet-300 transition-all group cursor-pointer"
                                onClick={() => setSelectedShortlist(job)}
                            >
                                <div className="absolute top-3 right-3">
                                    <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200">
                                        <Sparkles size={9} /> AI Match
                                    </span>
                                </div>
                                <div className="space-y-2 pr-16">
                                    <div>
                                        <p className="font-bold text-slate-900 text-sm leading-tight">{job.title}</p>
                                        <p className="text-xs font-semibold text-violet-700 mt-0.5">{job.company}</p>
                                    </div>
                                    {job.location && (
                                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                            <MapPin size={11} className="text-slate-400" /> {job.location}
                                        </div>
                                    )}
                                    {job.resume_id && (
                                        <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
                                            <FileText size={11} className="shrink-0" />
                                            <span className="truncate font-mono">{job.resume_id}</span>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-4 flex items-center justify-between">
                                    <span className="text-[10px] text-slate-400">
                                        {job.applied_at ? new Date(job.applied_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''}
                                    </span>
                                    <span className="flex items-center gap-1 text-xs font-bold text-violet-600 group-hover:text-violet-800 transition-colors">
                                        View & Apply <ChevronRight size={13} />
                                    </span>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            )}

            {/* ── Applied Jobs ── */}
            {jobs.length > 0 && (
            <div className="space-y-4">
            {shortlisted.length > 0 && (
                <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center">
                        <Briefcase size={14} className="text-blue-600" />
                    </div>
                    <h2 className="text-lg font-bold text-slate-800">My Applications</h2>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                        {jobs.length}
                    </span>
                </div>
            )}

            {/* Desktop Table View */}
            <div className="hidden md:block glass-card overflow-hidden border-slate-200 shadow-xl bg-white/80 backdrop-blur-xl">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-slate-50/50 border-b border-slate-100">
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Job Position</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Company</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Applied Date</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Status</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {jobs.map((job, idx) => (
                            <motion.tr
                                key={job.job_id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: idx * 0.05 }}
                                className="hover:bg-blue-50/30 transition-colors group"
                            >
                                <td className="px-6 py-6">
                                    <div className="space-y-1">
                                        <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">{job.title}</div>
                                        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                                            <MapPin size={12} /> {job.location || 'Remote'}
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-6">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-white group-hover:text-blue-500 transition-all border border-transparent group-hover:border-blue-100">
                                            <Building2 size={16} />
                                        </div>
                                        <span className="font-bold text-slate-700">{job.company}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-6">
                                    <div className="flex items-center gap-2 text-sm text-slate-500 font-semibold">
                                        <Calendar size={14} className="text-slate-300" />
                                        {new Date(job.applied_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                    </div>
                                </td>
                                <td className="px-6 py-6 font-medium">
                                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${job.applied_status === 'applied'
                                            ? 'bg-emerald-50 text-emerald-600 border-emerald-100'
                                            : 'bg-blue-50 text-blue-600 border-blue-100'
                                        }`}>
                                        <CheckCircle size={10} /> {job.applied_status}
                                    </span>
                                </td>
                                <td className="px-6 py-6 text-right">
                                    <Link
                                        to="/search"
                                        className="inline-flex items-center gap-1 text-xs font-black text-slate-400 hover:text-blue-600 uppercase tracking-widest transition-all"
                                    >
                                        Find Jobs <ExternalLink size={14} />
                                    </Link>
                                </td>
                            </motion.tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Mobile Card View */}
            <div className="md:hidden space-y-4">
                {jobs.map((job) => (
                    <motion.div
                        key={job.job_id}
                        className="glass-card p-6 bg-white border-slate-200 space-y-4"
                        whileHover={{ scale: 1.01 }}
                    >
                        <div className="flex justify-between items-start">
                            <div className="space-y-1">
                                <h3 className="text-xl font-bold text-slate-900">{job.title}</h3>
                                <p className="text-sm font-bold text-blue-600">{job.company}</p>
                            </div>
                            <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100 text-[10px] font-black uppercase tracking-widest">
                                {job.applied_status}
                            </span>
                        </div>

                        <div className="grid grid-cols-2 gap-4 pt-2">
                            <div className="flex items-center gap-2 text-xs text-slate-500 font-bold uppercase tracking-wider">
                                <MapPin size={14} className="text-slate-300" /> {job.location || 'Remote'}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-slate-500 font-bold uppercase tracking-wider">
                                <Clock size={14} className="text-slate-300" /> {new Date(job.applied_at).toLocaleDateString()}
                            </div>
                        </div>

                        <Link
                            to="/search"
                            className="w-full inline-flex items-center justify-center gap-2 bg-slate-50 border border-slate-200 text-slate-600 py-3 rounded-xl font-black text-xs uppercase tracking-widest hover:bg-slate-100 transition-all"
                        >
                            Find More Jobs <ArrowRight size={14} />
                        </Link>
                    </motion.div>
                ))}
            </div>
            </div>
            )}
        </div>

        {selectedShortlist && (
            <CandidateJDModal
                jobId={selectedShortlist.job_id}
                resumeId={selectedShortlist.resume_id}
                onClose={() => setSelectedShortlist(null)}
                onApplied={() => { handleApplied(); setSelectedShortlist(null); }}
            />
        )}
        </>
    );
};

export default MyApplications;

