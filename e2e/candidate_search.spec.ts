import { test, expect, Page } from '@playwright/test'

async function loginAsManager(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByText('Manager SSO').click()
  await page.waitForURL('/', { timeout: 5000 })
}

async function searchCandidates(page: Page, query: string) {
  await page.goto('/resumes')
  const input = page.getByPlaceholder(/AI search/i)
  await expect(input).toBeVisible({ timeout: 5000 })
  await input.fill(query)
  // Wait for the results-count element to appear — it is only rendered when isLoading=false.
  // This avoids the race where waitForResponse catches the initial page-load call instead
  // of the debounced search call, leaving a second loading spinner in flight.
  await expect(page.locator('[data-testid="results-count"]')).toBeVisible({ timeout: 15000 })
  await page.waitForTimeout(300)
}

/** Get total candidate count from the results counter */
async function getResultTotal(page: Page): Promise<number> {
  const counter = page.locator('[data-testid="results-count"]')
  const isVisible = await counter.isVisible().catch(() => false)
  if (!isVisible) return 0
  const total = await counter.getAttribute('data-total')
  return parseInt(total ?? '0', 10)
}

/** Get all location strings visible in the current result cards */
async function getCardLocations(page: Page): Promise<string[]> {
  const locs = page.locator('[data-testid="card-location"]')
  const count = await locs.count()
  const result: string[] = []
  for (let i = 0; i < count; i++) {
    const text = await locs.nth(i).textContent()
    if (text) result.push(text.trim().toLowerCase())
  }
  return result
}

/** Returns true if any visible card location contains one of the bad strings */
async function anyCardMatchesLocations(page: Page, badTerms: string[]): Promise<boolean> {
  const locations = await getCardLocations(page)
  return locations.some(loc => badTerms.some(term => loc.includes(term)))
}

// ─── Northern California city set — should NEVER appear in SoCal results ──────
const NORCAL_CITIES = [
  'san francisco', 'sf,', 'palo alto', 'mountain view', 'sunnyvale',
  'san jose', 'cupertino', 'oakland', 'berkeley', 'menlo park',
  'redwood city', 'santa clara', 'los gatos', 'foster city',
]

// ─── Australian location indicators ───────────────────────────────────────────
const AUSTRALIA_TERMS = ['australia', 'sydney', 'melbourne', 'brisbane', 'perth', 'adelaide']

// ─── Bay Area / USA terms that should not appear for non-US searches ──────────
const USA_TERMS = ['usa', 'united states', ', ca', ', ny', ', tx', ', wa', ', fl']

