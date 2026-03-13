import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
});

// Auth + non-sensitive preference interceptor
// NOTE: Credentials (openRouterKey, linkedinUser, linkedinPass) are now stored
// server-side with encryption. Only the non-sensitive llmModel preference
// remains in localStorage. The backend's resolve_credentials() automatically
// falls back to server-stored values when X- headers are absent.
// Generate or retrieve a stable per-browser user identity for jobseeker isolation.
// Recruiter/manager roles are determined by the token and cannot be overridden.
const getOrCreateUserUid = (): string => {
    // If a user is logged in, use their email as a stable identity
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
        try {
            const user = JSON.parse(storedUser);
            if (user.email) return `uid_${user.email}`;
        } catch (e) {
            console.error('Failed to parse user for UID', e);
        }
    }

    let uid = localStorage.getItem('user_uid');
    if (!uid) {
        uid = 'uid_' + Math.random().toString(36).substring(2, 10) + Math.random().toString(36).substring(2, 10);
        localStorage.setItem('user_uid', uid);
    }
    return uid;
};

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    // Send a stable per-browser user ID so each jobseeker has isolated data.
    // The backend only uses this for non-recruiter/non-manager tokens.
    config.headers['X-User-ID'] = getOrCreateUserUid();

    // Only non-sensitive preference stays in localStorage
    const llmModel = localStorage.getItem('llmModel');
    if (llmModel) config.headers['X-LLM-Model'] = llmModel;

    return config;
});

// One-time migration: remove legacy credential keys from localStorage
// This runs once per browser to clean up credentials that were previously stored insecurely
(() => {
    const legacyKeys = ['openRouterKey', 'linkedinUser', 'linkedinPass'];
    const migrated = localStorage.getItem('_credentialsMigrated');
    if (!migrated) {
        legacyKeys.forEach(key => localStorage.removeItem(key));
        localStorage.setItem('_credentialsMigrated', '1');
    }
})();

export const jobsApi = {
    list: (params: any) => api.get('/jobs', { params }),
    listPublic: (params?: any) => api.get('/jobs/public', { params }),
    get: (id: string) => api.get(`/jobs/${id}`),
    create: (data: any) => api.post('/jobs', data),
    update: (id: string, data: any) => api.put(`/jobs/${id}`, data),
    delete: (id: string) => api.delete(`/jobs/${id}`),
    parseUpload: (file: File) => {
        const fd = new FormData();
        fd.append('file', file);
        return api.post('/jobs/parse-upload', fd);
    },
    apply: (jobId: string, resumeId: string) => api.post(`/jobs/${jobId}/apply?resume_id=${resumeId}`),
    getAppliedJobs: () => api.get('/jobs/my-applied'),
    getCandidates: (jobId: string) => api.get(`/jobs/${jobId}/candidates`),
    updateCandidateStatus: (jobId: string, resumeId: string, status: string) => 
        api.put(`/jobs/${jobId}/candidates/${encodeURIComponent(resumeId)}/status`, { status }),
};

export const resumesApi = {
    list: () => api.get('/resumes'),
    getText: (filename: string) => api.get(`/resumes/${encodeURIComponent(filename)}/text`),
    updateText: (filename: string, text: string) => api.put(`/resumes/${encodeURIComponent(filename)}/text`, { text }),
    rename: (filename: string, newFilename: string) => api.put(`/resumes/${encodeURIComponent(filename)}/rename`, { new_filename: newFilename }),
};

export interface ResumeWithUser {
    filename: string;
    user_id: string;
}

export const matchApi = {
    matchResume: (resumeId: string, limit: number = 50) => api.get(`/match/resume/${resumeId}`, { params: { limit } }),
    matchResumeSkills: (resumeId: string, limit: number = 100) => api.get(`/match/resume/${resumeId}/skills-match`, { params: { limit } }),
    extractSkills: (resumeId: string) => api.get(`/match/resume/${resumeId}/extract-skills`),
    searchJobs: (query: string, limit: number = 50, filters: any = {}) => api.get('/match/search/jobs', { params: { q: query, limit, ...filters } }),
};
export default api;
