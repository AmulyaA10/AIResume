import React, { useEffect, useState } from 'react';
import { jobsApi } from '../../api';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Briefcase, MapPin, Calendar, CheckCircle, ExternalLink, ArrowRight, Building2, Clock } from 'lucide-react';

interface AppliedJob {
    job_id: string;
    title: string;
    company: string;
    location: string;
    posted_date: string;
    resume_id: string;
    applied_at: string;
    applied_status: string;
}

const MyApplications: React.FC = () => {
    const [jobs, setJobs] = useState<AppliedJob[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchApplied = async () => {
            try {
                const response = await jobsApi.getAppliedJobs();
                setJobs(response.data);
            } catch (err) {
                console.error('Failed to fetch applied jobs', err);
            } finally {
                setLoading(false);
            }
        };
        fetchApplied();
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-96 space-y-4">
                <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <div className="text-slate-500 font-medium animate-pulse">Loading your applications...</div>
            </div>
        );
    }

    if (jobs.length === 0) {
        return (
            <div className="max-w-xl mx-auto mt-20 text-center space-y-6 p-8 glass-card border-dashed border-slate-200">
                <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mx-auto text-slate-300">
                    <Briefcase size={40} />
                </div>
                <div className="space-y-2">
                    <h2 className="text-3xl font-black text-slate-900">No Applications Yet</h2>
                    <p className="text-slate-500">Explore jobs and apply to start building your application history. Your future career starts here.</p>
                </div>
                <Link
                    to="/search"
                    className="inline-flex items-center gap-2 bg-blue-600 text-white px-8 py-4 rounded-2xl font-black text-sm uppercase tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-200 active:scale-95"
                >
                    Find Jobs <ArrowRight size={18} />
                </Link>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto p-4 md:p-8 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="space-y-2">
                <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">My <span className="text-blue-600">Applications</span></h1>
                <p className="text-slate-500 font-medium">Tracking {jobs.length} active job applications</p>
            </div>

            {/* Desktop Table View */}
            <div className="hidden md:block glass-card overflow-hidden border-slate-200 shadow-xl bg-white/80 backdrop-blur-xl">
                <table className="w-full text-left">
                    <thead>
                        <tr className="bg-slate-50/50 border-b border-slate-100">
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Job Position</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Company</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Applied Date</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest">Status</th>
                            <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-widest text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {jobs.map((job, idx) => (
                            <motion.tr
                                key={job.job_id}
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: idx * 0.05 }}
                                className="hover:bg-blue-50/30 transition-colors group"
                            >
                                <td className="px-6 py-6">
                                    <div className="space-y-1">
                                        <div className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors">{job.title}</div>
                                        <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                                            <MapPin size={12} /> {job.location || 'Remote'}
                                        </div>
                                    </div>
                                </td>
                                <td className="px-6 py-6">
                                    <div className="flex items-center gap-3">
                                        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400 group-hover:bg-white group-hover:text-blue-500 transition-all border border-transparent group-hover:border-blue-100">
                                            <Building2 size={16} />
                                        </div>
                                        <span className="font-bold text-slate-700">{job.company}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-6">
                                    <div className="flex items-center gap-2 text-sm text-slate-500 font-semibold">
                                        <Calendar size={14} className="text-slate-300" />
                                        {new Date(job.applied_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                    </div>
                                </td>
                                <td className="px-6 py-6 font-medium">
                                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${job.applied_status === 'applied'
                                            ? 'bg-emerald-50 text-emerald-600 border-emerald-100'
                                            : 'bg-blue-50 text-blue-600 border-blue-100'
                                        }`}>
                                        <CheckCircle size={10} /> {job.applied_status}
                                    </span>
                                </td>
                                <td className="px-6 py-6 text-right">
                                    <Link
                                        to={`/jobs/${job.job_id}`}
                                        className="inline-flex items-center gap-1 text-xs font-black text-slate-400 hover:text-blue-600 uppercase tracking-widest transition-all"
                                    >
                                        Details <ExternalLink size={14} />
                                    </Link>
                                </td>
                            </motion.tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Mobile Card View */}
            <div className="md:hidden space-y-4">
                {jobs.map((job) => (
                    <motion.div
                        key={job.job_id}
                        className="glass-card p-6 bg-white border-slate-200 space-y-4"
                        whileHover={{ scale: 1.01 }}
                    >
                        <div className="flex justify-between items-start">
                            <div className="space-y-1">
                                <h3 className="text-xl font-bold text-slate-900">{job.title}</h3>
                                <p className="text-sm font-bold text-blue-600">{job.company}</p>
                            </div>
                            <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-600 border border-emerald-100 text-[10px] font-black uppercase tracking-widest">
                                {job.applied_status}
                            </span>
                        </div>

                        <div className="grid grid-cols-2 gap-4 pt-2">
                            <div className="flex items-center gap-2 text-xs text-slate-500 font-bold uppercase tracking-wider">
                                <MapPin size={14} className="text-slate-300" /> {job.location || 'Remote'}
                            </div>
                            <div className="flex items-center gap-2 text-xs text-slate-500 font-bold uppercase tracking-wider">
                                <Clock size={14} className="text-slate-300" /> {new Date(job.applied_at).toLocaleDateString()}
                            </div>
                        </div>

                        <Link
                            to={`/jobs/${job.job_id}`}
                            className="w-full inline-flex items-center justify-center gap-2 bg-slate-50 border border-slate-200 text-slate-600 py-3 rounded-xl font-black text-xs uppercase tracking-widest hover:bg-slate-100 transition-all"
                        >
                            View Details <ArrowRight size={14} />
                        </Link>
                    </motion.div>
                ))}
            </div>
        </div>
    );
};

export default MyApplications;

