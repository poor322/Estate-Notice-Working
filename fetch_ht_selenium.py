"""
Estate Notice - Phase 1: Daily Fetcher (Selenium version)
Fetches Hindustan Times e-paper page using a real browser session (Selenium),
since the page content loads via JavaScript and plain requests can't see it.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
from datetime import date
import os

# --- CONFIG ---
HT_EPAPER_URL = "https://epaper.hindustantimes.com/?date=2026-09-20&page=1&storyId=HT_BLRU_FRONTFLAP1_B1_P085_20260920_ART_001&type=Story&view=text"
OUTPUT_DIR = "raw_pages"
WAIT_SECONDS = 8  # time to let the page's JavaScript finish loading


def get_driver():
    """Set up a headless Chrome browser session."""
    options = Options()
    options.add_argument("--headless=new")  # run without opening a visible window
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def fetch_rendered_page(url):
    """Load the page in a real browser and return the fully-rendered text."""
    driver = get_driver()
    try:
        driver.get(url)
        time.sleep(WAIT_SECONDS)  # let JavaScript finish rendering content
        page_text = driver.find_element(By.TAG_NAME, "body").text
        return page_text
    finally:
        driver.quit()


def save_raw_page(source, page_date, page_text):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"{OUTPUT_DIR}/{source}_{page_date}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(page_text)
    print(f"Saved: {filename}")


def main():
    today = date.today().isoformat()
    print(f"Fetching Hindustan Times e-paper (rendered) for {today}...")

    text = fetch_rendered_page(HT_EPAPER_URL)
    save_raw_page("hindustan_times", today, text)

    print(f"Done. Extracted {len(text)} characters.")


if __name__ == "__main__":
    main()