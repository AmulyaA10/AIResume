import React, { useState } from 'react';
import { Settings as SettingsIcon, Key, User, Lock, Save, Database, Cpu } from 'lucide-react';
import { PageHeader } from '../common';

const Settings = () => {
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
        { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1 (DeepSeek)' },
    ];

    const handleSave = () => {
        localStorage.setItem('openRouterKey', config.openRouterKey);
        localStorage.setItem('llmModel', config.llmModel);
        localStorage.setItem('linkedinUser', config.linkedinUser);
        localStorage.setItem('linkedinPass', config.linkedinPass);
        alert('Configuration saved successfully!');
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <PageHeader
                title="System Configuration"
                subtitle="Manage AI models, API keys, and integration credentials."
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* AI Configuration */}
                <div className="glass-card p-8 space-y-6">
                    <div className="flex items-center gap-3 border-b border-slate-100 pb-4 mb-4">
                        <div className="w-10 h-10 bg-purple-50 rounded-xl flex items-center justify-center text-purple-600">
                            <Cpu size={20} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-900">AI Model Settings</h3>
                            <p className="text-xs text-slate-500 font-medium">Configure LLM provider and inference parameters</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">Active Model</label>
                            <div className="relative">
                                <select
                                    value={config.llmModel}
                                    onChange={(e) => setConfig({ ...config, llmModel: e.target.value })}
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 px-4 text-sm font-bold text-slate-700 focus:ring-2 focus:ring-purple-500/20 outline-none transition-all appearance-none cursor-pointer"
                                >
                                    {models.map(m => (
                                        <option key={m.id} value={m.id}>{m.name}</option>
                                    ))}
                                </select>
                                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none">
                                    <Cpu size={14} className="text-slate-400" />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">OpenRouter API Key</label>
                            <div className="relative">
                                <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="password"
                                    value={config.openRouterKey}
                                    onChange={(e) => setConfig({ ...config, openRouterKey: e.target.value })}
                                    placeholder="sk-or-v1-..."
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:ring-2 focus:ring-purple-500/20 outline-none transition-all"
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* LinkedIn Integration */}
                <div className="glass-card p-8 space-y-6">
                    <div className="flex items-center gap-3 border-b border-slate-100 pb-4 mb-4">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
                            <Database size={20} />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-900">Data Sources</h3>
                            <p className="text-xs text-slate-500 font-medium">Manage scraper credentials and external connections</p>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="space-y-2">
                            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">LinkedIn Username</label>
                            <div className="relative">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="text"
                                    value={config.linkedinUser}
                                    onChange={(e) => setConfig({ ...config, linkedinUser: e.target.value })}
                                    placeholder="email@example.com"
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">LinkedIn Password</label>
                            <div className="relative">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="password"
                                    value={config.linkedinPass}
                                    onChange={(e) => setConfig({ ...config, linkedinPass: e.target.value })}
                                    placeholder="••••••••"
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex justify-end pt-6">
                <button
                    onClick={handleSave}
                    className="bg-slate-900 hover:bg-slate-800 text-white px-8 py-4 rounded-xl font-bold flex items-center gap-3 shadow-xl hover:shadow-2xl transition-all active:scale-95"
                >
                    <Save size={20} />
                    Save System Configuration
                </button>
            </div>
        </div>
    );
};

export default Settings;
