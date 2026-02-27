import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { useAuth } from './context/AuthContext';

// Feature-based imports
import { Login, AuthCallback } from './features/auth';
<<<<<<< HEAD
import { Dashboard, JobDefinitions, JobForm } from './features/dashboard';
import { ResumeUpload, ResumeGenerator, LinkedInScraper } from './features/resumes';
import { QualityScoring, SkillGap, AutoScreening, AISearch } from './features/analysis';
import { JobSearch } from './features/jobs';
=======
import { Dashboard, JobDefinitions } from './features/dashboard';
import { ResumeUpload, ResumeGenerator, LinkedInScraper } from './features/resumes';
import { QualityScoring, SkillGap, AutoScreening, AISearch } from './features/analysis';
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
import { Settings } from './features/settings';

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
<<<<<<< HEAD
                    <JobSearch />
=======
                    <AISearch />
>>>>>>> 9d136502ee9374e86211849855e67746afb88872
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
<<<<<<< HEAD
            <Route path="/jd/new" element={
                <ProtectedRoute>
                    <JobForm />
                </ProtectedRoute>
            } />
            <Route path="/jd/edit/:id" element={
                <ProtectedRoute>
                    <JobForm />
                </ProtectedRoute>
            } />
=======
>>>>>>> 9d136502ee9374e86211849855e67746afb88872

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
