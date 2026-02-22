import React from 'react';
import Sidebar from './Sidebar';
import { useAuth } from '../context/AuthContext';

const Layout = ({ children }: { children: React.ReactNode }) => {
    const { user, persona } = useAuth();

    return (
        <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
            <Sidebar />

            <main className="flex-1 flex flex-col overflow-hidden">
                <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between z-20 shadow-sm">
                    <div className="flex items-center gap-4">
                        <span className="text-xs font-black text-blue-600 bg-blue-50 px-2.5 py-1 rounded tracking-widest">
                            {persona ? persona.toUpperCase() : 'GUEST'} MODE
                        </span>
                        <div className="h-4 w-px bg-slate-200"></div>
                        <span className="text-xs font-semibold text-slate-400">Environment: <span className="text-slate-900">PROD-LLM-01</span></span>
                    </div>
                    {user && (
                        <div className="flex items-center gap-3">
                            <div className="text-right hidden sm:block">
                                <p className="text-xs font-bold leading-none">{user.name}</p>
                                <p className="text-[10px] text-slate-400 mt-1">{user.email}</p>
                            </div>
                            <div className="w-9 h-9 bg-slate-900 rounded-xl flex items-center justify-center text-white text-xs font-bold ring-2 ring-white shadow-md">
                                {user.name.split(' ').map(n => n[0]).join('')}
                            </div>
                        </div>
                    )}
                </header>

                <div className="flex-1 overflow-y-auto p-8 bg-slate-50/50">
                    <div className="max-w-7xl mx-auto">
                        {children}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Layout;
