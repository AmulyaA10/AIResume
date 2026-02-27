import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api from '../api';

interface Credentials {
    openRouterKey: string;
    linkedinUser: string;
    linkedinPass: string;
}

interface MaskedCredentials {
    openRouterKey: string | null;
    linkedinUser: string | null;
    linkedinPass: string | null;
    has_openRouterKey: boolean;
    has_linkedinUser: boolean;
    has_linkedinPass: boolean;
}

interface CredentialContextType {
    credentials: Credentials;
    maskedCredentials: MaskedCredentials | null;
    setCredential: (key: keyof Credentials, value: string) => void;
    saveCredentials: () => Promise<void>;
    loadMaskedCredentials: () => Promise<void>;
    clearCredentials: () => Promise<void>;
    isLoaded: boolean;
    isLoading: boolean;
    loadError: boolean;
}

const CredentialContext = createContext<CredentialContextType | undefined>(undefined);

export const CredentialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [credentials, setCredentials] = useState<Credentials>({
        openRouterKey: '',
        linkedinUser: '',
        linkedinPass: '',
    });
    const [maskedCredentials, setMaskedCredentials] = useState<MaskedCredentials | null>(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const [loadError, setLoadError] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    const setCredential = useCallback((key: keyof Credentials, value: string) => {
        setCredentials(prev => ({ ...prev, [key]: value }));
    }, []);

    const loadMaskedCredentials = useCallback(async () => {
        try {
            setLoadError(false);
            setIsLoading(true);
            const resp = await api.get('/user/settings');
            setMaskedCredentials(resp.data);
            setIsLoaded(true);
        } catch (err) {
            console.error('Failed to load credential status:', err);
            setLoadError(true);
            // Do NOT set isLoaded=true on failure — allow consumers to retry
        } finally {
            setIsLoading(false);
        }
    }, []);

    const saveCredentials = useCallback(async () => {
        const payload: Record<string, string> = {};
        if (credentials.openRouterKey) payload.openRouterKey = credentials.openRouterKey;
        if (credentials.linkedinUser) payload.linkedinUser = credentials.linkedinUser;
        if (credentials.linkedinPass) payload.linkedinPass = credentials.linkedinPass;

        if (Object.keys(payload).length === 0) return;

        await api.put('/user/settings', payload);
        setCredentials({ openRouterKey: '', linkedinUser: '', linkedinPass: '' });
        await loadMaskedCredentials();
    }, [credentials, loadMaskedCredentials]);

    const clearCredentials = useCallback(async () => {
        await api.delete('/user/settings');
        setCredentials({ openRouterKey: '', linkedinUser: '', linkedinPass: '' });
        setMaskedCredentials(null);
    }, []);

    // Listen for logout event to clear in-memory cache
    useEffect(() => {
        const handler = () => {
            setCredentials({ openRouterKey: '', linkedinUser: '', linkedinPass: '' });
            setMaskedCredentials(null);
            setIsLoaded(false);
            setLoadError(false);
        };
        window.addEventListener('auth:logout', handler);
        return () => window.removeEventListener('auth:logout', handler);
    }, []);

    // Listen for login event to auto-load credentials from server with retry
    useEffect(() => {
        const handler = async () => {
            // Reset state for the new session
            setIsLoaded(false);
            setLoadError(false);
            setMaskedCredentials(null);
            setIsLoading(true); // prevent mount effects from competing

            // Retry with increasing delays to handle auth token timing
            const delays = [200, 500, 1000];
            for (const delay of delays) {
                await new Promise(resolve => setTimeout(resolve, delay));
                try {
                    const resp = await api.get('/user/settings');
                    setMaskedCredentials(resp.data);
                    setIsLoaded(true);
                    setIsLoading(false);
                    return; // success — stop retrying
                } catch (err) {
                    console.warn(`Credential load attempt failed (delay=${delay}ms):`, err);
                }
            }
            // All retries exhausted
            console.error('Failed to load credentials after all retries');
            setIsLoading(false);
            setLoadError(true);
        };
        window.addEventListener('auth:login', handler);
        return () => window.removeEventListener('auth:login', handler);
    }, []);

    const value = React.useMemo(() => ({
        credentials,
        maskedCredentials,
        setCredential,
        saveCredentials,
        loadMaskedCredentials,
        clearCredentials,
        isLoaded,
        isLoading,
        loadError,
    }), [credentials, maskedCredentials, setCredential, saveCredentials,
         loadMaskedCredentials, clearCredentials, isLoaded, isLoading, loadError]);

    return (
        <CredentialContext.Provider value={value}>
            {children}
        </CredentialContext.Provider>
    );
};

export const useCredentials = () => {
    const ctx = useContext(CredentialContext);
    if (!ctx) throw new Error('useCredentials must be used within CredentialProvider');
    return ctx;
};
