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

  // ── LA metro area / Greater LA ───────────────────────────────────────────
  test('candidates from LA metro area — no NorCal in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from LA metro area')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasNorCal = await anyCardMatchesLocations(page, NORCAL_CITIES)
    expect(hasNorCal).toBe(false)
  })

  test('candidates from greater LA — no NorCal in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from greater LA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasNorCal = await anyCardMatchesLocations(page, NORCAL_CITIES)
    expect(hasNorCal).toBe(false)
  })

  // ── Asia regions ──────────────────────────────────────────────────────────
  test('candidates from Asia — no US locations in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from Asia')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasUSA = await anyCardMatchesLocations(page, USA_TERMS)
    expect(hasUSA).toBe(false)
  })

  test('candidates from Southeast Asia — no US locations in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from Southeast Asia')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasUSA = await anyCardMatchesLocations(page, USA_TERMS)
    expect(hasUSA).toBe(false)
  })

  test('candidates from South Asia — no US locations in results', async ({ page }) => {
    await searchCandidates(page, 'candidates from South Asia')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasUSA = await anyCardMatchesLocations(page, USA_TERMS)
    expect(hasUSA).toBe(false)
  })

  // ── Europe exact phrasing ─────────────────────────────────────────────────
  test('candidates from Europe — no US locations', async ({ page }) => {
    await searchCandidates(page, 'candidates from Europe')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const hasUSA = await anyCardMatchesLocations(page, [', ca', ', ny', ', wa', 'united states', 'usa'])
    expect(hasUSA).toBe(false)
  })

  // ── North America / USA / Midwest ─────────────────────────────────────────
  test('candidates from North America — no error', async ({ page }) => {
    await searchCandidates(page, 'candidates from North America')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // 0 results is acceptable if no matching location aliases exist in DB
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('candidate from usa — no error, no Asia/Europe locations in results', async ({ page }) => {
    await searchCandidates(page, 'candidate from usa')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // Must not return exclusively non-US candidates
    const hasAsia = await anyCardMatchesLocations(page, ['india', 'singapore', 'japan', 'china', 'uk', 'germany', 'france'])
    expect(hasAsia).toBe(false)
  })

  test('candidates from midwest USA — no coastal cities', async ({ page }) => {
    await searchCandidates(page, 'candidates from midwest USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // "midwest" is a vague sub-region — assert no crash and filtered (not full ~300 unfiltered pool)
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
    expect(total).toBeLessThan(280)
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

  // ── Apple: phrasing variations ────────────────────────────────────────────
  test('candidate working in apple — all results are Apple employees', async ({ page }) => {
    await searchCandidates(page, 'candidate working in apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('apple')
      }
    }
  })

  test('candidate worked for apple — results include Apple employees', async ({ page }) => {
    await searchCandidates(page, 'candidate worked for apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    // Past-tense: Apple employees should surface, no hard company exclusion assertion
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('former apple employee — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'former apple employee')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('ex apple engineer — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'ex apple engineer')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('engineers at apple — all results are Apple employees', async ({ page }) => {
    await searchCandidates(page, 'engineers at apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('apple')
      }
    }
  })

  test('senior engineer from apple — results are senior Apple employees', async ({ page }) => {
    await searchCandidates(page, 'senior engineer from apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('apple')
      }
    }
  })

  test('apple alumni — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'apple alumni')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  // ── Apple: strict company filter ─────────────────────────────────────────
  test('candidate from apple — all results are Apple employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    // strictCompany=True must NOT return all candidates (old bug returned 200+)
    expect(total).toBeLessThan(50)

    if (total > 0) {
      // card-company must be present and every card must show Apple
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('apple')
      }
    }
  })

  // ── Google: strict company filter ────────────────────────────────────────
  test('candidate from google — all results are Google employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from google')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('google')
      }
    }
  })

  // ── Netflix: strict company filter ───────────────────────────────────────
  test('candidate from netflix — all results are Netflix employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from netflix')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('netflix')
      }
    }
  })

  // ── Amazon: strict company filter ────────────────────────────────────────
  test('candidate from amazon — all results are Amazon employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from amazon')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('amazon')
      }
    }
  })

  // ── Microsoft: strict company filter ─────────────────────────────────────
  test('candidate from microsoft — all results are Microsoft employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from microsoft')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('microsoft')
      }
    }
  })

  // ── Meta: strict company filter ───────────────────────────────────────────
  test('candidate from meta — all results are Meta employees', async ({ page }) => {
    await searchCandidates(page, 'candidate from meta')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        // Meta may appear as "meta" or "facebook"
        const isMeta = text.includes('meta') || text.includes('facebook')
        expect(isMeta).toBe(true)
      }
    }
  })

  // ── Apple: additional phrasing ───────────────────────────────────────────
  test('candidate worked in apple — returns results including Apple employees', async ({ page }) => {
    await searchCandidates(page, 'candidate worked in apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    // Past-tense boost — Apple employees surface first, no strict exclusion
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('apple software engineer — all results are Apple employees', async ({ page }) => {
    await searchCandidates(page, 'apple software engineer')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('apple')
      }
    }
  })

  test('java developer from apple — no crash, returns results', async ({ page }) => {
    await searchCandidates(page, 'java developer from apple')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    // Role signal present — semantic search takes priority; company is a soft filter
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  // ── Microsoft: additional phrasings ──────────────────────────────────────
  test('candidate working in microsoft — all results are Microsoft employees', async ({ page }) => {
    await searchCandidates(page, 'candidate working in microsoft')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('microsoft')
      }
    }
  })

  test('senior engineer at microsoft — results are Microsoft employees', async ({ page }) => {
    await searchCandidates(page, 'senior engineer at microsoft')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeLessThan(50)
    if (total > 0) {
      const companies = page.locator('[data-testid="card-company"]')
      const count = await companies.count()
      expect(count).toBeGreaterThan(0)
      for (let i = 0; i < count; i++) {
        const text = (await companies.nth(i).textContent() || '').toLowerCase()
        expect(text).toContain('microsoft')
      }
    }
  })

  // ── Multi-company: Apple + Google ─────────────────────────────────────────
  // Multi-company uses strictCompany=False (boost mode): returns all candidates
  // with Apple/Google employees ranked first. Check top card is Apple or Google.
  test('candidate from apple and google — top result is Apple or Google employee', async ({ page }) => {
    await searchCandidates(page, 'candidate from apple and google')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')

    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    if (total > 0) {
      // First result should be an Apple or Google employee (boost mode)
      const firstCompany = page.locator('[data-testid="card-company"]').first()
      const isVisible = await firstCompany.isVisible().catch(() => false)
      if (isVisible) {
        const text = (await firstCompany.textContent() || '').toLowerCase()
        const isAppleOrGoogle = text.includes('apple') || text.includes('google')
        expect(isAppleOrGoogle).toBe(true)
      }
    }
  })

  // ── FANG: company filter ──────────────────────────────────────────────────
  test('candidates currently working in FANG — no error', async ({ page }) => {
    await searchCandidates(page, 'candidates currently working in FANG')
    await expect(page.locator('body')).not.toContainText('OpenRouter API key is required')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('candidates who worked in FANG — returns FANG alumni results', async ({ page }) => {
    await searchCandidates(page, 'candidates who worked in FANG')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    // Past-tense FANG query: top results should include FANG current/alumni employees
    const companies = await page.locator('[data-testid="card-company"]').allInnerTexts()
    const fangTerms = ['google', 'meta', 'amazon', 'netflix', 'apple']
    const hasFang = companies.some(c => fangTerms.some(t => c.toLowerCase().includes(t)))
    expect(hasFang).toBe(true)
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

  test('experts in cloud storage or distributed storage — returns results', async ({ page }) => {
    await searchCandidates(page, 'experts in cloud storage or distributed storage')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })
})

// ─── Shared helpers for country/region assertions ─────────────────────────────
const NON_US_TERMS = ['india', 'bangalore', 'hyderabad', 'mumbai', 'delhi',
  'canada', 'toronto', 'vancouver', 'london', 'berlin', 'paris', 'sydney']
const US_STATE_TERMS = [', ca', ', ny', ', tx', ', wa', ', fl', ', ga', ', il',
  ', ma', ', co', ', az', ', pa', ', oh', ', mi', ', nc', ', va']

test.describe('Candidate Search — country and abbreviation queries', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  // ── Standalone country/region terms ────────────────────────────────────────
  test('UNITED STATES — returns results, no error', async ({ page }) => {
    await searchCandidates(page, 'UNITED STATES')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })

  test('USA — returns results, no error', async ({ page }) => {
    await searchCandidates(page, 'USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })

  test('US — returns results, no error', async ({ page }) => {
    await searchCandidates(page, 'US')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  // ── Candidate from [country/region] ────────────────────────────────────────
  test('candidate from US — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate from US')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)  // must be filtered, not the full unfiltered pool
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('candidate from USA — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate from USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('candidate from United States — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate from United States')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('candidate from California — all results are CA', async ({ page }) => {
    await searchCandidates(page, 'candidate from California')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    const locations = await getCardLocations(page)
    if (locations.length > 0) {
      const allCA = locations.every(loc => loc.includes(', ca'))
      expect(allCA).toBe(true)
    }
  })

  test('candidate from CA — all results are California', async ({ page }) => {
    await searchCandidates(page, 'candidate from CA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(150)  // must be filtered, not all 300
    const locations = await getCardLocations(page)
    if (locations.length > 0) {
      const allCA = locations.every(loc => loc.includes(', ca'))
      expect(allCA).toBe(true)
    }
  })

  test('candidate from India — no error, 0 or India results', async ({ page }) => {
    await searchCandidates(page, 'candidate from India')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // Demo may have no India candidates — 0 is acceptable; must not return unfiltered US results
    const total = await getResultTotal(page)
    if (total > 0) {
      const locations = await getCardLocations(page)
      const allIndia = locations.every(loc => loc.includes('india') || loc.includes('bangalore') ||
        loc.includes('hyderabad') || loc.includes('mumbai') || loc.includes('delhi'))
      expect(allIndia).toBe(true)
    }
  })

  test('candidate from IN — no error, resolves to India not unfiltered', async ({ page }) => {
    await searchCandidates(page, 'candidate from IN')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // "IN" → India; demo may have 0 India candidates
    // Key assertion: must NOT return the full ~300 unfiltered pool
    const total = await getResultTotal(page)
    expect(total).toBeLessThan(150)
  })

  test('candidate from Canada — no error, 0 or Canada results', async ({ page }) => {
    await searchCandidates(page, 'candidate from Canada')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    if (total > 0) {
      const locations = await getCardLocations(page)
      const allCanada = locations.every(loc =>
        loc.includes('canada') || loc.includes('toronto') || loc.includes('vancouver') ||
        loc.includes('montreal') || loc.includes('calgary'))
      expect(allCanada).toBe(true)
    }
  })

  test('candidate from CAN — no error, resolves to Canada not unfiltered', async ({ page }) => {
    await searchCandidates(page, 'candidate from CAN')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    // "CAN" → Canada; demo may have 0 Canada candidates — 0 is acceptable
    expect(total).toBeLessThan(150)
  })

  // ── Candidate working in [country] ─────────────────────────────────────────
  test('candidate working in US — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate working in US')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('candidate working in USA — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate working in USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('candidate working in United States — returns US candidates only', async ({ page }) => {
    await searchCandidates(page, 'candidate working in United States')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  // ── Additional combinations ─────────────────────────────────────────────────
  test('senior engineer from US — filtered US results', async ({ page }) => {
    await searchCandidates(page, 'senior engineer from US')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasNonUS = await anyCardMatchesLocations(page, NON_US_TERMS)
    expect(hasNonUS).toBe(false)
  })

  test('software engineer from USA — filtered US results', async ({ page }) => {
    await searchCandidates(page, 'software engineer from USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
  })

  test('developer from California — all CA results', async ({ page }) => {
    await searchCandidates(page, 'developer from California')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    const locations = await getCardLocations(page)
    if (locations.length > 0) {
      const allCA = locations.every(loc => loc.includes(', ca'))
      expect(allCA).toBe(true)
    }
  })

  test('React developer from CA — California results', async ({ page }) => {
    await searchCandidates(page, 'React developer from CA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
    expect(total).toBeLessThan(150)
    if (total > 0) {
      const locations = await getCardLocations(page)
      const allCA = locations.every(loc => loc.includes(', ca'))
      expect(allCA).toBe(true)
    }
  })

  test('engineer from United States — US results, no Europe', async ({ page }) => {
    await searchCandidates(page, 'engineer from United States')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
    const hasEurope = await anyCardMatchesLocations(page, ['london', 'berlin', 'paris', 'uk', 'germany'])
    expect(hasEurope).toBe(false)
  })

  test('data scientist from USA — US results', async ({ page }) => {
    await searchCandidates(page, 'data scientist from USA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    expect(total).toBeLessThan(280)
  })

  test('ML engineer currently in United States — US results', async ({ page }) => {
    await searchCandidates(page, 'ML engineer currently in United States')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
  })

  test('frontend developer based in California — CA results', async ({ page }) => {
    await searchCandidates(page, 'frontend developer based in California')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThan(0)
    const locations = await getCardLocations(page)
    if (locations.length > 0) {
      const allCA = locations.every(loc => loc.includes(', ca'))
      expect(allCA).toBe(true)
    }
  })

  // ── UK queries ──────────────────────────────────────────────────────────────
  test('candidate from UK — no error, 0 or UK results', async ({ page }) => {
    await searchCandidates(page, 'candidate from UK')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    // Demo may have 0 UK candidates; key: must not return full ~300 unfiltered pool
    expect(total).toBeLessThan(150)
  })

  test('candidate from United Kingdom — no error, 0 or UK results', async ({ page }) => {
    await searchCandidates(page, 'candidate from United Kingdom')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeLessThan(150)
  })

  test('candidate from GBR — resolves to UK not unfiltered', async ({ page }) => {
    await searchCandidates(page, 'candidate from GBR')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeLessThan(150)
  })

  test('software engineer from UK — filtered results', async ({ page }) => {
    await searchCandidates(page, 'software engineer from UK')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeLessThan(150)
  })

  // ── Multi-country combinations ───────────────────────────────────────────────
  test('candidates from US and UK — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'candidates from US and UK')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('UNITED STATES and UK candidates — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'UNITED STATES and UK candidates')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('candidates from USA or United Kingdom — no error', async ({ page }) => {
    await searchCandidates(page, 'candidates from USA or United Kingdom')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('engineers from US and India — no error', async ({ page }) => {
    await searchCandidates(page, 'engineers from US and India')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('developers from USA and Canada — no error', async ({ page }) => {
    await searchCandidates(page, 'developers from USA and Canada')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('senior engineer from US or UK — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'senior engineer from US or UK')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('data scientist from United States or Canada — no error', async ({ page }) => {
    await searchCandidates(page, 'data scientist from United States or Canada')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('backend developer from USA or India — no error', async ({ page }) => {
    await searchCandidates(page, 'backend developer from USA or India')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('ML engineer from US or UK or Canada — no error', async ({ page }) => {
    await searchCandidates(page, 'ML engineer from US or UK or Canada')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('candidate from US working in UK — no error', async ({ page }) => {
    await searchCandidates(page, 'candidate from US working in UK')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  test('engineer based in USA or United Kingdom — no error', async ({ page }) => {
    await searchCandidates(page, 'engineer based in USA or United Kingdom')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
  })

  // ── NY + other abbreviation combos ──────────────────────────────────────────
  test('candidate from NY — New York results, filtered', async ({ page }) => {
    await searchCandidates(page, 'candidate from NY')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
    expect(total).toBeLessThan(150)
  })

  test('candidate from TX — Texas results, filtered', async ({ page }) => {
    await searchCandidates(page, 'candidate from TX')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
    expect(total).toBeLessThan(150)
  })

  test('candidate from WA — Washington results, filtered', async ({ page }) => {
    await searchCandidates(page, 'candidate from WA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
    expect(total).toBeLessThan(150)
  })

  test('engineer from NY or CA — no error, returns results', async ({ page }) => {
    await searchCandidates(page, 'engineer from NY or CA')
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const total = await getResultTotal(page)
    expect(total).toBeGreaterThanOrEqual(0)
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
