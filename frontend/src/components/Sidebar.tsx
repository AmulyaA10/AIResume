import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
    Layout,
    User,
    Briefcase,
    Settings,
    Search,
    FileText,
    ShieldCheck,
    BarChart3,
    Cpu,
    LogOut,
    Linkedin,
    Upload,
    Home
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
    const { persona, logout } = useAuth();
    const navigate = useNavigate();

    // Default to jobseeker if null (shouldn't happen in authenticated layout)
    const currentPersona = persona || 'jobseeker';

    // Map Wireframe IDs to existing Routes
    const menus = {
        jobseeker: [
            { path: '/', label: 'Home', icon: Home },
            { path: '/my-applications', label: 'My Applications', icon: Layout },
            { path: '/search', label: 'Find Jobs', icon: Search },
            { path: '/generate', label: 'Resume Refiner', icon: FileText },
            { path: '/upload', label: 'My Documents', icon: Upload },
            { path: '/linkedin', label: 'Sync LinkedIn', icon: Linkedin },
        ],
        recruiter: [
            { path: '/resumes', label: 'Resume Database', icon: Upload },
            { path: '/search', label: 'Candidate Search', icon: Search },
            { path: '/scoring', label: 'Quality Scoring', icon: BarChart3 },
            { path: '/screen', label: 'Auto Screening', icon: ShieldCheck },
            { path: '/skill-gap', label: 'Skill Gap Analysis', icon: Cpu },
            { path: '/generate', label: 'Resume Refiner', icon: FileText },
            { path: '/jd', label: 'Job Definitions', icon: Briefcase },
        ],
        manager: [
            { path: '/resumes', label: 'Resume Database', icon: Upload },
            { path: '/scoring', label: 'Active Rankings', icon: BarChart3 },
            { path: '/skill-gap', label: 'Skill Analysis', icon: Cpu },
            { path: '/screen', label: 'Auto Screening', icon: ShieldCheck },
            { path: '/jd', label: 'Job Definitions', icon: Briefcase },
            { path: '/settings', label: 'Settings', icon: Settings },
        ]
    };

    const currentMenu = (menus as any)[currentPersona] || menus.jobseeker;

    return (
        <div className="w-64 bg-slate-900 text-slate-300 flex flex-col h-full border-r border-slate-800">
            <div className="p-6">
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="text-blue-500" /> RESUME.AI
                </h1>
            </div>

            <nav className="flex-1 px-4 space-y-2">
                {(currentPersona === 'recruiter' || currentPersona === 'manager') ? (
                    <button
                        onClick={() => navigate('/')}
                        title="Console View"
                        className="text-xs font-semibold uppercase tracking-wider mb-4 px-3 py-1.5 rounded-md bg-slate-700 text-slate-300 shadow-md hover:bg-blue-600 hover:text-white hover:shadow-lg active:shadow-inner active:translate-y-px transition-all cursor-pointer text-left"
                    >
                        Recruitment Suite
                    </button>
                ) : (
                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-4 px-2">
                        Candidate Portal
                    </div>
                )}
                {currentMenu.map((item: any) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all ${isActive
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/20'
                                : 'hover:bg-slate-800'
                            }`
                        }
                    >
                        <item.icon size={18} />
                        <span className="text-sm font-medium">{item.label}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="p-4 border-t border-slate-800">
                <button
                    onClick={logout}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-red-900/20 text-red-400 transition-colors"
                >
                    <LogOut size={18} />
                    <span className="text-sm font-semibold">Sign Out</span>
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
