import React, { useState } from 'react';
import { Linkedin, Loader2, Link as LinkIcon, Download, RefreshCw, FileCheck } from 'lucide-react';
import api from '../api';
import { motion } from 'framer-motion';
import { PageHeader } from '../common';
import { useAuth } from '../context/AuthContext';

const LinkedInScraper = () => {
    const [url, setUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [resume, setResume] = useState<any | null>(null);
    const inputRef = React.useRef<HTMLInputElement>(null);

    const handleScrape = async () => {
        if (!url.trim()) return;
        setLoading(true);
        setResume(null);
        try {
            const response = await api.post('/linkedin/scrape', { query: url });
            setResume(response.data.resume);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const { user, login } = useAuth(); // Get user and login from context

    // Auto-populate and handle focus if linked via OAuth
    React.useEffect(() => {
        const isConnected = localStorage.getItem('linkedin_connected');
        const storedUrl = localStorage.getItem('linkedin_profile_url');

        // Extract from URL params for fresh override
        const urlParams = new URLSearchParams(window.location.search);
        const paramUrl = urlParams.get('profile_url');

        if (paramUrl) {
            setUrl(paramUrl);
        } else if (storedUrl && !url) {
            setUrl(storedUrl);
        }

        // Focus input if we are authenticated but have no resume
        if (isConnected && !resume && inputRef.current) {
            inputRef.current.focus();
        }

        let retryCount = 0;
        const maxRetries = 15; // 75 seconds total

        if (isConnected && user) {
            const fetchSyncedProfile = async () => {
                try {
                    const response = await api.get('/user/profile');
                    const potentialResume = response.data.resume;
                    const isValidStub = potentialResume &&
                        potentialResume.contact?.name &&
                        (potentialResume.summary?.length > 100 || (potentialResume.experience && potentialResume.experience.length > 0));

                    if (response.data.found && potentialResume && isValidStub) {
                        setResume(potentialResume);
                        setLoading(false);
                    } else if (retryCount < maxRetries) {
                        if (loading) {
                            console.log(`Synced profile not found yet (attempt ${retryCount + 1}), polling...`);
                            retryCount++;
                            setTimeout(fetchSyncedProfile, 5000);
                        } else {
                            setLoading(false);
                        }
                    } else {
                        console.log("Max retries reached or sync idle.");
                        setLoading(false);
                    }
                } catch (err) {
                    console.error("Failed to fetch synced profile:", err);
                    setLoading(false);
                }
            };

            fetchSyncedProfile();
        }
    }, [user, loading, resume]); // resume added to dependency to allow focusing logic to work correctly

    const handleReset = () => {
        localStorage.removeItem('linkedin_connected');
        localStorage.removeItem('linkedin_profile_url');
        setResume(null);
        setLoading(false);
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

    return (
        <div className="space-y-8">
            <PageHeader
                title="LinkedIn Scraper"
                subtitle="Convert public LinkedIn profiles into structured professional resumes instantly."
            />

            <div className="glass-card p-12 max-w-4xl mx-auto border-blue-100 bg-white/80 shadow-lg shadow-blue-500/5">
                <div className="flex flex-col items-center gap-8">
                    <div
                        onClick={!isResumeValid ? handleLinkedInConnect : undefined}
                        className={`w-24 h-24 bg-[#0077b5] rounded-[2rem] flex items-center justify-center shadow-xl shadow-[#0077b5]/20 rotate-12 hover:rotate-0 transition-transform cursor-pointer ${loading ? 'animate-pulse' : ''}`}
                    >
                        <Linkedin className="text-white w-12 h-12" />
                    </div>

                    <div className="text-center">
                        <h3 className="text-xl font-bold text-slate-800 mb-2">
                            {isResumeValid ? 'Profile Synced Successfully' : (localStorage.getItem('linkedin_connected') ? 'LinkedIn Authenticated' : 'Social Profile Import')}
                        </h3>
                        <p className="text-sm text-slate-500 font-medium max-w-md mx-auto">
                            {isResumeValid
                                ? 'Your profile has been automatically imported and processed.'
                                : (localStorage.getItem('linkedin_connected')
                                    ? (loading ? 'AI Scraper Active. This may take up to a minute...' : 'Verify your profile URL below and click "Start AI Sync" to begin.')
                                    : 'Click the LinkedIn icon above or the button below to authenticate and sync your profile data.')}
                        </p>
                    </div>

                    {!isResumeValid && (
                        <div className="w-full space-y-6">
                            {/* Confirmation Input for LikedIn Auth */}
                            {localStorage.getItem('linkedin_connected') ? (
                                <div className="space-y-4">
                                    <div className="bg-blue-50 border border-blue-100 p-4 rounded-xl space-y-2">
                                        <p className="text-xs font-bold text-[#0077b5] uppercase tracking-wider flex items-center gap-2">
                                            <LinkIcon className="w-3.5 h-3.5" /> Action Required: Verify Profile URL
                                        </p>
                                        <p className="text-[11px] text-slate-500 font-medium leading-relaxed">
                                            LinkedIn API restricts private vanity URLs. Please check the URL below.
                                            If it's wrong, <strong>copy the link from your "Public profile & URL" section</strong> (the one with the unique numbers at the end) and paste it here.
                                        </p>
                                    </div>
                                    <div className="w-full relative group">
                                        <LinkIcon className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 group-focus-within:text-[#0077b5] transition-colors" />
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={url}
                                            onChange={(e) => setUrl(e.target.value)}
                                            placeholder="https://www.linkedin.com/in/username"
                                            className="w-full bg-white border border-blue-200 rounded-2xl py-5 pl-14 pr-4 focus:border-[#0077b5] outline-none text-lg transition-all shadow-sm focus:ring-4 focus:ring-[#0077b5]/5 text-slate-800 placeholder:text-slate-300"
                                        />
                                    </div>
                                    <button
                                        onClick={handleScrape}
                                        disabled={loading || !url.trim()}
                                        className="w-full bg-[#0077b5] hover:bg-[#006396] text-white py-5 rounded-2xl font-black uppercase tracking-widest text-sm transition-all shadow-xl shadow-[#0077b5]/20 active:scale-95 flex items-center justify-center gap-3"
                                    >
                                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                                        {loading ? 'AI Scraper Active...' : 'Verify & Start AI Sync'}
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

                                    <div className="w-full relative group">
                                        <LinkIcon className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 group-focus-within:text-[#0077b5] transition-colors" />
                                        <input
                                            type="text"
                                            value={url}
                                            onChange={(e) => setUrl(e.target.value)}
                                            placeholder="https://www.linkedin.com/in/username"
                                            className="w-full bg-white border border-slate-200 rounded-2xl py-5 pl-14 pr-4 focus:border-[#0077b5] outline-none text-lg transition-all shadow-sm focus:ring-4 focus:ring-[#0077b5]/5 text-slate-800 placeholder:text-slate-300"
                                        />
                                    </div>

                                    <button
                                        onClick={handleScrape}
                                        disabled={loading || !url.trim()}
                                        className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 py-4 rounded-xl font-bold transition-all disabled:opacity-50 flex items-center justify-center gap-3"
                                    >
                                        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                                        {loading ? 'Fetching...' : 'Convert from URL'}
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
                    </div>
                </motion.div>
            )}

            {!resume && !loading && (
                <div className="text-center py-10 space-y-6">
                    <p className="max-w-sm mx-auto text-xs text-slate-400 font-bold uppercase tracking-widest leading-relaxed">
                        Note: This feature uses automated browser agents to parse profile data and structure it into standardized blocks.
                    </p>
                    {localStorage.getItem('linkedin_connected') && (
                        <button
                            onClick={handleReset}
                            className="text-[10px] font-black text-red-400 hover:text-red-600 uppercase tracking-widest transition-colors flex items-center gap-2 mx-auto"
                        >
                            <RefreshCw className="w-3.5 h-3.5" /> Reset Connection State
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default LinkedInScraper;
