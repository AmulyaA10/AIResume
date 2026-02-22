import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000/api/v1',
});

// Mock auth interceptor
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    // Dynamic configuration headers
    const openRouterKey = localStorage.getItem('openRouterKey');
    const llmModel = localStorage.getItem('llmModel');
    const linkedinUser = localStorage.getItem('linkedinUser');
    const linkedinPass = localStorage.getItem('linkedinPass');

    if (openRouterKey) config.headers['X-OpenRouter-Key'] = openRouterKey;
    if (llmModel) config.headers['X-LLM-Model'] = llmModel;
    if (linkedinUser) config.headers['X-LinkedIn-User'] = linkedinUser;
    if (linkedinPass) config.headers['X-LinkedIn-Pass'] = linkedinPass;

    return config;
});

export default api;
