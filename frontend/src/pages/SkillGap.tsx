import React, { useState } from 'react';
import { BrainCircuit, Loader2, Sparkles, AlertCircle, CheckCircle2, ChevronRight } from 'lucide-react';
import api from '../api';
import { motion, AnimatePresence } from 'framer-motion';

const SkillGap = () => {
    const [resumeText, setResumeText] = useState('');
    const [jdText, setJdText] = useState('');
    const [analyzing, setAnalyzing] = useState(false);
    const [gaps, setGaps] = useState<any>(null);

    const handleAnalyze = async () => {
        if (!resumeText.trim() || !jdText.trim()) return;
        setAnalyzing(true);
        setGaps(null);
        try {
            const response = await api.post('/analyze/gap', {
                resume_text: resumeText,
                jd_text: jdText
            });
            setGaps(response.data.gaps);
        } catch (err) {
            console.error(err);
        } finally {
            setAnalyzing(false);
        }
    };

    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">Skill Gap Analysis</h1>
                <p className="text-slate-500 font-medium">Identify missing competencies by comparing candidate resumes against job requirements.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="glass-card p-8 flex flex-col gap-6 bg-white/70 border-slate-100 shadow-sm">
                    <div className="flex flex-col gap-2">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Candidate Profile</span>
                        <textarea
                            value={resumeText}
                            onChange={(e) => setResumeText(e.target.value)}
                            className="w-full h-48 bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm font-medium text-slate-800 shadow-inner"
                            placeholder="Paste resume text here..."
                        />
                    </div>
                    <div className="flex flex-col gap-2">
                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Job Description</span>
                        <textarea
                            value={jdText}
                            onChange={(e) => setJdText(e.target.value)}
                            className="w-full h-48 bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm font-medium text-slate-800 shadow-inner"
                            placeholder="Paste job description here..."
                        />
                    </div>
                    <button
                        onClick={handleAnalyze}
                        disabled={analyzing || !resumeText.trim() || !jdText.trim()}
                        className="bg-primary-600 hover:bg-primary-500 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-primary-500/20 disabled:opacity-50 transition-all mt-2"
                    >
                        {analyzing ? <Loader2 className="w-5 h-5 animate-spin" /> : <BrainCircuit className="w-5 h-5 shadow-sm" />}
                        Analyze Skill Alignment
                    </button>
                </div>

                <div className="flex flex-col h-full min-h-[500px]">
                    <AnimatePresence mode="wait">
                        {!gaps && !analyzing && (
                            <motion.div
                                key="empty"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex-1 glass-card flex flex-col items-center justify-center p-12 text-center bg-slate-50/50 border-dashed border-2 border-slate-200"
                            >
                                <div className="w-20 h-20 bg-white rounded-3xl flex items-center justify-center mb-6 shadow-sm border border-slate-100">
                                    <Sparkles className="w-10 h-10 text-slate-200" />
                                </div>
                                <h3 className="text-xl font-bold text-slate-400">Ready to Compare</h3>
                                <p className="text-slate-400 text-sm mt-2 max-w-xs font-medium">Fill in both inputs to start the AI-powered competency analysis.</p>
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
