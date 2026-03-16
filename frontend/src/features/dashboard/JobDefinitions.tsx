import React, { useState, useEffect, useRef } from 'react';
import { Briefcase, Plus, MapPin, Trash2, Users, Sparkles, Star, UserCheck, Pencil, Search, X, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../../common';
import { jobsApi } from '../../api';
import JobCandidatesModal from './JobCandidatesModal';
import JobMatchCandidatesModal from './JobMatchCandidatesModal';
import JobDetailModal from './JobDetailModal';

const JobDefinitions = () => {
    const navigate = useNavigate();
    const [jobs, setJobs] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [selectedJobForCandidates, setSelectedJobForCandidates] = useState<{ id: string, title: string, skills: string[] } | null>(null);
    const [selectedJobForMatches, setSelectedJobForMatches] = useState<{ id: string, title: string, skills: string[] } | null>(null);
    const [selectedJobForShortlisted, setSelectedJobForShortlisted] = useState<{ id: string, title: string, skills: string[] } | null>(null);
    const [selectedJobForSelected, setSelectedJobForSelected] = useState<{ id: string, title: string, skills: string[] } | null>(null);
    const [selectedJobForRejected, setSelectedJobForRejected] = useState<{ id: string, title: string, skills: string[] } | null>(null);
    const [selectedJobForDetail, setSelectedJobForDetail] = useState<any | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [filterLevel, setFilterLevel] = useState('');
    const [filterStatus, setFilterStatus] = useState('');
    const [filterHasApplicants, setFilterHasApplicants] = useState(false);
    const [filterLocation, setFilterLocation] = useState('');
    const [filterDateRange, setFilterDateRange] = useState('');
    const [locationGroups, setLocationGroups] = useState<Record<string, string[]>>({});
    const [locationsFetched, setLocationsFetched] = useState(false);

    const [searchIntent, setSearchIntent] = useState<{ location: string | null; topN: number | null; sortBySalary: boolean } | null>(null);

    const activeFilterCount = [searchQuery, filterLevel, filterStatus, filterLocation, filterDateRange].filter(Boolean).length + (filterHasApplicants ? 1 : 0);
    const clearAllFilters = () => { setSearchQuery(''); setFilterLevel(''); setFilterStatus(''); setFilterLocation(''); setFilterDateRange(''); setFilterHasApplicants(false); setSearchIntent(null); };

    // Always holds the latest filter values — read by effects to avoid stale closures
    const filterRef = useRef({ search: searchQuery, filterLevel, filterStatus, filterLocation, filterDateRange, filterHasApplicants });
    useEffect(() => {
        filterRef.current = { search: searchQuery, filterLevel, filterStatus, filterLocation, filterDateRange, filterHasApplicants };
    });

    // Cache parsed intents per query string to avoid redundant LLM calls
    const intentCache = useRef<Record<string, any>>({});

    const fetchJobs = async (params?: Record<string, any>) => {
        setIsLoading(true);
        try {
            const apiParams: Record<string, any> = {
                limit: 200,
                ...(params?.filterLevel ? { job_level: params.filterLevel } : {}),
                ...(params?.filterStatus ? { status: params.filterStatus } : {}),
                ...(params?.filterLocation ? { location: params.filterLocation } : {}),
                ...(params?.filterDateRange ? { date_range: parseInt(params.filterDateRange) } : {}),
                ...(params?.filterHasApplicants ? { has_applicants: true } : {}),
            };

            if (params?.search?.trim()) {
                const raw = params.search.trim();
                let intent = intentCache.current[raw];
                if (!intent) {
                    try {
                        const r = await jobsApi.parseQueryIntent(raw);
                        intent = r.data;
                        intentCache.current[raw] = intent;
                    } catch {
                        intent = { cleanQuery: raw, location: null, locationAliases: [], topN: null, sortBySalary: false };
                    }
                }
                apiParams.search = intent.cleanQuery || raw;
                if (intent.locationAliases?.length && !params.filterLocation) {
                    apiParams.location_aliases = intent.locationAliases.join(',');
                }
                if (intent.sortBySalary) apiParams.sort_by_salary = true;
                if (intent.topN && intent.topN > 0) {
                    apiParams.top_n = intent.topN;
                    apiParams.limit = intent.topN;
                }
                const hasIntent = !!(intent.location || intent.topN || intent.sortBySalary);
                setSearchIntent(hasIntent ? { location: intent.location, topN: intent.topN, sortBySalary: intent.sortBySalary } : null);
            } else {
                setSearchIntent(null);
                apiParams.search = undefined;
            }

            const response = await jobsApi.list(apiParams);
            setJobs(response.data);
        } catch (error) {
            console.error("Failed to fetch jobs:", error);
        } finally {
            setIsLoading(false);
        }
    };

    // Fetch on mount and whenever filters change; debounce only free-text search
    useEffect(() => {
        const t = setTimeout(() => fetchJobs(filterRef.current), searchQuery ? 400 : 0);
        return () => clearTimeout(t);
    }, [searchQuery, filterLevel, filterStatus, filterLocation, filterDateRange, filterHasApplicants]);

    // Re-fetch when a modal closes so counts stay current
    const modalClosedRef = useRef(false);
    React.useEffect(() => {
        if (!modalClosedRef.current) { modalClosedRef.current = true; return; }
        if (!selectedJobForCandidates && !selectedJobForShortlisted && !selectedJobForSelected && !selectedJobForRejected) {
            fetchJobs(filterRef.current);
        }
    }, [selectedJobForCandidates, selectedJobForShortlisted, selectedJobForSelected, selectedJobForRejected]);

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this job definition?")) return;
        try {
            await jobsApi.delete(id);
            setJobs(jobs.filter(j => j.job_id !== id));
        } catch (error) {
            console.error("Failed to delete job:", error);
        }
    };

    const fetchLocations = async () => {
        if (locationsFetched) return;
        try {
            const r = await jobsApi.getLocations();
            setLocationGroups(r.data.groups || {});
        } catch {
            setLocationGroups({});
        } finally {
            setLocationsFetched(true);
        }
    };

    const hasLocationGroups = Object.keys(locationGroups).length > 0;

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <PageHeader
                title="Job Definitions"
                subtitle="Manage job descriptions and screening criteria."
                action={
                    <button
                        onClick={() => navigate('/jd/new')}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-blue-500/20 transition-all"
                    >
                        <Plus size={18} /> New Job Definition
                    </button>
                }
            />

            {/* Filter bar */}
            {(jobs.length > 0 || activeFilterCount > 0) && (
                <div className="flex flex-wrap gap-3 items-center">
                    <div className="relative flex-1 min-w-48">
                        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                        <input
                            type="text"
                            placeholder="AI search — try 'senior backend engineer'..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            className="w-full pl-9 pr-8 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200"
                        />
                        {searchQuery && (
                            <button onClick={() => setSearchQuery('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                                <X size={14} />
                            </button>
                        )}
                    </div>
                    <select
                        value={filterLevel}
                        onChange={e => setFilterLevel(e.target.value)}
                        className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 text-slate-600"
                    >
                        <option value="">All Levels</option>
                        <option value="JUNIOR">Junior</option>
                        <option value="MID">Mid</option>
                        <option value="SENIOR">Senior</option>
                    </select>
                    <select
                        value={filterStatus}
                        onChange={e => setFilterStatus(e.target.value)}
                        className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 text-slate-600"
                    >
                        <option value="">All Status</option>
                        <option value="in_progress">In Progress</option>
                        <option value="completed">Completed</option>
                    </select>
                    <select
                        value={filterLocation}
                        onChange={e => setFilterLocation(e.target.value)}
                        onFocus={fetchLocations}
                        className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 text-slate-600"
                    >
                        <option value="">All Locations</option>
                        {hasLocationGroups
                            ? [
                                ...Object.entries(locationGroups).filter(([r]) => r.toLowerCase() !== 'remote'),
                                ...Object.entries(locationGroups).filter(([r]) => r.toLowerCase() === 'remote'),
                              ].map(([region, locs]) => (
                                <optgroup key={region} label={region}>
                                    {(locs as string[]).map(loc => <option key={loc} value={loc}>{loc}</option>)}
                                </optgroup>
                              ))
                            : null
                        }
                    </select>
                    <select
                        value={filterDateRange}
                        onChange={e => setFilterDateRange(e.target.value)}
                        className="px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-200 text-slate-600"
                    >
                        <option value="">Any Date</option>
                        <option value="7">Last 7 days</option>
                        <option value="30">Last 30 days</option>
                        <option value="90">Last 90 days</option>
                    </select>
                    <button
                        onClick={() => setFilterHasApplicants(v => !v)}
                        className={`px-3 py-2 text-sm rounded-lg border font-medium transition-colors ${filterHasApplicants ? 'bg-indigo-50 text-indigo-600 border-indigo-200' : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-50'}`}
                    >
                        Has Applicants
                    </button>
                    {activeFilterCount > 0 && (
                        <button
                            onClick={clearAllFilters}
                            className="px-3 py-2 text-sm text-slate-500 hover:text-slate-700 flex items-center gap-1.5 border border-slate-200 rounded-lg bg-white hover:bg-slate-50"
                        >
                            <X size={13} /> Clear ({activeFilterCount})
                        </button>
                    )}
                    {isLoading
                        ? <Loader2 size={15} className="text-slate-400 animate-spin" />
                        : <span className="text-xs text-slate-400 font-medium">{jobs.length} result{jobs.length !== 1 ? 's' : ''}</span>
                    }
                </div>
            )}

            {/* AI intent banner */}
            {searchIntent && !isLoading && (
                <div className="flex flex-wrap gap-3 items-center text-xs font-semibold text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2">
                    <Sparkles size={13} className="text-blue-500 shrink-0" />
                    {searchIntent.location && (
                        <span className="flex items-center gap-1">
                            <MapPin size={12} className="text-blue-500" /> {searchIntent.location}
                        </span>
                    )}
                    {searchIntent.sortBySalary && (
                        <span className="flex items-center gap-1 text-green-700">↑ Sorted by salary</span>
                    )}
                    {searchIntent.topN && (
                        <span>Top {jobs.length} shown</span>
                    )}
                </div>
            )}

            {isLoading && jobs.length === 0 ? (
                <div className="flex items-center justify-center py-24">
                    <Loader2 size={32} className="text-blue-400 animate-spin" />
                </div>
            ) : jobs.length === 0 && activeFilterCount === 0 ? (
                <div className="text-center py-20 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                        <Briefcase size={32} />
                    </div>
                    <h4 className="text-slate-900 font-bold text-lg">No Job Definitions</h4>
                    <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                        Start by creating your first job definition or uploading a JD to automate candidate screening.
                    </p>
                    <button
                        onClick={() => navigate('/jd/new')}
                        className="mt-6 text-blue-600 font-bold hover:underline"
                    >
                        Create New Definition →
                    </button>
                </div>
            ) : (activeFilterCount > 0 && jobs.length === 0) ? (
                <div className="text-center py-16 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <p className="text-slate-500 font-medium">No jobs match the current filters.</p>
                    <button onClick={clearAllFilters} className="mt-3 text-blue-600 text-sm font-bold hover:underline">Clear filters</button>
                </div>
            ) : (
                <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 transition-opacity ${isLoading ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
                    {jobs.map((job) => (
                        <div
                            key={job.job_id}
                            onClick={() => setSelectedJobForDetail(job)}
                            className="glass-card p-4 hover:shadow-lg hover:border-blue-200 transition-all cursor-pointer group relative flex flex-col"
                            style={{ minHeight: '220px' }}
                        >
                            {/* Title + salary + hover actions */}
                            <div className="flex items-start gap-2 shrink-0">
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-baseline gap-2 min-w-0">
                                        <p className="font-bold text-slate-900 text-sm leading-snug truncate">{job.title}</p>
                                        {(job.salary_min > 0 || job.salary_max > 0) && (
                                            <span className="shrink-0 text-[11px] font-semibold text-green-700 whitespace-nowrap">
                                                {job.salary_currency || 'USD'} {job.salary_min > 0 ? `${(job.salary_min / 1000).toFixed(0)}K` : ''}
                                                {job.salary_min > 0 && job.salary_max > 0 ? '–' : ''}
                                                {job.salary_max > 0 ? `${(job.salary_max / 1000).toFixed(0)}K` : ''}
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <div
                                    className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto transition-opacity"
                                    onClick={e => e.stopPropagation()}
                                >
                                    <button onClick={(e) => { e.stopPropagation(); navigate(`/jd/edit/${job.job_id}`); }} className="p-1.5 text-slate-400 hover:text-blue-500 transition-colors" title="Edit"><Pencil size={13} /></button>
                                    <button onClick={(e) => handleDelete(job.job_id, e)} className="p-1.5 text-slate-400 hover:text-red-500 transition-colors" title="Delete"><Trash2 size={13} /></button>
                                </div>
                            </div>

                            {/* Location — second line, colored */}
                            {/* Location · level · employment type — second line in purple */}
                            <div className="flex items-center gap-1.5 mt-0.5 shrink-0 flex-wrap">
                                <span className="flex items-center gap-1 text-[11px] font-semibold text-purple-600">
                                    <MapPin size={10} className="shrink-0 text-purple-400" />
                                    {(job.location_name || 'Remote').replace(/\s*\(.*?\)\s*/g, '').trim()}
                                </span>
                                {job.job_level && (() => {
                                    const expMap: Record<string, string> = {
                                        entry: '0–2 yrs', junior: '0–2 yrs', mid: '2–5 yrs',
                                        senior: '5–8 yrs', lead: '8–12 yrs', principal: '10+ yrs',
                                        staff: '8–12 yrs', director: '12+ yrs', vp: '15+ yrs',
                                        'c-suite': '15+ yrs', executive: '15+ yrs',
                                    };
                                    const exp = expMap[job.job_level.toLowerCase()];
                                    return (
                                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200 uppercase tracking-wide">
                                            {job.job_level}{exp ? ` · ${exp}` : ''}
                                        </span>
                                    );
                                })()}
                                {job.employment_type && (
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-100">
                                        {job.employment_type.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}
                                    </span>
                                )}
                            </div>

                            {/* Key requirements (skills) */}
                            <div className="flex flex-wrap gap-1 mt-2 flex-1 content-start">
                                {job.skills_required?.length > 0
                                    ? job.skills_required.slice(0, 8).map((s: string) => (
                                        <span key={s} className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">{s}</span>
                                    ))
                                    : <span className="text-[11px] text-slate-300 italic">No requirements listed</span>
                                }
                            </div>

                            {/* Footer */}
                            <div className="flex items-center gap-2 shrink-0 mt-2 pt-2 border-t border-slate-100 mt-auto flex-wrap">
                                {job.shortlisted_count > 0 && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedJobForShortlisted({ id: job.job_id, title: job.title, skills: job.skills_required || [] }); }}
                                        className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 transition-colors"
                                    >
                                        <Star size={9} />{job.shortlisted_count} Shortlisted
                                    </button>
                                )}
                                {job.applied_count > 0 && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedJobForCandidates({ id: job.job_id, title: job.title, skills: job.skills_required || [] }); }}
                                        className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100 transition-colors"
                                    >
                                        <Users size={9} />{job.applied_count} Applied
                                    </button>
                                )}
                                {job.selected_count > 0 && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedJobForSelected({ id: job.job_id, title: job.title, skills: job.skills_required || [] }); }}
                                        className="inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-green-50 text-green-700 border-green-200 hover:bg-green-100 transition-colors"
                                    >
                                        <UserCheck size={9} />{job.selected_count} Selected
                                    </button>
                                )}
                                {job.posted_date && (
                                    <span className="text-[10px] text-slate-400 whitespace-nowrap ml-auto">
                                        Posted {new Date(job.posted_date).toLocaleDateString()}
                                    </span>
                                )}
                                <button
                                    onClick={(e) => { e.stopPropagation(); setSelectedJobForMatches({ id: job.job_id, title: job.title, skills: job.skills_required || [] }); }}
                                    className={`${job.posted_date ? '' : 'ml-auto '}inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded border bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100 transition-colors`}
                                >
                                    <Sparkles size={9} /> Find Matches
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
            
            {selectedJobForCandidates && (
                <JobCandidatesModal
                    jobId={selectedJobForCandidates.id}
                    jobTitle={selectedJobForCandidates.title}
                    jobSkills={selectedJobForCandidates.skills}
                    statusFilter="applied"
                    onClose={() => setSelectedJobForCandidates(null)}
                    onViewSelected={() => {
                        const job = selectedJobForCandidates;
                        setSelectedJobForCandidates(null);
                        setSelectedJobForSelected({ id: job.id, title: job.title, skills: job.skills });
                    }}
                />
            )}

            {selectedJobForMatches && (
                <JobMatchCandidatesModal
                    jobId={selectedJobForMatches.id}
                    jobTitle={selectedJobForMatches.title}
                    jobSkills={selectedJobForMatches.skills}
                    onClose={() => setSelectedJobForMatches(null)}
                />
            )}

            {selectedJobForShortlisted && (
                <JobCandidatesModal
                    jobId={selectedJobForShortlisted.id}
                    jobTitle={selectedJobForShortlisted.title}
                    jobSkills={selectedJobForShortlisted.skills}
                    statusFilter="shortlisted"
                    onClose={() => setSelectedJobForShortlisted(null)}
                />
            )}

            {selectedJobForSelected && (
                <JobCandidatesModal
                    jobId={selectedJobForSelected.id}
                    jobTitle={selectedJobForSelected.title}
                    jobSkills={selectedJobForSelected.skills}
                    statusFilter="selected"
                    onClose={() => setSelectedJobForSelected(null)}
                />
            )}

            {selectedJobForDetail && (
                <JobDetailModal
                    job={selectedJobForDetail}
                    onClose={() => setSelectedJobForDetail(null)}
                />
            )}

            {selectedJobForRejected && (
                <JobCandidatesModal
                    jobId={selectedJobForRejected.id}
                    jobTitle={selectedJobForRejected.title}
                    jobSkills={selectedJobForRejected.skills}
                    statusFilter="rejected"
                    onClose={() => setSelectedJobForRejected(null)}
                />
            )}
        </div>
    );
};

export default JobDefinitions;
