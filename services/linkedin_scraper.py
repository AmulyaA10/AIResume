import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
        raise ValueError("LinkedIn credentials not provided and not found in .env")

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Initialize driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Step 1: Login
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        driver.find_element(By.ID, "username").send_keys(email)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        time.sleep(3) # Wait for login to complete

        # Step 2: Navigate to Profile
        driver.get(profile_url)
        time.sleep(5) # Wait for profile to load

        # Step 3: Extract Content
        # We'll take the main body content for now. Refinement might be needed based on page structure.
        # LinkedIn often uses dynamic class names, so we'll try to get common containers.
        main_content = ""
        try:
            # Try to get the main profile container
            main_el = driver.find_element(By.TAG_NAME, "main")
            main_content = main_el.text
        except:
            # Fallback to body if main is not found
            main_content = driver.find_element(By.TAG_NAME, "body").text

        return main_content

    finally:
        driver.quit()

if __name__ == "__main__":
    # Test block
    test_url = "https://www.linkedin.com/in/bijuemathew/" # Example URL from user info if applicable, or generic
    print(f"Scraping: {test_url}")
    try:
        profile_text = scrape_linkedin_profile(test_url)
        print("Scraped Content Preview:")
        print(profile_text[:500])
    except Exception as e:
        print(f"Error: {e}")
