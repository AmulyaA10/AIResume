import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

def scrape_linkedin_profile(profile_url, email=None, password=None):
    """
    Scrapes a LinkedIn profile using Selenium.
    Requires LinkedinLogin and LinkedinPassword in .env or passed as arguments
    """
    email = email or os.getenv("LinkedinLogin")
    password = password or os.getenv("LinkedinPassword")

    if not email or not password:
        raise ValueError(
            "LinkedIn scraper credentials are not configured. "
            "Please set LinkedinLogin and LinkedinPassword in your backend/.env file."
        )

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

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

        # Wait for login to complete — check for feed or profile nav
        time.sleep(4)

        # Check if login failed (still on login page or challenge page)
        current_url = driver.current_url
        if "login" in current_url or "checkpoint" in current_url or "challenge" in current_url:
            page_text = driver.find_element(By.TAG_NAME, "body").text[:500]
            if "verification" in page_text.lower() or "security" in page_text.lower() or "challenge" in page_text.lower():
                raise ValueError(
                    "LinkedIn requires verification (CAPTCHA/2FA). "
                    "Please log into LinkedIn manually in a browser first to clear any security challenges, then retry."
                )
            if "incorrect" in page_text.lower() or "wrong" in page_text.lower():
                raise ValueError(
                    "LinkedIn login failed — incorrect email or password. "
                    "Check your LinkedinLogin and LinkedinPassword in .env."
                )
            print(f"--- [Scraper] Warning: Still on login-like page: {current_url} ---")

        # Step 2: Navigate to Profile
        print(f"--- [Scraper] Navigating to profile: {profile_url} ---")
        driver.get(profile_url)

        # Wait for main content to load
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        except:
            time.sleep(5)

        # Give dynamic content a moment to render
        time.sleep(3)

        # Step 3: Scroll to load lazy sections
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Step 4: Extract Content
        main_content = ""
        try:
            main_el = driver.find_element(By.TAG_NAME, "main")
            main_content = main_el.text
        except:
            main_content = driver.find_element(By.TAG_NAME, "body").text

        # Check for common blocked/error pages
        if not main_content or len(main_content.strip()) < 50:
            body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
            if "page not found" in body_text.lower() or "this page doesn" in body_text.lower():
                raise ValueError(f"LinkedIn profile not found at {profile_url}. The URL may be incorrect.")
            raise ValueError(
                "Could not extract meaningful content from the profile. "
                "LinkedIn may have blocked the request or the profile is private."
            )

        print(f"--- [Scraper] Extracted {len(main_content)} characters from profile ---")
        return main_content

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