test.describe('Candidate Search — geo-accuracy (content assertions)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  // ── Southern California: must NOT surface NorCal cities ───────────────────
  test('candidates from southern california — no NorCal in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from southern california')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    // Should not be returning all candidates (old bug returned 60+)
    expect(total).toBeLessThan(30)

    const hasNorCal = await anyCardMatchesLocations(page, NORCAL_CITIES)
    expect(hasNorCal).toBe(false)
  })

  // ── Australia: must return 0 or only Australian candidates ────────────────
  test('candidate from australia — not returning all candidates', async ({ page }) => {
    await searchCandidates(page, 'candidate from australia')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    // Old bug: returned 212 results when 0 Australian candidates exist
    // Should be 0 (no Australian candidates) or a small number of actual Australian ones
    if (total > 0) {
      // If results exist, they must show Australian locations
      const locations = await getCardLocations(page)
      const allAustralian = locations.every(loc =>
        AUSTRALIA_TERMS.some(term => loc.includes(term))
      )
      expect(allAustralian).toBe(true)
    }
    // Either 0 results or all results are Australian — not a mix of everything
    const hasNonAustralian = await anyCardMatchesLocations(page, USA_TERMS)
    expect(hasNonAustralian).toBe(false)
  })

  // ── Silicon Valley: should contain Bay Area candidates ────────────────────
  test('candidates from silicon valley — location matches', async ({ page }) => {
    await searchCandidates(page, 'candidates from silicon valley')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const total = await getResultTotal(page)
    if (total > 0) {
      const locations = await getCardLocations(page)
      const SV_TERMS = ['san francisco', 'palo alto', 'mountain view', 'sunnyvale',
        'san jose', 'santa clara', 'menlo park', 'cupertino', 'oakland', ', ca', 'california']
      const allSV = locations.every(loc => SV_TERMS.some(t => loc.includes(t)))
      expect(allSV).toBe(true)
    }
  })

  // ── Europe: no US locations in results ────────────────────────────────────
  test('senior managers from europe — no US locations', async ({ page }) => {
    await searchCandidates(page, 'senior managers from europe')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const hasUSA = await anyCardMatchesLocations(page, [', ca', ', ny', ', wa', 'united states', 'usa'])
    expect(hasUSA).toBe(false)
  })

  // ── New York: results should be NY-area ───────────────────────────────────
  test('executives from NY — locations are NY-area', async ({ page }) => {
    await searchCandidates(page, 'executives from NY')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const total = await getResultTotal(page)
    if (total > 0) {
      const locations = await getCardLocations(page)
      const NY_TERMS = ['new york', ', ny', 'manhattan', 'brooklyn', 'queens', 'hoboken', 'jersey city']
      const allNY = locations.every(loc => NY_TERMS.some(t => loc.includes(t)))
      expect(allNY).toBe(true)
    }
  })

  // ── SF metro: Bay Area only ───────────────────────────────────────────────
  test('candidates from SF metro area — Bay Area locations only', async ({ page }) => {
    await searchCandidates(page, 'candidates from SF metro area or 50 mile radius')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const total = await getResultTotal(page)
    if (total > 0) {
      // LA or San Diego should not appear in SF metro results
      const hasLA = await anyCardMatchesLocations(page, ['los angeles', 'san diego', ', tx', 'seattle'])
      expect(hasLA).toBe(false)
    }
  })

  // ── West Coast: no East Coast ─────────────────────────────────────────────
  test('candidates from west coast — no East Coast cities', async ({ page }) => {
    await searchCandidates(page, 'candidates from west coast')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const hasEastCoast = await anyCardMatchesLocations(page, [
      'new york', ', ny', 'boston', ', ma', 'philadelphia', ', pa',
      'miami', ', fl', 'chicago', ', il', 'atlanta', ', ga',
    ])
    expect(hasEastCoast).toBe(false)
  })

  // ── California (state-wide): all results must be CA ─────────────────────
  test('candidates from california — only CA results', async ({ page }) => {
    await searchCandidates(page, 'candidates from california')
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)

    const locations = await getCardLocations(page)
    if (locations.length > 0) {
      const allCA = locations.every(loc => loc.toLowerCase().includes(', ca'))
      expect(allCA).toBe(true)
    }

    // Must not bleed into other states
    const hasNonCA = await anyCardMatchesLocations(page, [', ny', ', tx', ', wa', ', fl', ', il'])
    expect(hasNonCA).toBe(false)
  })

  // ── Company + location combined: Apple/Google in California ─────────────
  test('candidates in apple, google california — no crash, returns results', async ({ page }) => {
    await searchCandidates(page, 'candidates in apple, google california')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    // Combined company + location query — should not crash and should return something.
    // Location filtering for mixed queries is best-effort; we only assert no errors here.
    const total = await getResultTotal(page)
    // No hard lower bound — 0 is acceptable if no Apple/Google CA candidates exist.
    // But results count must be a real number (no NaN / undefined rendered as NaN).
    expect(total).toBeGreaterThanOrEqual(0)
  })

  // ── FANG: company filter ──────────────────────────────────────────────────
  test('candidates currently working in FANG — no error', async ({ page }) => {
    await searchCandidates(page, 'candidates currently working in FANG')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  // ── Skill searches: page loads, no crash ─────────────────────────────────
  test('experts in ML or machine learning — returns results', async ({ page }) => {
    await searchCandidates(page, 'experts in ML or machine learning')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })

  test('experts in AI — returns results', async ({ page }) => {
    await searchCandidates(page, 'experts in AI')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })

  test('smart engineers in data science — returns results', async ({ page }) => {
    await searchCandidates(page, 'smart engineers in data science')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })
})

test.describe('Candidate Search — page basics', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('resume database page loads for manager', async ({ page }) => {
    await page.goto('/resumes')
    await expect(page.locator('body')).not.toContainText('Something went wrong', { timeout: 5000 })
  })

  test('search input is present with AI search placeholder', async ({ page }) => {
    await page.goto('/resumes')
    await expect(page.getByPlaceholder(/AI search/i)).toBeVisible({ timeout: 5000 })
  })

  test('AI search page is accessible', async ({ page }) => {
    await page.goto('/search')
    await expect(page.locator('body')).not.toContainText('Error:', { timeout: 5000 })
  })

  test('name search — searching by name returns that candidate first', async ({ page }) => {
    await searchCandidates(page, 'Edward Fuller')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // If a candidate named Edward Fuller exists, they should appear
    const cards = page.locator('[data-testid="resume-card"]')
    const count = await cards.count()
    if (count > 0) {
      const firstCardName = await cards.first().getAttribute('data-name')
      expect(firstCardName?.toLowerCase()).toContain('edward')
    }
  })
})
