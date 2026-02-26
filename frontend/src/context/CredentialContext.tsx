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

    const setCredential = useCallback((key: keyof Credentials, value: string) => {
        setCredentials(prev => ({ ...prev, [key]: value }));
    }, []);

    const loadMaskedCredentials = useCallback(async () => {
        try {
            const resp = await api.get('/user/settings');
            setMaskedCredentials(resp.data);
            setIsLoaded(true);
        } catch (err) {
            console.error('Failed to load credential status:', err);
            setIsLoaded(true);
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
        };
        window.addEventListener('auth:logout', handler);
        return () => window.removeEventListener('auth:logout', handler);
    }, []);

    const value = React.useMemo(() => ({
        credentials,
        maskedCredentials,
        setCredential,
        saveCredentials,
        loadMaskedCredentials,
        clearCredentials,
        isLoaded,
    }), [credentials, maskedCredentials, setCredential, saveCredentials,
         loadMaskedCredentials, clearCredentials, isLoaded]);

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
