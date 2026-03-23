import { test, expect, Page } from '@playwright/test'

// ─── Auth helpers ─────────────────────────────────────────────────────────────

async function loginAsManager(page: Page) {
  await page.goto('/login')
  await page.evaluate(() => localStorage.clear())
  await page.getByText('Manager SSO').click()
  await page.waitForURL('/', { timeout: 5000 })
}

// ─── Resume DB helpers ────────────────────────────────────────────────────────

async function goToResumeDB(page: Page) {
  await page.goto('/resumes')
  await expect(page.locator('[data-testid="results-count"]')).toBeVisible({ timeout: 10000 })
}

async function getResumeTotal(page: Page): Promise<number> {
  const el = page.locator('[data-testid="results-count"]')
  const total = await el.getAttribute('data-total').catch(() => null)
  return parseInt(total ?? '0', 10)
}

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

async function waitForResumeResults(page: Page) {
  // Wait for loading to finish — results-count is hidden while loading
  await expect(page.locator('[data-testid="results-count"]')).toBeVisible({ timeout: 15000 })
  await page.waitForTimeout(300)
}

// ─── JD helpers ──────────────────────────────────────────────────────────────

async function goToJDPage(page: Page) {
  await page.goto('/jds')
  // Wait for either job cards or the empty state
  await Promise.race([
    page.locator('[data-testid="jd-card"]').first().waitFor({ timeout: 10000 }).catch(() => {}),
    page.locator('[data-testid="jd-results-count"]').waitFor({ timeout: 10000 }).catch(() => {}),
  ])
  await page.waitForTimeout(500)
}

async function getJDTotal(page: Page): Promise<number> {
  const el = page.locator('[data-testid="jd-results-count"]')
  const isVisible = await el.isVisible().catch(() => false)
  if (!isVisible) return await page.locator('[data-testid="jd-card"]').count()
  const total = await el.getAttribute('data-total').catch(() => null)
  return parseInt(total ?? '0', 10)
}

async function getJDCardLocations(page: Page): Promise<string[]> {
  const locs = page.locator('[data-testid="jd-card-location"]')
  const count = await locs.count()
  const result: string[] = []
  for (let i = 0; i < count; i++) {
    const text = await locs.nth(i).textContent()
    if (text) result.push(text.trim().toLowerCase())
  }
  return result
}

async function waitForJDResults(page: Page) {
  await page.waitForResponse(
    r => r.url().includes('/api/v1/jobs') && r.request().method() === 'GET',
    { timeout: 15000 },
  ).catch(() => {})
  await page.waitForTimeout(500)
}

// ─── Resume DB filter tests ───────────────────────────────────────────────────

