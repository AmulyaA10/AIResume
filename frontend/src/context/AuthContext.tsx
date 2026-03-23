import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import api from '../api';

type Persona = 'jobseeker' | 'recruiter' | 'manager' | null;

interface User {
    name: string;
    email: string;
    avatar?: string;
}

interface AuthContextType {
    isAuthenticated: boolean;
    persona: Persona;
    user: User | null;
    login: (method: string) => void;
    logout: () => void;
    handleOAuthCallback: (token: string, name: string, email?: string, linkedinConnected?: boolean, profileUrl?: string) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Initialise synchronously from localStorage so ProtectedRoute never flashes /login
    // on a fresh page.goto() when the token is already in storage.
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
        const token = localStorage.getItem('token');
        const storedPersona = localStorage.getItem('persona');
        const storedUser = localStorage.getItem('user');
        return !!(token && storedPersona && storedUser);
    });
    const [persona, setPersona] = useState<Persona>(() => {
        return (localStorage.getItem('persona') as Persona) ?? null;
    });
    const [user, setUser] = useState<User | null>(() => {
        const raw = localStorage.getItem('user');
        try { return raw ? JSON.parse(raw) : null; } catch { return null; }
    });
    const navigate = useNavigate();
    const location = useLocation();

    // Handle OAuth Callback - Logic moved to AuthCallback page via handleOAuthCallback
    const handleOAuthCallback = React.useCallback((token: string, name: string, email?: string, linkedinConnected?: boolean, profileUrl?: string) => {
        // Parse linkedin_connected from URL if present (passed via query params in the callback URL? 
        // No, the callback URL logic is in AuthCallback.tsx, we need to update that or pass params here.
        // Actually, AuthCallback calls this function. We should update the signature or letting AuthCallback handle parsing.)

        // Assume JobSeeker for OAuth for now (unless recruiter token)
        let newPersona: Persona = 'jobseeker';

        // ONLY corporate SSO login maps to Recruiter
        if (token.includes('recruiter')) {
            newPersona = 'recruiter';
        }

        const newUser: User = { name: name || 'User', email: email || 'user@example.com' };

        localStorage.setItem('token', token);
        localStorage.setItem('persona', newPersona);
        localStorage.setItem('user', JSON.stringify(newUser));

        // Check for linkedin_connected param in the window location (since we represent the redirect)
        // Explicitly set flag if passed
        if (linkedinConnected) {
            localStorage.setItem('linkedin_connected', 'true');
        } else {
            localStorage.removeItem('linkedin_connected');
        }

        if (profileUrl) {
            localStorage.setItem('linkedin_profile_url', profileUrl);
        } else {
            localStorage.removeItem('linkedin_profile_url');
        }

        setIsAuthenticated(true);
        setPersona(newPersona);
        setUser(newUser);

        // Notify CredentialContext to reload server-stored credentials
        window.dispatchEvent(new Event('auth:login'));

        // Redirect to /linkedin if we just connected LinkedIn
        if (linkedinConnected) {
            navigate('/linkedin', { replace: true });
        } else {
            navigate('/', { replace: true });
        }
    }, [navigate]);

    const login = React.useCallback((method: string) => {
        if (method === 'gmail') {
            window.location.href = `${api.defaults.baseURL}/auth/google`;
            return;
        }
        if (method === 'linkedin') {
            window.location.href = `${api.defaults.baseURL}/auth/linkedin`;
            return;
        }

        // Mock login logic for others
        let newPersona: Persona = 'jobseeker';
        let newUser: User = { name: 'User', email: 'user@example.com' };

        if (method === 'corporate') {
            newPersona = 'recruiter';
            newUser = { name: 'Recruiter Pro', email: 'admin@company.com' };
        } else if (method === 'manager') {
            newPersona = 'manager';
            newUser = { name: 'Hiring Lead', email: 'lead@company.com' };
        } else if (method === 'jobseeker') {
            newPersona = 'jobseeker';
            newUser = { name: 'Job Seeker', email: 'lintojm@yahoo.com' };
        }

        // Persist mock session with distinct tokens for RBAC testing
        const mockToken = newPersona === 'manager'
            ? 'mock-manager-token'
            : newPersona === 'recruiter'
            ? 'mock-recruiter-token'
            : 'mock-token-123';

        localStorage.setItem('token', mockToken);
        localStorage.setItem('persona', newPersona);
        localStorage.setItem('user', JSON.stringify(newUser));

        setIsAuthenticated(true);
        setPersona(newPersona);
        setUser(newUser);

        // Notify CredentialContext to reload server-stored credentials
        window.dispatchEvent(new Event('auth:login'));

        navigate('/');
    }, [navigate]);

    const logout = React.useCallback(() => {
        // Dispatch event so CredentialContext clears in-memory credentials
        window.dispatchEvent(new Event('auth:logout'));

        localStorage.removeItem('token');
        localStorage.removeItem('persona');
        localStorage.removeItem('user');
        localStorage.removeItem('user_uid');
        localStorage.removeItem('linkedin_connected');
        localStorage.removeItem('linkedin_profile_url');
        setIsAuthenticated(false);
        setPersona(null);
        setUser(null);
        navigate('/login');
    }, [navigate]);

    const value = React.useMemo(() => ({
        isAuthenticated,
        persona,
        user,
        login,
        logout,
        handleOAuthCallback
    }), [isAuthenticated, persona, user, login, logout, handleOAuthCallback]);

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
