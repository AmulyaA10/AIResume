import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import { AuthProvider } from './context/AuthContext'
import { CredentialProvider } from './context/CredentialContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <BrowserRouter>
            <AuthProvider>
                <CredentialProvider>
                    <App />
                </CredentialProvider>
            </AuthProvider>
        </BrowserRouter>
    </React.StrictMode>,
)
