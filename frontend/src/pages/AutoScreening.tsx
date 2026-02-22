import React, { useState } from 'react';
import { ShieldCheck, Loader2, UserCheck, UserX, Info, Target } from 'lucide-react';
import api from '../api';
import { motion } from 'framer-motion';

const AutoScreening = () => {
    const [resumeText, setResumeText] = useState('');
    const [jdText, setJdText] = useState('');
    const [threshold, setThreshold] = useState(75);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);

    const handleScreen = async () => {
        if (!resumeText.trim() || !jdText.trim()) return;
        setLoading(true);
        setResult(null);
        try {
            const response = await api.post('/analyze/screen', {
                resume_text: resumeText,
                jd_text: jdText,
                threshold: threshold
            });
            setResult(response.data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            <header>
                <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">Auto Screening Decisions</h1>
                <p className="text-slate-500 font-medium">Automated candidate matching against custom thresholds and JD requirements.</p>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-6">
                    <div className="glass-card p-8 space-y-6 bg-white/70 border-slate-100 shadow-sm">
                        <div className="flex flex-col gap-2">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Candidate Resume</span>
                            <textarea
                                value={resumeText}
                                onChange={(e) => setResumeText(e.target.value)}
                                className="w-full h-40 bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm font-medium text-slate-800 shadow-inner"
                                placeholder="Candidate resume..."
                            />
                        </div>
                        <div className="flex flex-col gap-2">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Target Job Description</span>
                            <textarea
                                value={jdText}
                                onChange={(e) => setJdText(e.target.value)}
                                className="w-full h-40 bg-white border border-slate-200 rounded-xl p-4 outline-none focus:border-primary-500 transition-all resize-none text-sm font-medium text-slate-800 shadow-inner"
                                placeholder="Job description..."
                            />
                        </div>
                    </div>

                    <div className="glass-card p-8 bg-white/50 border-slate-100 shadow-sm">
                        <div className="flex justify-between items-center mb-6">
                            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Selection Threshold</span>
                            <span className="text-primary-600 font-black bg-primary-50 px-2 py-0.5 rounded border border-primary-100 shadow-sm">{threshold}%</span>
                        </div>
                        <input
                            type="range"
                            min="50" max="90"
                            value={threshold}
                            onChange={(e) => setThreshold(parseInt(e.target.value))}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-primary-600 border border-slate-200"
                        />
                        <div className="flex justify-between text-[10px] text-slate-400 mt-2 font-black uppercase tracking-tight">
                            <span>Standard (50%)</span>
                            <span>Strict (75%)</span>
                            <span>Elite (90%)</span>
                        </div>
                    </div>

                    <button
                        onClick={handleScreen}
                        disabled={loading || !resumeText.trim() || !jdText.trim()}
                        className="w-full bg-primary-600 hover:bg-primary-500 text-white py-5 rounded-xl font-bold flex items-center justify-center gap-3 shadow-lg shadow-primary-500/20 disabled:opacity-50 transition-all"
                    >
                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ShieldCheck className="w-5 h-5" />}
                        {loading ? 'Executing Agentic Flow...' : 'Execute Screening Decision'}
                    </button>
                </div>

                <div className="flex flex-col min-h-[500px]">
                    {!result && !loading && (
                        <div className="flex-1 glass-card border-dashed border-2 border-slate-200 flex flex-col items-center justify-center p-12 text-center bg-slate-50/30">
                            <div className="w-20 h-20 bg-white rounded-3xl flex items-center justify-center mb-6 border border-slate-100 shadow-sm text-slate-200">
                                <ShieldCheck className="w-10 h-10" />
                            </div>
                            <h3 className="text-xl font-bold text-slate-400">Decision Engine Standby</h3>
                            <p className="text-slate-400 text-sm mt-2 max-w-xs font-medium">Provide resume and JD data to trigger the AI-agentic screening flow.</p>
                        </div>
                    )}

                    {loading && (
                        <div className="flex-1 glass-card flex flex-col items-center justify-center p-12 bg-white/80 border-primary-100">
                            <div className="w-24 h-24 relative">
                                <div className="absolute inset-0 rounded-2xl border-4 border-primary-100 animate-pulse" />
                                <div className="absolute inset-0 rounded-2xl border-t-4 border-primary-500 animate-spin" />
                                <ShieldCheck className="absolute inset-0 m-auto w-10 h-10 text-primary-200" />
                            </div>
                            <p className="mt-8 text-primary-600 font-black uppercase tracking-[0.2em] text-xs">Simulating Agent Reasoning...</p>
                        </div>
                    )}

                    {result && (
                        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex-1 flex flex-col shadow-lg rounded-xl overflow-hidden">
                            <div className={`p-10 rounded-t-xl border-x border-t flex flex-col items-center text-center ${result.decision.selected ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'
                                }`}>
                                <div className={`w-20 h-20 rounded-2xl shadow-sm flex items-center justify-center mb-6 ${result.decision.selected ? 'bg-white border border-emerald-200' : 'bg-white border border-red-200'
                                    }`}>
                                    {result.decision.selected ? <UserCheck className="text-emerald-500 w-10 h-10" /> : <UserX className="text-red-500 w-10 h-10" />}
                                </div>
                                <h2 className={`text-2xl font-black uppercase tracking-widest ${result.decision.selected ? 'text-emerald-700' : 'text-red-700'
                                    }`}>
                                    {result.decision.selected ? 'Candidate Selected' : 'Candidate Rejected'}
                                </h2>
                                <div className="mt-6 flex items-baseline gap-2">
                                    <span className="text-6xl font-black text-slate-900 tracking-tighter">{result.score.overall}%</span>
                                    <span className="text-slate-400 text-xs font-bold uppercase tracking-widest">Alignment Score</span>
                                </div>
                            </div>

                            <div className="flex-1 glass-card border-t-0 rounded-t-none p-10 space-y-8 bg-white/90">
                                <div className="space-y-3">
                                    <h4 className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
                                        <Info className="w-3.5 h-3.5" /> Logical Reasoning Path
                                    </h4>
                                    <p className="text-sm leading-relaxed text-slate-600 bg-slate-50 p-6 rounded-xl border border-slate-100 font-medium italic shadow-inner">
                                        "{result.decision.reason}"
                                    </p>
                                </div>

                                <div className="pt-8 border-t border-slate-100">
                                    <div className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">
                                        <Target className="w-3.5 h-3.5" /> KPI Benchmarks
                                    </div>
                                    <div className="space-y-4">
                                        <div className="flex justify-between items-center text-sm">
                                            <span className="text-slate-500 font-bold">Required Score Threshold</span>
                                            <span className="font-mono bg-slate-50 px-2 py-0.5 rounded border border-slate-200 font-black text-slate-700">{threshold}%</span>
                                        </div>
                                        <div className="flex justify-between items-center text-sm">
                                            <span className="text-slate-500 font-bold">Actual Calculated Score</span>
                                            <span className={`font-mono font-black px-2 py-0.5 rounded border ${result.score.overall >= threshold ? 'text-emerald-700 bg-emerald-50 border-emerald-100' : 'text-red-700 bg-red-50 border-red-100'}`}>
                                                {result.score.overall}%
                                            </span>
                                        </div>
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

export default AutoScreening;
