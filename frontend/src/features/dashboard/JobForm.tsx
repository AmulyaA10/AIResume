import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
    const isEdit = !!id;
    const [formData, setFormData] = useState<any>(DEFAULTS);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isParsing, setIsParsing] = useState(false);

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

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.[0]) return;
        setIsParsing(true);
        try {
            const response = await jobsApi.parseUpload(e.target.files[0]);
            const parsed = response.data;
            setFormData((prev: any) => ({
                ...prev,
                title: parsed.title || prev.title,
                description: parsed.description || prev.description,
                skills_required: parsed.skills_required?.join(', ') || prev.skills_required,
                job_level: parsed.job_level || prev.job_level,
            }));
        } catch (error) {
            console.error('Failed to parse file:', error);
            alert('Failed to parse job description');
        } finally {
            setIsParsing(false);
        }
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
                <div className="glass-card p-6 border-dashed border-2 border-slate-700 flex flex-col items-center justify-center gap-4 group">
                    <div className="w-12 h-12 bg-blue-500/10 rounded-full flex items-center justify-center text-blue-500 group-hover:scale-110 transition-transform">
                        {isParsing ? <Loader2 size={24} className="animate-spin" /> : <Upload size={24} />}
                    </div>
                    <div className="text-center">
                        <label className="text-blue-500 font-bold cursor-pointer hover:text-blue-400">
                            Upload Job Description
                            <input type="file" className="hidden" onChange={handleFileChange} accept=".docx,.txt" />
                        </label>
                        <p className="text-xs text-slate-500 mt-1">AI will attempt to auto-fill the form fields below.</p>
                    </div>
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
