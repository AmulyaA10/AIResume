import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { X, Sparkles, FileText, ChevronDown, ChevronUp, CheckCircle, XCircle, Loader2, UserPlus, Mail, Phone } from 'lucide-react';
import { matchApi, resumesApi, jobsApi } from '../../api';

interface CandidateMatch {
    score: number;
    resume_id: string;
    user_id: string;
    snippet: string;
}

interface Props {
    jobId: string;
    jobTitle: string;
    jobSkills: string[];
    onClose: () => void;
}

const scoreColor = (score: number) => {
    if (score >= 0.75) return { bar: 'bg-green-500', badge: 'bg-green-100 text-green-700 border-green-200' };
    if (score >= 0.50) return { bar: 'bg-blue-500',  badge: 'bg-blue-100 text-blue-700 border-blue-200' };
    if (score >= 0.30) return { bar: 'bg-yellow-500', badge: 'bg-yellow-100 text-yellow-700 border-yellow-200' };
    return { bar: 'bg-slate-400', badge: 'bg-slate-100 text-slate-500 border-slate-200' };
};

const JobMatchCandidatesModal: React.FC<Props> = ({ jobId, jobTitle, jobSkills, onClose }) => {
    const [candidates, setCandidates] = useState<CandidateMatch[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [cutoff, setCutoff] = useState(30);
    const [expandedRow, setExpandedRow] = useState<string | null>(null);
    const [resumeTexts, setResumeTexts] = useState<Record<string, string>>({});
    const [loadingText, setLoadingText] = useState<string | null>(null);
    const [shortlisted, setShortlisted] = useState<Set<string>>(new Set());
    const [shortlisting, setShortlisting] = useState<string | null>(null);

    useEffect(() => {
        matchApi.matchCandidatesForJob(jobId).then(res => {
            setCandidates(res.data || []);
        }).catch(err => {
            console.error('Failed to fetch matching candidates', err);
        }).finally(() => setIsLoading(false));
    }, [jobId]);

    const toggleRow = async (resumeId: string) => {
        if (expandedRow === resumeId) {
            setExpandedRow(null);
            return;
        }
        setExpandedRow(resumeId);
        if (!resumeTexts[resumeId]) {
            setLoadingText(resumeId);
            try {
                const res = await resumesApi.getText(resumeId);
                setResumeTexts(prev => ({ ...prev, [resumeId]: res.data?.text || '' }));
            } catch {
                setResumeTexts(prev => ({ ...prev, [resumeId]: '(Unable to load resume text)' }));
            } finally {
                setLoadingText(null);
            }
        }
    };

    const handleShortlist = async (c: CandidateMatch) => {
        setShortlisting(c.resume_id);
        try {
            await jobsApi.shortlistCandidate(jobId, c.resume_id, c.user_id);
            setShortlisted(prev => new Set(prev).add(c.resume_id));
        } catch (err) {
            console.error('Shortlist failed', err);
        } finally {
            setShortlisting(null);
        }
    };

    const extractContact = (text: string) => {
        const email = text.match(/[\w.+-]+@[\w-]+\.[a-z]{2,}/i)?.[0] ?? null;
        const phone = text.match(/(\+?\d[\d\s\-().]{7,}\d)/)?.[0]?.trim() ?? null;
        const nameLine = text.split('\n').find(l => l.trim().length > 2 && l.trim().length < 50 && !/[@\d]/.test(l));
        return { email, phone, name: nameLine?.trim() ?? null };
    };

    const skillGap = (resumeText: string) => {
        const text = resumeText.toLowerCase();
        return jobSkills.map(skill => ({
            skill,
            matched: text.includes(skill.toLowerCase()),
        }));
    };

    const filtered = candidates.filter(c => Math.round(c.score * 100) >= cutoff);

    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl relative z-10 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="p-6 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-md z-20 rounded-t-2xl">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center text-purple-600">
                            <Sparkles size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Matching Candidates</h2>
                            <p className="text-sm text-slate-500">{jobTitle}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                            <label className="font-medium whitespace-nowrap">Min match:</label>
                            <input
                                type="range" min={0} max={90} step={5} value={cutoff}
                                onChange={e => setCutoff(Number(e.target.value))}
                                className="w-24 accent-purple-600"
                            />
                            <span className="font-bold text-purple-600 w-8">{cutoff}%</span>
                        </div>
                        <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="overflow-y-auto flex-1">
                    {isLoading ? (
                        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
                            <div className="w-8 h-8 border-4 border-slate-200 border-t-purple-600 rounded-full animate-spin" />
                            <p className="mt-4">Finding best matches…</p>
                        </div>
                    ) : filtered.length === 0 ? (
                        <div className="py-20 text-center m-6 glass-card bg-slate-50/50 border-dashed border-slate-200">
                            <Sparkles size={32} className="mx-auto mb-4 text-slate-300" />
                            <h4 className="text-slate-900 font-bold text-lg">No Matches Above {cutoff}%</h4>
                            <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">Lower the threshold to see more candidates.</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-100">
                            {filtered.map((c, idx) => {
                                const colors = scoreColor(c.score);
                                const pct = Math.round(c.score * 100);
                                const isExpanded = expandedRow === c.resume_id;
                                const text = resumeTexts[c.resume_id] || '';
                                const gap = text ? skillGap(text) : [];
                                const matched = gap.filter(g => g.matched).length;
                                const missing = gap.filter(g => !g.matched).length;

                                return (
                                    <div key={c.resume_id + idx}>
                                        {/* Summary row */}
                                        <div
                                            className="flex items-center gap-4 px-6 py-4 hover:bg-slate-50 cursor-pointer transition-colors"
                                            onClick={() => toggleRow(c.resume_id)}
                                        >
                                            {/* Rank */}
                                            <span className="text-slate-400 font-bold text-sm w-6 shrink-0">{idx + 1}</span>

                                            {/* Resume name */}
                                            <div className="flex items-center gap-2 flex-1 min-w-0">
                                                <FileText size={15} className="text-slate-400 shrink-0" />
                                                <div className="min-w-0">
                                                    <p className="font-semibold text-slate-900 truncate text-sm">{c.resume_id}</p>
                                                    <p className="text-xs text-slate-400 truncate">{c.snippet.substring(0, 80)}…</p>
                                                </div>
                                            </div>

                                            {/* Skill gap summary (only if loaded) */}
                                            {gap.length > 0 && (
                                                <div className="text-xs font-medium shrink-0 flex gap-2">
                                                    <span className="text-green-600">{matched} matched</span>
                                                    <span className="text-red-500">{missing} missing</span>
                                                </div>
                                            )}

                                            {/* Score bar + badge */}
                                            <div className="flex items-center gap-3 shrink-0">
                                                <div className="w-20">
                                                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                        <div className={`h-full rounded-full ${colors.bar}`} style={{ width: `${pct}%` }} />
                                                    </div>
                                                </div>
                                                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border ${colors.badge} w-14 justify-center`}>
                                                    {pct}%
                                                </span>
                                                {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                                            </div>
                                        </div>

                                        {/* Expanded detail panel */}
                                        {isExpanded && (
                                            <div className="bg-slate-50/70 border-t border-slate-100 px-6 py-5 space-y-5">
                                                {loadingText === c.resume_id ? (
                                                    <div className="flex items-center gap-2 text-slate-400 text-sm">
                                                        <Loader2 size={16} className="animate-spin" /> Loading resume…
                                                    </div>
                                                ) : (() => {
                                                    const contact = extractContact(text);
                                                    const isShortlisted = shortlisted.has(c.resume_id);
                                                    const isShortlisting = shortlisting === c.resume_id;
                                                    return (
                                                        <>
                                                            {/* Contact info + shortlist action */}
                                                            <div className="flex items-start justify-between gap-4">
                                                                <div className="space-y-1">
                                                                    <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Contact Info</h4>
                                                                    {contact.name && <p className="text-sm font-semibold text-slate-800">{contact.name}</p>}
                                                                    {contact.email && (
                                                                        <a href={`mailto:${contact.email}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                                                                            <Mail size={13} /> {contact.email}
                                                                        </a>
                                                                    )}
                                                                    {contact.phone && (
                                                                        <p className="flex items-center gap-1.5 text-sm text-slate-600">
                                                                            <Phone size={13} /> {contact.phone}
                                                                        </p>
                                                                    )}
                                                                    {!contact.email && !contact.phone && (
                                                                        <p className="text-xs text-slate-400 italic">No contact info found in resume</p>
                                                                    )}
                                                                </div>
                                                                <button
                                                                    onClick={(e) => { e.stopPropagation(); handleShortlist(c); }}
                                                                    disabled={isShortlisted || isShortlisting}
                                                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all shrink-0 ${
                                                                        isShortlisted
                                                                            ? 'bg-green-50 text-green-700 border-green-200 cursor-default'
                                                                            : 'bg-purple-600 text-white border-purple-600 hover:bg-purple-700 disabled:opacity-60'
                                                                    }`}
                                                                >
                                                                    {isShortlisting ? <Loader2 size={14} className="animate-spin" /> : <UserPlus size={14} />}
                                                                    {isShortlisted ? 'Shortlisted' : isShortlisting ? 'Shortlisting…' : 'Shortlist Candidate'}
                                                                </button>
                                                            </div>

                                                            {/* Skill Gap */}
                                                            {jobSkills.length > 0 && gap.length > 0 && (
                                                                <div>
                                                                    <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Skill Gap Analysis</h4>
                                                                    <div className="flex flex-wrap gap-2">
                                                                        {gap.map(({ skill, matched }) => (
                                                                            <span
                                                                                key={skill}
                                                                                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${
                                                                                    matched
                                                                                        ? 'bg-green-50 text-green-700 border-green-200'
                                                                                        : 'bg-red-50 text-red-600 border-red-200'
                                                                                }`}
                                                                            >
                                                                                {matched ? <CheckCircle size={11} /> : <XCircle size={11} />}
                                                                                {skill}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                </div>
                                                            )}

                                                            {/* Resume text preview */}
                                                            <div>
                                                                <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Resume Preview</h4>
                                                                <pre className="text-xs text-slate-600 bg-white border border-slate-200 rounded-lg p-4 max-h-64 overflow-y-auto whitespace-pre-wrap font-sans leading-relaxed">
                                                                    {text || '(No text available)'}
                                                                </pre>
                                                            </div>
                                                        </>
                                                    );
                                                })()}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Footer */}
                {!isLoading && (
                    <div className="px-6 py-3 border-t border-slate-100 text-xs text-slate-400 flex justify-between bg-slate-50/50 rounded-b-2xl">
                        <span>Showing {filtered.length} of {candidates.length} candidates</span>
                        <span>Ranked by semantic similarity · click row to expand</span>
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
};

export default JobMatchCandidatesModal;
