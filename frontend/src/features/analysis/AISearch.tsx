import React, { useState } from 'react';
import { Search, Loader2, Star, AlertTriangle, CheckCircle, Download, FileText, Sparkles, Target, Info } from 'lucide-react';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';

const AISearch = () => {
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [results, setResults] = useState<any[]>([]);
    const [cutoff, setCutoff] = useState(10);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setSearching(true);
        try {
            const response = await api.post('/search', { query });
            setResults(response.data.results || []);
        } catch (err) {
            console.error(err);
        } finally {
            setSearching(false);
        }
    };

    const filteredResults = results.filter(res => (res.score || 0) >= cutoff);

    return (
        <div className="max-w-6xl mx-auto space-y-8 p-4 md:p-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-black uppercase tracking-widest border border-blue-100">
                        <Sparkles size={12} /> AI-Powered Candidate Search
                    </div>
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">
                        Find the <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Perfect Talent</span>
                    </h1>
                    <p className="text-slate-500 max-w-lg">
                        Our semantic engine uses natural language reasoning to find candidates that match your specific requirements.
                    </p>
                </div>
            </div>

            {/* Search Bar */}
            <div className="glass-card p-2 rounded-2xl shadow-xl border-slate-200 bg-white/80 backdrop-blur-xl">
                <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="e.g. Senior Backend Engineer with Python and AWS experience..."
                            className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-slate-900"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={searching}
                        className="bg-slate-900 text-white px-8 py-4 rounded-xl font-bold hover:bg-slate-800 transition-all active:scale-95 shadow-lg shadow-slate-200 disabled:opacity-50"
                    >
                        {searching ? (
                            <span className="flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin" /> Searching...
                            </span>
                        ) : 'Search Candidates'}
                    </button>
                </form>

                <div className="flex flex-wrap items-center gap-6 px-4 py-3 border-t border-slate-100 mt-2">
                    <div className="flex items-center gap-3 flex-1 min-w-[200px]">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                            <Target size={14} /> Min Match: {cutoff}%
                        </span>
                        <input
                            type="range"
                            min="0"
                            max="95"
                            step="5"
                            value={cutoff}
                            onChange={(e) => setCutoff(Number(e.target.value))}
                            className="flex-1 h-1.5 bg-slate-100 rounded-full accent-blue-600 cursor-pointer"
                        />
                    </div>
                </div>
            </div>

            {/* Results */}
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                        {searching ? (
                            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                        ) : (
                            <Sparkles size={18} className="text-blue-500" />
                        )}
                        {searching ? 'AI Reasoning in Progress...' : `${filteredResults.length} Candidates Found`}
                    </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <AnimatePresence mode="popLayout">
                        {filteredResults.map((res, idx) => (
                            <motion.div
                                key={res.filename + idx}
                                layout
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                                className="glass-card p-6 bg-white border-slate-200 hover:border-blue-400 hover:shadow-xl hover:shadow-blue-500/5 transition-all group relative overflow-hidden"
                            >
                                {/* Score Badge */}
                                <div className="absolute top-0 right-0 p-4">
                                    <div className={`px-3 py-1 rounded-bl-xl absolute top-0 right-0 font-black text-xs shadow-lg ${res.score >= 80 ? 'bg-emerald-600 text-white' : 'bg-blue-600 text-white'}`}>
                                        {res.score}% Match
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${res.auto_screen?.toLowerCase() === 'selected'
                                                ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
                                                : 'bg-red-100 text-red-700 border-red-200'
                                                }`}>
                                                {res.auto_screen?.toUpperCase() || 'SCORED'}
                                            </span>
                                            <span className="text-[10px] font-black px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                                                RESUME
                                            </span>
                                        </div>
                                        <h4 className="text-xl font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1 pr-16">
                                            {res.filename}
                                        </h4>
                                    </div>

                                    <div className="space-y-3">
                                        <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                                            <h5 className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-2">
                                                <Info size={12} className="text-blue-500" /> AI Justification
                                            </h5>
                                            <p className="text-slate-600 text-sm leading-relaxed italic line-clamp-3">
                                                "{res.justification}"
                                            </p>
                                        </div>

                                        <div className="space-y-2">
                                            <h5 className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                                <AlertTriangle size={12} className="text-amber-500" /> Missing Skills
                                            </h5>
                                            <div className="flex flex-wrap gap-1.5">
                                                {res.missing_skills?.length > 0 ? res.missing_skills.map((skill: string) => (
                                                    <span key={skill} className="px-2 py-1 bg-white border border-slate-200 text-slate-500 rounded text-[10px] font-bold">
                                                        {skill}
                                                    </span>
                                                )) : (
                                                    <span className="text-xs text-emerald-600 font-bold flex items-center gap-1">
                                                        <CheckCircle className="w-3 h-3" /> Perfect skill match
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-slate-50 flex items-center justify-between">
                                        <div className="flex items-center gap-1">
                                            {[1, 2, 3, 4, 5].map((s) => (
                                                <Star key={s} size={10} className={s <= Math.round((res.score / 100) * 5) ? 'text-blue-500 fill-blue-500' : 'text-slate-200'} />
                                            ))}
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={() => {
                                                    window.open(`${api.defaults.baseURL}/resumes/download/${res.filename}`, '_blank');
                                                }}
                                                className="bg-white text-slate-600 font-black text-[10px] uppercase tracking-widest flex items-center gap-1 hover:bg-slate-50 transition-all px-4 py-2 rounded-lg border border-slate-200 shadow-sm"
                                            >
                                                <Download size={14} /> Download
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>

                {!searching && filteredResults.length === 0 && (
                    <div className="text-center py-24 glass-card bg-slate-50/50 border-dashed border-slate-200">
                        <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                            <FileText size={32} />
                        </div>
                        <h4 className="text-slate-900 font-bold text-lg">No candidates found</h4>
                        <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                            {results.length > 0 ? 'Try lowering the minimum match score.' : 'Enter a query to search through the candidate database.'}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AISearch;
