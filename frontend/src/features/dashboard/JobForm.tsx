import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ChevronLeft, Plus, Upload, Loader2, Save, Briefcase, FileText, AlertCircle } from 'lucide-react';
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
    const isEdit = !!id;
    const [formData, setFormData] = useState<any>(DEFAULTS);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isParsing, setIsParsing] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [parseError, setParseError] = useState<string | null>(null);

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

    // Required fields that must be found in the document
    const REQUIRED_PARSED_FIELDS: Array<{ key: string; label: string }> = [
        { key: 'title', label: 'Job Title' },
        { key: 'employer_name', label: 'Employer Name' },
        { key: 'description', label: 'Job Description' },
    ];

    const processFile = async (file: File) => {
        const allowed = ['.docx', '.txt'];
        const ext = '.' + file.name.split('.').pop()?.toLowerCase();
        if (!allowed.includes(ext)) {
            setParseError(`Invalid file type. Please upload a .docx or .txt file.`);
            return;
        }

        setIsParsing(true);
        setParseError(null);
        try {
            const response = await jobsApi.parseUpload(file);
            const parsed = response.data;

            // Validate that required fields were found in the document
            const missing = REQUIRED_PARSED_FIELDS.filter(f => !parsed[f.key]?.toString().trim());
            if (missing.length > 0) {
                setParseError(
                    `Document rejected: the following required fields were not found — ${missing.map(f => f.label).join(', ')}. Please ensure the document contains this information.`
                );
                return;
            }

            setFormData((prev: any) => ({
                ...prev,
                title: parsed.title || prev.title,
                employer_name: parsed.employer_name || prev.employer_name,
                location_name: parsed.location_name || prev.location_name,
                description: parsed.description || prev.description,
                skills_required: parsed.skills_required?.join(', ') || prev.skills_required,
                job_level: parsed.job_level || prev.job_level,
            }));
        } catch (error) {
            console.error('Failed to parse file:', error);
            setParseError('Failed to parse job description. Please try again.');
        } finally {
            setIsParsing(false);
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0]) return;
        processFile(e.target.files[0]);
        e.target.value = ''; // reset so same file can be re-selected
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) processFile(file);
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
            } else {
                await jobsApi.create(payload);
            }
            navigate('/jd');
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

            {!isEdit && (
                <div className="space-y-2">
                    <div
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        className={`glass-card p-6 border-dashed border-2 flex flex-col items-center justify-center gap-4 transition-all cursor-pointer
                            ${isDragging
                                ? 'border-blue-400 bg-blue-500/10 scale-[1.01]'
                                : 'border-slate-700 hover:border-slate-500 group'
                            }`}
                    >
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-transform
                            ${isDragging ? 'bg-blue-500/20 text-blue-400 scale-110' : 'bg-blue-500/10 text-blue-500 group-hover:scale-110'}`}>
                            {isParsing
                                ? <Loader2 size={24} className="animate-spin" />
                                : isDragging
                                    ? <FileText size={24} />
                                    : <Upload size={24} />
                            }
                        </div>
                        <div className="text-center">
                            {isParsing ? (
                                <p className="text-blue-400 font-bold">Parsing document...</p>
                            ) : isDragging ? (
                                <p className="text-blue-400 font-bold">Drop to upload</p>
                            ) : (
                                <label className="text-blue-500 font-bold cursor-pointer hover:text-blue-400">
                                    Drag & drop or click to upload Job Description
                                    <input type="file" className="hidden" onChange={handleFileChange} accept=".docx,.txt" />
                                </label>
                            )}
                            <p className="text-xs text-slate-500 mt-1">
                                Accepts .docx or .txt — must contain Job Title, Employer Name, and Job Description.
                            </p>
                        </div>
                    </div>
                    {parseError && (
                        <div className="flex items-start gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3">
                            <AlertCircle size={16} className="mt-0.5 shrink-0" />
                            <span>{parseError}</span>
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
                            {isEdit ? 'Update Definition' : 'Save Definition'}
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
