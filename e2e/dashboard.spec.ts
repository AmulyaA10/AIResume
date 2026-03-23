import { test, expect, Page } from '@playwright/test'

async function loginAsManager(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByText('Manager SSO').click()
  await page.waitForURL('/', { timeout: 5000 })
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('shows main navigation sidebar', async ({ page }) => {
    // Sidebar should be visible after login
    await expect(page.locator('nav, aside').first()).toBeVisible()
  })

  test('dashboard page loads without crashing', async ({ page }) => {
    await page.goto('/')
    // No error boundary / crash page
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('Error:')
  })

  test('navigates to Settings page', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'System Configuration' })).toBeVisible({ timeout: 5000 })
  })

  test('Settings page shows OAuth section for manager', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('OAuth & System Config')).toBeVisible({ timeout: 5000 })
  })
})

test.describe('Dashboard — jobseeker role', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    // Jobseeker login (gmail redirects to OAuth, skip — use direct localStorage set)
    await page.evaluate(() => {
      localStorage.setItem('token', 'mock-token-123')
      localStorage.setItem('persona', 'jobseeker')
      localStorage.setItem('user', JSON.stringify({ name: 'Test User', email: 'test@example.com' }))
    })
    await page.goto('/')
  })

  test('Settings page does NOT show OAuth section for jobseeker', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.getByText('OAuth & System Config')).not.toBeVisible({ timeout: 3000 })
  })
})
