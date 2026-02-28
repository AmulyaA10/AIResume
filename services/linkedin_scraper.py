import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

# Time budget: stop expensive operations after this many seconds.
# Allows up to ~34s for login (inc. security challenge approval) plus
# ~56s for scrolling, expanding, and extracting profile content.
_TIME_BUDGET_SECONDS = 90


def _check_budget(start_time: float) -> bool:
    """Return True if we still have time budget remaining."""
    return (time.time() - start_time) < _TIME_BUDGET_SECONDS


def _dismiss_modals(driver):
    """Dismiss LinkedIn notification modals, cookie banners, and other overlays.

    LinkedIn shows custom HTML overlay modals after login (e.g. "Turn on
    notifications?") that block page content.  The ``--disable-notifications``
    Chrome flag only suppresses *browser*-level prompts, not LinkedIn's own
    DOM overlays.  This helper clicks "Not now" / "Skip" / "Dismiss" buttons
    so the underlying profile content becomes accessible.
    """
    dismiss_xpaths = [
        # LinkedIn "Turn on notifications" modal — "Not now" / "Skip"
        "//button[contains(text(), 'Not now')]",
        "//button[contains(text(), 'not now')]",
        "//button[contains(text(), 'Skip')]",
        "//button[contains(text(), 'Dismiss')]",
        "//button[contains(text(), 'Later')]",
        # LinkedIn messaging overlay close button
        "//button[contains(@data-control-name, 'overlay.close')]",
        # Generic artdeco modal dismiss (LinkedIn design system)
        "//button[contains(@class, 'artdeco-modal__dismiss')]",
        "//button[@aria-label='Dismiss']",
        # Cookie consent — prefer "Reject" for privacy
        "//button[contains(text(), 'Reject')]",
    ]
    dismissed = 0
    for xpath in dismiss_xpaths:
        try:
            buttons = driver.find_elements(By.XPATH, xpath)
            for btn in buttons:
                try:
                    btn.click()
                    dismissed += 1
                    time.sleep(0.5)
                except Exception:
                    pass
        except Exception:
            pass
    if dismissed:
        print(f"--- [Scraper] Dismissed {dismissed} modal(s)/overlay(s) ---")


