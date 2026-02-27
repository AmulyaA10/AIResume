import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Key, User, Lock, Save, Database, Cpu, Trash2, CheckCircle, AlertCircle, Loader2, Shield } from 'lucide-react';
import { PageHeader } from '../../common';
import { useCredentials } from '../../context/CredentialContext';

const Settings = () => {
    const {
        credentials,
        maskedCredentials,
        setCredential,
        saveCredentials,
        loadMaskedCredentials,
        clearCredentials,
        isLoaded,
    } = useCredentials();

    const [llmModel, setLlmModel] = useState(localStorage.getItem('llmModel') || 'gpt-4o-mini');
    const [saving, setSaving] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    // Load masked credentials from server on mount
    useEffect(() => {
        loadMaskedCredentials();
    }, [loadMaskedCredentials]);

    const models = [
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini (OpenAI)' },
        { id: 'anthropic/claude-3-haiku', name: 'Claude 3 Haiku (Anthropic)' },
        { id: 'google/gemini-pro-1.5', name: 'Gemini Pro 1.5 (Google)' },
        { id: 'x-ai/grok-beta', name: 'Grok Beta (xAI)' },
        { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1 (DeepSeek)' },
    ];

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);
        try {
            // Save non-sensitive model preference to localStorage
            localStorage.setItem('llmModel', llmModel);

            // Save sensitive credentials to server (encrypted)
            await saveCredentials();

            setMessage({ type: 'success', text: 'Configuration saved securely.' });
            setTimeout(() => setMessage(null), 4000);
        } catch (err: any) {
            console.error('Save failed:', err);
            setMessage({ type: 'error', text: err?.response?.data?.detail || 'Failed to save credentials.' });
        } finally {
            setSaving(false);
        }
    };

    const handleClear = async () => {
        if (!confirm('Are you sure you want to remove all stored credentials? This cannot be undone.')) return;
        setClearing(true);
        setMessage(null);
        try {
            await clearCredentials();
            setMessage({ type: 'success', text: 'All credentials cleared.' });
            setTimeout(() => setMessage(null), 4000);
        } catch (err: any) {
            console.error('Clear failed:', err);
            setMessage({ type: 'error', text: 'Failed to clear credentials.' });
        } finally {
            setClearing(false);
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
            <PageHeader
                title="System Configuration"
                subtitle="Manage AI models, API keys, and integration credentials."
            />

            {/* Security badge */}
            <div className="flex items-center gap-2 text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl px-4 py-2.5 w-fit">
                <Shield size={14} />
                Credentials are encrypted and stored server-side. Nothing sensitive is saved in your browser.
            </div>

            {/* Status message */}
            {message && (
                <div className={`flex items-center gap-2 text-sm font-bold px-4 py-3 rounded-xl border ${
                    message.type === 'success'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-red-50 text-red-700 border-red-200'
                }`}>
                    {message.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
                    {message.text}
                </div>
            )}

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
                                    value={llmModel}
                                    onChange={(e) => setLlmModel(e.target.value)}
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
                            {maskedCredentials?.has_openRouterKey && !credentials.openRouterKey && (
                                <p className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
                                    <CheckCircle size={12} /> Saved: {maskedCredentials.openRouterKey}
                                </p>
                            )}
                            <div className="relative">
                                <Key className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="password"
                                    value={credentials.openRouterKey}
                                    onChange={(e) => setCredential('openRouterKey', e.target.value)}
                                    placeholder={maskedCredentials?.has_openRouterKey ? 'Enter new key to replace' : 'sk-or-v1-...'}
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
                            {maskedCredentials?.has_linkedinUser && !credentials.linkedinUser && (
                                <p className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
                                    <CheckCircle size={12} /> Saved: {maskedCredentials.linkedinUser}
                                </p>
                            )}
                            <div className="relative">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="text"
                                    value={credentials.linkedinUser}
                                    onChange={(e) => setCredential('linkedinUser', e.target.value)}
                                    placeholder={maskedCredentials?.has_linkedinUser ? 'Enter new email to replace' : 'email@example.com'}
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="text-xs font-black text-slate-400 uppercase tracking-widest">LinkedIn Password</label>
                            {maskedCredentials?.has_linkedinPass && !credentials.linkedinPass && (
                                <p className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
                                    <CheckCircle size={12} /> Saved: {maskedCredentials.linkedinPass}
                                </p>
                            )}
                            <div className="relative">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                                <input
                                    type="password"
                                    value={credentials.linkedinPass}
                                    onChange={(e) => setCredential('linkedinPass', e.target.value)}
                                    placeholder={maskedCredentials?.has_linkedinPass ? 'Enter new password to replace' : '••••••••'}
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-10 pr-4 text-sm font-medium focus:ring-2 focus:ring-blue-500/20 outline-none transition-all"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex justify-between items-center pt-6">
                {/* Clear credentials button */}
                <button
                    onClick={handleClear}
                    disabled={clearing || !maskedCredentials || (!maskedCredentials.has_openRouterKey && !maskedCredentials.has_linkedinUser && !maskedCredentials.has_linkedinPass)}
                    className="text-red-500 hover:text-red-700 hover:bg-red-50 px-6 py-4 rounded-xl font-bold flex items-center gap-2 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                >
                    {clearing ? <Loader2 size={18} className="animate-spin" /> : <Trash2 size={18} />}
                    Clear All Credentials
                </button>

                {/* Save button */}
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-slate-900 hover:bg-slate-800 text-white px-8 py-4 rounded-xl font-bold flex items-center gap-3 shadow-xl hover:shadow-2xl transition-all active:scale-95 disabled:opacity-50"
                >
                    {saving ? <Loader2 size={20} className="animate-spin" /> : <Save size={20} />}
                    Save System Configuration
                </button>
            </div>
        </div>
    );
};

export default Settings;
