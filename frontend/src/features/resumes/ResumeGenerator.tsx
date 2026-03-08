import { useState, useEffect, useRef } from 'react';
import { FileText, Loader2, Download, Sparkles, CheckCircle2, ChevronRight, Save, RotateCcw, ArrowRight, TrendingUp, TrendingDown, Minus, PenLine, AlertCircle, User, Briefcase, GraduationCap, Award, FolderOpen } from 'lucide-react';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';
import { EmptyState, LoadingOverlay, ActionButton, FormTextarea, ValidationBanner } from '../../common';
import { useAuth } from '../../context/AuthContext';

const classificationConfig: Record<string, { label: string; color: string; bg: string; border: string }> = {
    not_resume: { label: 'Not a Resume', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
    resume_invalid_or_incomplete: { label: 'Invalid', color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200' },
    resume_valid_but_weak: { label: 'Weak', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
    resume_valid_good: { label: 'Good', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
    resume_valid_strong: { label: 'Strong', color: 'text-emerald-800', bg: 'bg-emerald-50', border: 'border-emerald-100' },
};
const MAX_TOP_INPUTS = 5;

const TABS = [
    { id: 'overview', label: 'Full Preview', icon: FileText },
    { id: 'contact', label: 'Contact', icon: User },
    { id: 'summary', label: 'Summary', icon: FileText },
    { id: 'skills', label: 'Skills', icon: Sparkles },
    { id: 'experience', label: 'Experience', icon: Briefcase },
    { id: 'education', label: 'Education', icon: GraduationCap },
    { id: 'certifications', label: 'Certifications', icon: Award },
    { id: 'projects', label: 'Projects', icon: FolderOpen },
] as const;

type TabId = typeof TABS[number]['id'];

const MANDATORY_FIELDS: Record<string, string[]> = {
    contact: ['name', 'email', 'phone', 'location'],
    summary: ['summary'],
    skills: ['skills'],
    experience: ['experience'],
    education: ['education'],
};

function getSectionStatus(resume: any, tabId: string): 'valid' | 'warning' | 'missing' {
    if (!resume) return 'missing';
    switch (tabId) {
        case 'contact': {
            const c = resume.contact || {};
            const has = ['name', 'email', 'phone', 'location'].filter(f => c[f] && c[f].trim && c[f].trim() !== '');
            if (has.length >= 4) return 'valid';
            if (has.length >= 2) return 'warning';
            return 'missing';
        }
        case 'summary':
            return resume.summary && resume.summary.length > 30 ? 'valid' : resume.summary ? 'warning' : 'missing';
        case 'skills': {
            const skills = resume.skills || [];
            if (skills.length >= 6) return 'valid';
            if (skills.length >= 1) return 'warning';
            return 'missing';
        }
        case 'experience': {
            const exp = resume.experience || [];
            if (exp.length >= 1 && exp.every((e: any) => e.bullets?.length >= 2)) return 'valid';
            if (exp.length >= 1) return 'warning';
            return 'missing';
        }
        case 'education':
            return (resume.education || []).length >= 1 ? 'valid' : 'missing';
        case 'certifications':
            return (resume.certifications || []).length >= 1 ? 'valid' : 'warning'; // optional — amber if empty
        case 'projects':
            return (resume.projects || []).length >= 1 ? 'valid' : 'warning'; // optional — amber if empty
        default:
            return 'valid';
    }
}

function StatusDot({ status }: { status: 'valid' | 'warning' | 'missing' }) {
    if (status === 'valid') return <CheckCircle2 className="w-3 h-3 text-emerald-500" />;
    if (status === 'warning') return <AlertCircle className="w-3 h-3 text-amber-500" />;
    return <AlertCircle className="w-3 h-3 text-red-400" />;
}

const ResumeGenerator = () => {
    const { persona } = useAuth();
    const editorRef = useRef<HTMLDivElement>(null);
    const [profile, setProfile] = useState('');
    const [generating, setGenerating] = useState(false);
    const [resume, setResume] = useState<any>(null);
    const [outputValidation, setOutputValidation] = useState<any>(null);
    const [fieldValidation, setFieldValidation] = useState<any>(null);
    const [validationError, setValidationError] = useState<any>(null);
    const [inputValidationWarning, setInputValidationWarning] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<TabId>('overview');
    const [error, setError] = useState<string | null>(null);

    // Resume picker state
    const [myResumes, setMyResumes] = useState<{ filename: string; validation: any }[]>([]);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [loadingText, setLoadingText] = useState(false);

    // Accept / save state
    const [accepted, setAccepted] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
    const [showNewNameInput, setShowNewNameInput] = useState(false);
    const [newFilename, setNewFilename] = useState('');
    // Tracks the validation of the previous refinement pass for comparison
    const [prevRefinedValidation, setPrevRefinedValidation] = useState<any>(null);
    // Refinement instructions sent as a separate field (not embedded in profile text)
    const [refinementInstructions, setRefinementInstructions] = useState<string | null>(null);

    useEffect(() => {
        const isRecruiterMode = persona === 'recruiter' || persona === 'manager';
        if (isRecruiterMode) {
            api.get('/resumes')
                .then(r => setMyResumes((r.data.all_resumes || r.data.resumes || []).map((item: any) => ({
                    filename: typeof item === 'string' ? item : item.filename,
                    validation: item.validation ?? null,
                }))))
                .catch(console.error);
        } else {
            api.get('/resumes/list')
                .then(r => setMyResumes(r.data.resumes || []))
                .catch(console.error);
        }
    }, [persona]);

    const handleSelectResume = async (filename: string) => {
        setSelectedFile(filename);
        setLoadingText(true);
        // Clear any previous generation output when switching resumes
        setResume(null);
        setOutputValidation(null);
        setValidationError(null);
        setInputValidationWarning(null);
        setAccepted(false);
        setSaveSuccess(null);
        setShowNewNameInput(false);
        setNewFilename('');
        setPrevRefinedValidation(null);
        setRefinementInstructions(null);
        try {
            const res = await api.get(`/resumes/${encodeURIComponent(filename)}/text`);
            setProfile(res.data.text || '');
        } catch (err) {
            console.error('Failed to load resume text:', err);
        } finally {
            setLoadingText(false);
        }
    };

    const refreshResumes = () => {
        const isRecruiterMode = persona === 'recruiter' || persona === 'manager';
        if (isRecruiterMode) {
            api.get('/resumes')
                .then(r => setMyResumes((r.data.all_resumes || r.data.resumes || []).map((item: any) => ({
                    filename: typeof item === 'string' ? item : item.filename,
                    validation: item.validation ?? null,
                }))))
                .catch(console.error);
        } else {
            api.get('/resumes/list').then(r => setMyResumes(r.data.resumes || [])).catch(console.error);
        }
    };

    const resumeJsonToText = (r: any): string => {
        const contact = r?.contact || {};
        const lines: string[] = [
            contact.name || '',
            [contact.email, contact.phone, contact.location].filter(Boolean).join(' | '),
            contact.linkedin ? `LinkedIn: ${contact.linkedin}` : '',
            '',
            'PROFESSIONAL SUMMARY',
            r?.summary || '',
            '',
            'CORE COMPETENCIES',
            (r?.skills || []).join(', '),
            '',
            'PROFESSIONAL EXPERIENCE',
        ];
        for (const exp of r?.experience || []) {
            lines.push(`${exp.title} | ${exp.company} | ${exp.period}`);
            for (const b of exp.bullets || []) lines.push(`• ${b}`);
            lines.push('');
        }
        lines.push('EDUCATION');
        for (const edu of r?.education || []) {
            lines.push(`${edu.degree} — ${edu.school} (${edu.year})`);
        }
        return lines.join('\n');
    };

    const isFormattingIssue = (issue: string) =>
        /\b(format|formatting|layout|readability|spacing|section\s+structure|visual|presentation|alignment)\b/i.test(issue);

    const getProfileSignals = (text: string) => ({
        hasLinkedIn: /(?:https?:\/\/)?(?:www\.)?linkedin\.com\/[^\s)]+/i.test(text),
        hasEmail: /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(text),
        hasPhone: /(?:\+?\d[\d().\-\s]{7,}\d)/.test(text),
        hasMetrics: /\b\d+(\.\d+)?\s?(%|x|k|m|b)\b|\b\d{3,}\b/i.test(text),
        hasDates: /\b(?:19|20)\d{2}\b|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b/i.test(text),
    });

    const buildAtsQualityHints = (validation: any): string[] => {
        const scores = validation?.scores || {};
        const ats = Number(scores?.ats_friendliness ?? 0);
        const quality = Number(scores?.achievement_quality ?? 0);
        const completeness = Number(scores?.completeness ?? 0);
        const missing: string[] = (validation?.missing_fields || []).map((m: any) => String(m).toLowerCase());
        const hints: string[] = [];

        if (ats < 5) {
            hints.push('Use standard ATS section headers exactly once: PROFESSIONAL SUMMARY, CORE COMPETENCIES, PROFESSIONAL EXPERIENCE, EDUCATION.');
            hints.push('Mirror important role keywords in summary, skills, and experience bullets.');
            hints.push('Use machine-readable date formats consistently (e.g., Jan 2022 - Mar 2024).');
        }
        if (quality < 5) {
            hints.push('Rewrite bullets using Action + Scope + Measurable Result structure.');
            hints.push('Add concrete impact metrics (%, revenue, time saved, latency, scale).');
        }
        if (completeness < 5) {
            hints.push('Ensure all core fields are complete: contact details, titles, companies, dates, education, and skills.');
        }
        if (missing.some(m => m.includes('linkedin'))) {
            hints.push('If present in the profile text, include the full LinkedIn URL in contact.linkedin.');
        }

        return Array.from(new Set(hints));
    };

    const getTopImprovementInputs = (validation: any): string[] => {
        const rawIssues: string[] = (validation?.top_issues || validation?.issues || []).filter((i: string) => !isFormattingIssue(i));
        const rawSuggestions: string[] = (validation?.suggested_improvements || validation?.improvements || []).filter((s: string) => !isFormattingIssue(s));
        const missing: string[] = validation?.missing_fields || [];
        const atsHints = buildAtsQualityHints(validation);

        const prioritized = [
            ...missing.map(f => `Add missing field from source text: ${f}`),
            ...rawIssues,
            ...rawSuggestions,
            ...atsHints,
        ].map(v => String(v).trim()).filter(Boolean);

        return Array.from(new Set(prioritized)).slice(0, MAX_TOP_INPUTS);
    };

    const buildRefinementInstructions = (validation: any, profileText: string): string => {
        const topInputs = getTopImprovementInputs(validation);
        const signals = getProfileSignals(profileText);

        const instructionParts: string[] = [
            'AUTO-FIX REQUIREMENT: Handle all formatting/layout improvements internally and silently.',
            `SOURCE CHECKS: LinkedIn ${signals.hasLinkedIn ? 'found' : 'missing'}, email ${signals.hasEmail ? 'found' : 'missing'}, phone ${signals.hasPhone ? 'found' : 'missing'}, metrics ${signals.hasMetrics ? 'found' : 'missing'}, dates ${signals.hasDates ? 'found' : 'missing'}.`,
            'For missing contact fields, extract from source text if present. Do NOT fabricate facts.',
        ];

        if (topInputs.length) {
            instructionParts.push(`Apply only these top ${topInputs.length} ATS/quality improvements now:\n${topInputs.map(s => `- ${s}`).join('\n')}`);
        }

        return instructionParts.join('\n\n');
    };

    const handleSave = async (overwrite: boolean) => {
        const raw = newFilename.trim();
        const fname = overwrite ? selectedFile! : (raw.match(/\.\w+$/) ? raw : raw + '.docx');
        if (!fname) return;
        setSaving(true);
        try {
            await api.post('/resumes/save-generated', {
                original_filename: selectedFile,
                new_filename: overwrite ? null : fname,
                resume_json: resume,
                validation: outputValidation,
            });
            setSaveSuccess(fname);
            setShowNewNameInput(false);
            setSelectedFile(null);
            await refreshResumes();
        } catch (err) {
            console.error('Save failed:', err);
        } finally {
            setSaving(false);
        }
    };

    const handleGenerate = async (overrideRefinementInstructions?: unknown) => {
        if (generating) return;
        if (!profile.trim()) return;
        setGenerating(true);
        setResume(null);
        setOutputValidation(null);
        setFieldValidation(null);
        setValidationError(null);
        setInputValidationWarning(null);
        setAccepted(false);
        setSaveSuccess(null);
        setShowNewNameInput(false);
        setNewFilename('');
        const overrideInstructions = typeof overrideRefinementInstructions === 'string'
            ? overrideRefinementInstructions
            : null;
        const currentRefinementInstructions = overrideInstructions
            ?? refinementInstructions
            ?? (selectedFile ? 'Improve the clarity, impact, and ATS compatibility of this resume. Strengthen bullet points with action verbs. Ensure consistent formatting and section structure throughout. Extract all contact details from the text (name, email, phone, LinkedIn URL, location) and populate the contact section — do NOT fabricate any contact info. Preserve all existing content.' : null);
        setRefinementInstructions(null);
        setError(null);
        setActiveTab('overview');
        try {
            const response = await api.post('/generate/resume', {
                profile,
                ...(currentRefinementInstructions ? { refinement_instructions: currentRefinementInstructions } : {}),
            });
            const resumeJson = response.data.resume_json;
            setResume(resumeJson);
            if (resumeJson) setProfile(resumeJsonToText(resumeJson));
            if (response.data.field_validation) setFieldValidation(response.data.field_validation);
            if (response.data.output_validation) setOutputValidation(response.data.output_validation);
            if (response.data.input_validation_warning) setInputValidationWarning(response.data.input_validation_warning);
        } catch (err: any) {
            if (err.response?.status === 422 && err.response?.data?.detail?.error === 'not_a_resume') {
                setValidationError(err.response.data.detail.validation);
            } else {
                const msg = err.response?.data?.detail || err.message || 'Resume generation failed. Please try again.';
                setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
        } finally {
            setGenerating(false);
        }
    };

    const hasRequiredFieldErrors = fieldValidation?.errors?.length > 0;

    const handleExport = async () => {
        if (!resume) return;
        if (hasRequiredFieldErrors) {
            setError('Cannot export: required fields are missing. Please fix the errors shown below before exporting.');
            return;
        }
        try {
            const response = await api.post('/generate/export', resume, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'resume.docx');
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error('Export failed:', err);
        }
    };

    const handleRefine = async () => {
        if (!resume) return;
        setGenerating(true);
        setError(null);
        try {
            const response = await api.post('/generate/refine', resume);
            setResume(response.data.resume_json);
            if (response.data.field_validation) {
                setFieldValidation(response.data.field_validation);
            }
            if (response.data.output_validation) {
                setOutputValidation(response.data.output_validation);
            }
        } catch (err: any) {
            const msg = err.response?.data?.detail || err.message || 'Refine failed. Please try again.';
            setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setGenerating(false);
        }
    };

    const renderTabContent = () => {
        if (!resume) return null;

        switch (activeTab) {
            case 'contact':
                return <ContactTab resume={resume} />;
            case 'summary':
                return <SummaryTab resume={resume} />;
            case 'skills':
                return <SkillsTab resume={resume} />;
            case 'experience':
                return <ExperienceTab resume={resume} />;
            case 'education':
                return <EducationTab resume={resume} />;
            case 'certifications':
                return <CertificationsTab resume={resume} />;
            case 'projects':
                return <ProjectsTab resume={resume} />;
            case 'overview':
            default:
                return <FullPreviewTab resume={resume} />;
        }
    };

    return (
        <div className="space-y-8">
            <div className="glass-card p-6 border-slate-100 bg-white/80">
                <h1 className="text-xl font-black text-slate-900 tracking-tight">AI Resume Generator</h1>
                <p className="text-slate-500 text-sm font-medium mt-0.5">Transform profile descriptions into professionally formatted, structured resumes.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* ── Left: Resume Picker + Input + Tips ── */}
                <div className="space-y-6">

                    {/* Resume Picker */}
                    <div className="glass-card overflow-hidden border-slate-100 shadow-sm">
                        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-50 to-white">
                            <h3 className="font-bold text-sm text-slate-700 flex items-center gap-2">
                                <FileText className="w-4 h-4 text-primary-400" />
                                Select Resume to Refine
                            </h3>
                            <span className="text-[10px] font-black text-white bg-primary-500 px-2 py-0.5 rounded-full">
                                {myResumes.length}
                            </span>
                        </div>

                        {myResumes.length === 0 ? (
                            <div className="py-8 text-center text-slate-300 text-sm font-medium italic">
                                No resumes found — upload via Resume Manager.
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-50 max-h-56 overflow-y-auto">
                                {myResumes.map(({ filename, validation }, i) => {
                                    const ext = filename.split('.').pop()?.toUpperCase() || '';
                                    const totalScore: number | null = validation?.total_score ?? null;
                                    const atsScore: number | null = validation?.scores?.ats_friendliness ?? null;
                                    const completeness: number | null = validation?.scores?.completeness ?? null;
                                    const quality: number | null = validation?.scores?.achievement_quality ?? null;
                                    const scorePct = totalScore !== null ? Math.round((totalScore / 30) * 100) : null;
                                    const classConfig = validation?.classification
                                        ? (classificationConfig[validation.classification] || classificationConfig.resume_valid_good)
                                        : null;
                                    const barColor = scorePct !== null
                                        ? scorePct >= 83 ? 'bg-emerald-400' : scorePct >= 60 ? 'bg-amber-400' : 'bg-red-400'
                                        : 'bg-slate-200';
                                    const isSelected = selectedFile === filename;

                                    return (
                                        <motion.button
                                            key={i}
                                            initial={{ opacity: 0, y: 4 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: i * 0.04 }}
                                            onClick={() => handleSelectResume(filename)}
                                            className={`w-full text-left px-4 py-3 transition-colors border-l-2 ${isSelected ? 'bg-primary-50 border-primary-500' : 'hover:bg-slate-50/70 border-transparent'}`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 border ${isSelected ? 'bg-primary-100 border-primary-200' : 'bg-slate-50 border-slate-100'}`}>
                                                    {isSelected
                                                        ? <CheckCircle2 className="w-4 h-4 text-primary-500" />
                                                        : <FileText className="w-4 h-4 text-slate-400" />
                                                    }
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className={`text-xs font-bold truncate ${isSelected ? 'text-primary-700' : 'text-slate-700'}`}>{filename}</p>
                                                    <div className="flex items-center gap-1.5 mt-0.5">
                                                        <span className="text-[9px] font-black text-slate-400 tracking-widest">{ext}</span>
                                                        {classConfig && (
                                                            <span className={`text-[9px] font-black uppercase px-1 py-0.5 rounded border ${classConfig.color} ${classConfig.bg} ${classConfig.border}`}>
                                                                {classConfig.label}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                                <ChevronRight className={`w-3.5 h-3.5 flex-shrink-0 ${isSelected ? 'text-primary-400' : 'text-slate-200'}`} />
                                            </div>

                                            {totalScore !== null && (
                                                <div className="mt-2 ml-11 space-y-1.5">
                                                    <div className="flex items-center gap-2">
                                                        <div className="flex-1 h-1 bg-slate-100 rounded-full overflow-hidden">
                                                            <motion.div
                                                                initial={{ width: 0 }}
                                                                animate={{ width: `${scorePct}%` }}
                                                                transition={{ duration: 0.7, ease: 'easeOut' }}
                                                                className={`h-full rounded-full ${barColor}`}
                                                            />
                                                        </div>
                                                        <span className="text-[10px] font-black text-slate-400 flex-shrink-0">{totalScore}/30</span>
                                                    </div>
                                                    <div className="flex gap-1 flex-wrap">
                                                        {atsScore !== null && (
                                                            <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${atsScore >= 4 ? 'text-emerald-500' : atsScore >= 3 ? 'text-amber-500' : 'text-red-400'}`}>ATS {atsScore}/5</span>
                                                        )}
                                                        {quality !== null && (
                                                            <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${quality >= 4 ? 'text-emerald-500' : quality >= 3 ? 'text-amber-500' : 'text-red-400'}`}>Quality {quality}/5</span>
                                                        )}
                                                        {completeness !== null && (
                                                            <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${completeness >= 4 ? 'text-emerald-500' : completeness >= 3 ? 'text-amber-500' : 'text-red-400'}`}>Complete {completeness}/5</span>
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </motion.button>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Editor */}
                    <div ref={editorRef} className="glass-card p-8 flex flex-col gap-6 bg-white/70 border-slate-100 shadow-sm">
                        {selectedFile && (
                            <div className="flex items-center gap-2 px-3 py-2 bg-primary-50 border border-primary-100 rounded-xl">
                                <CheckCircle2 className="w-4 h-4 text-primary-500 flex-shrink-0" />
                                <p className="text-xs font-bold text-primary-700 truncate flex-1">Editing: {selectedFile}</p>
                                {loadingText && <Loader2 className="w-3.5 h-3.5 text-primary-400 animate-spin flex-shrink-0" />}
                            </div>
                        )}
                        <FormTextarea
                            label="Candidate Profile & Highlights"
                            value={profile}
                            onChange={setProfile}
                            placeholder="Select a resume above, or describe the candidate's experience, skills, and achievements..."
                            height="h-64"
                        />
                        <ActionButton
                            onClick={handleGenerate}
                            loading={generating}
                            disabled={!profile.trim() || loadingText}
                            icon={<Sparkles className="w-5 h-5" />}
                            label={selectedFile ? 'Refine with AI' : 'Generate AI Resume'}
                            loadingLabel="Crafting Professional Content..."
                        />
                    </div>

                    {/* Tips */}
                    <div className="glass-card p-8 border-primary-100 bg-primary-50/50 shadow-sm">
                        <h4 className="text-[10px] font-black text-primary-700 uppercase tracking-widest mb-4 flex items-center gap-2">
                            <Sparkles className="w-3 h-3" /> AI Writing Tips
                        </h4>
                        <ul className="text-xs text-primary-800 space-y-3 font-medium">
                            {[
                                'Include name, email, phone, and location for complete contact info.',
                                'Include specific metrics and achievements (e.g., "Increased sales by 20%").',
                                'Mention key technologies, certifications, and specialized skills.',
                                'Include education details with field of study for better results.',
                            ].map((tip, i) => (
                                <li key={i} className="flex items-start gap-2">
                                    <div className="w-1 h-1 bg-primary-400 rounded-full mt-1.5 flex-shrink-0" />
                                    {tip}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>

                {/* ── Right: Preview ── */}
                <div className="flex flex-col min-h-[600px]">
                    {validationError && (
                        <div className="mb-4">
                            <ValidationBanner validation={validationError} type="error" />
                        </div>
                    )}
                    {inputValidationWarning && !validationError && (
                        <div className="mb-4">
                            <ValidationBanner validation={inputValidationWarning} type="warning" onDismiss={() => setInputValidationWarning(null)} />
                        </div>
                    )}

                    {error && !validationError && (
                        <div className="mb-4">
                            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 font-medium">
                                <div className="flex items-center gap-2 mb-1 font-black text-[10px] uppercase tracking-widest text-red-500">
                                    <AlertCircle className="w-3.5 h-3.5" /> Generation Error
                                </div>
                                {error}
                            </div>
                        </div>
                    )}

                    {!resume && !generating && !validationError && !error && (
                        <EmptyState
                            icon={<FileText className="w-10 h-10" />}
                            heading="Preview Engine Standby"
                            description="Your AI-generated resume preview will materialize here once processed."
                        />
                    )}

                    {generating && (
                        <LoadingOverlay
                            icon={<FileText className="w-10 h-10 text-primary-200" />}
                            message="Architecting Sections..."
                        />
                    )}

                    {resume && (
                        <div className="flex-1 flex flex-col gap-4">
                            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex-1 glass-card flex flex-col shadow-xl">
                                {/* Header with export */}
                                <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-white">
                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                        <FileText className="w-3.5 h-3.5" /> Live Preview
                                    </span>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={handleRefine}
                                            disabled={generating}
                                            className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white px-3 py-2 rounded-lg text-xs font-bold transition-all shadow-md active:scale-95 disabled:opacity-50"
                                            title="Re-extract skills from experience text and re-validate"
                                        >
                                            <Sparkles className="w-3.5 h-3.5" /> Refine Skills
                                        </button>
                                        <button
                                            onClick={handleExport}
                                            disabled={hasRequiredFieldErrors}
                                            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-md active:scale-95 ${
                                                hasRequiredFieldErrors
                                                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                                                    : 'bg-slate-900 hover:bg-slate-800 text-white'
                                            }`}
                                            title={hasRequiredFieldErrors ? 'Fix required field errors before exporting' : 'Export as DOCX'}
                                        >
                                            <Download className="w-3.5 h-3.5" /> Export DOCX
                                        </button>
                                    </div>
                                </div>

                                {/* Category tabs */}
                                <div className="border-b border-slate-100 bg-slate-50/50 overflow-x-auto">
                                    <div className="flex min-w-max">
                                        {TABS.map(tab => {
                                            const status = tab.id === 'overview' ? null : getSectionStatus(resume, tab.id);
                                            const Icon = tab.icon;
                                            const isActive = activeTab === tab.id;
                                            return (
                                                <button
                                                    key={tab.id}
                                                    onClick={() => setActiveTab(tab.id)}
                                                    className={`flex items-center gap-1.5 px-3 py-2.5 text-[10px] font-bold uppercase tracking-wider transition-all border-b-2 whitespace-nowrap ${
                                                        isActive
                                                            ? 'border-primary-500 text-primary-700 bg-white'
                                                            : 'border-transparent text-slate-400 hover:text-slate-600 hover:bg-white/50'
                                                    }`}
                                                >
                                                    <Icon className="w-3 h-3" />
                                                    {tab.label}
                                                    {status && <StatusDot status={status} />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                </div>

                                {/* Tab content */}
                                <div className="flex-1 p-8 bg-white text-slate-900 overflow-y-auto max-h-[650px] shadow-inner font-serif selection:bg-primary-100">
                                    {renderTabContent()}
                                </div>
                            </motion.div>

                            {/* Field validation (structural checks) */}
                            {fieldValidation && (fieldValidation.errors?.length > 0 || fieldValidation.warnings?.length > 0) && (
                                <div className={`rounded-xl p-4 text-sm font-medium border ${fieldValidation.errors?.length > 0
                                    ? 'bg-red-50 border-red-200 text-red-700'
                                    : 'bg-amber-50 border-amber-200 text-amber-700'
                                }`}>
                                    <div className="flex items-center gap-2 mb-2 font-black text-[10px] uppercase tracking-widest">
                                        <AlertCircle className="w-3.5 h-3.5" />
                                        {fieldValidation.errors?.length > 0 ? 'Missing Required Fields' : 'Field Warnings'}
                                    </div>
                                    <ul className="space-y-1 text-xs">
                                        {(fieldValidation.errors || []).map((e: string, i: number) => (
                                            <li key={`e-${i}`} className="flex items-start gap-2">
                                                <span className="text-red-400 mt-0.5">&#8226;</span> {e}
                                            </li>
                                        ))}
                                        {(fieldValidation.warnings || []).map((w: string, i: number) => (
                                            <li key={`w-${i}`} className="flex items-start gap-2 text-amber-600">
                                                <span className="text-amber-400 mt-0.5">&#8226;</span> {w}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* AI quality validation */}
                            {outputValidation && (
                                <ValidationBanner
                                    validation={outputValidation}
                                    type={
                                        outputValidation.classification === 'not_resume' ||
                                            outputValidation.classification === 'resume_invalid_or_incomplete'
                                            ? 'error'
                                            : 'warning'
                                    }
                                    onDismiss={() => setOutputValidation(null)}
                                />
                            )}

                            {/* Quality Comparison */}
                            {(() => {
                                const fileValidation = myResumes.find(r => r.filename === selectedFile)?.validation;
                                // After "Refine Further", compare previous refinement → new refinement
                                // On first generation, compare original file → first refinement
                                const origValidation = prevRefinedValidation ?? fileValidation;
                                if (!origValidation && !outputValidation) return null;

                                const renderScores = (v: any, label: string) => {
                                    const total: number | null = v?.total_score ?? null;
                                    const pct = total !== null ? Math.round((total / 30) * 100) : null;
                                    const ats: number | null = v?.scores?.ats_friendliness ?? null;
                                    const quality: number | null = v?.scores?.achievement_quality ?? null;
                                    const complete: number | null = v?.scores?.completeness ?? null;
                                    const barColor = pct !== null ? (pct >= 83 ? 'bg-emerald-400' : pct >= 60 ? 'bg-amber-400' : 'bg-red-400') : 'bg-slate-200';
                                    const classConfig = v?.classification ? (classificationConfig[v.classification] || classificationConfig.resume_valid_good) : null;
                                    return (
                                        <div className="flex-1 space-y-2">
                                            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{label}</p>
                                            {total !== null ? (
                                                <>
                                                    <div className="flex items-center gap-2">
                                                        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                            <motion.div initial={{ width: 0 }} animate={{ width: `${pct}%` }} transition={{ duration: 0.7 }} className={`h-full rounded-full ${barColor}`} />
                                                        </div>
                                                        <span className="text-xs font-black text-slate-600 flex-shrink-0">{total}/30</span>
                                                    </div>
                                                    {classConfig && (
                                                        <span className={`inline-block text-[9px] font-black uppercase px-1.5 py-0.5 rounded border ${classConfig.color} ${classConfig.bg} ${classConfig.border}`}>{classConfig.label}</span>
                                                    )}
                                                    <div className="flex gap-1 flex-wrap">
                                                        {ats !== null && <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${ats >= 4 ? 'text-emerald-500' : ats >= 3 ? 'text-amber-500' : 'text-red-400'}`}>ATS {ats}/5</span>}
                                                        {quality !== null && <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${quality >= 4 ? 'text-emerald-500' : quality >= 3 ? 'text-amber-500' : 'text-red-400'}`}>Quality {quality}/5</span>}
                                                        {complete !== null && <span className={`text-[9px] font-black px-1.5 py-0.5 rounded bg-slate-50 border border-slate-100 ${complete >= 4 ? 'text-emerald-500' : complete >= 3 ? 'text-amber-500' : 'text-red-400'}`}>Complete {complete}/5</span>}
                                                    </div>
                                                </>
                                            ) : (
                                                <p className="text-[10px] text-slate-300 italic">No score available</p>
                                            )}
                                        </div>
                                    );
                                };

                                const origTotal = origValidation?.total_score ?? null;
                                const refinedTotal = outputValidation?.total_score ?? null;
                                const delta = (origTotal !== null && refinedTotal !== null) ? refinedTotal - origTotal : null;

                                return (
                                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-4 border-slate-100 bg-white/80">
                                        <div className="flex items-center justify-between mb-3">
                                            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1.5">
                                                <TrendingUp className="w-3 h-3" /> Quality Comparison
                                            </p>
                                            {delta !== null && (
                                                <span className={`text-xs font-black px-2 py-0.5 rounded-full flex items-center gap-1 ${delta > 0 ? 'text-emerald-700 bg-emerald-50' : delta < 0 ? 'text-red-600 bg-red-50' : 'text-slate-500 bg-slate-50'}`}>
                                                    {delta > 0 ? <TrendingUp className="w-3 h-3" /> : delta < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                                                    {delta > 0 ? `+${delta}` : delta} pts
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex gap-4">
                                            {renderScores(origValidation, prevRefinedValidation ? 'Previous Pass' : 'Original')}
                                            <div className="flex items-center self-start mt-4">
                                                <ArrowRight className="w-4 h-4 text-slate-300" />
                                            </div>
                                            {renderScores(outputValidation, 'Refined')}
                                        </div>

                                        {/* AI Feedback — always shown after generation */}
                                        {outputValidation && (() => {
                                            const topInputs = getTopImprovementInputs(outputValidation);
                                            const missing: string[] = outputValidation.missing_fields || [];
                                            if (!topInputs.length) return null;

                                            return (
                                                <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
                                                    <div className="space-y-1.5">
                                                        <p className="text-[9px] font-black uppercase tracking-widest flex items-center gap-1 text-primary-600">
                                                            <Sparkles className="w-2.5 h-2.5" /> Top {topInputs.length} inputs to improve ATS + quality
                                                        </p>
                                                        {topInputs.map((item, i) => (
                                                            <div key={`top-${i}`} className="flex items-start gap-1.5">
                                                                <span className="text-primary-400 mt-0.5 flex-shrink-0 text-[10px]">→</span>
                                                                <p className="text-[10px] text-slate-600 leading-snug">{item}</p>
                                                            </div>
                                                        ))}
                                                        {missing.length > 0 && (
                                                            <button
                                                                onClick={() => editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
                                                                className="mt-1 flex items-center gap-1.5 text-[10px] font-bold text-primary-600 hover:text-primary-500 transition-colors"
                                                            >
                                                                <PenLine className="w-3 h-3" /> Add missing info in the profile text box →
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })()}
                                    </motion.div>
                                );
                            })()}

                            {/* Accept / Refine actions */}
                            {!saveSuccess && (
                                <AnimatePresence mode="wait">
                                    {!accepted ? (
                                        <motion.div key="actions" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="flex gap-3">
                                            <button
                                                onClick={() => {
                                                    setPrevRefinedValidation(outputValidation);
                                                    const instructions = buildRefinementInstructions(outputValidation, profile);
                                                    void handleGenerate(instructions);
                                                }}
                                                className="flex-1 flex items-center justify-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-600 px-4 py-2.5 rounded-xl text-xs font-bold transition-all"
                                            >
                                                <RotateCcw className="w-3.5 h-3.5" /> Refine Further
                                            </button>
                                            <button
                                                onClick={() => setAccepted(true)}
                                                className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-md"
                                            >
                                                <CheckCircle2 className="w-3.5 h-3.5" /> Accept
                                            </button>
                                        </motion.div>
                                    ) : (
                                        <motion.div key="save" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="glass-card p-4 border-emerald-100 bg-emerald-50/40 space-y-3">
                                            <p className="text-[10px] font-black text-emerald-700 uppercase tracking-widest flex items-center gap-1.5">
                                                <Save className="w-3 h-3" /> Save Refined Resume
                                            </p>
                                            <div className="flex gap-2 flex-wrap">
                                                {selectedFile && (
                                                    <button
                                                        onClick={() => handleSave(true)}
                                                        disabled={saving}
                                                        className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-xs font-bold transition-all"
                                                    >
                                                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                                                        Replace "{selectedFile}"
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => setShowNewNameInput(v => !v)}
                                                    className="flex items-center gap-1.5 border border-slate-200 hover:bg-slate-50 text-slate-600 px-3 py-2 rounded-lg text-xs font-bold transition-all"
                                                >
                                                    <Save className="w-3 h-3" /> Save as New
                                                </button>
                                            </div>
                                            {showNewNameInput && (
                                                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="flex gap-2">
                                                    <input
                                                        value={newFilename}
                                                        onChange={e => setNewFilename(e.target.value)}
                                                        placeholder="my-refined-resume.docx"
                                                        className="flex-1 text-xs border border-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-primary-300"
                                                    />
                                                    <button
                                                        onClick={() => handleSave(false)}
                                                        disabled={saving || !newFilename.trim()}
                                                        className="flex items-center gap-1.5 bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-xs font-bold transition-all"
                                                    >
                                                        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
                                                        Save
                                                    </button>
                                                </motion.div>
                                            )}
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            )}

                            {/* Save success */}
                            {saveSuccess && (
                                <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="flex items-center gap-2.5 px-4 py-3 bg-emerald-50 border border-emerald-200 rounded-xl">
                                    <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                                    <p className="text-xs font-bold text-emerald-700">Saved as <span className="font-black">"{saveSuccess}"</span> — visible in Resume Manager.</p>
                                </motion.div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

/* ─── Section validation helper ──────────────── */
function SectionValidation({ fields, data }: { fields: { key: string; label: string }[]; data: any }) {
    return (
        <div className="mt-6 pt-4 border-t border-slate-100">
            <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-3">Field Validation</h4>
            <div className="grid grid-cols-2 gap-2">
                {fields.map(f => {
                    const val = data?.[f.key];
                    const present = Array.isArray(val) ? val.length > 0 : val && String(val).trim() !== '';
                    return (
                        <div key={f.key} className="flex items-center gap-2 text-[10px]">
                            {present
                                ? <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                                : <AlertCircle className="w-3 h-3 text-red-400" />
                            }
                            <span className={present ? 'text-slate-600 font-medium' : 'text-red-500 font-bold'}>{f.label}</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

/* ─── Tab: Contact ──────────────── */
function ContactTab({ resume }: { resume: any }) {
    const c = resume.contact || {};
    const fields = [
        { key: 'name', label: 'Full Name' },
        { key: 'email', label: 'Email' },
        { key: 'phone', label: 'Phone' },
        { key: 'location', label: 'Location' },
        { key: 'linkedin', label: 'LinkedIn URL' },
    ];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Contact Information</h3>
            <div className="space-y-4">
                {fields.map(f => (
                    <div key={f.key} className="flex items-start gap-4">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-wider w-24 shrink-0 pt-0.5">{f.label}</span>
                        <span className={`text-sm font-medium ${c[f.key] ? 'text-slate-800' : 'text-red-400 italic'}`}>
                            {c[f.key] || 'Not provided'}
                        </span>
                    </div>
                ))}
            </div>
            <SectionValidation fields={fields} data={c} />
        </div>
    );
}

/* ─── Tab: Summary ──────────────── */
function SummaryTab({ resume }: { resume: any }) {
    const charCount = (resume.summary || '').length;
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Professional Summary</h3>
            {resume.summary ? (
                <p className="text-sm leading-relaxed text-slate-700 text-justify font-medium">{resume.summary}</p>
            ) : (
                <p className="text-sm text-red-400 italic">No summary generated.</p>
            )}
            <div className="mt-4 flex items-center gap-3 text-[10px] text-slate-400 font-bold">
                <span>{charCount} characters</span>
                <span className="opacity-30">|</span>
                {charCount >= 150 ? (
                    <span className="flex items-center gap-1 text-emerald-500"><CheckCircle2 className="w-3 h-3" /> Good length</span>
                ) : charCount > 0 ? (
                    <span className="flex items-center gap-1 text-amber-500"><AlertCircle className="w-3 h-3" /> Could be more detailed</span>
                ) : (
                    <span className="flex items-center gap-1 text-red-400"><AlertCircle className="w-3 h-3" /> Missing</span>
                )}
            </div>
        </div>
    );
}

/* ─── Tab: Skills ──────────────── */
function SkillsTab({ resume }: { resume: any }) {
    const skills = resume.skills || [];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Core Competencies</h3>
            {skills.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                    {skills.map((s: string, i: number) => (
                        <span key={i} className="px-3 py-1.5 bg-primary-50 text-primary-700 rounded-full text-[11px] font-bold border border-primary-100">
                            {s}
                        </span>
                    ))}
                </div>
            ) : (
                <p className="text-sm text-red-400 italic">No skills generated.</p>
            )}
            <div className="mt-4 flex items-center gap-3 text-[10px] text-slate-400 font-bold">
                <span>{skills.length} skills</span>
                <span className="opacity-30">|</span>
                {skills.length >= 6 ? (
                    <span className="flex items-center gap-1 text-emerald-500"><CheckCircle2 className="w-3 h-3" /> Good coverage</span>
                ) : skills.length >= 1 ? (
                    <span className="flex items-center gap-1 text-amber-500"><AlertCircle className="w-3 h-3" /> Add more skills for better results</span>
                ) : (
                    <span className="flex items-center gap-1 text-red-400"><AlertCircle className="w-3 h-3" /> Missing</span>
                )}
            </div>
        </div>
    );
}

/* ─── Tab: Experience ──────────────── */
function ExperienceTab({ resume }: { resume: any }) {
    const experience = resume.experience || [];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Professional Experience</h3>
            {experience.length > 0 ? (
                <div className="space-y-8">
                    {experience.map((exp: any, i: number) => {
                        const bulletCount = (exp.bullets || []).length;
                        return (
                            <div key={i} className="group">
                                <div className="flex justify-between items-baseline mb-1">
                                    <h4 className="font-black text-sm text-slate-900 uppercase tracking-tight">{exp.title}</h4>
                                    <span className="text-[10px] italic font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded">{exp.period}</span>
                                </div>
                                <div className="flex items-center gap-2 mb-3">
                                    <p className="text-[10px] font-black text-primary-600 uppercase tracking-widest">{exp.company}</p>
                                    {exp.location && (
                                        <>
                                            <span className="text-slate-300 text-[10px]">|</span>
                                            <p className="text-[10px] font-bold text-slate-400">{exp.location}</p>
                                        </>
                                    )}
                                </div>
                                <ul className="space-y-2 list-none">
                                    {exp.bullets?.map((b: string, j: number) => (
                                        <li key={j} className="text-[11px] leading-relaxed text-slate-600 flex items-start gap-2 font-medium">
                                            <span className="text-slate-300 mt-1.5">•</span>
                                            {b}
                                        </li>
                                    ))}
                                </ul>
                                {bulletCount < 2 && (
                                    <p className="mt-2 text-[10px] text-amber-500 font-bold flex items-center gap-1">
                                        <AlertCircle className="w-3 h-3" /> Only {bulletCount} bullet{bulletCount === 1 ? '' : 's'} — recommend at least 2
                                    </p>
                                )}
                            </div>
                        );
                    })}
                </div>
            ) : (
                <p className="text-sm text-red-400 italic">No experience generated.</p>
            )}
            <div className="mt-4 text-[10px] text-slate-400 font-bold">
                {experience.length} position{experience.length !== 1 ? 's' : ''}
            </div>
        </div>
    );
}

/* ─── Tab: Education ──────────────── */
function EducationTab({ resume }: { resume: any }) {
    const education = resume.education || [];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Education</h3>
            {education.length > 0 ? (
                <div className="space-y-6">
                    {education.map((edu: any, i: number) => (
                        <div key={i} className="space-y-1">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-black text-slate-900">{edu.degree}</p>
                                    {edu.field_of_study && (
                                        <p className="text-[11px] font-bold text-primary-600">{edu.field_of_study}</p>
                                    )}
                                    <p className="text-[11px] text-slate-500 font-bold">{edu.school}</p>
                                </div>
                                <span className="text-[10px] font-black text-slate-400">{edu.year}</span>
                            </div>
                            {!edu.field_of_study && (
                                <p className="text-[10px] text-amber-500 font-bold flex items-center gap-1">
                                    <AlertCircle className="w-3 h-3" /> Field of study not specified
                                </p>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <p className="text-sm text-red-400 italic">No education generated.</p>
            )}
            <SectionValidation
                fields={[
                    { key: 'count', label: `${education.length} entr${education.length !== 1 ? 'ies' : 'y'}` },
                ]}
                data={{ count: education.length > 0 ? 'yes' : '' }}
            />
        </div>
    );
}

/* ─── Tab: Certifications ──────────────── */
function CertificationsTab({ resume }: { resume: any }) {
    const certs = resume.certifications || [];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Certifications</h3>
            {certs.length > 0 ? (
                <div className="space-y-4">
                    {certs.map((cert: any, i: number) => (
                        <div key={i} className="flex justify-between items-start border-b border-slate-50 pb-3">
                            <div>
                                <p className="text-sm font-bold text-slate-900">{cert.name}</p>
                                <p className="text-[11px] text-slate-500 font-medium">{cert.issuer}</p>
                            </div>
                            <span className="text-[10px] font-black text-slate-400">{cert.date}</span>
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-center py-8">
                    <Award className="w-8 h-8 text-slate-200 mx-auto mb-3" />
                    <p className="text-sm text-slate-400 font-medium">No certifications found in the input.</p>
                    <p className="text-[10px] text-slate-300 mt-1">Add certifications to the profile text to populate this section.</p>
                </div>
            )}
            <div className="mt-4 text-[10px] text-slate-400 font-bold">
                {certs.length} certification{certs.length !== 1 ? 's' : ''}
            </div>
        </div>
    );
}

/* ─── Tab: Projects ──────────────── */
function ProjectsTab({ resume }: { resume: any }) {
    const projects = resume.projects || [];
    return (
        <div>
            <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Projects</h3>
            {projects.length > 0 ? (
                <div className="space-y-6">
                    {projects.map((proj: any, i: number) => (
                        <div key={i} className="space-y-2">
                            <h4 className="text-sm font-black text-slate-900">{proj.name}</h4>
                            {proj.description && (
                                <p className="text-[11px] text-slate-600 font-medium leading-relaxed">{proj.description}</p>
                            )}
                            {proj.tech_stack && proj.tech_stack.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                    {proj.tech_stack.map((t: string, j: number) => (
                                        <span key={j} className="px-2 py-0.5 bg-slate-50 text-slate-600 rounded text-[10px] font-bold border border-slate-100">
                                            {t}
                                        </span>
                                    ))}
                                </div>
                            )}
                            {proj.outcomes && proj.outcomes.length > 0 && (
                                <ul className="space-y-1">
                                    {proj.outcomes.map((o: string, j: number) => (
                                        <li key={j} className="text-[11px] text-slate-500 flex items-start gap-2 font-medium">
                                            <span className="text-slate-300 mt-1">•</span>
                                            {o}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    ))}
                </div>
            ) : (
                <div className="text-center py-8">
                    <FolderOpen className="w-8 h-8 text-slate-200 mx-auto mb-3" />
                    <p className="text-sm text-slate-400 font-medium">No projects found in the input.</p>
                    <p className="text-[10px] text-slate-300 mt-1">Add project descriptions to the profile text to populate this section.</p>
                </div>
            )}
            <div className="mt-4 text-[10px] text-slate-400 font-bold">
                {projects.length} project{projects.length !== 1 ? 's' : ''}
            </div>
        </div>
    );
}

/* ─── Tab: Full Preview (original layout) ──────────────── */
function FullPreviewTab({ resume }: { resume: any }) {
    return (
        <div>
            {/* Contact Header */}
            <div className="text-center mb-10">
                <h2 className="text-4xl font-black uppercase tracking-tight border-b-2 border-slate-900 pb-3 mb-4">
                    {resume.contact?.name || 'CANDIDATE NAME'}
                </h2>
                <div className="text-[10px] font-bold text-slate-500 flex justify-center gap-4 uppercase tracking-widest flex-wrap">
                    {resume.contact?.email && <span>{resume.contact.email}</span>}
                    {resume.contact?.phone && <><span className="opacity-30">|</span><span>{resume.contact.phone}</span></>}
                    {resume.contact?.location && <><span className="opacity-30">|</span><span>{resume.contact.location}</span></>}
                    {resume.contact?.linkedin && <><span className="opacity-30">|</span><span>{resume.contact.linkedin}</span></>}
                </div>
            </div>

            {/* Summary */}
            {resume.summary && (
                <div className="mb-10">
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Professional Summary</h3>
                    <p className="text-xs leading-relaxed text-slate-700 text-justify font-medium">{resume.summary}</p>
                </div>
            )}

            {/* Skills */}
            {resume.skills && resume.skills.length > 0 && (
                <div className="mb-10">
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Core Competencies</h3>
                    <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                        {resume.skills.map((s: string, i: number) => (
                            <div key={i} className="text-[11px] flex items-center gap-3 font-semibold text-slate-800">
                                <div className="w-1.5 h-1.5 bg-primary-500 rounded-full shrink-0" />
                                {s}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Experience */}
            {resume.experience && resume.experience.length > 0 && (
                <div className="mb-10">
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Professional Experience</h3>
                    <div className="space-y-8">
                        {resume.experience.map((exp: any, i: number) => (
                            <div key={i} className="group">
                                <div className="flex justify-between items-baseline mb-1">
                                    <h4 className="font-black text-sm text-slate-900 group-hover:text-primary-600 transition-colors uppercase tracking-tight">{exp.title}</h4>
                                    <span className="text-[10px] italic font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded">{exp.period}</span>
                                </div>
                                <div className="flex items-center gap-2 mb-3">
                                    <p className="text-[10px] font-black text-primary-600 uppercase tracking-widest">{exp.company}</p>
                                    {exp.location && (
                                        <>
                                            <span className="text-slate-300 text-[10px]">|</span>
                                            <p className="text-[10px] font-bold text-slate-400">{exp.location}</p>
                                        </>
                                    )}
                                </div>
                                <ul className="space-y-2 list-none">
                                    {exp.bullets?.map((b: string, j: number) => (
                                        <li key={j} className="text-[11px] leading-relaxed text-slate-600 flex items-start gap-2 font-medium">
                                            <span className="text-slate-300 mt-1.5">•</span>
                                            {b}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Education */}
            {resume.education && resume.education.length > 0 && (
                <div className="mb-10">
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Education</h3>
                    <div className="space-y-4">
                        {resume.education.map((edu: any, i: number) => (
                            <div key={i} className="flex justify-between items-start">
                                <div>
                                    <p className="text-[11px] font-black text-slate-900">{edu.degree}</p>
                                    {edu.field_of_study && <p className="text-[10px] font-bold text-primary-600">{edu.field_of_study}</p>}
                                    <p className="text-[10px] text-slate-500 font-bold tracking-tight">{edu.school}</p>
                                </div>
                                <span className="text-[10px] font-black text-slate-400">{edu.year}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Certifications */}
            {resume.certifications && resume.certifications.length > 0 && (
                <div className="mb-10">
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Certifications</h3>
                    <div className="space-y-3">
                        {resume.certifications.map((cert: any, i: number) => (
                            <div key={i} className="flex justify-between items-center">
                                <div>
                                    <span className="text-[11px] font-bold text-slate-900">{cert.name}</span>
                                    <span className="mx-2 text-slate-300">•</span>
                                    <span className="text-[11px] text-slate-500 font-medium">{cert.issuer}</span>
                                </div>
                                <span className="text-[10px] font-black text-slate-400">{cert.date}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Projects */}
            {resume.projects && resume.projects.length > 0 && (
                <div>
                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Projects</h3>
                    <div className="space-y-4">
                        {resume.projects.map((proj: any, i: number) => (
                            <div key={i}>
                                <p className="text-[11px] font-black text-slate-900">{proj.name}</p>
                                {proj.description && <p className="text-[10px] text-slate-600 font-medium mt-1">{proj.description}</p>}
                                {proj.tech_stack && proj.tech_stack.length > 0 && (
                                    <p className="text-[10px] text-primary-600 font-bold mt-1">{proj.tech_stack.join(', ')}</p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default ResumeGenerator;
