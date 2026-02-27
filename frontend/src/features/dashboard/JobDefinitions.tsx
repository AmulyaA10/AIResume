import React from 'react';
import { Briefcase, Plus, Search, MapPin, Trash2, Edit } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PageHeader, LoadingOverlay } from '../../common';
import { jobsApi } from '../../api';

const JobDefinitions = () => {
    const navigate = useNavigate();
    const [jobs, setJobs] = React.useState<any[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);

    React.useEffect(() => {
        fetchJobs();
    }, []);

    const fetchJobs = async () => {
        setIsLoading(true);
        try {
            const response = await jobsApi.list({});
            setJobs(response.data);
        } catch (error) {
            console.error("Failed to fetch jobs:", error);
        } finally {
            setIsLoading(false);
        }
    };

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

    if (isLoading) return <LoadingOverlay icon={<Briefcase className="w-10 h-10 text-blue-500" />} message="Loading job definitions..." />;
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

            {jobs.length === 0 ? (
                <div className="text-center py-20 glass-card bg-slate-50/50 border-dashed border-slate-200">
                    <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                        <Briefcase size={32} />
                    </div>
                    <h4 className="text-slate-900 font-bold text-lg">No Job Definitions</h4>
                    <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                        Start by creating your first job definition or uploading a PD to automate candidate screening.
                    </p>
                    <button
                        onClick={() => navigate('/jd/new')}
                        className="mt-6 text-blue-600 font-bold hover:underline"
                    >
                        Create New Definition →
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {jobs.map((job) => (
                        <div
                            key={job.job_id}
                            onClick={() => navigate(`/jd/edit/${job.job_id}`)}
                            className="glass-card p-6 hover:shadow-md transition-shadow cursor-pointer group relative"
                        >
                            <div className="flex justify-between items-start mb-4">
                                <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform">
                                    <Briefcase size={20} />
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={(e) => handleDelete(job.job_id, e)}
                                        className="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            </div>
                            <h3 className="text-lg font-bold text-slate-900 mb-2 truncate pr-6">{job.title}</h3>
                            <p className="text-sm text-slate-500 mb-4 line-clamp-2">{job.description}</p>

                            <div className="space-y-2">
                                <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                                    <MapPin size={12} /> {job.location_name || 'Remote'}
                                </div>
                                <div className="flex items-center gap-4 text-xs font-medium text-slate-400">
                                    <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">
                                        {job.job_level}
                                    </span>
                                    <span>•</span>
                                    <span>{new Date(job.posted_date).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default JobDefinitions;
