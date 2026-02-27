import axios from 'axios';

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
});

// Auth + non-sensitive preference interceptor
// NOTE: Credentials (openRouterKey, linkedinUser, linkedinPass) are now stored
// server-side with encryption. Only the non-sensitive llmModel preference
// remains in localStorage. The backend's resolve_credentials() automatically
// falls back to server-stored values when X- headers are absent.
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

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

<<<<<<< HEAD
export const jobsApi = {
    list: (params: any) => api.get('/jobs', { params }),
    get: (id: string) => api.get(`/jobs/${id}`),
    create: (data: any) => api.post('/jobs', data),
    update: (id: string, data: any) => api.put(`/jobs/${id}`, data),
    delete: (id: string) => api.delete(`/jobs/${id}`),
    parseUpload: (file: File) => {
        const fd = new FormData();
        fd.append('file', file);
        return api.post('/jobs/parse-upload', fd);
    },
};

export const matchApi = {
    matchResume: (resumeId: string, limit: number = 50) => api.get(`/match/resume/${resumeId}`, { params: { limit } }),
    searchJobs: (query: string, limit: number = 50, filters: any = {}) => api.get('/match/search/jobs', { params: { q: query, limit, ...filters } }),
};

=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
export default api;
