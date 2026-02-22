import React, { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

const AuthCallback = () => {
    const [searchParams] = useSearchParams();
    const { handleOAuthCallback } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        const token = searchParams.get('token');
        const name = searchParams.get('name');
        const email = searchParams.get('email');
        const linkedinConnected = searchParams.get('linkedin_connected') === 'true';
        const profileUrl = searchParams.get('profile_url');

        if (token) {
            handleOAuthCallback(token, name || 'User', email || undefined, linkedinConnected, profileUrl || undefined);
        } else {
            console.error('No token found in callback URL');
            navigate('/login');
        }
    }, [searchParams, handleOAuthCallback, navigate]);

    return (
        <div className="h-screen flex flex-col items-center justify-center bg-slate-50 space-y-4">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
            <h2 className="text-xl font-bold text-slate-700">Completing Secure Sign-in...</h2>
            <p className="text-slate-400 text-sm">Please wait while we establish your session.</p>
        </div>
    );
};

export default AuthCallback;
