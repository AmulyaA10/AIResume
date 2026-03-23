import { test, expect, Page } from '@playwright/test'

async function loginAsManager(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByText('Manager SSO').click()
  await page.waitForURL('/', { timeout: 5000 })
}

test('search: candidates from greater los angeles metro area', async ({ page }) => {
  await loginAsManager(page)
  await page.goto('/resumes')
  await expect(page.locator('[data-testid="results-count"]')).toBeVisible({ timeout: 10000 })

  // Intercept the API response to see what the backend returns
  let apiResponse: any = null
  page.on('response', async resp => {
    if (resp.url().includes('/resumes/database') && resp.url().includes('search=')) {
      try { apiResponse = await resp.json() } catch {}
    }
  })

  const input = page.locator('[data-testid="resume-search-input"]')
  await input.fill('candidates from greater los angeles metro area')
  await page.waitForTimeout(2000)  // wait for debounce + API

  console.log('API total:', apiResponse?.total)
  const locs: string[] = (apiResponse?.resumes ?? []).map((r: any) => r.location).filter(Boolean)
  const locCounts: Record<string, number> = {}
  for (const l of locs) locCounts[l] = (locCounts[l] ?? 0) + 1
  console.log('Location breakdown:', JSON.stringify(locCounts, null, 2))

  const nonLA = locs.filter(l => {
    const lower = l.toLowerCase()
    return !lower.includes('los angeles') && !lower.includes(', ca')
  })
  console.log('Non-CA results:', nonLA.length)
})
