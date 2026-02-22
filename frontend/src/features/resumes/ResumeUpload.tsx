import React, { useState } from 'react';
import { Upload, File, FileText, CheckCircle2, AlertCircle, Loader2, Sparkles } from 'lucide-react';
import api from '../../api';
import { motion, AnimatePresence } from 'framer-motion';
import { PageHeader } from '../../common';

const ResumeUpload = () => {
    const [files, setFiles] = useState<any[]>([]);
    const [uploading, setUploading] = useState(false);
    const [results, setResults] = useState<any[]>([]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const newFiles = Array.from(e.target.files).map(file => ({
                file,
                name: file.name,
                status: 'pending'
            }));
            setFiles(newFiles);
        }
    };

    const handleUpload = async () => {
        console.log("handleUpload triggered", files);
        if (files.length === 0) return;
        setUploading(true);
        setResults([]);

        const formData = new FormData();
        files.forEach(f => formData.append('files', f.file));
        formData.append('store_db', 'true');

        try {
            console.log("Sending request to /resumes/upload");
            const response = await api.post('/resumes/upload', formData);
            console.log("Upload response:", response.data);
            setResults(response.data.processed);
            setFiles(prev => prev.map(f => ({ ...f, status: 'indexed' })));
        } catch (err: any) {
            console.error("Upload error details:", err.response?.data || err.message);
            setFiles(prev => prev.map(f => ({ ...f, status: 'error' })));
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-8">
            <PageHeader
                title="Resume Manager"
                subtitle="Upload candidate resumes to your private vector search database."
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                    <div className="glass-card p-16 border-2 border-dashed border-slate-200 hover:border-primary-300 hover:bg-slate-50/50 transition-all cursor-pointer flex flex-col items-center justify-center text-center relative group">
                        <input
                            type="file"
                            multiple
                            onChange={handleFileChange}
                            className="absolute inset-0 opacity-0 cursor-pointer"
                            accept=".pdf,.docx"
                        />
                        <div className="w-16 h-16 bg-primary-50 rounded-2xl flex items-center justify-center mb-4 border border-primary-100 shadow-sm group-hover:scale-110 transition-transform">
                            <Upload className="text-primary-600 w-8 h-8" />
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 mb-2">Click or drag resumes here</h3>
                        <p className="text-slate-500 max-w-xs mx-auto text-sm font-medium">Supports PDF and DOCX files. Files are indexed for semantic AI search instantly.</p>

                        {files.length > 0 && !uploading && (
                            <button
                                onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                                className="mt-6 bg-primary-600 hover:bg-primary-500 text-white px-6 py-3 rounded-lg text-base font-bold flex items-center gap-2 shadow-lg shadow-primary-500/20 transition-all relative z-20"
                            >
                                <Upload className="w-5 h-5" />
                                Process {files.length} Files
                            </button>
                        )}
                        {uploading && (
                            <div className="mt-6 flex items-center gap-3 text-primary-600 font-bold bg-primary-50 px-6 py-3 rounded-lg border border-primary-100">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Processing...
                            </div>
                        )}
                    </div>

                    <div className="glass-card">
                        <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-white">
                            <h3 className="font-bold flex items-center gap-2 text-slate-800">
                                <File className="w-4 h-4 text-primary-500" />
                                Processing Queue
                            </h3>
                            <span className="text-[10px] font-black text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-200 tracking-widest">{files.length} FILES</span>
                        </div>
                        <div className="divide-y divide-slate-100">
                            {files.length === 0 && (
                                <div className="p-12 text-center text-slate-300 italic font-medium">
                                    Queue is empty. Select files to see progress.
                                </div>
                            )}
                            {files.map((file, i) => (
                                <div key={i} className="p-4 flex items-center gap-4 hover:bg-slate-50/50 transition-colors">
                                    <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center border border-slate-200">
                                        <FileText className="w-4 h-4 text-slate-400" />
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex justify-between items-center mb-1">
                                            <span className="text-sm font-bold text-slate-700">{file.name}</span>
                                            <span className={`text-[10px] font-black uppercase tracking-widest ${file.status === 'indexed' ? 'text-emerald-600' :
                                                file.status === 'error' ? 'text-red-600' : 'text-primary-600'
                                                }`}>{file.status}</span>
                                        </div>
                                        <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200 shadow-inner">
                                            <motion.div
                                                initial={{ width: 0 }}
                                                animate={{ width: file.status === 'indexed' ? '100%' : uploading ? '60%' : '0%' }}
                                                className={`h-full ${file.status === 'indexed' ? 'bg-emerald-500' : 'bg-primary-500'}`}
                                            />
                                        </div>
                                    </div>
                                    {file.status === 'indexed' && <CheckCircle2 className="text-emerald-500 w-5 h-5 flex-shrink-0" />}
                                    {file.status === 'error' && <AlertCircle className="text-red-500 w-5 h-5 flex-shrink-0" />}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="glass-card p-6 bg-primary-600 text-white shadow-lg shadow-primary-500/20">
                        <h4 className="font-bold mb-4 flex items-center gap-2 text-primary-50">
                            <Sparkles className="w-4 h-4" />
                            AI Indexing Active
                        </h4>
                        <p className="text-sm text-primary-100 leading-relaxed mb-6 font-medium">
                            Our system extracts full text, parses skills, and indexes embeddings into your vector store for sub-second semantic retrieval.
                        </p>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3 text-xs font-bold bg-white/10 p-2 rounded border border-white/10">
                                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                OCR Processing Enabled
                            </div>
                            <div className="flex items-center gap-3 text-xs font-bold bg-white/10 p-2 rounded border border-white/10">
                                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                                Vector Embeddings: ON
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <AnimatePresence>
                {results.length > 0 && (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
                        <h3 className="font-bold text-slate-400 uppercase tracking-widest text-[10px]">Indexing Results</h3>
                        {results.map((res, i) => (
                            <div key={i} className="flex items-center gap-4 p-4 glass-card border-emerald-100 bg-emerald-50/50">
                                <CheckCircle2 className="text-emerald-500 w-5 h-5 flex-shrink-0" />
                                <div className="flex-1">
                                    <p className="text-sm font-bold text-slate-800">{res.filename}</p>
                                    <p className="text-xs text-emerald-600 font-medium">Successfully parsed and stored in LanceDB</p>
                                </div>
                            </div>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default ResumeUpload;
