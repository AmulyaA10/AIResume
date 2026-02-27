import React, { useState, useEffect } from 'react';
import { Search, Target, Briefcase, MapPin, PoundSterling, Filter, Sparkles, ExternalLink, ArrowRight, Star, X, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { matchApi } from '../../api';

const JobSearch = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [cutoff, setCutoff] = useState(45);
    const [searchMode, setSearchMode] = useState<'recommend' | 'search'>('recommend');
    const [selectedJob, setSelectedJob] = useState<any | null>(null);

    // For now, we'll try to match using a mock resume_id or look up the user's first resume
    const [resumeId, setResumeId] = useState<string | null>(null);

    useEffect(() => {
        // Mock finding the user's resume for the demo
        setResumeId("demo_resume_id");

        if (searchMode === 'recommend') {
            fetchRecommendations();
        }
    }, [searchMode]);

    const fetchRecommendations = async () => {
        setLoading(true);
        try {
            const response = await matchApi.matchResume("demo_resume_id");
            setResults(response.data);
        } catch (error) {
            console.error("Failed to fetch recommendations", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;

        setLoading(true);
        setSearchMode('search');
        try {
            const response = await matchApi.searchJobs(query);
            setResults(response.data);
        } catch (error) {
            console.error("Search failed", error);
        } finally {
            setLoading(false);
        }
    };

    const filteredResults = results.filter(r => (r.score * 100) >= cutoff);

    const levelCls = (l: string) => {
        switch (l) {
            case 'SENIOR': return 'bg-purple-100 text-purple-700 border-purple-200';
            case 'MID': return 'bg-blue-100 text-blue-700 border-blue-200';
            default: return 'bg-emerald-100 text-emerald-700 border-emerald-200';
        }
    };

    return (
        <div className="max-w-6xl mx-auto space-y-8 p-4 md:p-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-black uppercase tracking-widest border border-blue-100">
                        <Sparkles size={12} /> AI-Powered Search
                    </div>
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">
                        Find Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Next Career Move</span>
                    </h1>
                    <p className="text-slate-500 max-w-lg">
                        Our vector-based matching engine analyzes your resume against thousands of job definitions to find your perfect fit.
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
                            placeholder="Search by role, skill, or natural language (e.g. 'Frontend dev London React')..."
                            className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-slate-900"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        className="bg-slate-900 text-white px-8 py-4 rounded-xl font-bold hover:bg-slate-800 transition-all active:scale-95 shadow-lg shadow-slate-200 disabled:opacity-50"
                    >
                        {loading ? 'Searching...' : 'Search Jobs'}
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
                    <div className="flex gap-2">
                        <button
                            onClick={() => setSearchMode('recommend')}
                            className={`text-xs px-4 py-1.5 rounded-full border transition-all font-bold ${searchMode === 'recommend' ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-200' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'}`}
                        >
                            Best Matches
                        </button>
                        <button
                            onClick={() => setSearchMode('search')}
                            className={`text-xs px-4 py-1.5 rounded-full border transition-all font-bold ${searchMode === 'search' ? 'bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-200' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'}`}
                        >
                            All Jobs
                        </button>
                    </div>
                </div>
            </div>

            {/* Results */}
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                        {loading ? (
                            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                        ) : (
                            searchMode === 'recommend' ? <Sparkles size={18} className="text-blue-500" /> : <Search size={18} className="text-indigo-500" />
                        )}
                        {loading ? 'Finding Best Fits...' : `${filteredResults.length} Jobs Found`}
                    </h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <AnimatePresence mode="popLayout">
                        {filteredResults.map((match, idx) => (
                            <motion.div
                                key={match.job.job_id}
                                layout
                                initial={{ opacity: 0, scale: 0.9 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.9 }}
                                transition={{ duration: 0.3, delay: idx * 0.05 }}
                                className="glass-card p-6 bg-white border-slate-200 hover:border-blue-400 hover:shadow-xl hover:shadow-blue-500/5 transition-all group cursor-pointer relative overflow-hidden"
                            >
                                {/* Score Badge */}
                                <div className="absolute top-0 right-0 p-4">
                                    <div className="bg-blue-600 text-white px-3 py-1 rounded-bl-xl absolute top-0 right-0 font-black text-xs shadow-lg">
                                        {Math.round(match.score * 100)}% Match
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${levelCls(match.job.job_level)}`}>
                                                {match.job.job_level}
                                            </span>
                                            <span className="text-[10px] font-black px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                                                {match.job.employment_type?.replace('_', ' ')}
                                            </span>
                                        </div>
                                        <h4 className="text-xl font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1 pr-16">
                                            {match.job.title}
                                        </h4>
                                        <p className="text-slate-500 font-medium text-sm flex items-center gap-1 mt-0.5">
                                            {match.job.employer_name}
                                        </p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-500 font-semibold uppercase tracking-wider">
                                        <div className="flex items-center gap-1.5">
                                            <MapPin size={14} className="text-slate-400" /> {match.job.location_name || 'Remote'}
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <PoundSterling size={14} className="text-slate-400" />
                                            {match.job.salary_min > 0 ? `£${(match.job.salary_min / 1000).toFixed(0)}k+` : 'Negotiable'}
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <p className="text-slate-600 text-sm line-clamp-2 leading-relaxed italic">
                                            "{match.job.description}"
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {match.job.skills_required?.slice(0, 4).map((skill: string) => (
                                                <span key={skill} className="px-2 py-1 bg-slate-50 border border-slate-100 text-slate-500 rounded text-[10px] font-bold">
                                                    {skill}
                                                </span>
                                            ))}
                                            {match.job.skills_required?.length > 4 && (
                                                <span className="text-[10px] text-slate-400 font-bold px-1">+{match.job.skills_required.length - 4} more</span>
                                            )}
                                        </div>
                                    </div>

                                    <div className="pt-4 border-t border-slate-50 flex items-center justify-between">
                                        <div className="flex items-center gap-1">
                                            {[1, 2, 3, 4, 5].map((s) => (
                                                <Star key={s} size={10} className={s <= Math.round(match.score * 5) ? 'text-blue-500 fill-blue-500' : 'text-slate-200'} />
                                            ))}
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    setSelectedJob(match);
                                                }}
                                                className="text-slate-500 font-black text-[10px] uppercase tracking-widest flex items-center gap-1 hover:text-blue-600 transition-all border border-slate-200 px-3 py-1.5 rounded-lg hover:border-blue-200"
                                            >
                                                <Info size={12} /> View Details
                                            </button>
                                            <button className="bg-blue-600 text-white font-black text-[10px] uppercase tracking-widest flex items-center gap-1 hover:bg-blue-700 transition-all px-4 py-2 rounded-lg shadow-lg shadow-blue-200">
                                                Apply Now <ArrowRight size={12} />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>

                {!loading && filteredResults.length === 0 && (
                    <div className="text-center py-24 glass-card bg-slate-50/50 border-dashed border-slate-200">
                        <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                            <Briefcase size={32} />
                        </div>
                        <h4 className="text-slate-900 font-bold text-lg">No matches found</h4>
                        <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                            Try adjusting your minimum match score or search query to find more opportunities.
                        </p>
                    </div>
                )}
            </div>

            {/* Job Details Modal */}
            <AnimatePresence>
                {selectedJob && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8">
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setSelectedJob(null)}
                            className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.9, y: 20 }}
                            className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
                        >
                            {/* Modal Header */}
                            <div className="p-6 md:p-8 border-b border-slate-100 flex justify-between items-start bg-slate-50/50">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-3">
                                        <span className={`text-[10px] font-black px-2 py-0.5 rounded border ${levelCls(selectedJob.job.job_level)}`}>
                                            {selectedJob.job.job_level}
                                        </span>
                                        <div className="flex items-center gap-1">
                                            {[1, 2, 3, 4, 5].map((s) => (
                                                <Star key={s} size={10} className={s <= Math.round(selectedJob.score * 5) ? 'text-blue-500 fill-blue-500' : 'text-slate-200'} />
                                            ))}
                                        </div>
                                    </div>
                                    <h2 className="text-3xl font-black text-slate-900 leading-tight">
                                        {selectedJob.job.title}
                                    </h2>
                                    <p className="text-lg font-bold text-blue-600">
                                        {selectedJob.job.employer_name}
                                    </p>
                                </div>
                                <button
                                    onClick={() => setSelectedJob(null)}
                                    className="p-2 hover:bg-white rounded-xl text-slate-400 hover:text-slate-600 transition-all border border-transparent hover:border-slate-100 shadow-sm shadow-slate-200/0 hover:shadow-slate-200/50"
                                >
                                    <X size={24} />
                                </button>
                            </div>

                            {/* Modal Body */}
                            <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8">
                                {/* Stats Grid */}
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Location</p>
                                        <p className="text-sm font-bold text-slate-700 flex items-center gap-2">
                                            <MapPin size={16} className="text-blue-500" /> {selectedJob.job.location_name || 'Remote'}
                                        </p>
                                    </div>
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100">
                                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Salary</p>
                                        <p className="text-sm font-bold text-slate-700 flex items-center gap-2">
                                            <PoundSterling size={16} className="text-emerald-500" />
                                            {selectedJob.job.salary_min > 0 ? `£${(selectedJob.job.salary_min / 1000).toFixed(0)}k - £${(selectedJob.job.salary_max / 1000).toFixed(0)}k` : 'Negotiable'}
                                        </p>
                                    </div>
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 col-span-2 md:col-span-1">
                                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Match Score</p>
                                        <p className="text-sm font-bold text-blue-600 flex items-center gap-2">
                                            <Target size={16} /> {Math.round(selectedJob.score * 100)}% Match
                                        </p>
                                    </div>
                                </div>

                                {/* Description */}
                                <div className="space-y-3">
                                    <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-2">
                                        <Briefcase size={16} className="text-slate-400" /> Job Description
                                    </h3>
                                    <div className="text-slate-600 leading-relaxed space-y-4 text-sm font-medium">
                                        {selectedJob.job.description.split('\n').map((para: string, i: number) => (
                                            <p key={i}>{para}</p>
                                        ))}
                                    </div>
                                </div>

                                {/* Skills */}
                                <div className="space-y-4">
                                    <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-2">
                                        <Sparkles size={16} className="text-blue-400" /> Requirements & Skills
                                    </h3>
                                    <div className="flex flex-wrap gap-2">
                                        {selectedJob.job.skills_required?.map((skill: string) => (
                                            <span key={skill} className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs font-bold border border-blue-100/50">
                                                {skill}
                                            </span>
                                        ))}
                                    </div>
                                </div>

                                {/* Benefits */}
                                {selectedJob.job.benefits?.length > 0 && (
                                    <div className="space-y-4">
                                        <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-2">
                                            <Star size={16} className="text-amber-400" /> Benefits
                                        </h3>
                                        <div className="flex flex-wrap gap-2">
                                            {selectedJob.job.benefits?.map((benefit: string) => (
                                                <span key={benefit} className="px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-xs font-bold border border-amber-100/50">
                                                    {benefit}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Modal Footer */}
                            <div className="p-6 md:p-8 border-t border-slate-100 bg-slate-50/50 flex gap-4">
                                <button
                                    onClick={() => setSelectedJob(null)}
                                    className="flex-1 px-8 py-4 bg-white text-slate-600 rounded-2xl font-black text-xs uppercase tracking-widest border border-slate-200 hover:bg-slate-50 transition-all active:scale-95 shadow-lg shadow-slate-200"
                                >
                                    Close
                                </button>
                                <button
                                    className="flex-[2] px-8 py-4 bg-blue-600 text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-blue-700 transition-all active:scale-95 shadow-lg shadow-blue-200 flex items-center justify-center gap-2"
                                >
                                    Apply Now <ArrowRight size={16} />
                                </button>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default JobSearch;
