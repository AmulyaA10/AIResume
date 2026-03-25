import React, { useState, useEffect, useCallback } from 'react';
import {
    Bot, Zap, CheckCircle, XCircle, BarChart2, RefreshCw, Play,
    Settings2, ChevronDown, Loader2, Clock, Briefcase, FileText,
    ToggleLeft, ToggleRight, AlertCircle, X
} from 'lucide-react';
import { agentsApi, jobsApi, resumesApi } from '../../api';
import { PageHeader } from '../../common';

// ── types ──────────────────────────────────────────────────────────────────

interface Stats {
    total_screened: number;
    shortlisted: number;
    rejected: number;
    pass_rate: number;
    jobs_covered: number;
    resumes_covered: number;
    per_job: PerJobRow[];
}

interface PerJobRow {
    job_id: string;
    title: string;
    screened: number;
    shortlisted: number;
    rejected: number;
    pass_rate: number;
}

interface HistoryRow {
    resume_id: string;
    job_id: string;
    job_title: string;
    status: 'auto_shortlisted' | 'auto_rejected';
    timestamp: string;
}

interface AgentConfig {
    threshold: number;
    max_jds: number;
    enabled: boolean;
    jd_enabled: boolean;
}

// ── stat card ──────────────────────────────────────────────────────────────

