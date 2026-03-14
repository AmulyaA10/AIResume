import React, { useState, useEffect } from 'react';
import { Search, Target, Briefcase, MapPin, Banknote, Sparkles, ArrowRight, Star, X, Info, CheckCircle, FileText, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { matchApi, jobsApi, resumesApi } from '../../api';

interface MatchStats {
    total: number; qualifying: number; skipped: number; avgScore: number;
    topSkills: string[]; scoreBreakdown: { range: string; count: number }[];
}

const CURRENCY_SYMBOLS: Record<string, string> = {
    USD: '$', GBP: '£', EUR: '€', CAD: 'CAD$', AUD: 'AUD$', SGD: 'SGD$',
};

const formatSalary = (currency: string, min: number, max?: number): string => {
    const sym = CURRENCY_SYMBOLS[currency] ?? '$';
    if (!min || min <= 0) return 'Negotiable';
    if (max && max > 0) return `${sym}${(min / 1000).toFixed(0)}k – ${sym}${(max / 1000).toFixed(0)}k`;
    return `${sym}${(min / 1000).toFixed(0)}k+`;
};

const JobSearch = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [extracting, setExtracting] = useState(false);
    const [cutoff, setCutoff] = useState(0);
    const [searchMode, setSearchMode] = useState<'recommend' | 'search'>('recommend');
    const [selectedJob, setSelectedJob] = useState<any | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [confirmingJobId, setConfirmingJobId] = useState<string | null>(null);
    const [appStatus, setAppStatus] = useState<'idle' | 'confirming' | 'applying' | 'success' | 'error'>('idle');

    const [resumeId, setResumeId] = useState<string | null>(null);
    const [resumes, setResumes] = useState<string[]>([]);
    const [selectedResume, setSelectedResume] = useState<string>('');
    const [searchDone, setSearchDone] = useState(false);

    // Stats derived at render time from results
    const matchStats: MatchStats | null = (searchDone && results.length > 0) ? (() => {
        const threshold = cutoff / 100;
        const qualifying = results.filter(r => r.score >= threshold).length;
        const avgScore = Math.round(results.reduce((s, r) => s + r.score, 0) / results.length * 100);
        const skillFreq: Record<string, number> = {};
        results.forEach(r => (r.matched_skills || []).forEach((s: string) => {
            skillFreq[s] = (skillFreq[s] || 0) + 1;
        }));
        const topSkills = Object.entries(skillFreq).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([s]) => s);
        const bands = [
            { range: '80 – 100%', min: 0.80, max: 1.01 },
            { range: '60 – 79%',  min: 0.60, max: 0.80 },
            { range: '40 – 59%',  min: 0.40, max: 0.60 },
            { range: '20 – 39%',  min: 0.20, max: 0.40 },
            { range:  '0 – 19%',  min: 0.00, max: 0.20 },
        ];
        const scoreBreakdown = bands.map(({ range, min, max }) => ({
            range,
            count: results.filter(r => r.score >= min && r.score < max).length,
        }));
        return { total: results.length, qualifying, skipped: results.length - qualifying, avgScore, topSkills, scoreBreakdown };
    })() : null;

    const handleApply = async (jobId: string) => {
        const applyResume = selectedResume || resumeId;
        if (!applyResume) {
            alert("No resume found. Please upload a resume first.");
            return;
        }
        setConfirmingJobId(jobId);
        setAppStatus('confirming');
    };

    const confirmApply = async () => {
        const applyResume = selectedResume || resumeId;
        if (!confirmingJobId || !applyResume) return;
        setAppStatus('applying');
        try {
            await jobsApi.apply(confirmingJobId, applyResume);
            setAppStatus('success');
            setTimeout(() => { setConfirmingJobId(null); setAppStatus('idle'); }, 2000);
        } catch (error) {
            console.error("Application failed", error);
            setAppStatus('error');
        }
    };

    useEffect(() => {
        resumesApi.list().then(res => {
            setResumes(res.data?.resumes || []);
        }).catch(() => {});
    }, []);

    // When resume is selected: extract skills and populate the search box
    const handleResumeChange = async (val: string) => {
        setSelectedResume(val);
        setResumeId(val || null);
        setResults([]);
        setSearchDone(false);

        if (!val) {
            setQuery('');
            return;
        }

        setExtracting(true);
        try {
            const res = await matchApi.extractSkills(val);
            const skills: string[] = res.data?.skills || [];
            setQuery(skills.join(', '));
        } catch {
            setQuery('');
        } finally {
            setExtracting(false);
        }
    };

    const fetchAllJobs = async () => {
        setLoading(true);
        setSearchDone(false);
        try {
            const response = await jobsApi.listPublic();
            const jobs: any[] = response.data || [];
            setResults(jobs.map((job: any) => ({ score: 1, job, matched_skills: [] })));
        } catch (error) {
            console.error("Failed to fetch all jobs", error);
            setResults([]);
        } finally {
            setLoading(false);
            setSearchDone(true);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        const searchQuery = query.trim();
        if (!searchQuery) return;

        setLoading(true);
        setSearchDone(false);
        try {
            const response = await matchApi.searchJobs(searchQuery);
            setResults(response.data || []);
        } catch (error) {
            console.error("Search failed", error);
            setResults([]);
        } finally {
            setLoading(false);
            setSearchDone(true);
        }
    };

    const filteredResults = (searchMode === 'search' && !query.trim())
        ? results
        : results.filter(r => (r.score * 100) >= cutoff);

    const levelCls = (l: string) => {
        switch (l) {
            case 'SENIOR': return 'bg-purple-100 text-purple-700 border-purple-200';
            case 'MID':    return 'bg-blue-100 text-blue-700 border-blue-200';
            default:       return 'bg-emerald-100 text-emerald-700 border-emerald-200';
        }
    };

    return (
        <div className="max-w-6xl mx-auto space-y-8 p-4 md:p-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

            {/* Header */}
            <div className="space-y-2">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-600 text-[10px] font-black uppercase tracking-widest border border-blue-100">
                    <Sparkles size={12} /> AI-Powered Search
                </div>
                <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">
                    Find Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Next Career Move</span>
                </h1>
                <p className="text-slate-500 max-w-lg">
                    Select a resume to extract your skills, then search or refine the query to find matching jobs.
                </p>
            </div>

            {/* Search Bar */}
            <div className="glass-card p-2 rounded-2xl shadow-xl border-slate-200 bg-white/80 backdrop-blur-xl">

                {/* Resume selector */}
                <div className="flex items-center gap-3 px-2 pt-2 pb-2">
                    <div className="flex items-center gap-2 text-slate-400 shrink-0">
                        <FileText size={16} />
                        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Resume</span>
                    </div>
                    <select
                        value={selectedResume}
                        onChange={(e) => handleResumeChange(e.target.value)}
                        disabled={extracting}
                        className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-700 font-medium outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                    >
                        <option value="">— No resume selected —</option>
                        {resumes.map((r) => (
                            <option key={r} value={r}>{r}</option>
                        ))}
                    </select>
                    {extracting && (
                        <div className="flex items-center gap-2 text-blue-500 shrink-0">
                            <Loader2 size={14} className="animate-spin" />
                            <span className="text-xs font-bold">Extracting skills…</span>
                        </div>
                    )}
                </div>

                <div className="border-t border-slate-100 mt-1 mb-2" />

                {/* Search input */}
                <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                        <input
                            type="text"
                            placeholder="Skills extracted from your resume appear here — edit or type freely…"
                            className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-slate-900"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading || extracting || !query.trim()}
                        className="bg-slate-900 text-white px-8 py-4 rounded-xl font-bold hover:bg-slate-800 transition-all active:scale-95 shadow-lg shadow-slate-200 disabled:opacity-50"
                    >
                        {loading ? 'Searching…' : 'Search Jobs'}
                    </button>
                </form>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-6 px-4 py-3 border-t border-slate-100 mt-2">
                    <div className="flex items-center gap-3 flex-1 min-w-[200px]">
                        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                            <Target size={14} /> Min Match: {cutoff}%
                        </span>
                        <input
                            type="range" min="0" max="95" step="5" value={cutoff}
                            onChange={(e) => setCutoff(Number(e.target.value))}
                            className="flex-1 h-1.5 bg-slate-100 rounded-full accent-blue-600 cursor-pointer"
                        />
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => { setSearchMode('recommend'); }}
                            className={`text-xs px-4 py-1.5 rounded-full border transition-all font-bold ${searchMode === 'recommend' ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-200' : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'}`}
                        >
                            Best Matches
                        </button>
                        <button
                            onClick={() => { setSearchMode('search'); setQuery(''); fetchAllJobs(); }}
                            className={`text-xs px-4 py-1.5 rounded-full border transition-all font-bold ${searchMode === 'search' ? 'bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-200' : 'bg-white text-slate-600 border-slate-200 hover:border-indigo-300'}`}
                        >
                            All Jobs
                        </button>
                    </div>
                </div>
            </div>

            {/* Match Statistics Table */}
            <AnimatePresence>
                {matchStats && (
                    <motion.div
                        initial={{ opacity: 0, y: -12 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -12 }}
                        transition={{ duration: 0.35 }}
                        className="glass-card bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-lg"
                    >
                        <div className="flex items-center gap-2 px-6 py-4 bg-slate-50 border-b border-slate-100">
                            <Sparkles size={16} className="text-blue-500" />
                            <span className="text-xs font-black text-slate-700 uppercase tracking-widest">Match Statistics</span>
                            <span className="ml-auto text-[10px] font-bold text-slate-400 uppercase tracking-wider">Min threshold: {cutoff}%</span>
                        </div>

                        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">

                            {/* KPIs */}
                            <div className="space-y-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Overview</p>
                                <div className="space-y-2">
                                    {[
                                        { label: 'Total jobs searched',       value: matchStats.total,              cls: 'text-slate-800' },
                                        { label: `Qualifying (≥ ${cutoff}%)`, value: matchStats.qualifying,         cls: 'text-emerald-600 font-bold' },
                                        { label: `Skipped (< ${cutoff}%)`,    value: matchStats.skipped,            cls: 'text-slate-400' },
                                        { label: 'Average match score',       value: `${matchStats.avgScore}%`,     cls: 'text-blue-600 font-bold' },
                                    ].map(({ label, value, cls }) => (
                                        <div key={label} className="flex items-center justify-between py-1.5 border-b border-slate-50">
                                            <span className="text-xs text-slate-500">{label}</span>
                                            <span className={`text-sm ${cls}`}>{value}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Score breakdown */}
                            <div className="space-y-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Score Distribution</p>
                                <div className="space-y-2">
                                    {matchStats.scoreBreakdown.map(({ range, count }) => {
                                        const pct = matchStats.total > 0 ? Math.round(count / matchStats.total * 100) : 0;
                                        const isHigh = range.startsWith('80') || range.startsWith('60');
                                        return (
                                            <div key={range} className="space-y-1">
                                                <div className="flex justify-between text-[11px]">
                                                    <span className="text-slate-500 font-mono">{range}</span>
                                                    <span className="font-bold text-slate-700">{count} <span className="text-slate-400 font-normal">({pct}%)</span></span>
                                                </div>
                                                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                                    <motion.div
                                                        initial={{ width: 0 }}
                                                        animate={{ width: `${pct}%` }}
                                                        transition={{ duration: 0.6, delay: 0.1 }}
                                                        className={`h-full rounded-full ${isHigh ? 'bg-emerald-400' : 'bg-slate-300'}`}
                                                    />
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Top skills + qualify ring */}
                            <div className="space-y-3">
                                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Top Matched Skills</p>
                                {matchStats.topSkills.length > 0 ? (
                                    <div className="flex flex-wrap gap-1.5">
                                        {matchStats.topSkills.map(skill => (
                                            <span key={skill} className="px-2.5 py-1 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-lg text-[10px] font-bold">{skill}</span>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-xs text-slate-400">No direct skill overlaps found</p>
                                )}
                                <div className="mt-4 flex items-center gap-3">
                                    <div className="relative w-14 h-14 shrink-0">
                                        <svg className="w-14 h-14 -rotate-90" viewBox="0 0 56 56">
                                            <circle cx="28" cy="28" r="22" fill="none" stroke="#f1f5f9" strokeWidth="6" />
                                            <circle cx="28" cy="28" r="22" fill="none" stroke="#10b981" strokeWidth="6"
                                                strokeDasharray={`${2 * Math.PI * 22}`}
                                                strokeDashoffset={`${2 * Math.PI * 22 * (1 - matchStats.qualifying / Math.max(matchStats.total, 1))}`}
                                                strokeLinecap="round"
                                                style={{ transition: 'stroke-dashoffset 0.8s ease' }}
                                            />
                                        </svg>
                                        <span className="absolute inset-0 flex items-center justify-center text-[11px] font-black text-slate-700">
                                            {matchStats.total > 0 ? Math.round(matchStats.qualifying / matchStats.total * 100) : 0}%
                                        </span>
                                    </div>
                                    <div>
                                        <p className="text-xs font-bold text-slate-700">Qualify rate</p>
                                        <p className="text-[11px] text-slate-400">{matchStats.qualifying} of {matchStats.total} jobs</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* All searched jobs table */}
                        <div className="border-t border-slate-100">
                            <div className="px-6 py-3 bg-slate-50">
                                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">All Searched Jobs</span>
                            </div>
                            <div className="overflow-x-auto max-h-64 overflow-y-auto">
                                <table className="w-full text-xs">
                                    <thead className="sticky top-0 bg-slate-50 z-10">
                                        <tr className="text-left">
                                            {['#', 'Job Title', 'Employer', 'Level', 'Score', 'Status', 'Matched Skills'].map(h => (
                                                <th key={h} className="px-4 py-2 font-black text-slate-500 uppercase tracking-wider text-[10px]">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-50">
                                        {[...results].sort((a, b) => b.score - a.score).map((match, idx) => {
                                            const passes = match.score >= cutoff / 100;
                                            return (
                                                <tr key={match.job.job_id} className={`hover:bg-slate-50 transition-colors ${!passes ? 'opacity-50' : ''}`}>
                                                    <td className="px-4 py-2 text-slate-400 font-mono">{idx + 1}</td>
                                                    <td className="px-4 py-2 font-semibold text-slate-800 max-w-[180px] truncate">{match.job.title}</td>
                                                    <td className="px-4 py-2 text-slate-500 max-w-[140px] truncate">{match.job.employer_name}</td>
                                                    <td className="px-4 py-2">
                                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-black ${levelCls(match.job.job_level)}`}>{match.job.job_level}</span>
                                                    </td>
                                                    <td className="px-4 py-2">
                                                        <span className={`font-black ${passes ? 'text-emerald-600' : 'text-slate-400'}`}>{Math.round(match.score * 100)}%</span>
                                                    </td>
                                                    <td className="px-4 py-2">
                                                        {passes
                                                            ? <span className="flex items-center gap-1 text-emerald-600 font-bold"><CheckCircle size={11} /> Pass</span>
                                                            : <span className="text-slate-400 font-bold">Skip</span>}
                                                    </td>
                                                    <td className="px-4 py-2 text-slate-500 max-w-[160px] truncate">
                                                        {(match.matched_skills || []).join(', ') || '—'}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Results */}
            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                        {loading ? (
                            <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                        ) : (
                            <Sparkles size={18} className="text-blue-500" />
                        )}
                        {loading ? 'Searching…' : `${filteredResults.length} Jobs Found`}
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
                                <div className="absolute top-0 right-0">
                                    <div className="bg-blue-600 text-white px-3 py-1 rounded-bl-xl font-black text-xs shadow-lg">
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
                                        <p className="text-slate-500 font-medium text-sm mt-0.5">{match.job.employer_name}</p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-500 font-semibold uppercase tracking-wider">
                                        <div className="flex items-center gap-1.5">
                                            <MapPin size={14} className="text-slate-400" /> {match.job.location_name || 'Remote'}
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <Banknote size={14} className="text-slate-400" />
                                            {formatSalary(match.job.salary_currency || 'USD', match.job.salary_min)}
                                        </div>
                                    </div>

                                    <div className="space-y-3">
                                        <p className="text-slate-600 text-sm line-clamp-2 leading-relaxed italic">
                                            "{match.job.description}"
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {match.job.skills_required?.slice(0, 4).map((skill: string) => {
                                                const isMatched = (match.matched_skills || []).some(
                                                    (ms: string) => ms.toLowerCase() === skill.toLowerCase() ||
                                                        ms.toLowerCase().includes(skill.toLowerCase()) ||
                                                        skill.toLowerCase().includes(ms.toLowerCase())
                                                );
                                                return (
                                                    <span key={skill} className={`px-2 py-1 rounded text-[10px] font-bold border ${isMatched ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-50 border-slate-100 text-slate-500'}`}>
                                                        {isMatched && <CheckCircle size={9} className="inline mr-0.5 -mt-0.5" />}{skill}
                                                    </span>
                                                );
                                            })}
                                            {match.job.skills_required?.length > 4 && (
                                                <span className="text-[10px] text-slate-400 font-bold px-1">+{match.job.skills_required.length - 4} more</span>
                                            )}
                                        </div>
                                        {(match.matched_skills || []).length > 0 && (
                                            <p className="text-[10px] text-emerald-600 font-bold flex items-center gap-1">
                                                <CheckCircle size={10} /> {match.matched_skills.length} skill{match.matched_skills.length !== 1 ? 's' : ''} matched from your resume
                                            </p>
                                        )}
                                    </div>

                                    <div className="pt-4 border-t border-slate-50 flex items-center justify-between">
                                        <div className="flex items-center gap-1">
                                            {[1, 2, 3, 4, 5].map((s) => (
                                                <Star key={s} size={10} className={s <= Math.round(match.score * 5) ? 'text-blue-500 fill-blue-500' : 'text-slate-200'} />
                                            ))}
                                        </div>
                                        <div className="flex items-center gap-3">
                                            <button
                                                onClick={(e) => { e.stopPropagation(); setSelectedJob(match); }}
                                                className="text-slate-500 font-black text-[10px] uppercase tracking-widest flex items-center gap-1 hover:text-blue-600 transition-all border border-slate-200 px-3 py-1.5 rounded-lg hover:border-blue-200"
                                            >
                                                <Info size={12} /> View Details
                                            </button>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleApply(match.job.job_id); }}
                                                className="bg-blue-600 text-white font-black text-[10px] uppercase tracking-widest flex items-center gap-1 hover:bg-blue-700 transition-all px-4 py-2 rounded-lg shadow-lg shadow-blue-200"
                                            >
                                                Apply Now <ArrowRight size={12} />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                </div>

                {!loading && filteredResults.length === 0 && searchDone && (
                    <div className="text-center py-24 glass-card bg-slate-50/50 border-dashed border-slate-200">
                        <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                            <Briefcase size={32} />
                        </div>
                        <h4 className="text-slate-900 font-bold text-lg">No matches found</h4>
                        <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                            Try lowering the minimum match score or editing your search query.
                        </p>
                    </div>
                )}
            </div>

            {/* Job Details Modal */}
            <AnimatePresence>
                {selectedJob && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8">
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                            onClick={() => setSelectedJob(null)}
                            className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.9, y: 20 }}
                            className="relative w-full max-w-2xl bg-white rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
                        >
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
                                    <h2 className="text-3xl font-black text-slate-900 leading-tight">{selectedJob.job.title}</h2>
                                    <p className="text-lg font-bold text-blue-600">{selectedJob.job.employer_name}</p>
                                </div>
                                <button onClick={() => setSelectedJob(null)}
                                    className="p-2 hover:bg-white rounded-xl text-slate-400 hover:text-slate-600 transition-all border border-transparent hover:border-slate-100">
                                    <X size={24} />
                                </button>
                            </div>

                            <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8">
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
                                            <Banknote size={16} className="text-emerald-500" />
                                            {formatSalary(selectedJob.job.salary_currency || 'USD', selectedJob.job.salary_min, selectedJob.job.salary_max)}
                                        </p>
                                    </div>
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 col-span-2 md:col-span-1">
                                        <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-1">Match Score</p>
                                        <p className="text-sm font-bold text-blue-600 flex items-center gap-2">
                                            <Target size={16} /> {Math.round(selectedJob.score * 100)}% Match
                                        </p>
                                    </div>
                                </div>

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

                                <div className="space-y-4">
                                    <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-2">
                                        <Sparkles size={16} className="text-blue-400" /> Requirements & Skills
                                    </h3>
                                    <div className="flex flex-wrap gap-2">
                                        {selectedJob.job.skills_required?.map((skill: string) => (
                                            <span key={skill} className="px-3 py-1.5 bg-blue-50 text-blue-600 rounded-lg text-xs font-bold border border-blue-100/50">{skill}</span>
                                        ))}
                                    </div>
                                </div>

                                {selectedJob.job.benefits?.length > 0 && (
                                    <div className="space-y-4">
                                        <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest flex items-center gap-2">
                                            <Star size={16} className="text-amber-400" /> Benefits
                                        </h3>
                                        <div className="flex flex-wrap gap-2">
                                            {selectedJob.job.benefits?.map((benefit: string) => (
                                                <span key={benefit} className="px-3 py-1.5 bg-amber-50 text-amber-700 rounded-lg text-xs font-bold border border-amber-100/50">{benefit}</span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="p-6 md:p-8 border-t border-slate-100 bg-slate-50/50 flex gap-4">
                                <button onClick={() => setSelectedJob(null)}
                                    className="flex-1 px-8 py-4 bg-white text-slate-600 rounded-2xl font-black text-xs uppercase tracking-widest border border-slate-200 hover:bg-slate-50 transition-all active:scale-95 shadow-lg shadow-slate-200">
                                    Close
                                </button>
                                <button onClick={() => handleApply(selectedJob.job.job_id)}
                                    className="flex-[2] px-8 py-4 bg-blue-600 text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-blue-700 transition-all active:scale-95 shadow-lg shadow-blue-200 flex items-center justify-center gap-2">
                                    Apply Now <ArrowRight size={16} />
                                </button>
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>

            {/* Confirm Apply Modal */}
            <AnimatePresence>
                {confirmingJobId && (
                    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                            onClick={() => appStatus !== 'applying' && setConfirmingJobId(null)}
                            className="absolute inset-0 bg-slate-900/60 backdrop-blur-md"
                        />
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.9, y: 20 }}
                            className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl overflow-hidden p-8 text-center space-y-6"
                        >
                            {appStatus === 'success' ? (
                                <>
                                    <div className="w-20 h-20 bg-emerald-50 rounded-full flex items-center justify-center mx-auto text-emerald-600">
                                        <CheckCircle size={40} />
                                    </div>
                                    <div className="space-y-2">
                                        <h3 className="text-2xl font-black text-slate-900">Application Sent!</h3>
                                        <p className="text-slate-500 font-medium">Your application has been successfully submitted. Good luck!</p>
                                    </div>
                                </>
                            ) : appStatus === 'error' ? (
                                <>
                                    <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto text-red-600">
                                        <X size={40} />
                                    </div>
                                    <div className="space-y-2">
                                        <h3 className="text-2xl font-black text-slate-900">Application Failed</h3>
                                        <p className="text-slate-500 font-medium">Something went wrong or you've already applied for this position.</p>
                                    </div>
                                    <button onClick={() => setConfirmingJobId(null)}
                                        className="w-full px-6 py-4 bg-slate-900 text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-slate-800 transition-all">
                                        Close
                                    </button>
                                </>
                            ) : (
                                <>
                                    <div className="w-20 h-20 bg-blue-50 rounded-full flex items-center justify-center mx-auto text-blue-600">
                                        <Info size={40} />
                                    </div>
                                    <div className="space-y-2">
                                        <h3 className="text-2xl font-black text-slate-900">Confirm Application</h3>
                                        <p className="text-slate-500 font-medium">Your profile and resume will be sent to the employer.</p>
                                    </div>
                                    <div className="flex gap-4 pt-4">
                                        <button onClick={() => setConfirmingJobId(null)} disabled={appStatus === 'applying'}
                                            className="flex-1 px-6 py-4 bg-slate-50 text-slate-600 rounded-2xl font-black text-xs uppercase tracking-widest border border-slate-200 hover:bg-slate-100 transition-all disabled:opacity-50">
                                            Cancel
                                        </button>
                                        <button onClick={confirmApply} disabled={appStatus === 'applying'}
                                            className="flex-[1.5] px-6 py-4 bg-blue-600 text-white rounded-2xl font-black text-xs uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 flex items-center justify-center gap-2 disabled:opacity-50">
                                            {appStatus === 'applying'
                                                ? <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                                : <>Yes, Apply <ArrowRight size={16} /></>}
                                        </button>
                                    </div>
                                </>
                            )}
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>

        </div>
    );
};

export default JobSearch;
