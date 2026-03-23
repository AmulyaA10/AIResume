import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Login from '../features/auth/Login'
import { AuthProvider } from '../context/AuthContext'

// Mock useNavigate so login() doesn't crash trying to navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders login buttons', () => {
    renderLogin()
    expect(screen.getByText(/Login with User Account/i)).toBeInTheDocument()
    expect(screen.getByText(/Login with LinkedIn/i)).toBeInTheDocument()
    expect(screen.getByText(/Recruiter SSO/i)).toBeInTheDocument()
    expect(screen.getByText(/Manager SSO/i)).toBeInTheDocument()
  })

  it('renders branding text', () => {
    renderLogin()
    expect(screen.getByText('RESUME.AI')).toBeInTheDocument()
  })

  it('sets manager persona in localStorage when Manager SSO clicked', async () => {
    vi.useFakeTimers()
    renderLogin()
    fireEvent.click(screen.getByText(/Manager SSO/i))
    // Flush the 800 ms timeout inside handleLogin
    vi.runAllTimers()
    expect(localStorage.getItem('persona')).toBe('manager')
    vi.useRealTimers()
  })

  it('sets recruiter persona in localStorage when Recruiter SSO clicked', async () => {
    vi.useFakeTimers()
    renderLogin()
    fireEvent.click(screen.getByText(/Recruiter SSO/i))
    vi.runAllTimers()
    expect(localStorage.getItem('persona')).toBe('recruiter')
    vi.useRealTimers()
  })

  it('disables buttons while loading', () => {
    vi.useFakeTimers()
    renderLogin()
    const btn = screen.getByText(/Login with User Account/i)
    fireEvent.click(btn)
    // Status is 'loading' — buttons should be disabled until the timer fires
    expect(btn).toBeDisabled()
    vi.useRealTimers()
  })

  it('navigates to / after login completes', () => {
    vi.useFakeTimers()
    renderLogin()
    fireEvent.click(screen.getByText(/Manager SSO/i))
    vi.runAllTimers()
    expect(mockNavigate).toHaveBeenCalledWith('/')
    vi.useRealTimers()
  })
})