const StatCard = ({ icon: Icon, label, value, sub, color }: {
    icon: React.ElementType; label: string; value: string | number; sub?: string; color: string;
}) => (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex items-start gap-4">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
            <Icon size={20} />
        </div>
        <div>
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            <p className="text-sm font-semibold text-slate-600">{label}</p>
            {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
        </div>
    </div>
);

// ── main page ──────────────────────────────────────────────────────────────

const AgentDashboard = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [history, setHistory] = useState<HistoryRow[]>([]);
    const [config, setConfig] = useState<AgentConfig>({ threshold: 70, max_jds: 20, enabled: true, jd_enabled: true });
    const [loadingStats, setLoadingStats] = useState(true);
    const [loadingHistory, setLoadingHistory] = useState(true);
    const [savingConfig, setSavingConfig] = useState(false);
    const [configDirty, setConfigDirty] = useState(false);
    const [configSaved, setConfigSaved] = useState(false);

    // Manual trigger state
    const [resumes, setResumes] = useState<string[]>([]);
    const [jobs, setJobs] = useState<any[]>([]);
    const [triggerResume, setTriggerResume] = useState('');
    const [triggerJob, setTriggerJob] = useState('');
    const [triggering, setTriggering] = useState(false);
    const [triggerMsg, setTriggerMsg] = useState<{ ok: boolean; text: string } | null>(null);

    const [historyJobFilter, setHistoryJobFilter] = useState('');
    const [showAllJobs, setShowAllJobs] = useState(false);
    const [runningAll, setRunningAll] = useState(false);
    const [runAllMsg, setRunAllMsg] = useState<{ ok: boolean; text: string } | null>(null);

    const load = useCallback(async () => {
        setLoadingStats(true);
        setLoadingHistory(true);
        try {
            const [sRes, hRes, cfgRes] = await Promise.all([
                agentsApi.getStats(),
                agentsApi.getHistory({ limit: 60 }),
                agentsApi.getConfig(),
            ]);
            setStats(sRes.data);
            setHistory(hRes.data);
            setConfig(cfgRes.data);
        } catch (e) {
            console.error('Failed to load agent data', e);
        } finally {
            setLoadingStats(false);
            setLoadingHistory(false);
        }
    }, []);

    useEffect(() => {
        load();
        resumesApi.list().then(r => setResumes(r.data?.resumes || [])).catch(() => {});
        jobsApi.list({ limit: 200 }).then(r => setJobs(r.data || [])).catch(() => {});
    }, [load]);

    const handleConfigChange = (patch: Partial<AgentConfig>) => {
        setConfig(prev => ({ ...prev, ...patch }));
        setConfigDirty(true);
        setConfigSaved(false);
    };

    const saveConfig = async () => {
        setSavingConfig(true);
        try {
            const res = await agentsApi.saveConfig(config);
            setConfig(res.data);
            setConfigDirty(false);
            setConfigSaved(true);
            setTimeout(() => setConfigSaved(false), 3000);
        } catch (e) {
            console.error('Failed to save config', e);
        } finally {
            setSavingConfig(false);
        }
    };

    const runAll = async () => {
        setRunningAll(true);
        setRunAllMsg(null);
        try {
            const res = await agentsApi.runAll();
            const count = res.data?.resume_count ?? 0;
            setRunAllMsg({ ok: true, text: `Queued screening for ${count} resume${count !== 1 ? 's' : ''} against all open JDs. Results will appear in history shortly.` });
            setTimeout(() => load(), 5000);
        } catch (e: any) {
            const detail = e?.response?.data?.detail || 'Failed to start full screening.';
            setRunAllMsg({ ok: false, text: detail });
        } finally {
            setRunningAll(false);
        }
    };

    const runManual = async () => {
        if (!triggerResume) return;
        setTriggering(true);
        setTriggerMsg(null);
        try {
            await agentsApi.run(triggerResume, triggerJob || undefined);
            setTriggerMsg({ ok: true, text: `Screening queued for ${triggerResume}. Results will appear in history shortly.` });
            setTimeout(() => load(), 4000);
        } catch (e: any) {
            const detail = e?.response?.data?.detail || 'Failed to trigger screening.';
            setTriggerMsg({ ok: false, text: detail });
        } finally {
            setTriggering(false);
        }
    };

    const filteredHistory = historyJobFilter
        ? history.filter(r => r.job_id === historyJobFilter)
        : history;

    const visibleJobs = stats?.per_job
        ? (showAllJobs ? stats.per_job : stats.per_job.slice(0, 6))
        : [];

    return (
        <div className="p-6 space-y-6 max-w-6xl mx-auto">
            <div className="flex items-start justify-between gap-4">
                <PageHeader
                    title="Autonomous Recruiter"
                    subtitle="Monitors resume uploads and auto-screens candidates against open job definitions"
                    icon={<Bot size={22} />}
                />
                <div className="flex items-center gap-2 shrink-0">
                    <button
                        onClick={runAll}
                        disabled={runningAll}
                        className="flex items-center gap-2 px-4 py-2 text-sm font-bold bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-60 transition-colors"
                    >
                        {runningAll ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                        {runningAll ? 'Running…' : 'Run Full Screening'}
                    </button>
                    <button
                        onClick={load}
                        className="flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                        <RefreshCw size={14} className={loadingStats ? 'animate-spin' : ''} />
                        Refresh
                    </button>
                </div>
            </div>

            {runAllMsg && (
                <div className={`flex items-start gap-2 text-sm rounded-xl px-4 py-3 border ${
                    runAllMsg.ok ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'
                }`}>
                    {runAllMsg.ok ? <CheckCircle size={15} className="shrink-0 mt-0.5" /> : <AlertCircle size={15} className="shrink-0 mt-0.5" />}
                    <span>{runAllMsg.text}</span>
                    <button onClick={() => setRunAllMsg(null)} className="ml-auto shrink-0 opacity-50 hover:opacity-100"><X size={14} /></button>
                </div>
            )}

            {/* ── stats cards ── */}
            {loadingStats ? (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {[...Array(4)].map((_, i) => (
                        <div key={i} className="h-24 bg-slate-100 rounded-2xl animate-pulse" />
                    ))}
                </div>
            ) : (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard icon={Zap} label="Total Screened" value={stats?.total_screened ?? 0}
                        sub={`across ${stats?.jobs_covered ?? 0} jobs`} color="bg-violet-50 text-violet-600" />
                    <StatCard icon={CheckCircle} label="Shortlisted" value={stats?.shortlisted ?? 0}
                        sub="auto_shortlisted" color="bg-emerald-50 text-emerald-600" />
                    <StatCard icon={XCircle} label="Rejected" value={stats?.rejected ?? 0}
                        sub="auto_rejected" color="bg-red-50 text-red-500" />
                    <StatCard icon={BarChart2} label="Pass Rate" value={`${stats?.pass_rate ?? 0}%`}
                        sub={`${stats?.resumes_covered ?? 0} unique resumes`} color="bg-blue-50 text-blue-600" />
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* ── per-job breakdown ── */}
                <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
                    <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Briefcase size={15} className="text-slate-500" />
                            <h3 className="font-bold text-slate-800 text-sm">Per-Job Breakdown</h3>
                        </div>
                        {(stats?.per_job?.length ?? 0) > 6 && (
                            <button onClick={() => setShowAllJobs(p => !p)}
                                className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1">
                                {showAllJobs ? 'Show less' : `Show all ${stats!.per_job.length}`}
                                <ChevronDown size={12} className={showAllJobs ? 'rotate-180' : ''} />
                            </button>
                        )}
                    </div>
                    {loadingStats ? (
                        <div className="p-6 space-y-2">
                            {[...Array(4)].map((_, i) => <div key={i} className="h-8 bg-slate-100 rounded-lg animate-pulse" />)}
                        </div>
                    ) : visibleJobs.length === 0 ? (
                        <div className="py-14 text-center text-slate-400">
                            <Bot size={32} className="mx-auto mb-3 opacity-30" />
                            <p className="text-sm">No screening results yet.</p>
                            <p className="text-xs mt-1">Upload a resume to trigger the agent.</p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="bg-slate-50 text-xs font-bold text-slate-500 uppercase tracking-wider">
                                        <th className="text-left px-5 py-3">Job</th>
                                        <th className="text-right px-4 py-3">Screened</th>
                                        <th className="text-right px-4 py-3">Shortlisted</th>
                                        <th className="text-right px-4 py-3">Rejected</th>
                                        <th className="text-right px-5 py-3">Pass Rate</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-50">
                                    {visibleJobs.map(row => (
                                        <tr key={row.job_id} className="hover:bg-slate-50/60 transition-colors">
                                            <td className="px-5 py-3 font-medium text-slate-800 truncate max-w-[200px]" title={row.title}>
                                                {row.title || row.job_id}
                                            </td>
                                            <td className="px-4 py-3 text-right text-slate-600">{row.screened}</td>
                                            <td className="px-4 py-3 text-right">
                                                <span className="text-emerald-600 font-semibold">{row.shortlisted}</span>
                                            </td>
                                            <td className="px-4 py-3 text-right">
                                                <span className="text-red-500 font-semibold">{row.rejected}</span>
                                            </td>
                                            <td className="px-5 py-3 text-right">
                                                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold border ${
                                                    row.pass_rate >= 50
                                                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                                        : 'bg-red-50 text-red-600 border-red-200'
                                                }`}>
                                                    {row.pass_rate}%
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* ── config panel ── */}
                <div className="space-y-4">
                    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-5">
                        <div className="flex items-center gap-2">
                            <Settings2 size={15} className="text-slate-500" />
                            <h3 className="font-bold text-slate-800 text-sm">Agent Settings</h3>
                        </div>

                        {/* Resume upload toggle */}
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-semibold text-slate-700">Auto-screening</p>
                                <p className="text-xs text-slate-400">Run on every resume upload</p>
                            </div>
                            <button onClick={() => handleConfigChange({ enabled: !config.enabled })}>
                                {config.enabled
                                    ? <ToggleRight size={28} className="text-violet-600" />
                                    : <ToggleLeft size={28} className="text-slate-300" />
                                }
                            </button>
                        </div>

                        {/* JD upload toggle */}
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-semibold text-slate-700">Screen on JD upload</p>
                                <p className="text-xs text-slate-400">Run on every new job posting</p>
                            </div>
                            <button onClick={() => handleConfigChange({ jd_enabled: !config.jd_enabled })}>
                                {config.jd_enabled
                                    ? <ToggleRight size={28} className="text-violet-600" />
                                    : <ToggleLeft size={28} className="text-slate-300" />
                                }
                            </button>
                        </div>

                        <div className="border-t border-slate-100" />

                        {/* Threshold */}
                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <p className="text-sm font-semibold text-slate-700">Selection Threshold</p>
                                <span className="text-sm font-bold text-violet-700 bg-violet-50 px-2 py-0.5 rounded-lg">
                                    {config.threshold}%
                                </span>
                            </div>
                            <input
                                type="range" min={40} max={90} step={5}
                                value={config.threshold}
                                onChange={e => handleConfigChange({ threshold: Number(e.target.value) })}
                                className="w-full accent-violet-600"
                            />
                            <div className="flex justify-between text-xs text-slate-400 mt-1">
                                <span>40% (lenient)</span>
                                <span>90% (strict)</span>
                            </div>
                        </div>

                        {/* Max JDs */}
                        <div>
                            <div className="flex justify-between items-center mb-2">
                                <p className="text-sm font-semibold text-slate-700">Max JDs per Upload</p>
                                <span className="text-sm font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-lg">
                                    {config.max_jds}
                                </span>
                            </div>
                            <input
                                type="range" min={5} max={50} step={5}
                                value={config.max_jds}
                                onChange={e => handleConfigChange({ max_jds: Number(e.target.value) })}
                                className="w-full accent-blue-600"
                            />
                            <div className="flex justify-between text-xs text-slate-400 mt-1">
                                <span>5</span>
                                <span>50</span>
                            </div>
                        </div>

                        <button
                            onClick={saveConfig}
                            disabled={!configDirty || savingConfig}
                            className={`w-full py-2 rounded-xl text-sm font-bold border transition-all ${
                                configSaved
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : configDirty
                                    ? 'bg-violet-600 text-white border-violet-600 hover:bg-violet-700'
                                    : 'bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed'
                            }`}
                        >
                            {savingConfig ? <Loader2 size={14} className="animate-spin inline mr-2" /> : null}
                            {configSaved ? '✓ Saved' : 'Save Settings'}
                        </button>
                    </div>

                    {/* ── manual trigger ── */}
                    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 space-y-4">
                        <div className="flex items-center gap-2">
                            <Play size={14} className="text-slate-500" />
                            <h3 className="font-bold text-slate-800 text-sm">Manual Trigger</h3>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-slate-600 mb-1 block">Resume</label>
                            <select
                                value={triggerResume}
                                onChange={e => setTriggerResume(e.target.value)}
                                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-200"
                            >
                                <option value="">Select resume…</option>
                                {resumes.map(r => <option key={r} value={r}>{r}</option>)}
                            </select>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-slate-600 mb-1 block">Job (optional — blank = all open JDs)</label>
                            <select
                                value={triggerJob}
                                onChange={e => setTriggerJob(e.target.value)}
                                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-violet-200"
                            >
                                <option value="">All open JDs</option>
                                {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.title}</option>)}
                            </select>
                        </div>

                        {triggerMsg && (
                            <div className={`flex items-start gap-2 text-xs rounded-lg p-3 border ${
                                triggerMsg.ok
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                    : 'bg-red-50 text-red-600 border-red-200'
                            }`}>
                                {triggerMsg.ok ? <CheckCircle size={13} className="shrink-0 mt-0.5" /> : <AlertCircle size={13} className="shrink-0 mt-0.5" />}
                                {triggerMsg.text}
                            </div>
                        )}

                        <button
                            onClick={runManual}
                            disabled={!triggerResume || triggering}
                            className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-sm font-bold bg-violet-600 text-white border border-violet-600 hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            {triggering ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                            {triggering ? 'Queuing…' : 'Run Screening'}
                        </button>
                    </div>
                </div>
            </div>

            {/* ── activity history ── */}
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                        <Clock size={15} className="text-slate-500" />
                        <h3 className="font-bold text-slate-800 text-sm">Screening History</h3>
                        <span className="text-xs text-slate-400">({filteredHistory.length} records)</span>
                    </div>
                    <select
                        value={historyJobFilter}
                        onChange={e => setHistoryJobFilter(e.target.value)}
                        className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none max-w-[240px]"
                    >
                        <option value="">All jobs</option>
                        {jobs.map(j => <option key={j.job_id} value={j.job_id}>{j.title}</option>)}
                    </select>
                </div>

                {loadingHistory ? (
                    <div className="p-6 space-y-2">
                        {[...Array(5)].map((_, i) => <div key={i} className="h-8 bg-slate-100 rounded-lg animate-pulse" />)}
                    </div>
                ) : filteredHistory.length === 0 ? (
                    <div className="py-14 text-center text-slate-400">
                        <FileText size={28} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">No history yet.</p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-slate-50 text-xs font-bold text-slate-500 uppercase tracking-wider">
                                    <th className="text-left px-5 py-3">Resume</th>
                                    <th className="text-left px-4 py-3">Job</th>
                                    <th className="text-center px-4 py-3">Decision</th>
                                    <th className="text-right px-5 py-3">Screened At</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                                {filteredHistory.map((row, i) => (
                                    <tr key={i} className="hover:bg-slate-50/60 transition-colors">
                                        <td className="px-5 py-3 text-slate-700 font-medium truncate max-w-[200px]" title={row.resume_id}>
                                            <div className="flex items-center gap-1.5">
                                                <FileText size={12} className="text-slate-400 shrink-0" />
                                                {row.resume_id}
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-slate-600 truncate max-w-[200px]" title={row.job_title}>
                                            {row.job_title || row.job_id}
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                                                row.status === 'auto_shortlisted'
                                                    ? 'bg-violet-50 text-violet-700 border-violet-200'
                                                    : 'bg-rose-50 text-rose-600 border-rose-200'
                                            }`}>
                                                {row.status === 'auto_shortlisted'
                                                    ? <><CheckCircle size={10} /> Shortlisted</>
                                                    : <><XCircle size={10} /> Rejected</>
                                                }
                                            </span>
                                        </td>
                                        <td className="px-5 py-3 text-right text-xs text-slate-400">
                                            {row.timestamp
                                                ? new Date(row.timestamp).toLocaleString()
                                                : '—'
                                            }
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentDashboard;
