import React, { useState, useEffect } from 'react';
import { Settings, Key, User, Lock, ChevronDown, Save } from 'lucide-react';

const SettingsSidebar = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [config, setConfig] = useState({
        openRouterKey: localStorage.getItem('openRouterKey') || '',
        llmModel: localStorage.getItem('llmModel') || 'gpt-4o-mini',
        linkedinUser: localStorage.getItem('linkedinUser') || '',
        linkedinPass: localStorage.getItem('linkedinPass') || '',
    });

    const models = [
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini (OpenAI)' },
        { id: 'anthropic/claude-3-haiku', name: 'Claude 3 Haiku (Anthropic)' },
        { id: 'google/gemini-pro-1.5', name: 'Gemini Pro 1.5 (Google)' },
        { id: 'x-ai/grok-beta', name: 'Grok Beta (xAI)' },
    ];

    const handleSave = () => {
        localStorage.setItem('openRouterKey', config.openRouterKey);
        localStorage.setItem('llmModel', config.llmModel);
        localStorage.setItem('linkedinUser', config.linkedinUser);
        localStorage.setItem('linkedinPass', config.linkedinPass);
        alert('Settings saved locally!');
    };

    return (
        <div className="mt-auto border-t border-slate-100 p-4">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between w-full px-3 py-2 text-slate-500 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-all group"
            >
                <div className="flex items-center gap-3">
                    <Settings className="w-5 h-5 group-hover:rotate-45 transition-transform" />
                    <span className="text-sm font-semibold">System Settings</span>
                </div>
                <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <div className="mt-4 space-y-4 animate-in fade-in slide-in-from-bottom-2 duration-200">
                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">OpenRouter Key</label>
                        <div className="relative">
                            <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                            <input
                                type="password"
                                value={config.openRouterKey}
                                onChange={(e) => setConfig({ ...config, openRouterKey: e.target.value })}
                                placeholder="sk-or-v1-..."
                                className="w-full bg-white border border-slate-200 rounded-lg py-2 pl-9 pr-3 text-xs focus:ring-2 focus:ring-primary-500/20 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">AI Model</label>
                        <select
                            value={config.llmModel}
                            onChange={(e) => setConfig({ ...config, llmModel: e.target.value })}
                            className="w-full bg-white border border-slate-200 rounded-lg py-2 px-3 text-xs focus:ring-2 focus:ring-primary-500/20 outline-none transition-all appearance-none cursor-pointer"
                        >
                            {models.map(m => (
                                <option key={m.id} value={m.id}>{m.name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">LinkedIn Login</label>
                        <div className="relative">
                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                            <input
                                type="text"
                                value={config.linkedinUser}
                                onChange={(e) => setConfig({ ...config, linkedinUser: e.target.value })}
                                placeholder="email@example.com"
                                className="w-full bg-white border border-slate-200 rounded-lg py-2 pl-9 pr-3 text-xs focus:ring-2 focus:ring-primary-500/20 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">LinkedIn Password</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                            <input
                                type="password"
                                value={config.linkedinPass}
                                onChange={(e) => setConfig({ ...config, linkedinPass: e.target.value })}
                                placeholder="••••••••"
                                className="w-full bg-white border border-slate-200 rounded-lg py-2 pl-9 pr-3 text-xs focus:ring-2 focus:ring-primary-500/20 outline-none transition-all"
                            />
                        </div>
                    </div>

                    <button
                        onClick={handleSave}
                        className="w-full bg-primary-600 hover:bg-primary-700 text-white py-2 rounded-lg text-xs font-bold transition-all shadow-md shadow-primary-500/20 flex items-center justify-center gap-2"
                    >
                        <Save className="w-3.5 h-3.5" />
                        Save Configuration
                    </button>
                </div>
            )}
        </div>
    );
};

export default SettingsSidebar;
