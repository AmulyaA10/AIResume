import React, { useState } from 'react';
import { FileText, Loader2, Download, Sparkles, Send, User } from 'lucide-react';
import api from '../api';
import { motion, AnimatePresence } from 'framer-motion';

const ResumeGenerator = () => {
    const [profile, setProfile] = useState('');
    const [generating, setGenerating] = useState(false);
    const [resume, setResume] = useState<any>(null);

    const handleGenerate = async () => {
        if (!profile.trim()) return;
        setGenerating(true);
        setResume(null);
        try {
            const response = await api.post('/generate/resume', { profile });
            setResume(response.data.resume_json);
        } catch (err) {
            console.error(err);
        } finally {
            setGenerating(false);
        }
    };

    const handleExport = async () => {
        if (!resume) return;
        try {
            const response = await api.post('/generate/export', resume, {
                responseType: 'blob'
            });
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

    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">AI Resume Generator</h1>
                <p className="text-slate-500 font-medium">Transform profile descriptions into professionally formatted, structured resumes.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-6">
                    <div className="glass-card p-8 flex flex-col gap-6 bg-white/70 border-slate-100 shadow-sm">
                        <div className="flex flex-col gap-2">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Candidate Profile & Highlights</span>
                            <textarea
                                value={profile}
                                onChange={(e) => setProfile(e.target.value)}
                                className="w-full h-80 bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm leading-relaxed font-medium text-slate-800 shadow-inner"
                                placeholder="Describe the candidate's experience, skills, and achievements in detail..."
                            />
                        </div>
                        <button
                            onClick={handleGenerate}
                            disabled={generating || !profile.trim()}
                            className="w-full bg-primary-600 hover:bg-primary-500 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-3 shadow-lg shadow-primary-500/20 disabled:opacity-50 transition-all"
                        >
                            {generating ? <Loader2 className="w-5 h-5 animate-spin" /> : <Sparkles className="w-5 h-5" />}
                            {generating ? 'Crafting Professional Content...' : 'Generate AI Resume'}
                        </button>
                    </div>

                    <div className="glass-card p-8 border-primary-100 bg-primary-50/50 shadow-sm">
                        <h4 className="text-[10px] font-black text-primary-700 uppercase tracking-widest mb-4 flex items-center gap-2">
                            <Sparkles className="w-3 h-3" /> AI Writing Tips
                        </h4>
                        <ul className="text-xs text-primary-800 space-y-3 font-medium">
                            <li className="flex items-start gap-2">
                                <div className="w-1 h-1 bg-primary-400 rounded-full mt-1.5" />
                                Include specific metrics and achievements (e.g., "Increased sales by 20%").
                            </li>
                            <li className="flex items-start gap-2">
                                <div className="w-1 h-1 bg-primary-400 rounded-full mt-1.5" />
                                Mention key technologies and specialized soft skills.
                            </li>
                            <li className="flex items-start gap-2">
                                <div className="w-1 h-1 bg-primary-400 rounded-full mt-1.5" />
                                The AI will automatically structure education and job history logically.
                            </li>
                        </ul>
                    </div>
                </div>

                <div className="flex flex-col min-h-[600px]">
                    {!resume && !generating && (
                        <div className="flex-1 glass-card border-dashed border-2 border-slate-200 flex flex-col items-center justify-center p-12 text-center bg-slate-50/30">
                            <div className="w-20 h-20 bg-white rounded-3xl flex items-center justify-center mb-6 border border-slate-100 shadow-sm text-slate-200">
                                <FileText className="w-10 h-10" />
                            </div>
                            <h3 className="text-xl font-bold text-slate-400">Preview Engine Standby</h3>
                            <p className="text-slate-400 text-sm mt-2 max-w-xs font-medium">Your AI-generated resume preview will materialize here once processed.</p>
                        </div>
                    )}

                    {generating && (
                        <div className="flex-1 glass-card flex flex-col items-center justify-center p-12 bg-white/80 border-primary-100">
                            <div className="w-24 h-24 relative">
                                <div className="absolute inset-0 rounded-2xl border-4 border-primary-100 animate-pulse" />
                                <div className="absolute inset-0 rounded-2xl border-t-4 border-primary-500 animate-spin" />
                                <FileText className="absolute inset-0 m-auto w-10 h-10 text-primary-200" />
                            </div>
                            <p className="mt-8 text-primary-600 font-black uppercase tracking-[0.2em] text-xs">Architecting Sections...</p>
                        </div>
                    )}

                    {resume && (
                        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex-1 glass-card flex flex-col shadow-xl">
                            <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-white">
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                    <FileText className="w-3.5 h-3.5" /> Live Preview
                                </span>
                                <button
                                    onClick={handleExport}
                                    className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-md active:scale-95"
                                >
                                    <Download className="w-3.5 h-3.5" /> Export DOCX
                                </button>
                            </div>

                            <div className="flex-1 p-12 bg-white text-slate-900 overflow-y-auto max-h-[750px] shadow-inner font-serif selection:bg-primary-100">
                                {/* Visual Resume Rendering */}
                                <div className="text-center mb-10">
                                    <h2 className="text-4xl font-black uppercase tracking-tight border-b-2 border-slate-900 pb-3 mb-4">
                                        {resume.contact?.name || 'CANDIDATE NAME'}
                                    </h2>
                                    <div className="text-[10px] font-bold text-slate-500 flex justify-center gap-4 uppercase tracking-widest">
                                        <span>{resume.contact?.email}</span>
                                        <span className="opacity-30">|</span>
                                        <span>{resume.contact?.phone}</span>
                                        <span className="opacity-30">|</span>
                                        <span>{resume.contact?.location}</span>
                                    </div>
                                </div>

                                <div className="mb-10">
                                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Professional Summary</h3>
                                    <p className="text-xs leading-relaxed text-slate-700 text-justify font-medium">{resume.summary}</p>
                                </div>

                                <div className="mb-10">
                                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Core Competencies</h3>
                                    <div className="grid grid-cols-2 gap-x-8 gap-y-2">
                                        {resume.skills?.map((s: string, i: number) => (
                                            <div key={i} className="text-[11px] flex items-center gap-3 font-semibold text-slate-800">
                                                <div className="w-1.5 h-1.5 bg-primary-500 rounded-full shrink-0" />
                                                {s}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="mb-10">
                                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-6 text-slate-400">Professional Experience</h3>
                                    <div className="space-y-8">
                                        {resume.experience?.map((exp: any, i: number) => (
                                            <div key={i} className="group">
                                                <div className="flex justify-between items-baseline mb-1">
                                                    <h4 className="font-black text-sm text-slate-900 group-hover:text-primary-600 transition-colors uppercase tracking-tight">{exp.title}</h4>
                                                    <span className="text-[10px] italic font-bold text-slate-400 bg-slate-50 px-2 py-0.5 rounded">{exp.period}</span>
                                                </div>
                                                <p className="text-[10px] font-black text-primary-600 mb-3 uppercase tracking-widest">{exp.company}</p>
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

                                <div>
                                    <h3 className="text-xs font-black uppercase tracking-[0.3em] border-b border-slate-200 pb-1 mb-4 text-slate-400">Education</h3>
                                    <div className="space-y-4">
                                        {resume.education?.map((edu: any, i: number) => (
                                            <div key={i} className="flex justify-between items-center">
                                                <div>
                                                    <p className="text-[11px] font-black text-slate-900">{edu.degree}</p>
                                                    <p className="text-[10px] text-slate-500 font-bold tracking-tight">{edu.school}</p>
                                                </div>
                                                <span className="text-[10px] font-black text-slate-400">{edu.year}</span>
                                            </div>
                                        ))}
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

export default ResumeGenerator;
