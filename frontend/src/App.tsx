import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import { useAuth } from './context/AuthContext';

// Feature-based imports
import { Login, AuthCallback } from './features/auth';
import { MyApplications } from './features/dashboard';
import { Dashboard, JobDefinitions, JobForm, ResumeDatabase } from './features/dashboard';
import { ResumeUpload, ResumeGenerator, LinkedInScraper } from './features/resumes';
import { QualityScoring, SkillGap, AutoScreening, AgentDashboard } from './features/analysis';
import AISearch from './features/analysis/AISearch';
import JobSearch from './features/jobs/JobSearch';
import { Settings } from './features/settings';

// Auth Guard
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const { isAuthenticated } = useAuth();
    if (!isAuthenticated) return <Navigate to="/login" replace />;
    return <Layout>{children}</Layout>;
};

// Persona-aware search page: recruiter sees candidate search, jobseeker sees job search
const SearchPage = () => {
    const { persona } = useAuth();
    return persona === 'recruiter' ? <AISearch /> : <JobSearch />;
};

function App() {
    const { persona } = useAuth();
    return (
        <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            <Route path="/" element={
                <ProtectedRoute>
                    <Dashboard />
                </ProtectedRoute>
            } />
            <Route path="/my-applications" element={
                <ProtectedRoute>
                    <MyApplications />
                </ProtectedRoute>
            } />

            <Route path="/upload" element={
                <ProtectedRoute>
                    <ResumeUpload />
                </ProtectedRoute>
            } />

            <Route path="/search" element={
                <ProtectedRoute>
                    <SearchPage />
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

            <Route path="/agent" element={
                <ProtectedRoute>
                    <AgentDashboard />
                </ProtectedRoute>
            } />

            <Route path="/resumes" element={
                <ProtectedRoute>
                    <ResumeDatabase />
                </ProtectedRoute>
            } />

            <Route path="/jd" element={
                <ProtectedRoute>
                    <JobDefinitions />
                </ProtectedRoute>
            } />
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

            <Route path="/settings" element={
                <ProtectedRoute>
                    {persona === 'manager' ? <Settings /> : <Navigate to="/" replace />}
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
