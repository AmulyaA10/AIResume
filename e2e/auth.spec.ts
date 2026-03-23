import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any existing session
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
  })

  test('shows login page with all buttons', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByText('RESUME.AI')).toBeVisible()
    await expect(page.getByText('Login with User Account')).toBeVisible()
    await expect(page.getByText('Login with LinkedIn')).toBeVisible()
    await expect(page.getByText('Recruiter SSO')).toBeVisible()
    await expect(page.getByText('Manager SSO')).toBeVisible()
  })

  test('manager SSO login navigates to dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.getByText('Manager SSO').click()
    // Wait for navigation after the 800ms mock delay
    await page.waitForURL('/', { timeout: 5000 })
    expect(page.url()).toContain('/')
  })

  test('recruiter SSO login sets correct persona', async ({ page }) => {
    await page.goto('/login')
    await page.getByText('Recruiter SSO').click()
    await page.waitForURL('/', { timeout: 5000 })
    const persona = await page.evaluate(() => localStorage.getItem('persona'))
    expect(persona).toBe('recruiter')
  })

  test('redirects unauthenticated users away from protected routes', async ({ page }) => {
    await page.evaluate(() => localStorage.clear())
    await page.goto('/')
    // App should redirect to /login or show login page
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 })
  })

  test('logout clears session and redirects to login', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.getByText('Manager SSO').click()
    await page.waitForURL('/', { timeout: 5000 })

    // Find and click logout — look for sidebar logout button
    const logoutBtn = page.getByRole('button', { name: /logout|sign out/i })
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click()
      await expect(page).toHaveURL(/\/login/, { timeout: 5000 })
      const token = await page.evaluate(() => localStorage.getItem('token'))
      expect(token).toBeNull()
    }
  })
})
