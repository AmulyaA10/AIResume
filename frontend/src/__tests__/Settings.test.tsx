import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Settings from '../features/settings/Settings'
import * as CredentialContextModule from '../context/CredentialContext'

// Mock api module to prevent real HTTP calls
vi.mock('../api', () => ({
  default: { defaults: { baseURL: 'http://localhost:8000/api/v1' } },
  systemApi: {
    getSettings: vi.fn().mockResolvedValue({ data: {} }),
    saveSettings: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

const mockCredentials = {
  credentials: { openRouterKey: '', linkedinUser: '', linkedinPass: '' },
  maskedCredentials: null,
  setCredential: vi.fn(),
  saveCredentials: vi.fn().mockResolvedValue(undefined),
  loadMaskedCredentials: vi.fn().mockResolvedValue(undefined),
  clearCredentials: vi.fn().mockResolvedValue(undefined),
  isLoaded: true,
  isLoading: false,
  loadError: false,
}

function renderSettings() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>
  )
}

describe('Settings page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(CredentialContextModule, 'useCredentials').mockReturnValue(mockCredentials)
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('renders AI Model Settings section', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByText('AI Model Settings')).toBeInTheDocument()
  })

  it('renders Data Sources section', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByText('Data Sources')).toBeInTheDocument()
  })

  it('renders security badge', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByText(/encrypted and stored server-side/i)).toBeInTheDocument()
  })

  it('does NOT show OAuth & System Config section for jobseeker', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.queryByText('OAuth & System Config')).not.toBeInTheDocument()
  })

  it('shows OAuth & System Config section for manager', () => {
    localStorage.setItem('persona', 'manager')
    renderSettings()
    expect(screen.getByText('OAuth & System Config')).toBeInTheDocument()
  })

  it('shows OAuth & System Config section for recruiter', () => {
    localStorage.setItem('persona', 'recruiter')
    renderSettings()
    expect(screen.getByText('OAuth & System Config')).toBeInTheDocument()
  })

  it('renders model selector with default value', () => {
    localStorage.setItem('persona', 'jobseeker')
    localStorage.setItem('llmModel', 'gpt-4o-mini')
    renderSettings()
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('gpt-4o-mini')
  })

  it('renders all LLM model options', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByText(/GPT-4o Mini/i)).toBeInTheDocument()
    expect(screen.getByText(/Claude 3 Haiku/i)).toBeInTheDocument()
    expect(screen.getByText(/Gemini Pro/i)).toBeInTheDocument()
  })

  it('shows OpenRouter API Key input', () => {
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByPlaceholderText(/sk-or-v1-/i)).toBeInTheDocument()
  })

  it('shows "Saved" badge when masked credentials exist', () => {
    vi.spyOn(CredentialContextModule, 'useCredentials').mockReturnValue({
      ...mockCredentials,
      maskedCredentials: {
        openRouterKey: 'sk-or-v1-***abc',
        linkedinUser: null,
        linkedinPass: null,
        has_openRouterKey: true,
        has_linkedinUser: false,
        has_linkedinPass: false,
      },
    })
    localStorage.setItem('persona', 'jobseeker')
    renderSettings()
    expect(screen.getByText(/Saved: sk-or-v1-\*\*\*abc/i)).toBeInTheDocument()
  })
})