def _progressive_scroll(driver, pause: float = 1.0, max_scrolls: int = 12):
    """Scroll the page in increments to trigger lazy-loaded sections.

    Scrolls ~800px at a time, waiting for new content to load.
    Stops when page height stabilizes or max_scrolls reached.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_position = 0

    for i in range(max_scrolls):
        scroll_position += 800
        driver.execute_script(f"window.scrollTo(0, {scroll_position});")
        time.sleep(pause)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if scroll_position >= new_height and new_height == last_height:
            break
        last_height = new_height

    # Scroll back to top so we can interact with elements
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)


def _expand_show_all_buttons(driver, profile_url: str, start_time: float) -> str:
    """Click 'Show all' links to load full experience, education, skills, certifications.

    LinkedIn 'Show all' links navigate to detail pages like /details/experience/.
    We visit each detail page, extract its content, then return to the profile.

    Returns concatenated text from all detail pages.
    """
    detail_text_parts = []

    # Collect all "Show all" links before clicking (hrefs with /details/)
    detail_links = []
    try:
        anchors = driver.find_elements(
            By.XPATH,
            "//a[contains(@href, '/details/')]"
        )
        for a in anchors:
            href = a.get_attribute("href")
            if href and "/details/" in href:
                # Deduplicate
                if href not in detail_links:
                    detail_links.append(href)
                    print(f"--- [Scraper] Found detail link: {href} ---")
    except Exception as e:
        print(f"--- [Scraper] Warning: Could not find Show All links: {e} ---")

    # Also try button-style "Show all" elements
    try:
        buttons = driver.find_elements(
            By.XPATH,
            "//button[contains(translate(., 'SHOW', 'show'), 'show all')]"
        )
        for btn in buttons:
            if _check_budget(start_time):
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.3)
                    btn.click()
                    time.sleep(1.5)
                    print("--- [Scraper] Clicked a 'Show all' button ---")
                except Exception:
                    pass
    except Exception:
        pass

    # Visit each detail page and extract content
    for href in detail_links:
        if not _check_budget(start_time):
            print("--- [Scraper] Time budget reached, skipping remaining detail pages ---")
            break

        try:
            print(f"--- [Scraper] Visiting detail page: {href} ---")
            driver.get(href)
            time.sleep(2)

            # Scroll the detail page to load all items
            _progressive_scroll(driver, pause=0.8, max_scrolls=8)

            # Expand any "see more" buttons on the detail page
            _expand_see_more_buttons(driver)

            # Extract the detail page content
            page_text = driver.execute_script("""
                const main = document.querySelector('main');
                return main ? main.innerText : document.body.innerText;
            """)

            if page_text and len(page_text.strip()) > 20:
                # Determine section name from URL
                section_name = "DETAILS"
                if "/experience" in href:
                    section_name = "EXPERIENCE"
                elif "/education" in href:
                    section_name = "EDUCATION"
                elif "/skills" in href:
                    section_name = "SKILLS"
                elif "/certifications" in href or "/licenses" in href:
                    section_name = "CERTIFICATIONS"
                elif "/honors" in href or "/awards" in href:
                    section_name = "HONORS & AWARDS"
                elif "/projects" in href:
                    section_name = "PROJECTS"
                elif "/publications" in href:
                    section_name = "PUBLICATIONS"
                elif "/volunteer" in href:
                    section_name = "VOLUNTEER"
                elif "/languages" in href:
                    section_name = "LANGUAGES"
                elif "/recommendations" in href:
                    section_name = "RECOMMENDATIONS"

                detail_text_parts.append(f"\n===SECTION: {section_name}===\n{page_text.strip()}")
                print(f"--- [Scraper] Extracted {len(page_text)} chars from {section_name} ---")

        except Exception as e:
            print(f"--- [Scraper] Warning: Failed to extract detail page {href}: {e} ---")

    # Navigate back to the main profile
    if detail_links:
        try:
            driver.get(profile_url)
            time.sleep(2)
        except Exception:
            pass

    return "\n".join(detail_text_parts)


def _expand_see_more_buttons(driver):
    """Click all 'see more' / '...more' buttons to expand truncated descriptions."""
    selectors = [
        "//button[contains(@class, 'inline-show-more')]",
        "//button[contains(translate(., 'SEE MORE', 'see more'), 'see more')]",
        "//button[contains(text(), '…more')]",
        "//button[contains(text(), '...more')]",
        # LinkedIn's specific class for the inline expand button
        "button.inline-show-more-text__button",
    ]

    clicked = 0
    for selector in selectors:
        try:
            if selector.startswith("//"):
                buttons = driver.find_elements(By.XPATH, selector)
            else:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)

            for btn in buttons:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", btn)
                    clicked += 1
                    time.sleep(0.3)
                except Exception:
                    pass
        except Exception:
            pass

    if clicked:
        print(f"--- [Scraper] Expanded {clicked} 'see more' buttons ---")


def _extract_section_text(driver) -> str:
    """Extract text from the main profile page using section landmarks.

    LinkedIn uses anchor IDs like #experience, #education, #skills,
    #licenses_and_certifications within <section> elements.
    We extract each section's innerText separately with clear delimiters.
    """
    section_ids = {
        "about": "ABOUT",
        "experience": "EXPERIENCE",
        "education": "EDUCATION",
        "skills": "SKILLS",
        "licenses_and_certifications": "CERTIFICATIONS",
        "honors_and_awards": "HONORS & AWARDS",
        "projects": "PROJECTS",
        "publications": "PUBLICATIONS",
        "volunteer_experience": "VOLUNTEER",
        "languages": "LANGUAGES",
        "recommendations": "RECOMMENDATIONS",
    }

    parts = []

    # First, get the header/intro section (name, headline, location)
    try:
        header_text = driver.execute_script("""
            // Try the profile header section
            const topCard = document.querySelector('.pv-top-card') ||
                           document.querySelector('[data-section="summary"]') ||
                           document.querySelector('section.artdeco-card');
            if (topCard) return topCard.innerText;

            // Fallback: get first section in main
            const main = document.querySelector('main');
            if (main && main.children.length > 0) {
                return main.children[0].innerText;
            }
            return '';
        """)
        if header_text and len(header_text.strip()) > 10:
            parts.append(f"===SECTION: PROFILE HEADER===\n{header_text.strip()}")
    except Exception:
        pass

    # Extract each known section by anchor ID
    for anchor_id, section_name in section_ids.items():
        try:
            section_text = driver.execute_script(f"""
                // Find the anchor element
                const anchor = document.getElementById('{anchor_id}');
                if (!anchor) return '';

                // Walk up to the containing section
                let section = anchor.closest('section');
                if (!section) {{
                    // Sometimes the anchor is inside a div, try parent's parent
                    section = anchor.parentElement;
                    while (section && section.tagName !== 'SECTION') {{
                        section = section.parentElement;
                    }}
                }}
                return section ? section.innerText : '';
            """)
            if section_text and len(section_text.strip()) > 10:
                parts.append(f"===SECTION: {section_name}===\n{section_text.strip()}")
        except Exception:
            pass

    return "\n\n".join(parts)


def scrape_linkedin_profile(profile_url, email=None, password=None, login_wait=None):
    """
    Scrapes a LinkedIn profile using Selenium with progressive scrolling,
    section expansion, and structured text extraction.

    Args:
        login_wait: Max seconds to wait for login/security challenge.
            - First attempt: use 10 (detect challenge quickly, prompt user fast)
            - Retry after user approved on phone: use 45 (give more time)
            - Default (None): 30 seconds.

    Requires LinkedinLogin and LinkedinPassword in .env or passed as arguments.
    """
    start_time = time.time()

    email = email or os.getenv("LinkedinLogin")
    password = password or os.getenv("LinkedinPassword")

    if not email or not password:
        raise ValueError(
            "LinkedIn scraper credentials are not configured. "
            "Please set LinkedinLogin and LinkedinPassword in your backend/.env file "
            "or save your LinkedIn email and password in Settings."
        )

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Suppress notification prompts at browser level (belt-and-suspenders
    # alongside --disable-notifications flag above)
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,  # 2 = Block
    })

    # Initialize driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)

    try:
        # Step 1: Login
        print("--- [Scraper] Navigating to LinkedIn login... ---")
        driver.get("https://www.linkedin.com/login")

        wait = WebDriverWait(driver, 10)

        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        password_field = driver.find_element(By.ID, "password")

        username_field.send_keys(email)
        password_field.send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for login to complete — poll until login_wait expires.
        # LinkedIn may show a security challenge ("Is this you?" push
        # notification to the user's phone) which takes 10-30s to approve.
        # First attempt: 10s (detect quickly, prompt user to approve on phone)
        # Retry attempt: 45s (user is actively approving, give more time)
        _LOGIN_POLL_INTERVAL = 3   # seconds between checks
        _LOGIN_POLL_MAX_WAIT = login_wait if login_wait is not None else 30

        login_elapsed = 0
        login_success = False
        time.sleep(4)  # initial wait for fast logins

        while login_elapsed < _LOGIN_POLL_MAX_WAIT:
            current_url = driver.current_url

            # Dismiss any post-login modals (notifications, cookie banners)
            _dismiss_modals(driver)

            # Check for clear login failure (wrong password)
            page_text = driver.find_element(By.TAG_NAME, "body").text[:500]
            if "incorrect" in page_text.lower() or "wrong" in page_text.lower():
                raise ValueError(
                    "LinkedIn login failed — incorrect email or password. "
                    "Check your LinkedinLogin and LinkedinPassword in .env."
                )

            # If we're past the login/checkpoint pages, we're in
            if not any(kw in current_url for kw in ["login", "checkpoint", "challenge"]):
                login_success = True
                print(f"--- [Scraper] Login succeeded after ~{login_elapsed + 4}s (URL: {current_url}) ---")
                break

            # Still on a challenge page — keep waiting for user to approve
            page_lower = page_text.lower()
            is_challenge = any(kw in page_lower for kw in [
                "verification", "security", "challenge", "verify",
                "approve", "confirm", "recognize", "is this you",
            ])

            if is_challenge:
                print(f"--- [Scraper] Security challenge detected, waiting for approval... ({login_elapsed + 4}s elapsed) ---")
            else:
                print(f"--- [Scraper] Still on login-like page: {current_url} ({login_elapsed + 4}s elapsed) ---")

            time.sleep(_LOGIN_POLL_INTERVAL)
            login_elapsed += _LOGIN_POLL_INTERVAL

        if not login_success:
            # Final check after the full wait
            current_url = driver.current_url
            _dismiss_modals(driver)

            if any(kw in current_url for kw in ["login", "checkpoint", "challenge"]):
                page_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                page_lower = page_text.lower()
                if any(kw in page_lower for kw in ["verification", "security", "challenge", "verify", "approve", "is this you"]):
                    raise ValueError(
                        "LinkedIn security verification timed out after 30 seconds. "
                        "Please log into LinkedIn manually in a regular browser first, "
                        "approve any security checks, then retry the scrape."
                    )
                print(f"--- [Scraper] Warning: Still on login-like page after {_LOGIN_POLL_MAX_WAIT}s: {current_url} ---")

        # Step 2: Navigate to Profile
        print(f"--- [Scraper] Navigating to profile: {profile_url} ---")
        driver.get(profile_url)

        # Wait for main content to load
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        except Exception:
            time.sleep(5)

        # Give dynamic content a moment to render
        time.sleep(3)

        # Dismiss any per-page modals/overlays on the profile page
        _dismiss_modals(driver)

        # Step 3: Progressive scroll to load ALL lazy sections
        print("--- [Scraper] Progressive scrolling to load all sections... ---")
        _progressive_scroll(driver, pause=1.0, max_scrolls=12)

        # Step 4: Expand "see more" buttons on main profile page
        if _check_budget(start_time):
            print("--- [Scraper] Expanding 'see more' buttons... ---")
            _expand_see_more_buttons(driver)

        # Step 5: Extract main profile page content (structured by sections)
        print("--- [Scraper] Extracting main profile sections... ---")
        main_section_text = _extract_section_text(driver)

        # Step 6: Visit "Show all" detail pages for complete data
        detail_text = ""
        if _check_budget(start_time):
            print("--- [Scraper] Visiting detail pages for full content... ---")
            detail_text = _expand_show_all_buttons(driver, profile_url, start_time)

        # Step 7: Combine all content
        # Use detail pages as primary (more complete), main sections as fallback
        if detail_text and len(detail_text.strip()) > 100:
            # If we got good detail page content, use it as primary
            # but prepend the main profile header/about for context
            main_content = driver.execute_script("""
                const main = document.querySelector('main');
                return main ? main.innerText : document.body.innerText;
            """)
            combined = f"{main_section_text}\n\n{detail_text}"
            # Fallback: if structured extraction is thin, append full main text
            if len(main_section_text.strip()) < 200 and main_content:
                combined = f"{main_content}\n\n{detail_text}"
        elif main_section_text and len(main_section_text.strip()) > 100:
            combined = main_section_text
        else:
            # Last resort: grab everything from main
            combined = driver.execute_script("""
                const main = document.querySelector('main');
                return main ? main.innerText : document.body.innerText;
            """)

        # Validate we got meaningful content (200+ chars AND profile section evidence)
        if not combined or len(combined.strip()) < 200:
            body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
            if "page not found" in body_text.lower() or "this page doesn" in body_text.lower():
                raise ValueError(f"LinkedIn profile not found at {profile_url}. The URL may be incorrect.")
            raise ValueError(
                f"Scraped only {len(combined.strip()) if combined else 0} characters from profile. "
                "LinkedIn may have blocked the request (CAPTCHA/anti-bot) or the profile is private. "
                "Try logging into LinkedIn manually in a regular browser first, then retry."
            )

        # Additional check: does the content contain any profile section evidence?
        combined_lower = combined.lower()
        if not any(kw in combined_lower for kw in [
            "experience", "education", "skills", "===section:",
            "present", "full-time", "part-time",
        ]):
            raise ValueError(
                "Scraped content does not appear to contain LinkedIn profile sections "
                "(no experience, education, or skills found). LinkedIn may have shown a "
                "login wall or CAPTCHA instead of the actual profile."
            )

        elapsed = time.time() - start_time
        print(f"--- [Scraper] Extracted {len(combined)} characters from profile in {elapsed:.1f}s ---")
        return combined

    finally:
        driver.quit()


if __name__ == "__main__":
    test_url = "https://www.linkedin.com/in/bijuemathew/"
    print(f"Scraping: {test_url}")
    try:
        profile_text = scrape_linkedin_profile(test_url)
        print("Scraped Content Preview:")
        print(profile_text[:500])
    except Exception as e:
        print(f"Error: {e}")
