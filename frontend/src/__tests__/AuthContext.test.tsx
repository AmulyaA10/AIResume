import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from '../context/AuthContext'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => mockNavigate }
})

const TestConsumer = () => {
  const { isAuthenticated, persona, user } = useAuth()
  return (
    <div>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="persona">{persona ?? 'null'}</span>
      <span data-testid="user">{user?.name ?? 'null'}</span>
    </div>
  )
}

function renderWithAuth(initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('starts unauthenticated with no stored session', () => {
    renderWithAuth()
    expect(screen.getByTestId('auth').textContent).toBe('no')
    expect(screen.getByTestId('persona').textContent).toBe('null')
  })

  it('restores session from localStorage on mount', () => {
    localStorage.setItem('token', 'mock-manager-token')
    localStorage.setItem('persona', 'manager')
    localStorage.setItem('user', JSON.stringify({ name: 'Hiring Lead', email: 'lead@company.com' }))
    renderWithAuth()
    expect(screen.getByTestId('auth').textContent).toBe('yes')
    expect(screen.getByTestId('persona').textContent).toBe('manager')
    expect(screen.getByTestId('user').textContent).toBe('Hiring Lead')
  })

  it('does not restore session if token is missing', () => {
    localStorage.setItem('persona', 'manager')
    localStorage.setItem('user', JSON.stringify({ name: 'Hiring Lead', email: 'lead@company.com' }))
    renderWithAuth()
    expect(screen.getByTestId('auth').textContent).toBe('no')
  })

  it('login sets manager persona for manager method', () => {
    const LoginBtn = () => {
      const { login, isAuthenticated, persona } = useAuth()
      return (
        <>
          <button onClick={() => login('manager')}>login</button>
          <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
          <span data-testid="persona">{persona ?? 'null'}</span>
        </>
      )
    }
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginBtn />
        </AuthProvider>
      </MemoryRouter>
    )
    act(() => {
      screen.getByText('login').click()
    })
    expect(screen.getByTestId('auth').textContent).toBe('yes')
    expect(screen.getByTestId('persona').textContent).toBe('manager')
    expect(localStorage.getItem('persona')).toBe('manager')
  })

  it('login sets recruiter persona for corporate method', () => {
    const LoginBtn = () => {
      const { login, persona } = useAuth()
      return (
        <>
          <button onClick={() => login('corporate')}>login</button>
          <span data-testid="persona">{persona ?? 'null'}</span>
        </>
      )
    }
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginBtn />
        </AuthProvider>
      </MemoryRouter>
    )
    act(() => { screen.getByText('login').click() })
    expect(screen.getByTestId('persona').textContent).toBe('recruiter')
  })

  it('logout clears state and localStorage', () => {
    localStorage.setItem('token', 'mock-manager-token')
    localStorage.setItem('persona', 'manager')
    localStorage.setItem('user', JSON.stringify({ name: 'Hiring Lead', email: 'lead@company.com' }))

    const LogoutBtn = () => {
      const { logout, isAuthenticated } = useAuth()
      return (
        <>
          <button onClick={logout}>logout</button>
          <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
        </>
      )
    }
    render(
      <MemoryRouter>
        <AuthProvider>
          <LogoutBtn />
        </AuthProvider>
      </MemoryRouter>
    )
    act(() => { screen.getByText('logout').click() })
    expect(screen.getByTestId('auth').textContent).toBe('no')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('persona')).toBeNull()
  })

  it('useAuth throws outside AuthProvider', () => {
    const Bad = () => { useAuth(); return null }
    // suppress console.error from React
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<MemoryRouter><Bad /></MemoryRouter>)).toThrow(
      'useAuth must be used within an AuthProvider'
    )
    spy.mockRestore()
  })
})
