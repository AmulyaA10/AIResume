import React from 'react';
import ReactDOM from 'react-dom';
import { X, Briefcase, MapPin, Building2, Calendar, Edit2, Users, Star } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface JobDetailModalProps {
    job: any;
    onClose: () => void;
}

const JobDetailModal: React.FC<JobDetailModalProps> = ({ job, onClose }) => {
    const navigate = useNavigate();

    return ReactDOM.createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
            <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl relative z-10 animate-in fade-in zoom-in-95 duration-200 flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="p-6 border-b border-slate-100 flex items-start justify-between sticky top-0 bg-white/80 backdrop-blur-md z-20 rounded-t-2xl">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
                            <Briefcase size={20} />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900">{job.title}</h2>
                            <p className="text-sm text-slate-500">{job.employer_name}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => { onClose(); navigate(`/jd/edit/${job.job_id}`); }}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-500 transition-colors"
                        >
                            <Edit2 size={14} /> Edit
                        </button>
                        <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors">
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Body */}
                <div className="overflow-y-auto flex-1 p-6 space-y-5">

                    {/* Meta row */}
                    <div className="flex flex-wrap gap-3 text-sm text-slate-500">
                        {job.location_name && (
                            <span className="flex items-center gap-1.5"><MapPin size={14} /> {job.location_name}</span>
                        )}
                        <span className="flex items-center gap-1.5"><Building2 size={14} /> {job.employment_type?.replace('_', ' ')}</span>
                        <span className="flex items-center gap-1.5"><Calendar size={14} /> {new Date(job.posted_date).toLocaleDateString()}</span>
                        <span className="bg-slate-100 text-slate-600 text-xs font-bold px-2 py-0.5 rounded uppercase tracking-wider">{job.job_level}</span>
                        {job.positions > 1 && (
                            <span className="flex items-center gap-1 bg-blue-50 text-blue-600 text-xs font-bold px-2 py-0.5 rounded border border-blue-100">
                                <Users size={12} /> {job.positions} positions
                            </span>
                        )}
                    </div>

                    {/* Salary */}
                    {(job.salary_min > 0 || job.salary_max > 0) && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">Salary</h4>
                            <p className="text-sm font-semibold text-slate-700">
                                {job.salary_currency} {job.salary_min?.toLocaleString()} – {job.salary_max?.toLocaleString()}
                            </p>
                        </div>
                    )}

                    {/* Description */}
                    <div>
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Description</h4>
                        <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{job.description}</p>
                    </div>

                    {/* Skills */}
                    {job.skills_required?.length > 0 && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Skills Required</h4>
                            <div className="flex flex-wrap gap-2">
                                {job.skills_required.map((skill: string) => (
                                    <span key={skill} className="px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-semibold border border-blue-100">
                                        {skill}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Benefits */}
                    {job.benefits?.length > 0 && (
                        <div>
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Benefits</h4>
                            <div className="flex flex-wrap gap-2">
                                {job.benefits.map((b: string) => (
                                    <span key={b} className="flex items-center gap-1 px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-semibold border border-amber-100">
                                        <Star size={10} /> {b}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
};

export default JobDetailModal;
