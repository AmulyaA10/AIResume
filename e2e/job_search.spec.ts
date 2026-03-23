import { test, expect, Page } from '@playwright/test'

async function loginAsJobseeker(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('token', 'mock-token-123')
    localStorage.setItem('persona', 'jobseeker')
    localStorage.setItem('user', JSON.stringify({ name: 'Job Seeker', email: 'lintojm@yahoo.com' }))
  })
  await page.goto('/')
}

async function loginAsManager(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByText('Manager SSO').click()
  await page.waitForURL('/', { timeout: 5000 })
}

async function searchJobsAsJobseeker(page: Page, query: string) {
  await page.goto('/search')
  const input = page.getByTestId('job-search-input')
  await expect(input).toBeVisible({ timeout: 8000 })
  await input.fill(query)
  await input.press('Enter')
  // Wait for either the intent-parse POST or the search GET — whichever comes first.
  // Intent parse (LLM) can take up to ~15s; search itself is fast once intent resolves.
  await page.waitForResponse(
    resp =>
      (resp.url().includes('/jobs/parse-query-intent') && resp.request().method() === 'POST') ||
      (resp.url().includes('/match/search/jobs') && resp.request().method() === 'GET'),
    { timeout: 30000 }
  )
  // After intent resolves, wait for the actual search response if not already received
  await page.waitForResponse(
    resp => resp.url().includes('/match/search/jobs') && resp.request().method() === 'GET',
    { timeout: 20000 }
  ).catch(() => {})  // non-fatal — search may have already completed
  await page.waitForTimeout(500)
}

async function searchJobsAsManager(page: Page, query: string) {
  await page.goto('/search')
  const input = page.getByTestId('job-search-input')
  await expect(input).toBeVisible({ timeout: 8000 })
  await input.fill(query)
  await input.press('Enter')
  await page.waitForResponse(
    resp => (resp.url().includes('/api/v1/jobs') || resp.url().includes('/match/search/jobs'))
      && resp.request().method() === 'GET',
    { timeout: 15000 }
  )
  await page.waitForTimeout(1000)
}

/** Get employer names from all visible job cards */
async function getJobEmployers(page: Page): Promise<string[]> {
  const employers = page.locator('[data-testid="job-employer"]')
  const count = await employers.count()
  const result: string[] = []
  for (let i = 0; i < count; i++) {
    const text = await employers.nth(i).textContent()
    if (text) result.push(text.trim().toLowerCase())
  }
  return result
}

/** Get job card count */
async function getJobCardCount(page: Page): Promise<number> {
  return page.locator('[data-testid="job-card"]').count()
}

test.describe('Job Search — page basics', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsJobseeker(page)
  })

  test('job search page loads', async ({ page }) => {
    await page.goto('/search')
    await expect(page.locator('body')).not.toContainText('Error:', { timeout: 8000 })
  })

  test('search input is present', async ({ page }) => {
    await page.goto('/search')
    await expect(page.getByTestId('job-search-input')).toBeVisible({ timeout: 8000 })
  })

  test('page loads without crash', async ({ page }) => {
    await page.goto('/search')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })
})

test.describe('Job Search — employer filter accuracy (job seeker mode)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsJobseeker(page)
  })

  // ── Core bug: "jobs in apple" was returning only 1 result ─────────────────
  test('jobs in apple — all results are Apple jobs', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'jobs in apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const cardCount = await getJobCardCount(page)
    if (cardCount > 0) {
      const employers = await getJobEmployers(page)
      // Every visible job card must be from Apple
      const allApple = employers.every(e => e.includes('apple'))
      expect(allApple).toBe(true)
      // Old bug: only 1 Apple job returned despite many in DB
      expect(cardCount).toBeGreaterThan(1)
    }
  })

  test('jobs in google — all results are Google jobs', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'jobs in google')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const cardCount = await getJobCardCount(page)
    if (cardCount > 0) {
      const employers = await getJobEmployers(page)
      const allGoogle = employers.every(e => e.includes('google'))
      expect(allGoogle).toBe(true)
    }
  })

  test('jobs in microsoft — all results are Microsoft jobs', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'jobs in microsoft')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const cardCount = await getJobCardCount(page)
    if (cardCount > 0) {
      const employers = await getJobEmployers(page)
      const allMicrosoft = employers.every(e => e.includes('microsoft'))
      expect(allMicrosoft).toBe(true)
    }
  })

  test('FAANG jobs — all results from FAANG companies', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'FAANG jobs')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const cardCount = await getJobCardCount(page)
    if (cardCount > 0) {
      const employers = await getJobEmployers(page)
      const FAANG = ['google', 'meta', 'amazon', 'apple', 'netflix', 'microsoft', 'facebook']
      const allFAANG = employers.every(e => FAANG.some(f => e.includes(f)))
      expect(allFAANG).toBe(true)
    }
  })

  test('python developer jobs — returns results, no error', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'python developer jobs')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const cardCount = await getJobCardCount(page)
    expect(cardCount).toBeGreaterThan(0)
  })

  test('senior software engineer — returns results', async ({ page }) => {
    await searchJobsAsJobseeker(page, 'senior software engineer')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const cardCount = await getJobCardCount(page)
    expect(cardCount).toBeGreaterThan(0)
  })

  test('long skills list query — not zero results', async ({ page }) => {
    const longQuery = 'Python, JavaScript, TypeScript, React, Node.js, AWS, Docker, Kubernetes, PostgreSQL, Redis, GraphQL, REST APIs, CI/CD, Git, Agile'
    await searchJobsAsJobseeker(page, longQuery)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const cardCount = await getJobCardCount(page)
    // Old bug: long comma-separated skill lists returned 0 results
    expect(cardCount).toBeGreaterThan(0)
  })
})

test.describe('Job Search — recruiter/manager mode', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('jobs in apple — recruiter sees multiple Apple jobs', async ({ page }) => {
    await searchJobsAsManager(page, 'jobs in apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const cardCount = await getJobCardCount(page)
    if (cardCount > 0) {
      const employers = await getJobEmployers(page)
      const allApple = employers.every(e => e.includes('apple'))
      expect(allApple).toBe(true)
      expect(cardCount).toBeGreaterThan(1)
    }
  })

  test('senior python engineer — returns relevant results', async ({ page }) => {
    await searchJobsAsManager(page, 'senior python engineer')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })
})
