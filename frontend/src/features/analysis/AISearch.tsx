import React, { useState } from 'react';
import { Search, Loader2, Star, AlertTriangle, CheckCircle, Download, FileText } from 'lucide-react';
import api from '../../api';
import { motion } from 'framer-motion';
import { PageHeader } from '../../common';

const AISearch = () => {
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [results, setResults] = useState<any[]>([]);

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        setSearching(true);
        try {
            const response = await api.post('/search', { query });
            setResults(response.data.results);
        } catch (err) {
            console.error(err);
        } finally {
            setSearching(false);
        }
    };

    return (
        <div className="space-y-8">
            <PageHeader
                title="Semantic AI Search"
                subtitle="Find the best candidates using natural language reasoning powered by GPT-4o."
            />

            <form onSubmit={handleSearch} className="relative">
                <div className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                    <input
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="e.g. Senior Backend Engineer with Python and AWS experience..."
                        className="w-full bg-white border border-slate-200 rounded-xl py-4 pl-12 pr-32 focus:border-primary-500 outline-none text-lg transition-all shadow-sm focus:ring-4 focus:ring-primary-500/5 text-slate-900 placeholder:text-slate-400"
                    />
                    <button
                        type="submit"
                        disabled={searching}
                        className="absolute right-2 top-2 bottom-2 bg-primary-600 hover:bg-primary-500 text-white px-6 rounded-lg font-bold flex items-center gap-2 disabled:opacity-50 transition-all font-inter shadow-md shadow-primary-500/20"
                    >
                        {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Search'}
                    </button>
                </div>
            </form>

            <div className="space-y-6">
                {searching && (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-400 italic font-medium">
                        <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary-500/50" />
                        <p>Scanning vector database and reasoning with AI...</p>
                    </div>
                )}

                {results.map((res, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="glass-card p-8 border-l-4 border-l-primary-500 shadow-sm hover:shadow-md transition-shadow"
                    >
                        <div className="flex justify-between items-start mb-6">
                            <div>
                                <h3 className="text-xl font-bold mb-1 flex items-center gap-3 text-slate-900 tracking-tight">
                                    <FileText className="w-5 h-5 text-primary-500" />
                                    {res.filename}
                                </h3>
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-1.5 text-amber-700 bg-amber-50 px-2 py-0.5 rounded text-xs font-black ring-1 ring-amber-200">
                                        <Star className="w-3 h-3 fill-current" />
                                        MATCH {res.score}%
                                    </div>
                                    <span className={`text-xs font-black px-2 py-0.5 rounded ring-1 ${res.auto_screen.toLowerCase() === 'selected'
                                        ? 'text-emerald-700 bg-emerald-50 ring-emerald-200'
                                        : 'text-red-700 bg-red-50 ring-red-200'
                                        }`}>
                                        {res.auto_screen.toUpperCase()}
                                    </span>
                                </div>
                            </div>
                            <button
                                onClick={() => {
                                    window.open(`http://localhost:8000/api/v1/resumes/download/${res.filename}`, '_blank');
                                }}
                                className="flex items-center gap-2 text-slate-400 hover:text-primary-600 transition-colors text-sm font-bold"
                            >
                                <Download className="w-4 h-4" />
                                Resume
                            </button>
                        </div>

                        <p className="text-slate-600 text-sm leading-relaxed mb-6 bg-slate-50 p-4 rounded-lg border border-slate-100 font-medium">
                            {res.justification}
                        </p>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] mb-3 flex items-center gap-2">
                                    <AlertTriangle className="w-3 h-3 text-amber-500" />
                                    Missing Skills
                                </h4>
                                <div className="flex flex-wrap gap-2">
                                    {res.missing_skills.length > 0 ? res.missing_skills.map((s: string, j: number) => (
                                        <span key={j} className="text-xs bg-white border border-slate-200 text-slate-600 px-2.5 py-1 rounded-md font-semibold shadow-sm">{s}</span>
                                    )) : <span className="text-xs text-emerald-600 font-bold flex items-center gap-1">
                                        <CheckCircle className="w-3 h-3" /> Perfect skill match</span>}
                                </div>
                            </div>
                            <div>
                                <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.15em] mb-3 flex items-center gap-2">
                                    <CheckCircle className="w-3 h-3 text-emerald-500" />
                                    Key Highlights
                                </h4>
                                <p className="text-xs text-slate-500 italic font-medium">Demonstrates expertise in the core requirements defined in the query.</p>
                            </div>
                        </div>
                    </motion.div>
                ))}

                {!searching && results.length === 0 && (
                    <div className="text-center py-20 text-slate-500">
                        <Search className="w-12 h-12 mx-auto mb-4 opacity-20" />
                        <p>Enter a query to start searching resumes.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AISearch;
