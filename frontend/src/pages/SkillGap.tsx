import React, { useState } from 'react';
import { BrainCircuit, Loader2, Sparkles, AlertCircle, CheckCircle2, ChevronRight } from 'lucide-react';
import api from '../api';
import { motion, AnimatePresence } from 'framer-motion';
import { PageHeader, EmptyState, ActionButton, FormTextarea } from '../common';

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
            <PageHeader
                title="Skill Gap Analysis"
                subtitle="Identify missing competencies by comparing candidate resumes against job requirements."
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="glass-card p-8 flex flex-col gap-6 bg-white/70 border-slate-100 shadow-sm">
                    <FormTextarea
                        label="Candidate Profile"
                        value={resumeText}
                        onChange={setResumeText}
                        placeholder="Paste resume text here..."
                    />
                    <FormTextarea
                        label="Job Description"
                        value={jdText}
                        onChange={setJdText}
                        placeholder="Paste job description here..."
                    />
                    <ActionButton
                        onClick={handleAnalyze}
                        loading={analyzing}
                        disabled={!resumeText.trim() || !jdText.trim()}
                        icon={<BrainCircuit className="w-5 h-5" />}
                        label="Analyze Skill Alignment"
                        loadingLabel="Analyzing..."
                        className="mt-2"
                    />
                </div>

                <div className="flex flex-col h-full min-h-[500px]">
                    <AnimatePresence mode="wait">
                        {!gaps && !analyzing && (
                            <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                                <EmptyState
                                    icon={<Sparkles className="w-10 h-10" />}
                                    heading="Ready to Compare"
                                    description="Fill in both inputs to start the AI-powered competency analysis."
                                />
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
