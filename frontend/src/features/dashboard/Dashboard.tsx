import React from 'react';
import { Linkedin, History, AlertCircle, User, ArrowRight, Users, CheckCircle, Target, Zap, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';

const Dashboard = () => {
    const { persona, user } = useAuth();
    const [stats, setStats] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        const fetchStats = async () => {
            try {
                const token = localStorage.getItem('token') || 'mock-token-123';
                const response = await fetch('http://localhost:8000/api/v1/dashboard/stats', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    setStats(data);
                }
            } catch (error) {
                console.error("Failed to fetch dashboard stats", error);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, []);

    const isRecruiter = persona === 'recruiter';

    const renderStatCard = (title: string, value: number, icon: React.ReactNode, color: string) => (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-all hover:-translate-y-1">
            <div className={`w-12 h-12 rounded-lg ${color} flex items-center justify-center mb-4 text-white shadow-lg`}>
                {icon}
            </div>
            <p className="text-slate-500 text-sm font-medium">{title}</p>
            <h4 className="text-2xl font-bold text-slate-900 mt-1">{value}</h4>
        </div>
    );

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            {/* Hero Section */}
            <div className={`bg-gradient-to-r ${isRecruiter ? 'from-indigo-600 to-violet-700' : 'from-blue-600 to-indigo-700'} rounded-2xl p-8 text-white shadow-xl relative overflow-hidden`}>
                <div className="relative z-10">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-[10px] font-bold uppercase tracking-wider mb-4 border border-white/30">
                        {isRecruiter ? <Shield size={12} /> : <User size={12} />}
                        {isRecruiter ? 'Recruiter Intelligence' : 'Talent Portal'}
                    </div>
                    <h2 className="text-3xl font-bold mb-2">
                        {isRecruiter ? `Welcome back, ${user?.name || 'Recruiter'}` : 'Elevate Your Profile.'}
                    </h2>
                    <p className="opacity-90 max-w-md">
                        {isRecruiter
                            ? `You have ${stats?.total_resumes || 0} candidates indexed across your talent pipeline.`
                            : `Our AI engine has analyzed ${stats?.total_resumes || 0} documents in your private corpus.`}
                    </p>
                    <div className="mt-6 flex gap-3">
                        <button className="bg-white text-indigo-700 px-6 py-2 rounded-lg font-semibold flex items-center gap-2 hover:bg-slate-100 transition-all shadow-lg active:scale-95">
                            <Linkedin size={18} /> {isRecruiter ? 'Sync ATS' : 'Sync LinkedIn'}
                        </button>
                        <button className="bg-indigo-800/30 text-white border border-white/20 px-6 py-2 rounded-lg font-semibold flex items-center gap-2 hover:bg-indigo-800/50 transition-all active:scale-95">
                            View Reports <ArrowRight size={18} />
                        </button>
                    </div>
                </div>
                <div className="absolute right-[-20px] top-[-20px] opacity-10">
                    {isRecruiter ? <Users size={240} /> : <User size={240} />}
                </div>
            </div>

            {/* Recruiter Stats Grid */}
            {isRecruiter && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                    {renderStatCard("Total Candidates", stats?.total_resumes || 0, <Users size={24} />, "bg-blue-600")}
                    {renderStatCard("Auto-Screened", stats?.auto_screened || 0, <Zap size={24} />, "bg-amber-500")}
                    {renderStatCard("High Matches", stats?.high_matches || 0, <Target size={24} />, "bg-emerald-500")}
                    {renderStatCard("Skill Gaps", stats?.skill_gaps || 0, <AlertCircle size={24} />, "bg-rose-500")}
                    {renderStatCard("Quality Checks", stats?.quality_scored || 0, <CheckCircle size={24} />, "bg-violet-600")}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Recent Activity */}
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                    <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-slate-800">
                        <History size={20} className="text-indigo-600" /> Recent Activity
                    </h3>
                    <div className="space-y-3">
                        {loading ? (
                            <p className="text-sm text-slate-400">Loading activity...</p>
                        ) : stats?.recent_activity?.length > 0 ? (
                            stats.recent_activity.map((activity: any, i: number) => (
                                <div key={i} className="flex justify-between items-center p-3 hover:bg-slate-50 rounded-lg border border-transparent hover:border-slate-100 transition-all cursor-pointer group">
                                    <div className="flex gap-3 items-center">
                                        <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-indigo-600">
                                            {activity.type === 'screen' ? <Zap size={14} /> : <History size={14} />}
                                        </div>
                                        <div>
                                            <p className="text-xs font-bold text-slate-400 uppercase tracking-tighter">{activity.type}</p>
                                            <p className="text-sm font-semibold text-slate-700 truncate max-w-[180px]">{activity.filename}</p>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-xs font-bold text-slate-900">{activity.score > 0 ? `${activity.score}%` : ''}</p>
                                        <p className="text-[10px] text-slate-400">{new Date(activity.timestamp).toLocaleDateString()}</p>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <p className="text-sm text-slate-400 italic">No recent activity found.</p>
                        )}
                    </div>
                </div>

                {/* Optimization Alerts / Intelligence */}
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                    <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-slate-800">
                        <AlertCircle size={20} className="text-amber-500" />
                        {isRecruiter ? 'Talent Insights' : 'Optimization Alerts'}
                    </h3>
                    {isRecruiter ? (
                        <div className="space-y-4">
                            <div className="p-4 bg-indigo-50 rounded-lg border-l-4 border-indigo-500 text-sm text-indigo-900">
                                <strong>Pipeline Health:</strong> Your Python Developer role has 12 high matches ready for review.
                            </div>
                            <div className="p-4 bg-emerald-50 rounded-lg border-l-4 border-emerald-500 text-sm text-emerald-900">
                                <strong>Recommended:</strong> 5 candidates from last week's "Java dev" search match your new "Scala" requirement.
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="p-4 bg-amber-50 rounded-lg border-l-4 border-amber-400 text-sm text-amber-800">
                                "Consider adding <strong>GraphQL</strong> to your skills list. It appears in 40% of the roles you're targeting."
                            </div>
                            <div className="p-4 bg-blue-50 rounded-lg border-l-4 border-blue-400 text-sm text-blue-800">
                                <strong>Resume Tip:</strong> Your summary could be more impactful. Try our <span className="underline font-bold cursor-pointer">AI Refiner</span>.
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
