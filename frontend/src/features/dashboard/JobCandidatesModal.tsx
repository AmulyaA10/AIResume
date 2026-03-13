import React, { useState, useEffect } from 'react';
import { X, Users, Edit } from 'lucide-react';
import { jobsApi } from '../../api';

interface Candidate {
    resume_id: string;
    candidate_user_id: string;
    applied_at: string;
    applied_status: string;
}

interface JobCandidatesModalProps {
    jobId: string;
    jobTitle: string;
    onClose: () => void;
}

const JobCandidatesModal: React.FC<JobCandidatesModalProps> = ({ jobId, jobTitle, onClose }) => {
    const [candidates, setCandidates] = useState<Candidate[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUpdating, setIsUpdating] = useState<string | null>(null);

    useEffect(() => {
        fetchCandidates();
    }, [jobId]);

    const fetchCandidates = async () => {
        setIsLoading(true);
        try {
            const response = await jobsApi.getCandidates(jobId);
            setCandidates(response.data);
        } catch (error) {
            console.error("Failed to fetch candidates:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleStatusUpdate = async (resumeId: string, newStatus: string) => {
        setIsUpdating(resumeId);
        try {
            await jobsApi.updateCandidateStatus(jobId, resumeId, newStatus);
            setCandidates(candidates.map(c => 
                c.resume_id === resumeId ? { ...c, applied_status: newStatus } : c
            ));
        } catch (error) {
            console.error("Failed to update status:", error);
            alert("Failed to update status.");
        } finally {
            setIsUpdating(null);
        }
    };

    const getStatusTheme = (status: string) => {
        switch (status.toLowerCase()) {
            case 'selected': return 'bg-green-100 text-green-700 border-green-200';
            case 'rejected': return 'bg-red-100 text-red-700 border-red-200';
            default: return 'bg-blue-100 text-blue-700 border-blue-200';
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl relative z-10 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">
                <div className="p-6 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white/80 backdrop-blur-md z-20 rounded-t-2xl">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
                            <Users size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">Job Candidates</h2>
                            <p className="text-sm text-slate-500">{jobTitle}</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto flex-1">
                    {isLoading ? (
                        <div className="py-20 flex flex-col items-center justify-center text-slate-400">
                            <div className="w-8 h-8 border-4 border-slate-200 border-t-blue-600 rounded-full animate-spin"></div>
                            <p className="mt-4">Loading candidates...</p>
                        </div>
                    ) : candidates.length === 0 ? (
                        <div className="py-20 text-center glass-card bg-slate-50/50 border-dashed border-slate-200">
                            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
                                <Users size={32} />
                            </div>
                            <h4 className="text-slate-900 font-bold text-lg">No Candidates Yet</h4>
                            <p className="text-slate-500 max-w-xs mx-auto text-sm mt-1">
                                There are no applications for this job at the moment.
                            </p>
                        </div>
                    ) : (
                        <div className="overflow-x-auto rounded-xl border border-slate-200">
                            <table className="w-full text-left text-sm whitespace-nowrap">
                                <thead className="bg-slate-50/80 text-slate-600 font-semibold border-b border-slate-200">
                                    <tr>
                                        <th className="px-6 py-4">Candidate Resume</th>
                                        <th className="px-6 py-4">Applied Date</th>
                                        <th className="px-6 py-4">Status</th>
                                        <th className="px-6 py-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {candidates.map((candidate) => (
                                        <tr key={candidate.resume_id} className="hover:bg-slate-50/50 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="font-medium text-slate-900">{candidate.resume_id}</div>
                                                <div className="text-xs text-slate-500">ID: {candidate.candidate_user_id.substring(0, 8)}...</div>
                                            </td>
                                            <td className="px-6 py-4 text-slate-500">
                                                {new Date(candidate.applied_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusTheme(candidate.applied_status)}`}>
                                                    {candidate.applied_status.toUpperCase()}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <select
                                                    value={candidate.applied_status}
                                                    onChange={(e) => handleStatusUpdate(candidate.resume_id, e.target.value)}
                                                    disabled={isUpdating === candidate.resume_id}
                                                    className="text-sm border-slate-200 rounded-lg text-slate-700 bg-white hover:bg-slate-50 cursor-pointer disabled:opacity-50"
                                                >
                                                    <option value="applied">Applied</option>
                                                    <option value="selected">Selected</option>
                                                    <option value="rejected">Rejected</option>
                                                </select>
                                                {isUpdating === candidate.resume_id && (
                                                    <span className="ml-2 text-xs text-blue-500 animate-pulse">Updating...</span>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default JobCandidatesModal;
