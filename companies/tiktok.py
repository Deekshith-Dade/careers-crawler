import os
import ast
from playwright.sync_api import sync_playwright
import pandas as pd
from rich.console import Console
from rich.table import Table
from .base import BaseCareersScraper


BASE_URL = "https://lifeattiktok.com"

class TikTokCareersScrapper(BaseCareersScraper):
    def __init__(self, base_url=BASE_URL, keyword="software engineer", recruitment_id_list="", job_category_id_list="", subject_id_list="", locations=None):
        # TikTok-specific default locations
        default_locations = [
            "Austin", "Chicago", "Los Angeles", "New York", "San Francisco", "San Jose", "Seattle", "Washington DC"
        ] if locations is None else locations
        
        # Initialize base class
        super().__init__(
            company_name="tiktok",
            base_url=base_url,
            locations=default_locations
        )
        
        # TikTok-specific attributes
        self.keyword = keyword
        self.recruitment_id_list = recruitment_id_list
        self.job_category_id_list = job_category_id_list
        self.subject_id_list = subject_id_list
        self.primary_url = f"{self.base_url}/search?keyword={self.keyword.replace(' ', '+')}&recruitment_id_list={self.recruitment_id_list}&job_category_id_list={self.job_category_id_list}&subject_id_list={self.subject_id_list}&location_code_list="

        # Also scrapes the applied page and compares the job and updates the csv file
        self.applications_url = f"{self.base_url}/position/application"
        self.login_email = os.getenv("TIKTOK_LOGIN_EMAIL")
        self.login_password = os.getenv("TIKTOK_LOGIN_PASSWORD")
        
        # Override filters with TikTok-specific filters
        self.name_filters = {
            "include": [
                "Software Engineer",
                "Machine Learning Engineer",
            ],
            "exclude": [
                "Intern",
                "2026",
                "2025",
                "Contract",
                "Senior",
                "Principal",
                "Lead",
                "Staff",
                "ios",
                "sr",
            ]
        }
        self.qualification_filters = {
            "include": [
            ],
            "exclude": [
                "does not provide sponsorship",
            ]
        }
    
    def filter_and_find_applications(self):
        filtered_df = self.jobs_df[self.jobs_df['applied'] == False]

        include_mask = self.jobs_df['title'].str.contains('|'.join(self.name_filters['include']), case=False, na=False)
        exclude_mask = self.jobs_df['title'].str.contains('|'.join(self.name_filters['exclude']), case=False, na=False)
        qualification_include_mask = self.jobs_df['requirement'].str.contains('|'.join(self.qualification_filters['include']), case=False, na=False)
        qualification_exclude_mask = self.jobs_df['requirement'].str.contains('|'.join(self.qualification_filters['exclude']), case=False, na=False)
        final_mask = include_mask & ~exclude_mask & ~qualification_exclude_mask & qualification_include_mask
        
        filtered_df = filtered_df[final_mask]
        filter_indices = []
        for index, row in filtered_df.iterrows():
            # Handle both string and dict types for city_info
            city_info = row.city_info
            if isinstance(city_info, str):
                city_info = ast.literal_eval(city_info)
            city_name = city_info.get("en_name", "") if isinstance(city_info, dict) else ""
            if city_name in self.location_filters:
                filter_indices.append(index)
        
        final_filtered_df = filtered_df.loc[filter_indices]
        console = Console()
        
        if len(final_filtered_df) > 0:
            table = Table(title=f"Filtered Applications Found: {len(final_filtered_df)}", show_header=True, header_style="bold magenta")
            table.add_column("Job ID", style="cyan", no_wrap=True)
            table.add_column("Role", style="green")
            table.add_column("Apply Link", style="blue", no_wrap=False)
            
            for index, row in final_filtered_df.iterrows():
                job_code = str(row['code'])
                role = row['title']
                apply_link = f"{self.base_url}/search/{row['id']}"
                table.add_row(job_code, role, apply_link)
            
            console.print(table)
        else:
            console.print(f"[yellow]No filtered applications found.[/yellow]")


    def update_applications(self):
        applications = self.scrape_applied_page()
        print(f"Total applications found: {len(applications) if applications else 0}")

        if applications is None or self.jobs_df is None:
            print("No applications or jobs data available to update.")
            return
        
        applied_job_ids = set(str(job['job_post_info']['id']) for job in applications)
        for index, row in self.jobs_df.iterrows():
            if row['id'] in applied_job_ids:
                self.jobs_df.at[index, 'applied'] = True
        
        self.jobs_df.to_csv(self.file_path, index=False)
        print("Updated applications in the jobs dataframe.")

    def scrape_and_save_jobs(self, max_jobs=None):
        jobs = self.scrape_careers_page(max_jobs=max_jobs)
        previous_jobs = set(str(id) for id in self.jobs_df["id"].values) if self.jobs_df is not None else set()
        new_jobs = {job_id: job for job_id, job in jobs.items() if str(job_id) not in previous_jobs}

        if new_jobs:
            # Convert jobs dictionary to DataFrame
            jobs_list = list(new_jobs.values())
            new_jobs_df = pd.DataFrame(jobs_list)
            new_jobs_df["applied"] = False
            new_jobs_df["id"] = new_jobs_df["id"].astype(str)
            # Save to CSV
            try:
                if self.jobs_df is not None:
                    self.jobs_df = pd.concat([self.jobs_df, new_jobs_df], ignore_index=True)
                else:
                    self.jobs_df = new_jobs_df
                self.jobs_df.to_csv(self.file_path, index=False)
                print(f"Updated {len(new_jobs)} new jobs to {self.file_path}")
            except Exception as e:
                print(f"Error updating jobs dataframe: {str(e)}")
                self.jobs_df = new_jobs_df
        else:
            print("No new jobs found")
    
    def scrape_applied_page(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(self.applications_url, wait_until="networkidle")
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(2000)

                sign_in_with_email = page.get_by_text("Sign in with Email").first
                sign_in_with_email.click()
                page.wait_for_timeout(5000)

                email_input = page.locator('input[placeholder="Email"]').first
                email_input.fill(self.login_email)
                password_input = page.locator('input[placeholder="Password"]').first
                password_input.fill(self.login_password)

                agree_terms_checkbox = page.locator('input[type="checkbox"]').first
                agree_terms_checkbox.check()

                application_data = None
                def handle_application_data_from_response(response):
                    if "applications" in response.url and response.status == 200:
                        try:
                            response_data = response.json()
                            delivery_data = response_data.get("data", {})
                            applications = delivery_data.get("delivery_list", [])
                            nonlocal application_data
                            application_data = applications

                        except:
                            pass
                
                page.on("response", handle_application_data_from_response)
                
                submit_button = page.get_by_role("button", name="Sign in").first
                submit_button.click()
                page.wait_for_timeout(10000)

                
                return application_data

        except Exception as e:
            print(f"Error scraping applied page: {self.applications_url}")
            print(f"Error details: {str(e)}")
            return None

    def scrape_careers_page(self, max_jobs=None):
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
                page.goto(self.primary_url, wait_until="networkidle")
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
                print(f"Selecting {len(self.locations)} locations...")
                for location_name in self.locations:
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
                
                # Locations are selected by this point
                # now retreive the job data from the response by changing offset from 0 to n with limit = 12
                def handle_jobs_from_response(response):
                    if "posts" in response.url and response.status == 200:
                        try:
                            response_data = response.json()
                            json_data = response_data.get("data", {})
                            jobs = json_data.get("job_post_list", [])
                            nonlocal jobs_found
                            for job in jobs:
                                if max_jobs is not None and len(jobs_found) >= max_jobs:
                                    break
                                job_id = job.get("id")
                                jobs_found[job_id] = job
                                print(f"Found {len(jobs_found)} Number of jobs", end="\r")
                                
                        except:
                            pass

                page.on("response", handle_jobs_from_response)

                total_pages = int((total_jobs / 12)) + 1
                for index in range(1, total_pages+1):
                    print(f"Fetching jobs with offset {index}...")
                    if max_jobs is not None and len(jobs_found) >= max_jobs:
                        print("Reached maximum job limit.")
                        break
                    button_element = page.get_by_role("button", name=str(index)).first
                    button_element.click()
                    page.wait_for_timeout(5000)
                
                # Close the browser to free up resources
                browser.close()
                
                return jobs_found
               
        except Exception as e:
            print(f"Error scraping careers url: {self.primary_url}")
            print(f"Error details: {str(e)}")
            return None


            
         