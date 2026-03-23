import { test, expect, Page } from '@playwright/test'

async function loginAs(page: Page, persona: 'manager' | 'recruiter' | 'jobseeker') {
  await page.goto('/login')
  await page.evaluate((p) => {
    localStorage.clear()
    if (p === 'manager') {
      localStorage.setItem('token', 'mock-manager-token')
      localStorage.setItem('persona', 'manager')
      localStorage.setItem('user', JSON.stringify({ name: 'Hiring Lead', email: 'lead@company.com' }))
    } else if (p === 'recruiter') {
      localStorage.setItem('token', 'mock-recruiter-token')
      localStorage.setItem('persona', 'recruiter')
      localStorage.setItem('user', JSON.stringify({ name: 'Recruiter Pro', email: 'admin@company.com' }))
    } else {
      localStorage.setItem('token', 'mock-token-123')
      localStorage.setItem('persona', 'jobseeker')
      localStorage.setItem('user', JSON.stringify({ name: 'Test User', email: 'test@example.com' }))
    }
  }, persona)
  await page.goto('/settings')
}

test.describe('Settings — role-based visibility', () => {
  test('manager sees OAuth & System Config section', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByText('OAuth & System Config')).toBeVisible({ timeout: 5000 })
  })

  test('recruiter is redirected away from settings', async ({ page }) => {
    await loginAs(page, 'recruiter')
    await expect(page).not.toHaveURL('/settings', { timeout: 5000 })
  })

  test('jobseeker is redirected away from settings', async ({ page }) => {
    await loginAs(page, 'jobseeker')
    await expect(page).not.toHaveURL('/settings', { timeout: 5000 })
  })

  test('AI Model Settings visible to manager', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByText('AI Model Settings')).toBeVisible({ timeout: 5000 })
  })

  test('Data Sources section visible to manager', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByText('Data Sources')).toBeVisible({ timeout: 5000 })
  })

  test('security badge is visible to manager', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByText(/encrypted and stored server-side/i)).toBeVisible({ timeout: 5000 })
  })

  test('model selector shows LLM options', async ({ page }) => {
    await loginAs(page, 'manager')
    const modelSelect = page.getByRole('combobox').first()
    await expect(modelSelect).toBeVisible({ timeout: 5000 })
    await expect(modelSelect).toContainText(/GPT-4o Mini/i)
  })

  test('Save Configuration button is present', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByRole('button', { name: /save/i })).toBeVisible({ timeout: 5000 })
  })

  test('Google Client ID input visible for manager', async ({ page }) => {
    await loginAs(page, 'manager')
    await expect(page.getByPlaceholder(/169779074152-/i)).toBeVisible({ timeout: 5000 })
  })
})
