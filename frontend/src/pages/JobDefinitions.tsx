import React from 'react';
import { Briefcase, Plus, Search } from 'lucide-react';

const JobDefinitions = () => {
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <header className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold mb-2 text-slate-900 tracking-tight">Job Definitions</h1>
                    <p className="text-slate-500 font-medium">Manage job descriptions and screening criteria.</p>
                </div>
                <button className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 shadow-lg shadow-blue-500/20 transition-all">
                    <Plus size={18} /> New Job Definition
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {/* Mock Data for now as per user request to map 'existing' which might mean the concept */}
                {['Senior Frontend Engineer', 'Product Manager', 'Data Scientist'].map((job, i) => (
                    <div key={i} className="glass-card p-6 hover:shadow-md transition-shadow cursor-pointer group">
                        <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 group-hover:scale-110 transition-transform">
                                <Briefcase size={20} />
                            </div>
                            <span className="bg-slate-100 text-slate-600 text-[10px] font-bold px-2 py-1 rounded uppercase tracking-wider">Active</span>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">{job}</h3>
                        <p className="text-sm text-slate-500 mb-4 line-clamp-2">Responsible for leading development initiatives and optimizing application performance...</p>
                        <div className="flex items-center gap-4 text-xs font-medium text-slate-400">
                            <span className="flex items-center gap-1"><Search size={12} /> 12 Candidates</span>
                            <span>•</span>
                            <span>Created 2d ago</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default JobDefinitions;
