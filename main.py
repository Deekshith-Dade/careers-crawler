from dataclasses import dataclass
from enum import Enum
from playwright.sync_api import sync_playwright
from companies.meta import MetaCareersScraper
from companies.tiktok import TikTokCareersScrapper
from dotenv import load_dotenv

# load env files
load_dotenv()


united_states_locations = [
    "Austin", "Chicago", "Los Angeles", "New York", "San Francisco", "San Jose", "Seattle", "Washington DC"
] 

def scrape_tiktok_careers_page(url):

    try:
        with sync_playwright() as p:
            # headless=True means the browser runs in the background (no visible window)
            # headless=False would show you the browser window (useful for debugging)
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            total_jobs = 0
            jobs_found = {}
            def handle_count_from_response(response):
                if "posts" in response.url and response.status == 200:
                    try:
                        response_data = response.json()
                        nonlocal total_jobs
                        json_data = response_data.get("data", {})
                        total_jobs = json_data.get("count", 0)
                    except:
                        pass
                        
            
            page.on("response", handle_count_from_response)
            page.goto(url, wait_until="networkidle")
            page.wait_for_load_state("domcontentloaded")
            
            page.wait_for_timeout(2000)  # Wait 2 seconds for JavaScript to execute
            
            # Click on the "Location" text element to open the location filter
            print("Clicking on Location filter...")
            location_header = page.get_by_text("Location", exact=True).first
            location_header.click()
            
            # Wait for the location dropdown/checkbox group to appear
            print("Waiting for location options to load...")
            page.wait_for_selector('[data-testid="checkbox-group"]', timeout=5000)
            page.wait_for_timeout(1000)  # Give it a moment to fully render
            
            # Select each location from our list
            print(f"Selecting {len(united_states_locations)} locations...")
            for location_name in united_states_locations:
                try:
                    # Handle "Washington DC" vs "Washington D.C." in HTML
                    search_text = location_name
                    if location_name == "Washington DC":
                        # Try both variations
                        location_label = page.locator(f'label:has-text("Washington D.C."), label:has-text("Washington DC")').first
                    else:
                        # Find the label containing the location name text
                        location_label = page.locator(f'label:has-text("{location_name}")').first
                    
                    # Check if the checkbox is already checked
                    checkbox = location_label.locator('input[type="checkbox"]')
                    is_checked = checkbox.is_checked()
                    
                    if not is_checked:
                        # Click on the label (which will toggle the checkbox)
                        location_label.click()
                        print(f"  ✓ Selected: {location_name}")
                        page.wait_for_timeout(300)  # Small delay between clicks
                    else:
                        print(f"  ⊙ Already selected: {location_name}")
                        
                except Exception as e:
                    print(f"  ✗ Failed to select {location_name}: {str(e)}")
            
            print("Location selection complete!")
            
            # Wait a bit for the page to update with the selected filters
            page.wait_for_timeout(5000)
            
            # Locations are updated by this point
            # now retreive the job data from the response by changing offset from 0 to n with limit = 12
            def handle_jobs_from_response(response):
                if "posts" in response.url and response.status == 200:
                    try:
                        response_data = response.json()
                        json_data = response_data.get("data", {})
                        jobs = json_data.get("job_post_list", [])
                        nonlocal jobs_found
                        for job in jobs:
                            job_id = job.get("id")
                            jobs_found[job_id] = job
                    except:
                        pass
            page.on("response", handle_jobs_from_response)

            total_pages = int((total_jobs / 12)) + 1
            for index in range(1, total_pages+1):
                print(f"Fetching jobs with offset {index}...")
                button_element = page.get_by_role("button", name=str(index)).first
                button_element.click()
                page.wait_for_timeout(5000)
            
            # Close the browser to free up resources
            browser.close()
            
            return jobs_found
            
    except Exception as e:
        print(f"Error scraping careers url: {url}")
        print(f"Error details: {str(e)}")
        return None


def main():
    TIKTOK_BASE_URL = "https://lifeattiktok.com"
    META_BASE_URL = "https://www.metacareers.com/jobsearch"

    # scrapper = TikTokCareersScrapper(base_url=TIKTOK_BASE_URL)
    scrapper = MetaCareersScraper(base_url=META_BASE_URL)
    # scrapper.scrape_and_save_jobs(max_jobs=None)
    scrapper.update_applications(find_status=True)
    scrapper.filter_and_find_applications()
    
    

if __name__ == "__main__":
    main()
