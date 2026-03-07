import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { ChevronLeft, Plus, Upload, Loader2, Save, Briefcase } from 'lucide-react';
import { PageHeader, LoadingOverlay } from '../../common';
import { jobsApi } from '../../api';

const DEFAULTS = {
    title: '', description: '', employer_name: '', employer_email: '',
    location_name: '', location_lat: 0, location_lng: 0,
    employment_type: 'FULL_TIME', job_category: 'IT', job_level: 'MID',
    skills_required: '', salary_min: 0, salary_max: 0,
    benefits: '', application_url: '',
};

const JobForm = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const isEdit = !!id;
    const [formData, setFormData] = useState<any>(() => {
        const parsed = (location.state as any)?.parsed;
        if (!parsed) return DEFAULTS;
        return {
            ...DEFAULTS,
            title: parsed.title || '',
            employer_name: parsed.employer_name || '',
            location_name: parsed.location_name || '',
            description: parsed.description || '',
            skills_required: parsed.skills_required?.join(', ') || '',
            job_level: parsed.job_level || 'MID',
        };
    });
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isParsing, setIsParsing] = useState(false);
    const [isDragOver, setIsDragOver] = useState(false);
    const [parseError, setParseError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const dropZoneRef = useRef<HTMLDivElement>(null);
    // Queue for multi-file drops
    const fileQueueRef = useRef<File[]>([]);
    const queueIndexRef = useRef(0);
    const savedCountRef = useRef(0);
    const dropHandlerRef = useRef<(files: File[]) => void>(() => {});
    const [queueStatus, setQueueStatus] = useState<{ current: number; total: number } | null>(null);
    const [queueErrors, setQueueErrors] = useState<Array<{ name: string; reason: string }>>([]);

    // Prevent the browser from opening dropped files anywhere on the page
    useEffect(() => {
        const prevent = (e: DragEvent) => e.preventDefault();
        document.addEventListener('dragover', prevent);
        document.addEventListener('drop', prevent);
        return () => {
            document.removeEventListener('dragover', prevent);
            document.removeEventListener('drop', prevent);
        };
    }, []);

    // Native drag-and-drop listeners — more reliable than React synthetic events
    useEffect(() => {
        const el = dropZoneRef.current;
        if (!el) return;

        const onDragOver = (e: DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(true);
        };

        const onDragLeave = (e: DragEvent) => {
            e.preventDefault();
            // Only clear when the cursor truly leaves the zone (not just a child element)
            if (!el.contains(e.relatedTarget as Node)) {
                setIsDragOver(false);
            }
        };

        const onDrop = (e: DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);
            const files = Array.from(e.dataTransfer?.files || []);
            if (files.length > 0) dropHandlerRef.current(files);
        };

        el.addEventListener('dragover', onDragOver);
        el.addEventListener('dragleave', onDragLeave);
        el.addEventListener('drop', onDrop);

        return () => {
            el.removeEventListener('dragover', onDragOver);
            el.removeEventListener('dragleave', onDragLeave);
            el.removeEventListener('drop', onDrop);
        };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (isEdit) {
            fetchJob();
        }
    }, [id]);

    const fetchJob = async () => {
        setIsLoading(true);
        try {
            const response = await jobsApi.get(id!);
            const data = response.data;
            setFormData({
                ...data,
                skills_required: data.skills_required?.join(', ') || '',
                benefits: data.benefits?.join(', ') || '',
            });
        } catch (error) {
            console.error('Failed to fetch job:', error);
            alert('Failed to load job definition');
            navigate('/jd');
        } finally {
            setIsLoading(false);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setFormData((prev: any) => ({ ...prev, [name]: value }));
    };

    const parseFile = async (file: File): Promise<{ success: boolean; errorMsg?: string }> => {
        setParseError(null);
        setIsParsing(true);
        try {
            const response = await jobsApi.parseUpload(file);
            const parsed = response.data;
            setFormData((prev: any) => ({
                ...prev,
                title: parsed.title || prev.title,
                employer_name: parsed.employer_name || prev.employer_name,
                location_name: parsed.location_name || prev.location_name,
                description: parsed.description || prev.description,
                skills_required: parsed.skills_required?.join(', ') || prev.skills_required,
                job_level: parsed.job_level || prev.job_level,
            }));
            return { success: true };
        } catch (error: any) {
            const detail = error?.response?.data?.detail;
            const errorMsg = detail || 'Failed to parse file. Please check the file and try again.';
            setParseError(errorMsg);
            if (fileInputRef.current) fileInputRef.current.value = '';
            return { success: false, errorMsg };
        } finally {
            setIsParsing(false);
        }
    };

    const processQueueItem = async () => {
        const files = fileQueueRef.current;
        const index = queueIndexRef.current;

        if (index >= files.length) {
            setQueueStatus(null);
            if (savedCountRef.current > 0) navigate('/jd');
            // If nothing was saved (all failed), stay on page so errors are visible
            return;
        }

        if (files.length > 1) setQueueStatus({ current: index + 1, total: files.length });
        setFormData(DEFAULTS);

        const result = await parseFile(files[index]);

        if (!result.success) {
            setQueueErrors(prev => [...prev, { name: files[index].name, reason: result.errorMsg! }]);
            queueIndexRef.current = index + 1;
            await processQueueItem(); // skip to next immediately
        }
        // On success: form is pre-filled — wait for user to save
    };

    const startQueue = (files: File[]) => {
        fileQueueRef.current = files;
        queueIndexRef.current = 0;
        savedCountRef.current = 0;
        setQueueErrors([]);
        processQueueItem();
    };

    const advanceQueue = () => {
        savedCountRef.current += 1;
        queueIndexRef.current += 1;
        processQueueItem();
    };

    // Keep the drop handler ref current on every render so the native listener
    // always calls the latest version (avoids stale closure over queue state).
    dropHandlerRef.current = startQueue;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(e.target.files || []);
        if (files.length > 0) startQueue(files);
        e.target.value = '';
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        try {
            const payload = {
                ...formData,
                skills_required: formData.skills_required.split(',').map((s: string) => s.trim()).filter(Boolean),
                benefits: formData.benefits.split(',').map((s: string) => s.trim()).filter(Boolean),
                salary_min: parseFloat(formData.salary_min) || 0,
                salary_max: parseFloat(formData.salary_max) || 0,
            };

            if (isEdit) {
                await jobsApi.update(id!, payload);
                navigate('/jd');
            } else {
                await jobsApi.create(payload);
                if (fileQueueRef.current.length > 1) {
                    advanceQueue();
                } else {
                    navigate('/jd');
                }
            }
        } catch (error) {
            console.error('Failed to save job:', error);
            alert('Failed to save job definition');
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) return <LoadingOverlay icon={<Briefcase className="w-10 h-10 text-blue-500" />} message="Loading job definition..." />;

    return (
        <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <button
                onClick={() => navigate('/jd')}
                className="flex items-center gap-1 text-slate-500 hover:text-slate-300 mb-2 text-sm transition-colors"
            >
                <ChevronLeft size={16} /> Back to Job Definitions
            </button>

            <PageHeader
                title={isEdit ? "Edit Job Definition" : "New Job Definition"}
                subtitle="Define the requirements and criteria for automated candidate matching."
            />

            {queueStatus && (
                <div style={{
                    background: '#1e40af', borderRadius: 10, padding: '12px 20px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    flexWrap: 'wrap', gap: 8,
                }}>
                    <span style={{ color: '#fff', fontWeight: 700, fontSize: '0.9rem' }}>
                        Processing file {queueStatus.current} of {queueStatus.total}
                    </span>
                    <span style={{ color: '#bfdbfe', fontSize: '0.8rem' }}>
                        Review the pre-filled details below, then save to continue to the next file.
                    </span>
                </div>
            )}

            {queueErrors.length > 0 && (
                <div style={{
                    background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.35)',
                    borderRadius: 10, padding: '12px 20px',
                }}>
                    <p style={{ color: '#f87171', fontWeight: 700, margin: '0 0 8px 0', fontSize: '0.85rem' }}>
                        Skipped {queueErrors.length} file{queueErrors.length > 1 ? 's' : ''} due to validation errors:
                    </p>
                    {queueErrors.map((err, i) => (
                        <p key={i} style={{ color: '#fca5a5', fontSize: '0.8rem', margin: '2px 0' }}>
                            <strong>{err.name}</strong> — {err.reason}
                        </p>
                    ))}
                </div>
            )}

            {!isEdit && (
                <div
                    ref={dropZoneRef}
                    onClick={() => !isParsing && fileInputRef.current?.click()}
                    style={{
                        border: isDragOver ? '3px solid #3b82f6' : '3px dashed #94a3b8',
                        borderRadius: '12px',
                        minHeight: '220px',
                        background: isDragOver ? 'rgba(59,130,246,0.1)' : '#1e293b',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '16px',
                        padding: '40px 24px',
                        cursor: isParsing ? 'wait' : 'pointer',
                        transition: 'border 0.15s, background 0.15s',
                        userSelect: 'none',
                        boxSizing: 'border-box',
                    }}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        style={{ display: 'none' }}
                        onChange={handleFileChange}
                        accept=".pdf,.docx,.txt"
                        disabled={isParsing}
                    />

                    <div style={{
                        width: 68, height: 68, borderRadius: '50%',
                        background: isDragOver ? 'rgba(59,130,246,0.3)' : 'rgba(59,130,246,0.15)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        color: isDragOver ? '#93c5fd' : '#60a5fa',
                        transform: isDragOver ? 'scale(1.12)' : 'scale(1)',
                        transition: 'all 0.15s',
                    }}>
                        {isParsing ? <Loader2 size={32} className="animate-spin" /> : <Upload size={32} />}
                    </div>

                    <div style={{ textAlign: 'center' }}>
                        <p style={{ fontSize: '1.1rem', fontWeight: 700, margin: '0 0 6px 0',
                            color: isDragOver ? '#93c5fd' : '#f1f5f9' }}>
                            {isParsing
                            ? `Parsing${queueStatus ? ` file ${queueStatus.current} of ${queueStatus.total}` : ''}…`
                            : isDragOver ? 'Release to upload'
                            : 'Drop your job description here'}
                        </p>
                        <p style={{ fontSize: '0.875rem', color: '#94a3b8', margin: 0 }}>
                            {isParsing ? 'AI is extracting job details…' : 'or click anywhere in this box to browse'}
                        </p>
                        <p style={{ fontSize: '0.7rem', color: '#64748b', marginTop: 12,
                            textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 700 }}>
                            Accepted formats &nbsp;·&nbsp; PDF &nbsp;·&nbsp; Word (.docx) &nbsp;·&nbsp; Text (.txt)
                        </p>
                    </div>

                    {parseError && (
                        <div style={{
                            background: 'rgba(239,68,68,0.12)',
                            border: '1px solid rgba(239,68,68,0.4)',
                            borderRadius: 8, padding: '10px 16px', maxWidth: 440,
                        }}>
                            <p style={{ fontSize: '0.875rem', color: '#f87171', margin: 0 }}>{parseError}</p>
                        </div>
                    )}
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
                <div className="glass-card p-8 space-y-6 bg-white">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="md:col-span-2">
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Job Title *</label>
                            <input
                                required
                                name="title"
                                value={formData.title}
                                onChange={handleChange}
                                placeholder="e.g. Senior Frontend Engineer"
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Employer Name *</label>
                            <input
                                required
                                name="employer_name"
                                value={formData.employer_name}
                                onChange={handleChange}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Employer Email</label>
                            <input
                                name="employer_email"
                                type="email"
                                value={formData.employer_email}
                                onChange={handleChange}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Location</label>
                            <input
                                name="location_name"
                                value={formData.location_name}
                                onChange={handleChange}
                                placeholder="e.g. Remote, San Francisco, CA"
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Employment Type</label>
                            <select
                                name="employment_type"
                                value={formData.employment_type}
                                onChange={handleChange}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            >
                                <option value="FULL_TIME">Full Time</option>
                                <option value="PART_TIME">Part Time</option>
                                <option value="CONTRACT">Contract</option>
                                <option value="FREELANCE">Freelance</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Job Category</label>
                            <select
                                name="job_category"
                                value={formData.job_category}
                                onChange={handleChange}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            >
                                {['IT', 'Finance', 'Marketing', 'Sales', 'Engineering', 'Healthcare', 'Legal', 'Other'].map(c =>
                                    <option key={c} value={c}>{c}</option>
                                )}
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Experience Level</label>
                            <select
                                name="job_level"
                                value={formData.job_level}
                                onChange={handleChange}
                                className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            >
                                <option value="JUNIOR">Junior</option>
                                <option value="MID">Mid</option>
                                <option value="SENIOR">Senior</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Required Skills (comma-separated)</label>
                        <input
                            name="skills_required"
                            value={formData.skills_required}
                            onChange={handleChange}
                            placeholder="React, TypeScript, Node.js, AWS"
                            className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-black text-slate-400 uppercase tracking-widest mb-2">Job Description *</label>
                        <textarea
                            required
                            name="description"
                            value={formData.description}
                            onChange={handleChange}
                            rows={8}
                            placeholder="Paste the full job description here..."
                            className="w-full bg-slate-50 border border-slate-200 text-slate-900 rounded-lg px-4 py-2.5 focus:ring-2 focus:ring-blue-500 outline-none transition-all resize-none"
                        />
                    </div>

                    <div className="flex gap-4 pt-4">
                        <button
                            type="submit"
                            disabled={isSaving}
                            className="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50"
                        >
                            {isSaving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
                            {isEdit
                                ? 'Update Definition'
                                : queueStatus && queueStatus.current < queueStatus.total
                                    ? `Save & Continue (${queueStatus.total - queueStatus.current} remaining)`
                                    : 'Save Definition'}
                        </button>
                        <button
                            type="button"
                            onClick={() => navigate('/jd')}
                            className="px-8 py-3 rounded-lg font-bold text-slate-400 hover:bg-slate-50 transition-all"
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
};

export default JobForm;
