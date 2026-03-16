import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
    FileText, Download, Trash2, Search, X, Loader2, Sparkles,
    CheckCircle, AlertCircle, XCircle, Shield, Eye,
    ChevronLeft, ChevronRight, Building2, MapPin, Send, Star,
    Mail, Phone, ExternalLink, Briefcase, SlidersHorizontal,
    ChevronDown, ChevronUp, Target, Users, Calendar, Tag,
} from 'lucide-react';
import { resumesApi, matchApi, jobsApi } from '../../api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface ResumeRecord {
    filename: string;
    user_id: string;
    classification: string | null;
    total_score: number | null;
    scores: Record<string, number>;
    uploaded_at: string | null;
    industry?: string | null;
    role?: string | null;
    exp_level?: string | null;
    candidate_name?: string | null;
    current_company?: string | null;
    location?: string | null;
    phone?: string | null;
    skills?: Array<{ name: string; level?: string | null } | string> | null;
    apply_count?: number | null;
    shortlist_count?: number | null;
    email?: string | null;
    linkedin_url?: string | null;
    github_url?: string | null;
    summary?: string | null;
    years_experience?: string | null;
    education?: string | null;
    certifications?: string[] | null;
    _initials?: string;
    _avatarHue?: number;
    _scorePercent?: number | null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function metaQualityScore(r: ResumeRecord): number {
    const fields = [
        !!r.candidate_name, !!r.email, !!r.phone, !!r.location,
        !!r.role, !!r.summary, !!(r.skills && r.skills.length >= 3),
        !!r.education, !!r.years_experience,
    ];
    return Math.round((fields.filter(Boolean).length / fields.length) * 100);
}

function enrichRecord(r: ResumeRecord): ResumeRecord {
    const label = r.candidate_name || r.filename;
    return {
        ...r,
        _initials: label.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() ?? '').join(''),
        _avatarHue: label.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 360,
        _scorePercent: r.total_score != null
            ? Math.round((r.total_score / 30) * 100)
            : metaQualityScore(r),
    };
}

const CLASSIFICATION_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    resume_valid_strong:       { label: 'Strong',     color: 'bg-green-50 text-green-700 border-green-200',   icon: <CheckCircle size={11} /> },
    resume_valid_good:         { label: 'Good',       color: 'bg-blue-50 text-blue-700 border-blue-200',      icon: <CheckCircle size={11} /> },
    resume_valid_but_weak:     { label: 'Weak',       color: 'bg-yellow-50 text-yellow-700 border-yellow-200', icon: <AlertCircle size={11} /> },
    resume_invalid_or_incomplete: { label: 'Incomplete', color: 'bg-red-50 text-red-600 border-red-200',      icon: <XCircle size={11} /> },
    not_resume:                { label: 'Not a Resume', color: 'bg-slate-100 text-slate-500 border-slate-200', icon: <Shield size={11} /> },
};

const EXP_LEVEL_STYLE: Record<string, string> = {
    Executive:   'bg-purple-100 text-purple-800 border-purple-300',
    Lead:        'bg-indigo-100 text-indigo-800 border-indigo-300',
    Senior:      'bg-blue-100   text-blue-800   border-blue-300',
    'Mid-level': 'bg-teal-100   text-teal-800   border-teal-300',
    Junior:      'bg-green-100  text-green-800  border-green-300',
    Entry:       'bg-slate-100  text-slate-600  border-slate-300',
};

type SkillEntry = { name: string; level?: string | null } | string;
const skillName  = (s: SkillEntry): string => (typeof s === 'string' ? s : s.name);
const skillLevel = (s: SkillEntry): string | null => (typeof s === 'string' ? null : (s.level ?? null));

const LEVEL_STYLE: Record<string, string> = {
    Expert:       'bg-green-50  text-green-700  border-green-200',
    Advanced:     'bg-blue-50   text-blue-700   border-blue-200',
    Intermediate: 'bg-amber-50  text-amber-700  border-amber-200',
    Beginner:     'bg-slate-100 text-slate-600  border-slate-200',
};
const LEVEL_ABBR: Record<string, string> = { Expert: 'E', Advanced: 'A', Intermediate: 'I', Beginner: 'B' };
const LEVEL_RANK: Record<string, number> = { Expert: 4, Advanced: 3, Intermediate: 2, Beginner: 1 };

function sortedSkills(skills: SkillEntry[]): SkillEntry[] {
    return [...skills].sort((a, b) => (LEVEL_RANK[skillLevel(b) ?? ''] ?? 0) - (LEVEL_RANK[skillLevel(a) ?? ''] ?? 0));
}

