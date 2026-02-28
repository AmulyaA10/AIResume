import React, { useState, useEffect } from 'react';
import { Linkedin, Loader2, Link as LinkIcon, Download, RefreshCw, FileCheck, AlertCircle, Settings, ClipboardPaste, Smartphone } from 'lucide-react';
import api from '../../api';
import { motion } from 'framer-motion';
import { PageHeader } from '../../common';
import { useAuth } from '../../context/AuthContext';
import { useCredentials } from '../../context/CredentialContext';
import { useNavigate } from 'react-router-dom';

const LinkedInScraper = () => {
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [resume, setResume] = useState<any | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [showPasteFallback, setShowPasteFallback] = useState(false);
    const [pastedText, setPastedText] = useState('');
    const [parseLoading, setParseLoading] = useState(false);
    const [securityChallenge, setSecurityChallenge] = useState(false);
    const inputRef = React.useRef<HTMLInputElement>(null);
    const navigate = useNavigate();
    const { maskedCredentials, loadMaskedCredentials, isLoaded, isLoading, loadError } = useCredentials();

    // Load credential status from server on mount (skip if auth:login handler is already loading)
    useEffect(() => {
        if (!isLoaded && !loadError && !isLoading) loadMaskedCredentials();
    }, [isLoaded, loadError, isLoading, loadMaskedCredentials]);

    // Retry once if credential load failed (e.g., auth token wasn't ready)
    useEffect(() => {
        if (loadError && !isLoading) {
            const timer = setTimeout(() => loadMaskedCredentials(), 1000);
            return () => clearTimeout(timer);
        }
    }, [loadError, isLoading, loadMaskedCredentials]);

    const hasScraperCreds = maskedCredentials?.has_linkedinUser && maskedCredentials?.has_linkedinPass;

    const handleScrape = async (retry = false) => {
        if (!url.trim()) return;

        setLoading(true);
        setResume(null);
        setError(null);
        setShowPasteFallback(false);
        setSecurityChallenge(false);
        try {
            const response = await api.post('/linkedin/scrape', { query: url, retry });
            if (response.data.resume) {
                setResume(response.data.resume);
            } else if (response.data.error) {
                const errorMsg = response.data.error;
                const errorCode = response.data.error_code;
                setError(errorMsg);

                // Detect security challenge (2-step verification on phone)
                const isChallenge = errorCode === 'SECURITY_CHALLENGE'
                    || /security verif|verification timed|captcha|2fa/i.test(errorMsg);
                if (isChallenge) {
                    setSecurityChallenge(true);
                } else {
                    setShowPasteFallback(true);
                }
            } else {
                setError('No resume data was returned. The profile may be private or inaccessible.');
                setShowPasteFallback(true);
            }
        } catch (err: any) {
            console.error(err);
            const detail = err?.response?.data?.detail;
            const errorMsg = detail || err?.message || 'An unexpected error occurred while scraping the profile.';
            setError(typeof detail === 'string' ? detail : errorMsg);

            // Also check HTTPException detail for security challenge keywords
            const detailStr = typeof detail === 'string' ? detail : '';
            const isChallenge = /security verif|verification timed|captcha|2fa/i.test(detailStr);
            if (isChallenge) {
                setSecurityChallenge(true);
            } else {
                setShowPasteFallback(true);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleParsePasted = async () => {
        if (!pastedText.trim() || pastedText.trim().length < 100) return;

        setParseLoading(true);
        setResume(null);
        setError(null);
        try {
            const response = await api.post('/linkedin/parse', { profile_text: pastedText });
            if (response.data.resume) {
                setResume(response.data.resume);
                setShowPasteFallback(false);
            } else if (response.data.error) {
                setError(response.data.error);
            } else {
                setError('Could not generate resume from the pasted text. Please ensure you copied the full profile.');
            }
        } catch (err: any) {
            console.error(err);
            const detail = err?.response?.data?.detail;
            if (detail) {
                setError(detail);
            } else if (err?.message) {
                setError(`Request failed: ${err.message}`);
            } else {
                setError('An unexpected error occurred while parsing the profile text.');
            }
        } finally {
            setParseLoading(false);
        }
    };

    const { user, login } = useAuth();

    // Auto-populate URL from OAuth redirect
    React.useEffect(() => {
        const storedUrl = localStorage.getItem('linkedin_profile_url');
        const urlParams = new URLSearchParams(window.location.search);
        const paramUrl = urlParams.get('profile_url');

        if (paramUrl) {
            setUrl(paramUrl);
        } else if (storedUrl && !url) {
            setUrl(storedUrl);
        }

        if (localStorage.getItem('linkedin_connected') && !resume && inputRef.current) {
            inputRef.current.focus();
        }
    }, []);

    const handleReset = () => {
        localStorage.removeItem('linkedin_connected');
        localStorage.removeItem('linkedin_profile_url');
        setResume(null);
        setError(null);
        setLoading(false);
        setShowPasteFallback(false);
        setPastedText('');
        setParseLoading(false);
        setSecurityChallenge(false);
        window.location.reload();
    };

    const handleLinkedInConnect = () => {
        console.log("Triggering LinkedIn OAuth redirection...");
        login('linkedin');
    };

    const handleDownloadWord = async () => {
        if (!resume) return;
        try {
            const response = await api.post('/generate/export', resume, {
                responseType: 'blob',
            });
            const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `${resume.contact?.name || 'resume'}.docx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error('Export failed:', err);
        }
    };

    const isResumeValid = resume &&
        resume.contact?.name &&
        !resume.summary?.toLowerCase().includes('error') &&
        (resume.summary?.length > 100 || (resume.experience && resume.experience.length > 0));

    const isLinkedInConnected = localStorage.getItem('linkedin_connected');

    return (
        <div className="space-y-8">
            <PageHeader
                title="LinkedIn Profile Import"
                subtitle="Convert LinkedIn profiles into structured professional resumes — auto-scrape or paste your profile text."
            />

            <div className="glass-card p-12 max-w-4xl mx-auto border-blue-100 bg-white/80 shadow-lg shadow-blue-500/5">
                <div className="flex flex-col items-center gap-8">
                    <div
                        onClick={!isResumeValid ? handleLinkedInConnect : undefined}
                        className={`w-24 h-24 bg-[#0077b5] rounded-[2rem] flex items-center justify-center shadow-xl shadow-[#0077b5]/20 rotate-12 hover:rotate-0 transition-transform cursor-pointer ${loading || parseLoading ? 'animate-pulse' : ''}`}
                    >
                        <Linkedin className="text-white w-12 h-12" />
                    </div>

                    <div className="text-center">
                        <h3 className="text-xl font-bold text-slate-800 mb-2">
                            {isResumeValid ? 'Profile Synced Successfully' : (isLinkedInConnected ? 'LinkedIn Authenticated' : 'Social Profile Import')}
                        </h3>
                        <p className="text-sm text-slate-500 font-medium max-w-md mx-auto">
                            {isResumeValid
                                ? 'Your profile has been automatically imported and processed.'
                                : (isLinkedInConnected
                                    ? (loading ? 'AI Scraper Active. This may take up to a minute...' : (parseLoading ? 'Processing your pasted profile text...' : 'Verify your profile URL below and click "Start AI Sync" to begin.'))
                                    : 'Click the LinkedIn icon above or the button below to authenticate and sync your profile data.')}
                        </p>
                    </div>

                    {error && !showPasteFallback && !securityChallenge && (
                        <div className="w-full bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                            <div className="space-y-2">
                                <p className="text-sm font-bold text-red-700">Scraping Failed</p>
                                <p className="text-xs text-red-600 leading-relaxed">{error}</p>
                                <button
                                    onClick={() => navigate('/settings')}
                                    className="mt-1 inline-flex items-center gap-2 text-xs font-bold text-[#0077b5] hover:text-[#006396] transition-colors"
                                >
                                    <Settings className="w-3.5 h-3.5" /> Check Settings
                                </button>
                            </div>
                        </div>
                    )}

                    {/* Phone verification prompt — shown when LinkedIn 2-step verification is detected */}
                    {securityChallenge && !isResumeValid && (
                        <div className="w-full bg-indigo-50 border border-indigo-200 rounded-xl p-5 space-y-4">
                            <div className="flex items-start gap-3">
                                <Smartphone className="w-6 h-6 text-indigo-500 flex-shrink-0 mt-0.5" />
                                <div className="space-y-2">
                                    <p className="text-sm font-bold text-indigo-800">Phone Verification Required</p>
                                    <p className="text-xs text-indigo-600 leading-relaxed">
                                        LinkedIn sent a security notification to your phone.
                                        Please open the <strong>LinkedIn app</strong> on your phone,
                                        approve the <strong>"Is this you?"</strong> prompt,
                                        then click <strong>"Retry Scrape"</strong> below.
                                    </p>
                                    <p className="text-[11px] text-indigo-500 leading-relaxed">
                                        This is LinkedIn's 2-step verification to confirm the login.
                                        Once you approve it, the scraper will be able to access your profile.
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={() => { setSecurityChallenge(false); setError(null); handleScrape(true); }}
                                disabled={loading}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-4 rounded-2xl font-black uppercase tracking-widest text-sm transition-all shadow-xl shadow-indigo-500/20 active:scale-95 flex items-center justify-center gap-3 disabled:opacity-50"
                            >
                                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                                {loading ? 'Retrying — Waiting for Phone Approval...' : 'Retry Scrape (After Phone Approval)'}
                            </button>
                            <button
                                onClick={() => { setSecurityChallenge(false); setShowPasteFallback(true); }}
                                className="w-full text-xs text-indigo-500 hover:text-indigo-700 font-bold uppercase tracking-widest transition-colors py-2"
                            >
                                Skip — paste profile text instead
                            </button>
                        </div>
                    )}

                    {/* Paste fallback — shown when scraping fails */}
                    {showPasteFallback && !isResumeValid && (
                        <div className="w-full space-y-4">
                            <div className="w-full bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
                                <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                                <div className="space-y-2">
                                    <p className="text-sm font-bold text-amber-700">Auto-Scrape Unavailable</p>
                                    <p className="text-xs text-amber-600 leading-relaxed">
                                        {error || 'The automated scraper could not retrieve profile data.'}
                                    </p>
                                    <p className="text-xs text-amber-700 font-bold leading-relaxed">
                                        No worries — paste your LinkedIn profile text below instead. Go to your LinkedIn profile, select all (Ctrl+A / Cmd+A), copy (Ctrl+C / Cmd+C), and paste it here.
                                    </p>
                                </div>
                            </div>

                            <div className="relative">
                                <ClipboardPaste className="absolute left-4 top-4 w-5 h-5 text-slate-400" />
                                <textarea
                                    value={pastedText}
                                    onChange={(e) => { setPastedText(e.target.value); setError(null); }}
                                    placeholder={"Paste your LinkedIn profile content here...\n\nExample:\nJohn Doe\nProduct Manager at Deloitte\n\nExperience\nManager\nDeloitte · Full-time\nSep 2024 - Present\n...\n\nEducation\nLiverpool Business School\nMBA, Strategy and Marketing\n..."}
                                    className="w-full bg-white border border-slate-200 rounded-2xl py-4 pl-12 pr-4 focus:border-[#0077b5] outline-none text-sm transition-all shadow-sm focus:ring-4 focus:ring-[#0077b5]/5 text-slate-800 placeholder:text-slate-300 min-h-[200px] resize-y"
                                />
                            </div>

                            {pastedText.trim().length > 0 && pastedText.trim().length < 100 && (
                                <p className="text-xs text-red-500 font-medium px-2">
                                    Too short — please paste your full LinkedIn profile content (experience, education, skills, etc.)
                                </p>
                            )}

                            <button
                                onClick={handleParsePasted}
                                disabled={parseLoading || pastedText.trim().length < 100}
                                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-5 rounded-2xl font-black uppercase tracking-widest text-sm transition-all shadow-xl shadow-emerald-500/20 active:scale-95 flex items-center justify-center gap-3 disabled:opacity-50"
                            >
                                {parseLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <ClipboardPaste className="w-5 h-5" />}
                                {parseLoading ? 'AI Processing Profile Text...' : 'Generate Resume from Pasted Text'}
                            </button>

                            <div className="relative">
                                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-100"></div></div>
                                <div className="relative flex justify-center text-xs uppercase">
                                    <span className="bg-white px-4 text-slate-400 font-bold tracking-widest">Or try auto-scrape again</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {!isResumeValid && (
                        <div className="w-full space-y-6">
                            {/* Confirmation Input for LinkedIn Auth */}
                            {isLinkedInConnected ? (
                                <div className="space-y-4">
                                    {!showPasteFallback && (
                                        <div className="space-y-3">
                                            <div className="bg-blue-50 border border-blue-100 p-4 rounded-xl space-y-2">
                                                <p className="text-xs font-bold text-[#0077b5] uppercase tracking-wider flex items-center gap-2">
                                                    <LinkIcon className="w-3.5 h-3.5" /> Action Required: Verify Profile URL
                                                </p>
                                                <p className="text-[11px] text-slate-500 font-medium leading-relaxed">
                                                    LinkedIn API restricts private vanity URLs. Please check the URL below.
                                                    If it's wrong, <strong>copy the link from your "Public profile & URL" section</strong> (the one with the unique numbers at the end) and paste it here.
                                                </p>
                                            </div>
                                            <div className="bg-amber-50 border border-amber-200 p-4 rounded-xl flex items-start gap-3">
                                                <Smartphone className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                                                <div className="space-y-1.5">
                                                    <p className="text-xs font-bold text-amber-700">
                                                        📱 Keep your phone nearby
                                                    </p>
                                                    <p className="text-[11px] text-amber-600 font-medium leading-relaxed">
                                                        If you have <strong>2-step verification</strong> enabled on LinkedIn,
                                                        you'll receive an <strong>"Is this you?"</strong> notification on your phone.
                                                        You must <strong>tap "Yes"</strong> in the LinkedIn app to allow the scraper to access your profile.
                                                    </p>
                                                    <p className="text-[11px] text-amber-500 leading-relaxed">
                                                        Don't have your phone? Use the <strong>"Paste LinkedIn Profile Text"</strong> option below as an alternative.
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    {isLoaded && !hasScraperCreds && !showPasteFallback && (
                                        <div className="bg-blue-50 border border-blue-200 p-3 rounded-xl flex items-center gap-2">
                                            <Settings className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                                            <p className="text-[11px] text-blue-600 font-medium">
                                                No saved LinkedIn credentials detected.{' '}
                                                <button
                                                    onClick={() => navigate('/settings')}
                                                    className="font-bold text-[#0077b5] hover:text-[#006396] underline transition-colors"
                                                >
                                                    Add in Settings
                                                </button>
                                                {' '}for faster syncing, or just click the button below — the server may already have your credentials.
                                            </p>
                                        </div>
                                    )}
                                    <div className="w-full relative group">
                                        <LinkIcon className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 group-focus-within:text-[#0077b5] transition-colors" />
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={url}
                                            onChange={(e) => { setUrl(e.target.value); setError(null); }}
                                            placeholder="https://www.linkedin.com/in/username"
                                            className="w-full bg-white border border-blue-200 rounded-2xl py-5 pl-14 pr-4 focus:border-[#0077b5] outline-none text-lg transition-all shadow-sm focus:ring-4 focus:ring-[#0077b5]/5 text-slate-800 placeholder:text-slate-300"
                                        />
                                    </div>
                                    <button
                                        onClick={() => handleScrape()}
                                        disabled={loading || parseLoading || !url.trim()}
                                        className="w-full bg-[#0077b5] hover:bg-[#006396] text-white py-5 rounded-2xl font-black uppercase tracking-widest text-sm transition-all shadow-xl shadow-[#0077b5]/20 active:scale-95 flex items-center justify-center gap-3 disabled:opacity-50"
                                    >
                                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                                        {loading ? 'AI Scraper Active...' : (showPasteFallback ? 'Retry Auto-Scrape' : 'Verify & Start AI Sync')}
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <button
                                        onClick={handleLinkedInConnect}
                                        className="w-full bg-[#0077b5] hover:bg-[#006396] text-white py-5 rounded-2xl font-black uppercase tracking-widest text-sm transition-all shadow-xl shadow-[#0077b5]/20 active:scale-95 flex items-center justify-center gap-3"
                                    >
                                        <Linkedin className="w-5 h-5" />
                                        Sync with LinkedIn
                                    </button>

                                    <div className="relative">
                                        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-100"></div></div>
                                        <div className="relative flex justify-center text-xs uppercase"><span className="bg-white px-4 text-slate-400 font-bold tracking-widest">Or use public URL</span></div>
                                    </div>

                                    <div className="bg-amber-50 border border-amber-200 p-3 rounded-xl flex items-start gap-2.5">
                                        <Smartphone className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                                        <p className="text-[11px] text-amber-600 font-medium leading-relaxed">
                                            <strong>📱 Have your phone ready</strong> — LinkedIn may send an <strong>"Is this you?"</strong> notification
                                            if 2-step verification is on. Tap <strong>"Yes"</strong> in the LinkedIn app to proceed.
                                        </p>
                                    </div>

                                    <div className="w-full relative group">
                                        <LinkIcon className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 group-focus-within:text-[#0077b5] transition-colors" />
                                        <input
                                            type="text"
                                            value={url}
                                            onChange={(e) => { setUrl(e.target.value); setError(null); }}
                                            placeholder="https://www.linkedin.com/in/username"
                                            className="w-full bg-white border border-slate-200 rounded-2xl py-5 pl-14 pr-4 focus:border-[#0077b5] outline-none text-lg transition-all shadow-sm focus:ring-4 focus:ring-[#0077b5]/5 text-slate-800 placeholder:text-slate-300"
                                        />
                                    </div>

                                    <button
                                        onClick={() => handleScrape()}
                                        disabled={loading || !url.trim()}
                                        className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 py-4 rounded-xl font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-3"
                                    >
                                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                                        {loading ? 'Fetching...' : 'Convert from URL'}
                                    </button>

                                    <div className="relative">
                                        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-slate-100"></div></div>
                                        <div className="relative flex justify-center text-xs uppercase"><span className="bg-white px-4 text-slate-400 font-bold tracking-widest">Or paste profile text</span></div>
                                    </div>

                                    <button
                                        onClick={() => setShowPasteFallback(true)}
                                        className="w-full bg-slate-50 hover:bg-slate-100 text-slate-600 py-4 rounded-xl font-bold transition-all flex items-center justify-center gap-3 border border-slate-200"
                                    >
                                        <ClipboardPaste className="w-5 h-5" />
                                        Paste LinkedIn Profile Text
                                    </button>
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {resume && (
                <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-4xl mx-auto space-y-4">
                    <div className="flex justify-between items-center px-4">
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] flex items-center gap-2">
                            <FileCheck className="w-4 h-4 text-emerald-500" />
                            Generated Intelligence Output
                        </h3>
                        <button
                            onClick={handleDownloadWord}
                            className="text-[10px] font-black text-slate-600 hover:text-slate-900 transition-colors bg-white border border-slate-200 px-4 py-2 rounded-xl flex items-center gap-2 shadow-sm hover:shadow-md active:bg-slate-50"
                        >
                            <Download className="w-3.5 h-3.5" /> Download .docx
                        </button>
                    </div>

                    <div className="glass-card p-12 bg-white border-slate-100 shadow-2xl space-y-8 font-sans">
                        <div className="text-center space-y-2 border-b border-slate-100 pb-8">
                            <h2 className="text-4xl font-black text-slate-900">{resume.contact?.name}</h2>
                            <p className="text-slate-500 font-bold tracking-widest uppercase text-xs">
                                {resume.contact?.location} {resume.contact?.location && resume.contact?.email ? ' | ' : ''} {resume.contact?.email}
                            </p>
                        </div>

                        {resume.summary && (
                            <section className="space-y-3">
                                <h4 className="text-[10px] font-black text-[#0077b5] uppercase tracking-widest px-2 py-1 bg-blue-50 w-fit rounded-lg">Summary</h4>
                                <p className="text-slate-600 leading-relaxed text-sm font-medium">{resume.summary}</p>
                            </section>
                        )}

                        {resume.skills && resume.skills.length > 0 && (
                            <section className="space-y-3">
                                <h4 className="text-[10px] font-black text-[#0077b5] uppercase tracking-widest px-2 py-1 bg-blue-50 w-fit rounded-lg">Technical Expertise</h4>
                                <div className="flex flex-wrap gap-2">
                                    {resume.skills.map((skill: string, i: number) => (
                                        <span key={i} className="px-3 py-1.5 bg-slate-50 text-slate-600 rounded-full text-[11px] font-bold border border-slate-100">
                                            {skill}
                                        </span>
                                    ))}
                                </div>
                            </section>
                        )}

                        {resume.experience && resume.experience.length > 0 && (
                            <section className="space-y-6">
                                <h4 className="text-[10px] font-black text-[#0077b5] uppercase tracking-widest px-2 py-1 bg-blue-50 w-fit rounded-lg">Professional Experience</h4>
                                <div className="space-y-8">
                                    {resume.experience.map((exp: any, i: number) => (
                                        <div key={i} className="relative pl-6 border-l-2 border-slate-100 space-y-2">
                                            <div className="absolute -left-[9px] top-1 w-4 h-4 bg-white border-2 border-blue-500 rounded-full" />
                                            <div className="flex justify-between items-start">
                                                <div>
                                                    <h5 className="font-bold text-slate-900">{exp.title}</h5>
                                                    <p className="text-sm text-[#0077b5] font-black">{exp.company}</p>
                                                </div>
                                                <span className="text-[10px] font-black text-slate-400 bg-slate-50 px-3 py-1 rounded-full uppercase">{exp.period}</span>
                                            </div>
                                            <ul className="space-y-1.5 list-disc list-inside">
                                                {exp.bullets?.map((bullet: string, j: number) => (
                                                    <li key={j} className="text-sm text-slate-500 font-medium leading-relaxed marker:text-blue-500">{bullet}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        )}

                        {resume.education && resume.education.length > 0 && (
                            <section className="space-y-4">
                                <h4 className="text-[10px] font-black text-[#0077b5] uppercase tracking-widest px-2 py-1 bg-blue-50 w-fit rounded-lg">Education</h4>
                                {resume.education.map((edu: any, i: number) => (
                                    <div key={i} className="flex justify-between items-center text-sm">
                                        <div>
                                            <span className="font-bold text-slate-900">{edu.degree}</span>
                                            <span className="mx-2 text-slate-300">•</span>
                                            <span className="text-slate-500 font-medium">{edu.school}</span>
                                        </div>
                                        <span className="text-[10px] font-black text-slate-400">{edu.year}</span>
                                    </div>
                                ))}
                            </section>
                        )}

                        {resume.certifications && resume.certifications.length > 0 && (
                            <section className="space-y-4">
                                <h4 className="text-[10px] font-black text-[#0077b5] uppercase tracking-widest px-2 py-1 bg-blue-50 w-fit rounded-lg">Certifications</h4>
                                {resume.certifications.map((cert: any, i: number) => (
                                    <div key={i} className="flex justify-between items-center text-sm">
                                        <div>
                                            <span className="font-bold text-slate-900">{cert.name}</span>
                                            <span className="mx-2 text-slate-300">•</span>
                                            <span className="text-slate-500 font-medium">{cert.issuer}</span>
                                        </div>
                                        <span className="text-[10px] font-black text-slate-400">{cert.date}</span>
                                    </div>
                                ))}
                            </section>
                        )}
                    </div>
                </motion.div>
            )}

            {!resume && !loading && !parseLoading && !error && !showPasteFallback && (
                <div className="text-center py-10 space-y-6">
                    <p className="max-w-sm mx-auto text-xs text-slate-400 font-bold uppercase tracking-widest leading-relaxed">
                        Note: This feature uses automated browser agents to parse profile data and structure it into standardized blocks.
                    </p>
                    {isLinkedInConnected && (
                        <button
                            onClick={handleReset}
                            className="text-[10px] font-black text-red-400 hover:text-red-600 uppercase tracking-widest transition-colors flex items-center gap-2 mx-auto"
                        >
                            <RefreshCw className="w-3.5 h-3.5" /> Reset Connection State
                        </button>
                    )}
                </div>
            )}

            {!resume && !loading && !parseLoading && (error || showPasteFallback) && isLinkedInConnected && (
                <div className="text-center py-6">
                    <button
                        onClick={handleReset}
                        className="text-[10px] font-black text-red-400 hover:text-red-600 uppercase tracking-widest transition-colors flex items-center gap-2 mx-auto"
                    >
                        <RefreshCw className="w-3.5 h-3.5" /> Reset Connection State
                    </button>
                </div>
            )}
        </div>
    );
};

export default LinkedInScraper;
