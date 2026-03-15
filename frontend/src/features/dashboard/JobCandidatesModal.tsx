import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import {
    X, Users, Star, ChevronDown, ChevronUp, Mail, Phone, Loader2, Send,
    FileText, CheckCircle, XCircle, Copy, Check, UserCheck, UserX, ShieldCheck, Zap
} from 'lucide-react';
import api, { jobsApi, resumesApi } from '../../api';

interface Candidate {
    resume_id: string;
    candidate_user_id: string;
    applied_at: string;
    applied_status: string;
    notified?: boolean;
}

interface JobCandidatesModalProps {
    jobId: string;
    jobTitle: string;
    jobSkills?: string[];
    onClose: () => void;
    statusFilter?: string;
    onViewSelected?: () => void;
}

const JobCandidatesModal: React.FC<JobCandidatesModalProps> = ({ jobId, jobTitle, jobSkills = [], onClose, statusFilter, onViewSelected }) => {
    const [candidates, setCandidates] = useState<Candidate[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUpdating, setIsUpdating] = useState<string | null>(null);
    const [expandedRow, setExpandedRow] = useState<string | null>(null);
    const [resumeTexts, setResumeTexts] = useState<Record<string, string>>({});
    const [loadingText, setLoadingText] = useState<string | null>(null);
    const [notifyOpen, setNotifyOpen] = useState<string | null>(null);
    const [notifyBody, setNotifyBody] = useState<Record<string, string>>({});
    const [notifyIntendedStatus, setNotifyIntendedStatus] = useState<Record<string, string>>({});
    const [marking, setMarking] = useState<string | null>(null);
    const [copied, setCopied] = useState<string | null>(null);
    const [screeningResults, setScreeningResults] = useState<Record<string, any>>({});
    const [screeningLoading, setScreeningLoading] = useState<string | null>(null);
    const [jdText, setJdText] = useState<string>('');

    const isShortlistedView = statusFilter === 'shortlisted';
    const isSelectedView = statusFilter === 'selected';
    const isRejectedView = statusFilter === 'rejected';

    useEffect(() => { fetchCandidates(); }, [jobId]);

    const fetchCandidates = async () => {
        setIsLoading(true);
        try {
            const response = await jobsApi.getCandidates(jobId, statusFilter);
            setCandidates(response.data);
        } catch (error) {
            console.error("Failed to fetch candidates:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleStatusUpdate = async (resumeId: string, newStatus: string) => {
        setIsUpdating(resumeId);
        try {
            await jobsApi.updateCandidateStatus(jobId, resumeId, newStatus);
            setCandidates(prev => prev.map(c =>
                c.resume_id === resumeId ? { ...c, applied_status: newStatus } : c
            ));
            // Auto-open notification draft when candidate is invited, selected, or rejected
            if (newStatus === 'selected' || newStatus === 'rejected' || newStatus === 'invited') {
                const existing = candidates.find(c => c.resume_id === resumeId);
                if (existing) {
                    openNotify({ ...existing, applied_status: newStatus });
                }
            }
        } catch (error) {
            console.error("Failed to update status:", error);
            alert("Failed to update status.");
        } finally {
            setIsUpdating(null);
        }
    };

    const toggleRow = async (resumeId: string) => {
        if (expandedRow === resumeId) { setExpandedRow(null); return; }
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

    const openNotify = async (candidate: Candidate) => {
        if (notifyOpen === candidate.resume_id) { setNotifyOpen(null); return; }
        // Ensure resume text is loaded to extract email
        if (!resumeTexts[candidate.resume_id]) {
            setLoadingText(candidate.resume_id);
            try {
                const res = await resumesApi.getText(candidate.resume_id);
                setResumeTexts(prev => ({ ...prev, [candidate.resume_id]: res.data?.text || '' }));
            } catch {
                setResumeTexts(prev => ({ ...prev, [candidate.resume_id]: '' }));
            } finally {
                setLoadingText(null);
            }
        }
        const status = candidate.applied_status;
        // Always regenerate draft when status changes
        const draft =
            status === 'invited'
                ? `Dear Candidate,\n\nWe have reviewed your profile and are pleased to invite you to apply for the ${jobTitle} position.\n\nYour background looks like a strong match for what we are looking for. Please submit your application at your earliest convenience and we will be in touch to discuss next steps.\n\nWe look forward to hearing from you.\n\nBest regards`
                : status === 'selected'
                ? `Dear Candidate,\n\nWe are pleased to inform you that you have been selected for the ${jobTitle} position.\n\nWe will be in touch shortly to discuss next steps, including an interview schedule and offer details.\n\nThank you for your interest and we look forward to welcoming you to the team.\n\nBest regards`
                : `Dear Candidate,\n\nThank you for taking the time to apply for the ${jobTitle} position.\n\nAfter careful review of all applications, we have decided to move forward with other candidates whose experience more closely matches our current needs.\n\nWe appreciate your interest and encourage you to apply for future openings.\n\nBest regards`;
        setNotifyIntendedStatus(prev => ({ ...prev, [candidate.resume_id]: status }));
        setNotifyBody(prev => ({ ...prev, [candidate.resume_id]: draft }));
        setNotifyOpen(candidate.resume_id);
        setExpandedRow(candidate.resume_id);
    };

    const handleMarkSent = async (candidate: Candidate) => {
        setMarking(candidate.resume_id);
        try {
            // If draft was opened for a status not yet set (e.g. invite before committing), update it now
            const intended = notifyIntendedStatus[candidate.resume_id];
            if (intended && intended !== candidate.applied_status) {
                await jobsApi.updateCandidateStatus(jobId, candidate.resume_id, intended);
                setCandidates(prev => prev.map(c =>
                    c.resume_id === candidate.resume_id ? { ...c, applied_status: intended } : c
                ));
            }
            await jobsApi.markNotified(jobId, candidate.resume_id);
            setCandidates(prev => prev.map(c =>
                c.resume_id === candidate.resume_id ? { ...c, notified: true } : c
            ));
            setNotifyOpen(null);
            setNotifyIntendedStatus(prev => { const n = { ...prev }; delete n[candidate.resume_id]; return n; });
        } catch (error) {
            console.error("Failed to mark notified:", error);
        } finally {
            setMarking(null);
        }
    };

    const handleCopy = (resumeId: string, text: string) => {
        navigator.clipboard.writeText(text);
        setCopied(resumeId);
        setTimeout(() => setCopied(null), 2000);
    };

    const runAutoScreen = async (candidate: Candidate) => {
        setScreeningLoading(candidate.resume_id);
        try {
            // Ensure resume text is loaded
            let resumeText = resumeTexts[candidate.resume_id];
            if (!resumeText) {
                const res = await resumesApi.getText(candidate.resume_id);
                resumeText = res.data?.text || '';
                setResumeTexts(prev => ({ ...prev, [candidate.resume_id]: resumeText }));
            }
            // Ensure JD text is loaded
            let jd = jdText;
            if (!jd) {
                const jobRes = await jobsApi.get(jobId);
                const job = jobRes.data;
                jd = [
                    job.title && `Job Title: ${job.title}`,
                    job.employer_name && `Company: ${job.employer_name}`,
                    job.skills_required?.length && `Required Skills: ${job.skills_required.join(', ')}`,
                    job.description && `\n${job.description}`,
                ].filter(Boolean).join('\n');
                setJdText(jd);
            }
            const res = await api.post('/analyze/screen', { resume_text: resumeText, jd_text: jd, threshold: 75 });
            setScreeningResults(prev => ({ ...prev, [candidate.resume_id]: res.data }));
            setExpandedRow(candidate.resume_id);
        } catch (e) {
            console.error('Auto screening failed:', e);
        } finally {
            setScreeningLoading(null);
        }
    };

    const getEmail = (resumeId: string) =>
        (resumeTexts[resumeId] || '').match(/[\w.+-]+@[\w-]+\.[a-z]{2,}/i)?.[0] || '';

    const skillGap = (resumeText: string) => {
        const lower = resumeText.toLowerCase();
        return jobSkills.map(skill => ({ skill, matched: lower.includes(skill.toLowerCase()) }));
    };

    const extractContact = (text: string) => {
        const email = text.match(/[\w.+-]+@[\w-]+\.[a-z]{2,}/i)?.[0] ?? null;
        const phone = text.match(/(\+?\d[\d\s\-().]{7,}\d)/)?.[0]?.trim() ?? null;
        const nameLine = text.split('\n').find(l => l.trim().length > 2 && l.trim().length < 50 && !/[@\d]/.test(l));
        return { email, phone, name: nameLine?.trim() ?? null };
    };

    const getStatusTheme = (status: string) => {
        switch (status.toLowerCase()) {
            case 'selected':    return 'bg-green-100 text-green-700 border-green-200';
            case 'rejected':    return 'bg-red-100 text-red-700 border-red-200';
            case 'shortlisted': return 'bg-purple-100 text-purple-700 border-purple-200';
            case 'invited':     return 'bg-amber-100 text-amber-700 border-amber-200';
            default:            return 'bg-blue-100 text-blue-700 border-blue-200';
        }
    };

    const renderRow = (candidate: Candidate, extraVars?: { isInvited?: boolean }) => {
        const isExpanded = expandedRow === candidate.resume_id;
        const isNotifyOpen = notifyOpen === candidate.resume_id;
        const text = resumeTexts[candidate.resume_id] || '';
        const contact = text ? extractContact(text) : null;
        const gap = text ? skillGap(text) : [];
        const matchedCount = gap.filter(g => g.matched).length;
        const qualityPct = gap.length > 0 ? Math.round((matchedCount / gap.length) * 100) : null;
        const isUpdatingThis = isUpdating === candidate.resume_id;
        const isMarkingThis = marking === candidate.resume_id;

        const intendedStatus = notifyIntendedStatus[candidate.resume_id];
        const effectiveStatus = intendedStatus || candidate.applied_status;
        const canNotify = !!intendedStatus || ['invited', 'selected', 'rejected'].includes(candidate.applied_status);
        const email = getEmail(candidate.resume_id);
        const body = notifyBody[candidate.resume_id] || '';
        const isInvited = effectiveStatus === 'invited';
        const isSelected = effectiveStatus === 'selected';
        const statusLabel = candidate.applied_status.toUpperCase();
        const screenResult = screeningResults[candidate.resume_id];
        const isScreeningThis = screeningLoading === candidate.resume_id;

        return (
            <div key={candidate.resume_id}>
                {/* Summary row */}
                <div
                    className="flex items-center gap-3 px-6 py-4 hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => toggleRow(candidate.resume_id)}
                >
                    <FileText size={15} className="text-slate-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                        <p className="font-semibold text-slate-900 truncate text-sm">{candidate.resume_id}</p>
                        <p className="text-xs text-slate-400">{new Date(candidate.applied_at).toLocaleDateString()}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                        <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border ${getStatusTheme(candidate.applied_status)}`}>
                            {statusLabel}
                        </span>
                        {candidate.notified && (
                            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold bg-teal-50 text-teal-700 border border-teal-200">
                                <Check size={10} /> Notified
                            </span>
                        )}
                    </div>
                    {isUpdatingThis
                        ? <Loader2 size={14} className="text-slate-400 animate-spin shrink-0" />
                        : isExpanded ? <ChevronUp size={16} className="text-slate-400 shrink-0" /> : <ChevronDown size={16} className="text-slate-400 shrink-0" />}
                </div>

                {/* Expanded detail */}
                {isExpanded && (
                    <div className="bg-slate-50/70 border-t border-slate-100 px-6 py-5 space-y-5">
                        {loadingText === candidate.resume_id ? (
                            <div className="flex items-center gap-2 text-slate-400 text-sm">
                                <Loader2 size={16} className="animate-spin" /> Loading resume…
                            </div>
                        ) : (
                            <>
                                {/* Contact info + actions */}
                                <div className="flex items-start justify-between gap-4">
                                    <div className="space-y-1">
                                        <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Contact Info</h4>
                                        {contact?.name && <p className="text-sm font-semibold text-slate-800">{contact.name}</p>}
                                        {contact?.email && (
                                            <a href={`mailto:${contact.email}`} className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                                                <Mail size={13} /> {contact.email}
                                            </a>
                                        )}
                                        {contact?.phone && (
                                            <p className="flex items-center gap-1.5 text-sm text-slate-600">
                                                <Phone size={13} /> {contact.phone}
                                            </p>
                                        )}
                                        {!contact?.email && !contact?.phone && (
                                            <p className="text-xs text-slate-400 italic">No contact info found in resume</p>
                                        )}
                                    </div>
                                    <div className="flex flex-col gap-2 shrink-0">
                                        {isShortlistedView ? (
                                            <>
                                                {extraVars?.isInvited ? (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify(candidate); }}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${isNotifyOpen ? 'bg-purple-600 text-white border-purple-600' : 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100'}`}>
                                                        <Send size={14} /> Resend Invitation
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify({ ...candidate, applied_status: 'invited' }); }}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${isNotifyOpen ? 'bg-purple-700 text-white border-purple-700' : 'bg-purple-600 text-white border-purple-600 hover:bg-purple-700'}`}>
                                                        <Send size={14} /> Invite to Apply
                                                    </button>
                                                )}
                                            </>
                                        ) : (
                                            <div className="flex flex-col gap-2 shrink-0">
                                                {/* Auto Screen button */}
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); runAutoScreen(candidate); }}
                                                    disabled={isScreeningThis}
                                                    className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all bg-violet-600 text-white border-violet-600 hover:bg-violet-700 disabled:opacity-60"
                                                >
                                                    {isScreeningThis ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                                                    {isScreeningThis ? 'Screening…' : 'Auto Screen'}
                                                </button>
                                                {/* Manual screening */}
                                                <div className="flex gap-2">
                                                {candidate.applied_status === 'selected' ? (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify(candidate); }}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${isNotifyOpen && isSelected ? 'bg-green-600 text-white border-green-600' : 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'}`}>
                                                        <UserCheck size={14} /> {candidate.notified ? 'Resend' : 'Selected'}
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify({ ...candidate, applied_status: 'selected' }); }}
                                                        disabled={candidate.applied_status === 'rejected'}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${intendedStatus === 'selected' ? 'bg-green-700 text-white border-green-700' : 'bg-green-600 text-white border-green-600 hover:bg-green-700 disabled:opacity-40'}`}>
                                                        <UserCheck size={14} /> Select
                                                    </button>
                                                )}
                                                {candidate.applied_status === 'rejected' ? (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify(candidate); }}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${isNotifyOpen && !isSelected ? 'bg-red-600 text-white border-red-600' : 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100'}`}>
                                                        <UserX size={14} /> {candidate.notified ? 'Resend' : 'Rejected'}
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); openNotify({ ...candidate, applied_status: 'rejected' }); }}
                                                        disabled={candidate.applied_status === 'selected'}
                                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-bold border transition-all ${intendedStatus === 'rejected' ? 'bg-red-700 text-white border-red-700' : 'bg-white text-red-600 border-red-200 hover:bg-red-50 disabled:opacity-40'}`}>
                                                        <UserX size={14} /> Reject
                                                    </button>
                                                )}
                                            </div>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Auto Screening result panel */}
                                {screenResult && (
                                    <div className={`rounded-xl border p-4 space-y-3 ${screenResult.decision?.selected ? 'bg-green-50/60 border-green-200' : 'bg-red-50/60 border-red-200'}`}>
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <ShieldCheck size={15} className={screenResult.decision?.selected ? 'text-green-600' : 'text-red-600'} />
                                                <span className="text-xs font-bold uppercase tracking-wider text-slate-600">AI Screening Result</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${screenResult.decision?.selected ? 'bg-green-100 text-green-700 border-green-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                                                    {screenResult.score?.overall}% match
                                                </span>
                                                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${screenResult.decision?.selected ? 'bg-green-100 text-green-700 border-green-200' : 'bg-red-100 text-red-700 border-red-200'}`}>
                                                    {screenResult.decision?.selected ? 'Recommend: Select' : 'Recommend: Reject'}
                                                </span>
                                                <button
                                                    onClick={() => setScreeningResults(prev => { const n = { ...prev }; delete n[candidate.resume_id]; return n; })}
                                                    className="p-1 text-slate-400 hover:text-slate-600 rounded"
                                                >
                                                    <X size={14} />
                                                </button>
                                            </div>
                                        </div>
                                        <p className="text-xs text-slate-600 bg-white/70 rounded-lg p-3 border border-slate-100 leading-relaxed italic">
                                            "{screenResult.decision?.reason}"
                                        </p>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); openNotify({ ...candidate, applied_status: screenResult.decision?.selected ? 'selected' : 'rejected' }); setScreeningResults(prev => { const n = { ...prev }; delete n[candidate.resume_id]; return n; }); }}
                                                className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg border transition-all ${screenResult.decision?.selected ? 'bg-green-600 text-white border-green-600 hover:bg-green-700' : 'bg-red-600 text-white border-red-600 hover:bg-red-700'}`}
                                            >
                                                {screenResult.decision?.selected ? <UserCheck size={13} /> : <UserX size={13} />}
                                                Apply Recommendation
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Notification compose panel */}
                                {isNotifyOpen && canNotify && (() => {
                                    const panelBg = isInvited ? 'bg-purple-50/60 border-purple-200' : isSelected ? 'bg-green-50/60 border-green-200' : 'bg-red-50/60 border-red-200';
                                    const labelColor = isInvited ? 'text-purple-700' : isSelected ? 'text-green-700' : 'text-red-700';
                                    const label = isInvited ? '✉️ Invitation to Apply' : isSelected ? '🎉 Selection Notification' : '📋 Rejection Notification';
                                    const subject = isInvited ? `Invitation to Apply – ${jobTitle}` : isSelected ? `Congratulations – ${jobTitle}` : `Application Update – ${jobTitle}`;
                                    const sendBtnClass = isInvited ? 'bg-purple-600 text-white border-purple-600 hover:bg-purple-700' : isSelected ? 'bg-green-600 text-white border-green-600 hover:bg-green-700' : 'bg-slate-700 text-white border-slate-700 hover:bg-slate-800';
                                    return (
                                        <div className={`rounded-xl border p-4 space-y-3 ${panelBg}`}>
                                            <div className="flex items-center justify-between">
                                                <h4 className={`text-xs font-bold uppercase tracking-wider ${labelColor}`}>{label}</h4>
                                                <span className="text-xs text-slate-400">To: {email || 'email not found in resume'}</span>
                                            </div>
                                            <div>
                                                <p className="text-xs text-slate-500 mb-1 font-medium">Subject: {subject}</p>
                                                <textarea
                                                    value={body}
                                                    onChange={e => setNotifyBody(prev => ({ ...prev, [candidate.resume_id]: e.target.value }))}
                                                    rows={8}
                                                    className="w-full text-xs text-slate-700 bg-white border border-slate-200 rounded-lg p-3 resize-y font-sans leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-200"
                                                />
                                            </div>
                                            <div className="flex gap-2">
                                                <button
                                                    onClick={() => handleCopy(candidate.resume_id, body)}
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold border border-slate-200 bg-white text-slate-600 rounded-lg hover:bg-slate-50 transition-colors">
                                                    {copied === candidate.resume_id ? <Check size={12} className="text-green-600" /> : <Copy size={12} />}
                                                    {copied === candidate.resume_id ? 'Copied!' : 'Copy Text'}
                                                </button>
                                                <a
                                                    href={`mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}
                                                    target="_blank" rel="noreferrer"
                                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold border border-blue-200 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors">
                                                    <Mail size={12} /> Open Mail App
                                                </a>
                                                <button
                                                    onClick={() => handleMarkSent(candidate)}
                                                    disabled={isMarkingThis}
                                                    className={`ml-auto flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg border transition-all ${sendBtnClass} disabled:opacity-60`}>
                                                    {isMarkingThis ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                                                    {isMarkingThis ? 'Sending…' : isInvited ? 'Send Invitation' : isSelected ? 'Send Notification' : 'Send Notification'}
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })()}

                                {/* Skill gap */}
                                {gap.length > 0 && (
                                    <div>
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider">Skill Gap Analysis</h4>
                                            {qualityPct !== null && (
                                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${qualityPct >= 75 ? 'bg-green-50 text-green-700 border-green-200' : qualityPct >= 50 ? 'bg-blue-50 text-blue-700 border-blue-200' : qualityPct >= 30 ? 'bg-yellow-50 text-yellow-700 border-yellow-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                                                    {qualityPct}% match
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {gap.map(({ skill, matched }) => (
                                                <span key={skill} className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold border ${matched ? 'bg-green-50 text-green-700 border-green-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
                                                    {matched ? <CheckCircle size={11} /> : <XCircle size={11} />}{skill}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Resume preview */}
                                <div>
                                    <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">Resume Preview</h4>
                                    <pre className="text-xs text-slate-600 bg-white border border-slate-200 rounded-lg p-4 max-h-64 overflow-y-auto whitespace-pre-wrap font-sans leading-relaxed">
                                        {text || '(No text available)'}
                                    </pre>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>
        );
    };

    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl relative z-10 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="p-6 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-md z-20 rounded-t-2xl">
                    <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isShortlistedView ? 'bg-amber-50 text-amber-600' : isSelectedView ? 'bg-green-50 text-green-700' : isRejectedView ? 'bg-red-50 text-red-700' : 'bg-indigo-50 text-indigo-600'}`}>
                            {isShortlistedView ? <Star size={20} /> : isSelectedView ? <UserCheck size={20} /> : isRejectedView ? <UserX size={20} /> : <Users size={20} />}
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">
                                {isShortlistedView ? 'Shortlisted Candidates' : isSelectedView ? 'Selected Candidates' : isRejectedView ? 'Rejected Candidates' : 'Applied Candidates'}
                            </h2>
                            <p className="text-sm text-slate-500">{jobTitle}</p>
                        </div>
                        {/* Selected count link — shown in Applied view when candidates have been selected */}
                        {!isShortlistedView && !isSelectedView && onViewSelected && (() => {
                            const selectedCount = candidates.filter(c => c.applied_status === 'selected').length;
                            return selectedCount > 0 ? (
                                <button
                                    onClick={onViewSelected}
                                    className="ml-2 flex items-center gap-1.5 px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-full text-xs font-bold hover:bg-green-100 transition-colors"
                                >
                                    <UserCheck size={13} /> {selectedCount} Selected →
                                </button>
                            ) : null;
                        })()}
                    </div>
                    <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {/* Body */}
                <div className="overflow-y-auto flex-1">
                    {isLoading ? (
                        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
                            <div className={`w-8 h-8 border-4 border-slate-200 rounded-full animate-spin ${isShortlistedView ? 'border-t-amber-500' : 'border-t-indigo-600'}`} />
                            <p className="mt-4">Loading candidates...</p>
                        </div>
                    ) : candidates.length === 0 ? (
                        <div className="py-20 text-center glass-card bg-slate-50/50 border-dashed border-slate-200 m-6">
                            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                                {isShortlistedView ? <Star size={32} /> : <Users size={32} />}
                            </div>
                            <h4 className="text-slate-900 font-bold text-lg">
                                {isShortlistedView ? 'No Shortlisted Candidates' : isSelectedView ? 'No Selected Candidates' : isRejectedView ? 'No Rejected Candidates' : 'No Candidates Yet'}
                            </h4>
                            <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                                {isShortlistedView
                                    ? 'Use "Find Matches" to discover and shortlist candidates.'
                                    : isSelectedView
                                    ? 'Select candidates from the Applied view to see them here.'
                                    : isRejectedView
                                    ? 'No candidates have been rejected for this job yet.'
                                    : 'There are no applications for this job at the moment.'}
                            </p>
                        </div>
                    ) : (
                        <div className="divide-y divide-slate-100">
                            {candidates.map(candidate =>
                                renderRow(candidate, { isInvited: candidate.applied_status === 'invited' })
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                {!isLoading && candidates.length > 0 && (
                    <div className="px-6 py-3 border-t border-slate-100 text-xs text-slate-400 flex justify-between bg-slate-50/50 rounded-b-2xl">
                        <span>{candidates.length} candidate{candidates.length !== 1 ? 's' : ''}</span>
                        <span>
                            {isShortlistedView
                                ? 'Click row to preview resume and skill gap'
                                : 'Click row to expand · Select or Reject'}
                        </span>
                    </div>
                )}
            </div>
        </div>,
        document.body
    );
};

export default JobCandidatesModal;