const SkillChip: React.FC<{ skill: SkillEntry }> = ({ skill }) => {
    const name  = skillName(skill);
    const level = skillLevel(skill);
    const abbr  = level ? LEVEL_ABBR[level] : null;
    const style = level ? (LEVEL_STYLE[level] ?? 'bg-purple-50 text-purple-700 border-purple-100') : 'bg-purple-50 text-purple-700 border-purple-100';
    return (
        <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border text-[11px] font-medium whitespace-nowrap ${style}`}>
            {name}{abbr && <span className="opacity-60 font-bold">({abbr})</span>}
        </span>
    );
};

// ─── Job Match Modal ──────────────────────────────────────────────────────────

const ResumeJobMatchModal: React.FC<{ resume: ResumeRecord; onClose: () => void }> = ({ resume, onClose }) => {
    const [jobs, setJobs]       = useState<{ score: number; job: any }[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState<string | null>(null);
    const [minMatch, setMinMatch] = useState(30);
    const [shortlisted, setShortlisted]   = useState<Set<string>>(new Set());
    const [shortlisting, setShortlisting] = useState<Set<string>>(new Set());

    const handleShortlist = async (jobId: string) => {
        if (shortlisted.has(jobId)) return;
        setShortlisting(prev => new Set(prev).add(jobId));
        try {
            await jobsApi.shortlistCandidate(jobId, resume.filename, resume.user_id ?? '');
            setShortlisted(prev => new Set(prev).add(jobId));
        } finally {
            setShortlisting(prev => { const s = new Set(prev); s.delete(jobId); return s; });
        }
    };

    useEffect(() => {
        const query = [resume.role, ...(resume.skills?.slice(0, 3).map(s => typeof s === 'string' ? s : s.name) ?? [])].filter(Boolean).join(' ');
        matchApi.searchJobs(query, 20)
            .then(res => setJobs(res.data ?? []))
            .catch(() => setError('Failed to load matching jobs.'))
            .finally(() => setLoading(false));
    }, [resume.filename]);

    const scoreColor = (s: number) =>
        s >= 0.75 ? 'bg-green-50 text-green-700 border-green-200'
        : s >= 0.5 ? 'bg-blue-50 text-blue-700 border-blue-200'
        : s >= 0.3 ? 'bg-amber-50 text-amber-700 border-amber-200'
        :            'bg-slate-100 text-slate-500 border-slate-200';

    const filtered = jobs.filter(({ score }) => Math.round(score * 100) >= minMatch);

    return createPortal(
        <div className="fixed inset-0 z-[9999] bg-black/40 flex items-start justify-center pt-[8vh] px-4 pb-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-[32rem] max-w-[95vw] max-h-[84vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-start justify-between px-5 py-4 border-b border-slate-100 shrink-0">
                    <div>
                        <div className="flex items-center gap-2">
                            <Briefcase size={15} className="text-purple-500" />
                            <span className="font-bold text-slate-800 text-sm">Matching Jobs</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5">{resume.candidate_name || resume.filename} · {resume.role || 'Unknown role'}</p>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600 mt-0.5"><X size={15} /></button>
                </div>

                <div className="px-5 py-3 border-b border-slate-100 shrink-0 bg-slate-50/60">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[11px] font-semibold text-slate-500">Min match</span>
                        <span className={`text-[11px] font-bold px-2 py-0.5 rounded border w-12 text-center tabular-nums ${scoreColor(minMatch / 100)}`}>{minMatch}%</span>
                    </div>
                    <input type="range" min={0} max={90} step={5} value={minMatch} onChange={e => setMinMatch(Number(e.target.value))} className="w-full h-1.5 rounded-full accent-purple-500 cursor-pointer" />
                    <div className="flex justify-between text-[10px] text-slate-300 mt-0.5"><span>0%</span><span>90%</span></div>
                </div>

                <div className="overflow-y-auto flex-1 px-4 py-3 space-y-2">
                    {loading && <div className="flex justify-center py-10"><Loader2 size={20} className="animate-spin text-purple-400" /></div>}
                    {error   && <p className="text-sm text-red-500 text-center py-8">{error}</p>}
                    {!loading && !error && filtered.length === 0 && (
                        <p className="text-sm text-slate-400 text-center py-8">
                            {jobs.length === 0 ? 'No matching jobs found.' : `No jobs above ${minMatch}% match.`}
                        </p>
                    )}
                    {!loading && !error && filtered.map(({ score, job }, i) => (
                        <div key={job.job_id ?? i} className="p-3.5 rounded-xl border border-slate-100 hover:border-purple-100 hover:bg-purple-50/20 transition-colors space-y-2">
                            <div className="flex items-start justify-between gap-2">
                                <p className="font-bold text-slate-900 text-sm leading-snug line-clamp-1 flex-1">{job.title}</p>
                                <span className={`shrink-0 text-[11px] font-bold px-2 py-0.5 rounded border ${scoreColor(score)}`}>{Math.round(score * 100)}%</span>
                            </div>
                            {job.description && <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">{job.description}</p>}
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400">
                                {job.location_name && <span className="flex items-center gap-1"><MapPin size={10} className="shrink-0" />{job.location_name}</span>}
                                {job.job_level && <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">{job.job_level}</span>}
                            </div>
                            {job.skills_required?.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                    {job.skills_required.slice(0, 4).map((s: string) => (
                                        <span key={s} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 border border-slate-200">{s}</span>
                                    ))}
                                    {job.skills_required.length > 4 && <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400">+{job.skills_required.length - 4}</span>}
                                </div>
                            )}
                            <div className="flex items-center gap-1.5 pt-0.5">
                                {shortlisted.has(job.job_id) ? (
                                    <button disabled className="flex-1 px-2 py-1.5 bg-green-50 text-green-700 rounded-lg text-[11px] font-bold flex items-center justify-center gap-1 border border-green-200 cursor-default">
                                        <CheckCircle size={11} /> Shortlisted
                                    </button>
                                ) : (
                                    <button onClick={() => handleShortlist(job.job_id)} disabled={shortlisting.has(job.job_id)} className="flex-1 px-2 py-1.5 bg-amber-50 text-amber-600 rounded-lg text-[11px] font-bold flex items-center justify-center gap-1 hover:bg-amber-100 transition-colors border border-amber-100/50 disabled:opacity-50">
                                        {shortlisting.has(job.job_id) ? <Loader2 size={11} className="animate-spin" /> : <Star size={11} />} Shortlist
                                    </button>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {!loading && !error && jobs.length > 0 && (
                    <div className="px-5 py-2.5 border-t border-slate-100 shrink-0 bg-slate-50/60">
                        <p className="text-[11px] text-slate-400 text-center">
                            Showing <span className="font-semibold text-slate-600">{filtered.length}</span> of <span className="font-semibold text-slate-600">{jobs.length}</span> jobs
                        </p>
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
};

// ─── Preview Modal ────────────────────────────────────────────────────────────

interface PreviewModalProps {
    resume: ResumeRecord;
    resumes: ResumeRecord[];
    onClose: () => void;
    onNavigate: (resume: ResumeRecord) => void;
    onDownload: (filename: string, e: React.MouseEvent) => void;
    onDelete: (filename: string, e: React.MouseEvent) => void;
}

const PreviewModal: React.FC<PreviewModalProps> = ({ resume, resumes, onClose, onNavigate, onDownload, onDelete }) => {
    const [blobUrl, setBlobUrl]               = useState<string | null>(null);
    const [extractedText, setExtractedText]   = useState<string | null>(null);
    const [loading, setLoading]               = useState(true);
    const [error, setError]                   = useState(false);
    const currentIndex = resumes.findIndex(r => r.filename === resume.filename);
    const isPdf        = resume.filename.toLowerCase().endsWith('.pdf');
    const meta         = resume.classification ? CLASSIFICATION_META[resume.classification] : null;

    useEffect(() => {
        setError(false); setBlobUrl(null); setExtractedText(null);
        if (isPdf) {
            setBlobUrl(resumesApi.previewUrl(resume.filename));
            setLoading(false);
        } else {
            setLoading(true);
            resumesApi.getText(resume.filename)
                .then(res => setExtractedText(res.data?.text || ''))
                .catch(() => setError(true))
                .finally(() => setLoading(false));
        }
    }, [resume.filename]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
            if (e.key === 'ArrowLeft'  && currentIndex > 0)                   onNavigate(resumes[currentIndex - 1]);
            if (e.key === 'ArrowRight' && currentIndex < resumes.length - 1)  onNavigate(resumes[currentIndex + 1]);
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [currentIndex, resumes, onClose, onNavigate]);

    const sbLabel    = resume.candidate_name || resume.filename;
    const sbInitials = sbLabel.split(/\s+/).slice(0, 2).map(w => w[0]?.toUpperCase() ?? '').join('');
    const sbHue      = sbLabel.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 360;

    return createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl mx-4 flex flex-col overflow-hidden" style={{ height: '90vh' }} onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-100 shrink-0">
                    <div className="w-9 h-9 bg-purple-50 rounded-lg flex items-center justify-center text-purple-500 shrink-0"><FileText size={18} /></div>
                    <div className="flex-1 min-w-0">
                        <p className="font-bold text-slate-900 truncate">{resume.candidate_name || resume.filename.replace(/\.[^.]+$/, '')}</p>
                        <p className="text-xs text-slate-400 truncate">{resume.filename}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                        {meta && <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${meta.color}`}>{meta.icon} {meta.label}</span>}
                        <button onClick={e => onDownload(resume.filename, e)} className="p-2 text-slate-400 hover:text-blue-500 transition-colors rounded-lg hover:bg-blue-50" title="Download"><Download size={16} /></button>
                        <button onClick={e => { onDelete(resume.filename, e); onClose(); }} className="p-2 text-slate-400 hover:text-red-500 transition-colors rounded-lg hover:bg-red-50" title="Delete"><Trash2 size={16} /></button>
                        <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-700 transition-colors rounded-lg hover:bg-slate-100"><X size={18} /></button>
                    </div>
                </div>

                {/* Body */}
                <div className="flex flex-1 overflow-hidden">
                    {/* Sidebar */}
                    <div className="w-64 shrink-0 border-r border-slate-100 flex flex-col overflow-y-auto bg-slate-50/60">
                        <div className="px-5 py-5 border-b border-slate-100 flex items-center gap-3">
                            <div className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0" style={{ background: `hsl(${sbHue},55%,52%)` }}>{sbInitials}</div>
                            <div className="min-w-0">
                                <p className="font-bold text-slate-800 text-sm leading-tight truncate">{resume.candidate_name || resume.filename.replace(/\.[^.]+$/, '')}</p>
                                {resume.exp_level && <span className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full border font-semibold ${EXP_LEVEL_STYLE[resume.exp_level] ?? 'bg-slate-100 text-slate-600 border-slate-300'}`}>{resume.exp_level}</span>}
                            </div>
                        </div>
                        {resume.summary && (
                            <div className="px-5 py-4 border-b border-slate-100">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Summary</p>
                                <p className="text-[12px] text-slate-600 leading-relaxed">{resume.summary}</p>
                            </div>
                        )}
                        <div className="px-5 py-4 space-y-3 border-b border-slate-100">
                            {resume.role && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Title</p><p className="text-sm font-semibold text-slate-700">{resume.role}</p></div>}
                            {resume.current_company && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Company</p><p className="text-sm text-slate-600 flex items-center gap-1.5"><Building2 size={12} className="text-slate-400 shrink-0" />{resume.current_company}</p></div>}
                            {resume.location && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Location</p><p className="text-sm text-slate-600 flex items-center gap-1.5"><MapPin size={12} className="text-slate-400 shrink-0" />{resume.location}</p></div>}
                            {resume.industry && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Industry</p><p className="text-sm text-slate-600">{resume.industry}</p></div>}
                        </div>
                        {(resume.phone || resume.email || resume.linkedin_url || resume.github_url) && (
                            <div className="px-5 py-4 border-b border-slate-100 space-y-2">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Contact</p>
                                {resume.phone && <a href={`tel:${resume.phone}`} className="flex items-center gap-2 text-[12px] text-slate-600 hover:text-purple-600 transition-colors group"><Phone size={12} className="text-slate-400 group-hover:text-purple-500 shrink-0" /><span className="truncate font-medium">{resume.phone}</span></a>}
                                {resume.email && <a href={`mailto:${resume.email}`} className="flex items-center gap-2 text-[12px] text-slate-600 hover:text-purple-600 transition-colors group"><Mail size={12} className="text-slate-400 group-hover:text-purple-500 shrink-0" /><span className="truncate">{resume.email}</span></a>}
                                {resume.linkedin_url && <a href={resume.linkedin_url.startsWith('http') ? resume.linkedin_url : `https://${resume.linkedin_url}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[12px] text-blue-600 hover:text-blue-800 transition-colors"><ExternalLink size={12} className="shrink-0" /><span className="truncate">{resume.linkedin_url.replace(/^https?:\/\//i,'').replace(/\/$/,'')}</span></a>}
                                {resume.github_url && <a href={resume.github_url.startsWith('http') ? resume.github_url : `https://${resume.github_url}`} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-[12px] text-slate-700 hover:text-slate-900 transition-colors"><ExternalLink size={12} className="shrink-0" /><span className="truncate">{resume.github_url.replace(/^https?:\/\//i,'').replace(/\/$/,'')}</span></a>}
                            </div>
                        )}
                        {(resume.education || resume.years_experience || (resume.certifications && resume.certifications.length > 0)) && (
                            <div className="px-5 py-4 border-b border-slate-100 space-y-3">
                                {resume.years_experience && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Experience</p><p className="text-sm font-semibold text-slate-700">{resume.years_experience} years</p></div>}
                                {resume.education && <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Education</p><p className="text-[12px] text-slate-600 leading-snug">{resume.education}</p></div>}
                                {resume.certifications && resume.certifications.length > 0 && (
                                    <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Certifications</p>
                                        <div className="flex flex-col gap-1">{resume.certifications.map(c => <span key={c} className="text-[11px] text-slate-600 flex items-start gap-1.5"><span className="mt-1 w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />{c}</span>)}</div>
                                    </div>
                                )}
                            </div>
                        )}
                        {resume.skills && resume.skills.length > 0 && (() => {
                            const sorted   = sortedSkills(resume.skills);
                            const priority = sorted.filter(s => ['Expert','Advanced'].includes(skillLevel(s) ?? ''));
                            const rest     = sorted.filter(s => !['Expert','Advanced'].includes(skillLevel(s) ?? ''));
                            return (
                                <div className="px-5 py-4 border-b border-slate-100">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Skills &amp; Expertise</p>
                                    <div className="flex flex-wrap gap-1.5">
                                        {[...priority, ...rest].map(s => {
                                            const name  = skillName(s);
                                            const level = skillLevel(s);
                                            const abbr  = level ? LEVEL_ABBR[level] : null;
                                            const style = level ? (LEVEL_STYLE[level] ?? 'bg-purple-50 text-purple-700 border-purple-100') : 'bg-slate-100 text-slate-600 border-slate-200';
                                            return <span key={name} className={`inline-flex items-center px-2 py-0.5 rounded border text-[12px] font-medium whitespace-nowrap ${style}`}>{name}{abbr && <span className="opacity-60 font-bold ml-1">({abbr})</span>}</span>;
                                        })}
                                    </div>
                                </div>
                            );
                        })()}
                        {resume.total_score != null && (
                            <div className="px-5 py-4 border-b border-slate-100">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Quality Score</p>
                                <div className="flex items-end gap-2">
                                    <span className="text-2xl font-black text-slate-800 leading-none">{Math.round((resume.total_score / 30) * 100)}%</span>
                                    <span className="text-xs text-slate-400 mb-0.5">{resume.total_score}/30</span>
                                </div>
                                <div className="mt-2 h-2 bg-slate-200 rounded-full overflow-hidden">
                                    <div className="h-full rounded-full bg-gradient-to-r from-purple-400 to-purple-600" style={{ width: `${Math.round((resume.total_score / 30) * 100)}%` }} />
                                </div>
                            </div>
                        )}
                        {resume.uploaded_at && (
                            <div className="px-5 py-3 mt-auto">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Uploaded</p>
                                <p className="text-xs text-slate-500">{new Date(resume.uploaded_at).toLocaleDateString()}</p>
                            </div>
                        )}
                    </div>

                    {/* Viewer */}
                    <div className="flex-1 bg-slate-50 relative overflow-hidden">
                        {loading && <div className="absolute inset-0 flex items-center justify-center"><Loader2 size={32} className="text-purple-400 animate-spin" /></div>}
                        {!loading && error && (
                            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-400">
                                <FileText size={40} />
                                <p className="text-sm">Preview unavailable</p>
                                <button onClick={e => onDownload(resume.filename, e)} className="text-purple-600 text-sm font-semibold hover:underline">Download instead</button>
                            </div>
                        )}
                        {!loading && !error && blobUrl && <iframe src={blobUrl} title={resume.filename} style={{ width: '100%', height: '100%', border: 'none', display: 'block' }} />}
                        {!loading && !error && extractedText !== null && (
                            <div className="absolute inset-0 overflow-y-auto p-6">
                                <pre className="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-relaxed">{extractedText || <span className="text-slate-300 italic">No text content found.</span>}</pre>
                            </div>
                        )}
                    </div>
                </div>

                {/* Navigation */}
                {resumes.length > 1 && (
                    <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 shrink-0">
                        <button onClick={() => currentIndex > 0 && onNavigate(resumes[currentIndex - 1])} disabled={currentIndex === 0} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                            <ChevronLeft size={16} /> Previous
                        </button>
                        <span className="text-xs text-slate-400">{currentIndex + 1} / {resumes.length}</span>
                        <button onClick={() => currentIndex < resumes.length - 1 && onNavigate(resumes[currentIndex + 1])} disabled={currentIndex === resumes.length - 1} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
                            Next <ChevronRight size={16} />
                        </button>
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
};

// ─── Main Component ───────────────────────────────────────────────────────────

const EXAMPLE_SEARCHES = [
    { label: 'ML Engineer · Silicon Valley', query: 'Machine learning engineer based in San Francisco or Bay Area with PyTorch, LLMs, MLOps, and experience at a top-tier tech company', icon: '🤖' },
    { label: 'Java Architect · FinTech', query: 'Senior Java architect with Spring Boot, Kafka, microservices, and 8+ years in financial services or banking systems', icon: '☕' },
    { label: 'Staff Engineer · Platform', query: 'Staff or principal engineer with Kubernetes, Go, distributed systems, and experience leading platform or infrastructure teams', icon: '🏗️' },
    { label: 'React Lead · NYC', query: 'Lead frontend engineer in New York with React, TypeScript, design systems, and experience at a Series B or later startup', icon: '⚡' },
    { label: 'Data Science · Healthcare', query: 'Data scientist with Python, R, clinical data analysis, and experience in healthcare, pharma, or life sciences', icon: '🧬' },
    { label: 'DevOps · AWS Expert', query: 'DevOps or SRE engineer with deep AWS expertise, Terraform, CI/CD pipelines, and strong incident management background', icon: '☁️' },
];

interface FilterOptions { industries: string[]; exp_levels: string[]; }

const CandidateSearch: React.FC = () => {
    const [query, setQuery]               = useState('');
    const [searching, setSearching]       = useState(false);
    const [resumes, setResumes]           = useState<ResumeRecord[]>([]);
    const [total, setTotal]               = useState(0);
    const [searched, setSearched]         = useState(false);
    const [error, setError]               = useState<string | null>(null);
    const [minScore, setMinScore]         = useState(0);
    const [showRefine, setShowRefine]     = useState(false);
    const [previewResume, setPreviewResume]   = useState<ResumeRecord | null>(null);
    const [jobMatchResume, setJobMatchResume] = useState<ResumeRecord | null>(null);

    // Refine filters
    const [topN, setTopN]               = useState(50);
    const [expLevel, setExpLevel]       = useState('');
    const [location, setLocation]       = useState('');
    const [industry, setIndustry]       = useState('');
    const [classification, setClassification] = useState('');
    const [dateRange, setDateRange]     = useState('');

    // Loaded filter options
    const [locationGroups, setLocationGroups] = useState<Record<string, { value: string; label: string }[]>>({});
    const [filterOptions, setFilterOptions]   = useState<FilterOptions>({ industries: [], exp_levels: [] });

    useEffect(() => {
        Promise.all([
            resumesApi.getLocations().catch(() => null),
            resumesApi.getFilterOptions().catch(() => null),
        ]).then(([locsRes, optsRes]) => {
            if (locsRes) setLocationGroups(locsRes.data.groups || {});
            if (optsRes) setFilterOptions(optsRes.data || { industries: [], exp_levels: [] });
        });
    }, []);

    const activeRefineCount = [expLevel, location, industry, classification, dateRange].filter(Boolean).length;

    const clearRefine = () => {
        setExpLevel(''); setLocation(''); setIndustry('');
        setClassification(''); setDateRange(''); setTopN(50);
    };

    const runSearch = async () => {
        if (!query.trim()) return;
        setSearching(true);
        setError(null);
        setMinScore(0);
        try {
            const params: Record<string, any> = { search: query.trim(), limit: topN };
            if (expLevel)       params.exp_level     = expLevel;
            if (location)       params.location      = location;
            if (industry)       params.industry      = industry;
            if (classification) params.classification = classification;
            if (dateRange)      params.date_range    = parseInt(dateRange);
            const res = await resumesApi.database(params);
            const data = res.data;
            setResumes((data.resumes || []).map(enrichRecord));
            setTotal(data.total || 0);
            setSearched(true);
        } catch (err: any) {
            const msg = err.response?.data?.detail || err.message || 'Search failed.';
            setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setSearching(false);
        }
    };

    const handleSearch = (e: React.FormEvent) => { e.preventDefault(); runSearch(); };

    const handleDelete = async (filename: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return;
        try {
            await resumesApi.delete(filename);
            setResumes(prev => prev.filter(r => r.filename !== filename));
            setTotal(prev => prev - 1);
        } catch (err) { console.error('Delete failed', err); }
    };

    const handleDownload = async (filename: string, e: React.MouseEvent) => {
        e.stopPropagation();
        try {
            const res = await resumesApi.download(filename);
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
            window.URL.revokeObjectURL(url);
        } catch (err) { console.error('Download failed', err); }
    };

    const filteredResumes = minScore > 0
        ? resumes.filter(r => (r._scorePercent ?? 0) >= minScore)
        : resumes;

    const selectCls = 'px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-purple-200 text-slate-600';

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            {/* Header */}
            <div className="space-y-1">
                <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Candidate Search</h1>
                <p className="text-sm text-slate-500">Describe the role, skills, or experience you need — AI ranks candidates by semantic relevance.</p>
            </div>

            {/* Search card */}
            <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-4 space-y-3">
                {/* Search bar */}
                <form onSubmit={handleSearch} className="flex gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" size={16} />
                        <input
                            type="text"
                            placeholder="e.g. Senior Backend Engineer with Python and AWS experience..."
                            className="w-full pl-9 pr-8 py-2.5 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-purple-200 focus:border-purple-400 transition-all"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                        />
                        {query && (
                            <button type="button" onClick={() => { setQuery(''); setResumes([]); setSearched(false); }} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                                <X size={14} />
                            </button>
                        )}
                    </div>
                    <button
                        type="button"
                        onClick={() => setShowRefine(v => !v)}
                        className={`px-3 py-2.5 text-sm font-semibold rounded-lg border transition-all flex items-center gap-1.5 shrink-0 ${showRefine || activeRefineCount > 0 ? 'bg-purple-50 border-purple-300 text-purple-700' : 'bg-white border-slate-200 text-slate-500 hover:border-slate-300'}`}
                        title="Refine search"
                    >
                        <SlidersHorizontal size={14} />
                        {activeRefineCount > 0 && <span className="bg-purple-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">{activeRefineCount}</span>}
                        {showRefine ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                    </button>
                    <button
                        type="submit"
                        disabled={searching || !query.trim()}
                        className="px-5 py-2.5 bg-slate-900 text-white text-sm font-semibold rounded-lg hover:bg-slate-800 transition-all disabled:opacity-50 flex items-center gap-2 shrink-0"
                    >
                        {searching ? <><Loader2 size={14} className="animate-spin" /> Searching...</> : 'Search'}
                    </button>
                </form>

                {/* Example searches */}
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-slate-400 font-medium shrink-0">Try:</span>
                    {EXAMPLE_SEARCHES.map(ex => (
                        <button
                            key={ex.label}
                            type="button"
                            onClick={() => setQuery(ex.query)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-[11px] font-medium text-slate-600 hover:border-purple-300 hover:text-purple-700 hover:bg-purple-50 transition-all"
                        >
                            <span>{ex.icon}</span>{ex.label}
                        </button>
                    ))}
                </div>

                {/* ── Refine panel ── */}
                {showRefine && (
                    <div className="pt-3 border-t border-slate-100 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                                <SlidersHorizontal size={11} /> Refine Search
                            </span>
                            {activeRefineCount > 0 && (
                                <button onClick={clearRefine} className="text-[11px] text-slate-400 hover:text-red-500 flex items-center gap-1 transition-colors">
                                    <X size={11} /> Clear filters
                                </button>
                            )}
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                            {/* Result limit */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <Users size={10} /> Top Results
                                </label>
                                <div className="flex gap-1">
                                    {[10, 25, 50, 100].map(n => (
                                        <button
                                            key={n}
                                            type="button"
                                            onClick={() => setTopN(n)}
                                            className={`flex-1 py-1 text-[11px] font-semibold rounded border transition-all ${topN === n ? 'bg-purple-600 text-white border-purple-600' : 'bg-white text-slate-500 border-slate-200 hover:border-purple-300 hover:text-purple-600'}`}
                                        >
                                            {n}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Experience level */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <Target size={10} /> Experience Level
                                </label>
                                <select value={expLevel} onChange={e => setExpLevel(e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Any Level</option>
                                    {filterOptions.exp_levels.map(l => <option key={l} value={l}>{l}</option>)}
                                </select>
                            </div>

                            {/* Industry */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <Tag size={10} /> Industry
                                </label>
                                <select value={industry} onChange={e => setIndustry(e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Any Industry</option>
                                    {filterOptions.industries.map(i => <option key={i} value={i}>{i}</option>)}
                                </select>
                            </div>

                            {/* Location */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <MapPin size={10} /> Location
                                </label>
                                <select value={location} onChange={e => setLocation(e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Any Location</option>
                                    {Object.entries(locationGroups).map(([region, locs]) => (
                                        <optgroup key={region} label={region}>
                                            {locs.map(loc => <option key={loc.value} value={loc.value}>{loc.label}</option>)}
                                        </optgroup>
                                    ))}
                                </select>
                            </div>

                            {/* Resume quality */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <CheckCircle size={10} /> Resume Quality
                                </label>
                                <select value={classification} onChange={e => setClassification(e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Any Quality</option>
                                    <option value="resume_valid_strong">Strong</option>
                                    <option value="resume_valid_good">Good</option>
                                    <option value="resume_valid_but_weak">Weak</option>
                                </select>
                            </div>

                            {/* Date uploaded */}
                            <div className="space-y-1">
                                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
                                    <Calendar size={10} /> Uploaded
                                </label>
                                <select value={dateRange} onChange={e => setDateRange(e.target.value)} className={`w-full ${selectCls}`}>
                                    <option value="">Any Time</option>
                                    <option value="7">Last 7 days</option>
                                    <option value="30">Last 30 days</option>
                                    <option value="90">Last 90 days</option>
                                </select>
                            </div>
                        </div>
                    </div>
                )}

                {/* Min score slider (shown after search) */}
                {searched && resumes.length > 0 && (
                    <div className="flex items-center gap-3 pt-2 border-t border-slate-100">
                        <span className="text-[11px] font-semibold text-slate-500 shrink-0 whitespace-nowrap flex items-center gap-1">
                            <Target size={11} className="text-purple-400" /> Min score: <span className="text-purple-600">{minScore}%</span>
                        </span>
                        <input
                            type="range" min={0} max={90} step={5} value={minScore}
                            onChange={e => setMinScore(Number(e.target.value))}
                            className="flex-1 h-1.5 rounded-full accent-purple-500 cursor-pointer"
                        />
                        <span className="text-[11px] text-slate-400 shrink-0 font-medium">{filteredResumes.length} shown</span>
                    </div>
                )}
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700 flex items-start gap-2">
                    <AlertCircle size={15} className="text-red-400 mt-0.5 shrink-0" />
                    {error}
                </div>
            )}

            {/* Skill level legend */}
            {resumes.length > 0 && (
                <div className="flex items-center gap-3 text-[11px] text-slate-400">
                    <span className="font-semibold text-slate-500 uppercase tracking-wide text-[10px]">Skill level:</span>
                    {([['E','Expert','bg-green-50 text-green-700 border-green-200'],['A','Advanced','bg-blue-50 text-blue-700 border-blue-200'],['I','Intermediate','bg-amber-50 text-amber-700 border-amber-200'],['B','Beginner','bg-slate-100 text-slate-600 border-slate-200']] as const).map(([abbr, label, cls]) => (
                        <span key={abbr} className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border font-medium ${cls}`}>
                            <span className="opacity-60 font-bold">({abbr})</span>{label}
                        </span>
                    ))}
                </div>
            )}

            {/* Semantic search badge */}
            {query && !searching && resumes.length > 0 && (
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2">
                        <Sparkles size={13} className="text-purple-500 shrink-0" />
                        Ranked by semantic relevance to "{query}"
                    </div>
                    <span className="text-xs text-slate-400 font-medium">{filteredResumes.length} of {total} candidate{total !== 1 ? 's' : ''}</span>
                </div>
            )}

            {/* Loading */}
            {searching && (
                <div className="flex items-center justify-center py-24">
                    <Loader2 size={32} className="text-purple-400 animate-spin" />
                </div>
            )}

            {/* Empty states */}
            {!searching && searched && filteredResumes.length === 0 && resumes.length > 0 && (
                <div className="text-center py-16 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <p className="text-slate-500 font-medium">No candidates above {minMatch}% profile score.</p>
                    <button onClick={() => setMinMatch(0)} className="mt-3 text-purple-600 text-sm font-bold hover:underline">Clear score filter</button>
                </div>
            )}
            {!searching && searched && resumes.length === 0 && (
                <div className="text-center py-20 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300"><FileText size={32} /></div>
                    <h4 className="text-slate-900 font-bold text-lg">No candidates found</h4>
                    <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">Try a different search query.</p>
                </div>
            )}

            {!searching && !searched && (
                <div className="text-center py-20 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300"><Search size={32} /></div>
                    <h4 className="text-slate-900 font-bold text-lg">Search Candidates</h4>
                    <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">Enter a query above to find matching candidates from your resume database.</p>
                </div>
            )}

            {/* Results grid — identical layout to Resume DB */}
            {!searching && filteredResumes.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {filteredResumes.map(r => {
                        const meta = r.classification ? CLASSIFICATION_META[r.classification] : null;
                        return (
                            <div
                                key={r.filename}
                                onClick={() => setPreviewResume(r)}
                                className="glass-card p-4 hover:shadow-lg hover:border-purple-200 transition-all cursor-pointer group flex flex-col gap-0"
                                style={{ minHeight: '220px' }}
                            >
                                {/* Header: avatar + name/role + actions */}
                                <div className="flex items-start gap-2.5 shrink-0">
                                    <div
                                        className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold shrink-0 select-none"
                                        style={{ background: `hsl(${r._avatarHue},55%,52%)` }}
                                    >
                                        {r._initials}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1.5 min-w-0">
                                            <p className="font-bold text-slate-900 text-sm truncate leading-tight">
                                                {r.candidate_name || r.filename.replace(/\.[^.]+$/, '')}
                                            </p>
                                            {r.exp_level && (
                                                <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded-full border font-semibold whitespace-nowrap ${EXP_LEVEL_STYLE[r.exp_level] ?? 'bg-slate-100 text-slate-600 border-slate-300'}`}>
                                                    {r.exp_level}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-[11px] text-purple-600 font-semibold truncate flex items-center gap-1 mt-0.5">
                                            {r.role || <span className="text-slate-300 italic font-normal">Role unknown</span>}
                                            {r.role && r.current_company && <span className="text-slate-300 font-normal">·</span>}
                                            {r.current_company && (
                                                <span className="text-slate-500 font-normal flex items-center gap-0.5 truncate">
                                                    <Building2 size={9} className="shrink-0" />{r.current_company}
                                                </span>
                                            )}
                                        </p>
                                    </div>
                                    <div
                                        className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity"
                                        onClick={e => e.stopPropagation()}
                                    >
                                        <button onClick={e => { e.stopPropagation(); setPreviewResume(r); }} className="p-1.5 text-slate-400 hover:text-purple-500 transition-colors" title="Preview"><Eye size={13} /></button>
                                        <button onClick={e => handleDownload(r.filename, e)} className="p-1.5 text-slate-400 hover:text-blue-500 transition-colors" title="Download"><Download size={13} /></button>
                                        <button onClick={e => handleDelete(r.filename, e)} className="p-1.5 text-slate-400 hover:text-red-500 transition-colors" title="Delete"><Trash2 size={13} /></button>
                                    </div>
                                </div>

                                {/* Location */}
                                {r.location && (
                                    <div className="flex items-center gap-0.5 mt-1.5 shrink-0">
                                        <MapPin size={9} className="shrink-0 text-slate-300" />
                                        <span className="text-[11px] text-slate-400 truncate">{r.location}</span>
                                    </div>
                                )}

                                {/* Skills */}
                                <div className="flex flex-wrap gap-1 mt-2 flex-1 content-start">
                                    {r.skills && r.skills.length > 0
                                        ? sortedSkills(r.skills).slice(0, 8).map(s => <SkillChip key={skillName(s)} skill={s} />)
                                        : <span className="text-[11px] text-slate-300 italic">Skills not yet extracted</span>
                                    }
                                </div>

                                {/* Footer */}
                                <div className="flex items-center gap-2 shrink-0 mt-2 pt-2 border-t border-slate-100 mt-auto">
                                    {r._scorePercent != null && (
                                        <span
                                            className={`inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${r._scorePercent >= 70 ? 'bg-green-50 text-green-700 border-green-200' : r._scorePercent >= 40 ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}
                                            title={r.total_score != null ? 'JD match score' : 'Profile completeness'}
                                        >
                                            <Star size={9} className="shrink-0" />{r._scorePercent}%
                                        </span>
                                    )}
                                    {(r.shortlist_count ?? 0) > 0 && (
                                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
                                            <Star size={9} className="shrink-0" />{r.shortlist_count} Shortlisted
                                        </span>
                                    )}
                                    {(r.apply_count ?? 0) > 0 && (
                                        <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200">
                                            <Send size={9} className="shrink-0" />{r.apply_count} applied
                                        </span>
                                    )}
                                    {meta && (
                                        <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${meta.color}`}>
                                            {meta.icon}{meta.label}
                                        </span>
                                    )}
                                    <div className="flex-1" />
                                    {r.role && (
                                        <button
                                            onClick={e => { e.stopPropagation(); setJobMatchResume(r); }}
                                            className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-indigo-50 text-indigo-600 border-indigo-200 hover:bg-indigo-100 transition-colors"
                                            title="Find matching jobs"
                                        >
                                            <Briefcase size={9} className="shrink-0" />Find Jobs
                                        </button>
                                    )}
                                    <span className="text-[10px] text-slate-300">
                                        {r.uploaded_at ? new Date(r.uploaded_at).toLocaleDateString() : ''}
                                    </span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Modals */}
            {previewResume && (
                <PreviewModal
                    resume={previewResume}
                    resumes={resumes}
                    onClose={() => setPreviewResume(null)}
                    onNavigate={setPreviewResume}
                    onDownload={handleDownload}
                    onDelete={handleDelete}
                />
            )}
            {jobMatchResume && (
                <ResumeJobMatchModal
                    resume={jobMatchResume}
                    onClose={() => setJobMatchResume(null)}
                />
            )}
        </div>
    );
};

export default CandidateSearch;