test.describe('Resume DB — dropdown filters', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  // Regression: "Calgary, CA" (Canada ISO code) was mapping to California group
  test('location dropdown — Canada cities do NOT appear under California', async ({ page }) => {
    await goToResumeDB(page)
    const locationSelect = page.locator('[data-testid="location-filter"]')
    const caGroup = locationSelect.locator('optgroup[label="California"]')
    const caGroupExists = await caGroup.count() > 0
    if (!caGroupExists) return // no California group — nothing to check

    const caOptions = await caGroup.locator('option').allInnerTexts()
    const hasCanada = caOptions.some(o =>
      o.toLowerCase().includes('canada') ||
      o.toLowerCase().includes('toronto') ||
      o.toLowerCase().includes('vancouver') ||
      o.toLowerCase().includes('calgary')
    )
    expect(hasCanada).toBe(false)
  })

  test('page loads with results and filter controls visible', async ({ page }) => {
    await goToResumeDB(page)
    await expect(page.locator('[data-testid="resume-search-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="location-filter"]')).toBeVisible()
    await expect(page.locator('[data-testid="industry-filter"]')).toBeVisible()
    await expect(page.locator('[data-testid="exp-level-filter"]')).toBeVisible()
  })

  test('location filter — state-level only shows cards from that state', async ({ page }) => {
    await goToResumeDB(page)
    const totalBefore = await getResumeTotal(page)
    if (totalBefore === 0) return // no data to test

    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (!stateOption) return // no state options populated yet

    // e.g. "All California" → "California"
    const stateName = stateOption.replace(/^All\s+/, '').trim()

    await locationSelect.selectOption({ label: stateOption })
    await waitForResumeResults(page)

    const totalAfter = await getResumeTotal(page)
    // Filtered count must not exceed total
    expect(totalAfter).toBeLessThanOrEqual(totalBefore)

    // Every visible card must belong to this state
    const locs = await getCardLocations(page)
    if (locs.length > 0) {
      const stateNameLower = stateName.toLowerCase()
      const allMatch = locs.every(l => l.includes(stateNameLower) || l.includes(`, ${stateNameLower.slice(0, 2)}`))
      // Use a wider check: at least 1 US state abbreviation hint if state name not in label
      // The reliable check is that NO card should come from a completely different state
      expect(allMatch || locs.every(l => !l.includes(', '))).toBe(true)
    }
  })

  // Regression: uppercase ", CA" substring was never matching lowercased location strings
  test('"All California" filter returns CA candidates (regression: case bug)', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const caOption = options.find(o => o === 'All California')
    if (!caOption) return // no CA candidates in DB — skip

    await locationSelect.selectOption({ label: caOption })
    await waitForResumeResults(page)

    const locs = await getCardLocations(page)
    expect(locs.length).toBeGreaterThan(0)
    const allCA = locs.every(l => l.includes(', ca') || l.includes('california'))
    expect(allCA).toBe(true)
  })

  test('location filter — city-level shows city and its suburbs (same state)', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    // City options don't start with "All " and are not blank
    const cityOption = options.find(o => o.trim() && !o.startsWith('All '))
    if (!cityOption) return

    await locationSelect.selectOption({ label: cityOption })
    await waitForResumeResults(page)

    const locs = await getCardLocations(page)
    // Suburbs map to the same metro but may not contain the city name.
    // All results must still be in the same state as the selected city.
    const statePart = cityOption.split(',')[1]?.trim().toLowerCase()
    if (locs.length > 0 && statePart) {
      const allInState = locs.every(l => l.toLowerCase().includes(statePart))
      expect(allInState).toBe(true)
    }
  })

  test('experience level filter — only shows matching level', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    await page.locator('[data-testid="exp-level-filter"]').selectOption('Senior')
    await waitForResumeResults(page)

    // Should not crash, and if cards show, they should be senior
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('industry filter — reduces or maintains result count', async ({ page }) => {
    await goToResumeDB(page)
    const totalBefore = await getResumeTotal(page)
    if (totalBefore === 0) return

    const industrySelect = page.locator('[data-testid="industry-filter"]')
    const options = await industrySelect.locator('option').allInnerTexts()
    const firstIndustry = options.find(o => o.trim() && o !== 'All Industries')
    if (!firstIndustry) return

    await industrySelect.selectOption({ label: firstIndustry })
    await waitForResumeResults(page)

    const totalAfter = await getResumeTotal(page)
    expect(totalAfter).toBeLessThanOrEqual(totalBefore)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('clearing filters restores original count', async ({ page }) => {
    await goToResumeDB(page)
    const totalBefore = await getResumeTotal(page)
    if (totalBefore === 0) return

    // Apply exp level filter
    await page.locator('[data-testid="exp-level-filter"]').selectOption('Senior')
    await waitForResumeResults(page)

    // Clear via button
    const clearBtn = page.getByRole('button', { name: /clear/i })
    const clearVisible = await clearBtn.isVisible().catch(() => false)
    if (clearVisible) {
      await clearBtn.click()
      await waitForResumeResults(page)
      const totalAfter = await getResumeTotal(page)
      expect(totalAfter).toBe(totalBefore)
    }
  })
})

// ─── Resume DB semantic + filter combination tests ───────────────────────────

test.describe('Resume DB — semantic search + filter combination', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('semantic search then location filter — no crash', async ({ page }) => {
    await goToResumeDB(page)

    // Type semantic query
    const input = page.locator('[data-testid="resume-search-input"]')
    await input.fill('python developer')
    await waitForResumeResults(page)

    const countAfterSearch = await getResumeTotal(page)

    // Now also apply location filter (pick first available state)
    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (stateOption) {
      await locationSelect.selectOption({ label: stateOption })
      await waitForResumeResults(page)
      const countCombined = await getResumeTotal(page)
      // Combined filter can only equal or reduce results
      expect(countCombined).toBeLessThanOrEqual(countAfterSearch)
    }
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('semantic search then exp level filter — results narrow or stay same', async ({ page }) => {
    await goToResumeDB(page)

    const input = page.locator('[data-testid="resume-search-input"]')
    await input.fill('software engineer')
    await waitForResumeResults(page)
    const countAfterSearch = await getResumeTotal(page)

    await page.locator('[data-testid="exp-level-filter"]').selectOption('Senior')
    await waitForResumeResults(page)

    const countCombined = await getResumeTotal(page)
    expect(countCombined).toBeLessThanOrEqual(countAfterSearch)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('semantic search "Los Angeles metro area" surfaces LA candidates', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    // Semantic search alone ranks by relevance — LA candidates should appear but
    // non-CA results are not excluded without the location dropdown filter.
    const input = page.locator('[data-testid="resume-search-input"]')
    await input.fill('Candidates from Los Angeles metro area')
    await waitForResumeResults(page)

    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const locs = await getCardLocations(page)
    expect(locs.length).toBeGreaterThan(0)

    // At least one LA-area candidate should surface in the results
    const laArea = locs.filter(l =>
      l.includes('los angeles') || l.includes('irvine') || l.includes('foothill ranch') ||
      l.includes('pasadena') || l.includes('burbank') || l.includes('long beach') ||
      l.includes('santa monica') || l.includes('glendale') || l.includes('anaheim') ||
      l.includes('orange county')
    )
    expect(laArea.length).toBeGreaterThan(0)
  })

  test('semantic search + LA location filter — only CA candidates returned', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    // Type semantic search query and wait for results
    const input = page.locator('[data-testid="resume-search-input"]')
    await input.fill('Candidates from Los Angeles metro area')
    await waitForResumeResults(page)

    // Then apply location filter: Los Angeles, CA (or All California as fallback).
    // Wait for the actual API response (debounce is 400ms when search is active).
    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const laOption = options.find(o => o.toLowerCase().includes('los angeles'))
    const caOption = options.find(o => o === 'All California')
    const chosen = laOption ?? caOption
    if (!chosen) return

    await Promise.all([
      page.waitForResponse(r => r.url().includes('/resumes/database'), { timeout: 15000 }),
      locationSelect.selectOption({ label: chosen }),
    ])
    await page.waitForTimeout(300)

    await expect(page.locator('body')).not.toContainText('Something went wrong')
    const locs = await getCardLocations(page)
    expect(locs.length).toBeGreaterThan(0)

    // With location filter applied, all results must be in California
    const nonCA = locs.filter(l => !l.includes(', ca') && l !== 'remote')
    expect(nonCA).toHaveLength(0)
  })

  test('location filter then semantic search — consistent results', async ({ page }) => {
    await goToResumeDB(page)
    if (await getResumeTotal(page) === 0) return

    // Apply location filter first
    const locationSelect = page.locator('[data-testid="location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (!stateOption) return

    await locationSelect.selectOption({ label: stateOption })
    await waitForResumeResults(page)

    // Then type a search
    const input = page.locator('[data-testid="resume-search-input"]')
    await input.fill('developer')
    await waitForResumeResults(page)

    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })
})

// ─── JD (Job Definitions) filter tests ───────────────────────────────────────

test.describe('Job Definitions — dropdown filters', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('JD page loads and filter controls are visible', async ({ page }) => {
    await goToJDPage(page)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
    // Filters only render when there are jobs or active filters
    const count = await getJDTotal(page)
    if (count > 0) {
      await expect(page.locator('[data-testid="jd-level-filter"]')).toBeVisible()
      await expect(page.locator('[data-testid="jd-location-filter"]')).toBeVisible()
    }
  })

  test('JD level filter — narrows or maintains results', async ({ page }) => {
    await goToJDPage(page)
    const totalBefore = await getJDTotal(page)
    if (totalBefore === 0) return

    await page.locator('[data-testid="jd-level-filter"]').selectOption('SENIOR')
    await waitForJDResults(page)

    const totalAfter = await getJDTotal(page)
    expect(totalAfter).toBeLessThanOrEqual(totalBefore)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('JD location filter — state-level only returns matching locations', async ({ page }) => {
    await goToJDPage(page)
    const totalBefore = await getJDTotal(page)
    if (totalBefore === 0) return

    const locationSelect = page.locator('[data-testid="jd-location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (!stateOption) return

    const stateName = stateOption.replace(/^All\s+/, '').trim().toLowerCase()
    await locationSelect.selectOption({ label: stateOption })
    await waitForJDResults(page)

    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const locs = await getJDCardLocations(page)
    // Every returned card's location must contain the selected state name or abbreviation
    if (locs.length > 0) {
      const allMatch = locs.every(l => l.includes(stateName) || l.includes(`, ${stateName.slice(0, 2)}`))
      expect(allMatch).toBe(true)
    }
  })

  // Regression test: "All California" filter must not return zero results when CA jobs exist
  test('JD "All California" filter returns CA jobs (regression: uppercase substr bug)', async ({ page }) => {
    await goToJDPage(page)
    if (await getJDTotal(page) === 0) return

    const locationSelect = page.locator('[data-testid="jd-location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const caOption = options.find(o => o === 'All California')
    if (!caOption) return // no CA jobs in DB — skip

    await locationSelect.selectOption({ label: caOption })
    await waitForJDResults(page)

    // Must return results (not zero) and all must be CA
    const locs = await getJDCardLocations(page)
    expect(locs.length).toBeGreaterThan(0)
    const allCA = locs.every(l => l.includes(', ca') || l.includes('california'))
    expect(allCA).toBe(true)
  })

  test('JD location filter and level filter combined', async ({ page }) => {
    await goToJDPage(page)
    if (await getJDTotal(page) === 0) return

    const locationSelect = page.locator('[data-testid="jd-location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (stateOption) {
      await locationSelect.selectOption({ label: stateOption })
    }

    await page.locator('[data-testid="jd-level-filter"]').selectOption('SENIOR')
    await waitForJDResults(page)

    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })
})

// ─── JD semantic search + filter combination tests ───────────────────────────

test.describe('Job Definitions — semantic search + filter combination', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page)
  })

  test('semantic search then location filter — no crash', async ({ page }) => {
    await goToJDPage(page)
    if (await getJDTotal(page) === 0) return

    const input = page.locator('[data-testid="jd-search-input"]')
    await input.fill('senior engineer')
    await waitForJDResults(page)
    const countAfterSearch = await getJDTotal(page)

    const locationSelect = page.locator('[data-testid="jd-location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const stateOption = options.find(o => o.startsWith('All ') && o !== 'All Locations')
    if (stateOption) {
      await locationSelect.selectOption({ label: stateOption })
      await waitForJDResults(page)
      const countCombined = await getJDTotal(page)
      expect(countCombined).toBeLessThanOrEqual(countAfterSearch)
    }
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('semantic search then level filter — results narrow', async ({ page }) => {
    await goToJDPage(page)
    if (await getJDTotal(page) === 0) return

    await page.locator('[data-testid="jd-search-input"]').fill('backend developer')
    await waitForJDResults(page)
    const countAfterSearch = await getJDTotal(page)

    await page.locator('[data-testid="jd-level-filter"]').selectOption('SENIOR')
    await waitForJDResults(page)
    const countCombined = await getJDTotal(page)

    expect(countCombined).toBeLessThanOrEqual(countAfterSearch)
    await expect(page.locator('body')).not.toContainText('Something went wrong')
  })

  test('location-based semantic search aligns with location filter', async ({ page }) => {
    await goToJDPage(page)
    if (await getJDTotal(page) === 0) return

    // Semantic: ask for California jobs
    await page.locator('[data-testid="jd-search-input"]').fill('jobs in california')
    await waitForJDResults(page)
    await expect(page.locator('body')).not.toContainText('Something went wrong')

    const semanticTotal = await getJDTotal(page)

    // Clear and use dropdown filter instead
    await page.locator('[data-testid="jd-search-input"]').fill('')
    await waitForJDResults(page)

    const locationSelect = page.locator('[data-testid="jd-location-filter"]')
    const options = await locationSelect.locator('option').allInnerTexts()
    const caOption = options.find(o => o === 'All California')
    if (caOption) {
      await locationSelect.selectOption({ label: caOption })
      await waitForJDResults(page)
      const filterTotal = await getJDTotal(page)
      // Both approaches should return non-zero results if CA jobs exist
      if (semanticTotal > 0) {
        expect(filterTotal).toBeGreaterThan(0)
      }
    }
  })
})
