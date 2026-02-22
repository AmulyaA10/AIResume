import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import ResumeUpload from './pages/ResumeUpload';
import AISearch from './pages/AISearch';
import QualityScoring from './pages/QualityScoring';
import SkillGap from './pages/SkillGap';
import AutoScreening from './pages/AutoScreening';
import ResumeGenerator from './pages/ResumeGenerator';
import LinkedInScraper from './pages/LinkedInScraper';
import Layout from './components/Layout';
import JobDefinitions from './pages/JobDefinitions';
import Settings from './pages/Settings';
import AuthCallback from './pages/AuthCallback';

import { useAuth } from './context/AuthContext';

// Auth Guard
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    return <Layout>{children}</Layout>;
};

function App() {
    return (
        <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            <Route path="/" element={
                <ProtectedRoute>
                    <Dashboard />
                </ProtectedRoute>
            } />

            <Route path="/upload" element={
                <ProtectedRoute>
                    <ResumeUpload />
                </ProtectedRoute>
            } />

            <Route path="/search" element={
                <ProtectedRoute>
                    <AISearch />
                </ProtectedRoute>
            } />

            <Route path="/scoring" element={
                <ProtectedRoute>
                    <QualityScoring />
                </ProtectedRoute>
            } />

            <Route path="/skill-gap" element={
                <ProtectedRoute>
                    <SkillGap />
                </ProtectedRoute>
            } />

            <Route path="/screen" element={
                <ProtectedRoute>
                    <AutoScreening />
                </ProtectedRoute>
            } />

            <Route path="/jd" element={
                <ProtectedRoute>
                    <JobDefinitions />
                </ProtectedRoute>
            } />

            <Route path="/settings" element={
                <ProtectedRoute>
                    <Settings />
                </ProtectedRoute>
            } />

            <Route path="/generate" element={
                <ProtectedRoute>
                    <ResumeGenerator />
                </ProtectedRoute>
            } />

            <Route path="/linkedin" element={
                <ProtectedRoute>
                    <LinkedInScraper />
                </ProtectedRoute>
            } />

            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}

export default App;
