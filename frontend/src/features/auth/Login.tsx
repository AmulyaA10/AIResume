import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Mail, Linkedin, Lock, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const Login = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [status, setStatus] = useState<'idle' | 'loading'>('idle');

    const handleLogin = (method: string) => {
        setStatus('loading');
        // Simulate network delay
        setTimeout(() => {
            login(method);
            navigate('/');
        }, 800);
    };

    return (
        <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 font-sans">
            <div className="max-w-md w-full space-y-8 bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-blue-600/10 blur-3xl -mr-16 -mt-16"></div>
                <div className="text-center relative z-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl shadow-lg shadow-blue-500/30 mb-6">
                        <ShieldCheck className="text-white" size={32} />
                    </div>
                    <h1 className="text-3xl font-black text-white tracking-tight">RESUME.AI</h1>
                    <p className="mt-2 text-slate-400 text-sm">Intelligence Platform for Modern Talent</p>
                </div>

                <div className="space-y-4 relative z-10">
                    <button
                        onClick={() => handleLogin('gmail')}
                        disabled={status === 'loading'}
                        className="w-full flex items-center justify-center gap-3 bg-white text-slate-900 py-3.5 rounded-xl font-bold hover:bg-slate-100 transition-all active:scale-[0.98]"
                    >
                        <Mail className="text-red-500" size={20} /> Login with User Account
                    </button>
                    <button
                        onClick={() => handleLogin('linkedin')}
                        disabled={status === 'loading'}
                        className="w-full flex items-center justify-center gap-3 bg-[#0077b5] text-white py-3.5 rounded-xl font-bold hover:bg-[#006699] transition-all active:scale-[0.98]"
                    >
                        <Linkedin size={20} /> Login with LinkedIn
                    </button>

                    <div className="relative py-4">
                        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-800"></div></div>
                        <div className="relative flex justify-center text-[10px] uppercase font-bold tracking-widest"><span className="bg-slate-900 px-3 text-slate-500">Internal Access</span></div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <button onClick={() => handleLogin('corporate')} className="bg-slate-800 text-white p-3 rounded-xl font-bold hover:bg-slate-700 transition-all border border-slate-700 text-xs">Recruiter SSO</button>
                        <button onClick={() => handleLogin('manager')} className="bg-slate-800 text-white p-3 rounded-xl font-bold hover:bg-slate-700 transition-all border border-slate-700 text-xs">Manager SSO</button>
                    </div>
                </div>
                <p className="text-center text-[9px] text-slate-600 uppercase tracking-widest font-bold">Secure Session • Audit Logging Enabled</p>
            </div>
        </div>
    );
};

export default Login;
