import os
import json
import ast
import pandas as pd
from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from playwright.sync_api import sync_playwright

from companies.base import BaseCareersScraper

BASE_URL = "https://www.metacareers.com"


class MetaCareersScraper(BaseCareersScraper):
    def __init__(self, base_url=BASE_URL, locations=None):
        """
        Initialize Meta Careers Scraper.
        
        Args:
            base_url: Base URL of Meta careers page
            locations: List of location names to filter by
        """
        # Initialize base class
        super().__init__(
            company_name="meta",
            base_url=base_url,
            locations=locations
        )
        
        default_locations = [
            "Bellevue, WA"
        ]
        self.locations = default_locations if locations is None else locations

        self.primary_url = base_url

        self.applications_url = "https://www.metacareers.com/login"
        self.login_email = os.getenv("META_LOGIN_EMAIL")
        self.login_password = os.getenv("META_LOGIN_PASSWORD")
        
        # TODO: Add Meta-specific attributes here as needed
        # Example: self.seaorch_url = f"{self.base_url}/..."
        self.name_filters = {
            "include": [
                "Software Engineer",
                "Machine",
            ],
            "exclude": [
                "PhD",
                # "2026",
                # "2025",
                # "Contract",
                # "Senior",
                # "Principal",
                # "Lead",
                # "Staff",
                "ios",
                # "sr",
            ]
        }
        self.qualification_filters = {
            "include": [
            ],
            "exclude": [
                "does not provide sponsorship",
            ]
        }
    
    def _find_prospective_keys_in_json(self, obj, main_key, path=[]):
        if isinstance(obj, dict):
            if main_key in obj:
                return obj[main_key]
            for key, value in obj.items():
                result = self._find_prospective_keys_in_json(value, main_key, path + [key])
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_prospective_keys_in_json(item, main_key, path)
                if result is not None:
                    return result
        return None

    def find_description_in_page(self, page):
        # Find all script tags with type="application/json"
        script_tags = page.query_selector_all('script[type="application/json"]')
        
        for script in script_tags:
            try:
                script_content = script.inner_text()
                if script_content:
                    json_data = json.loads(script_content)

                    minimum_qualifications = self._find_prospective_keys_in_json(json_data, "minimum_qualifications")
                    breakpoint()
                    preferred_qualifications = self._find_prospective_keys_in_json(json_data, "preferred_qualifications")
                    responsibilities = self._find_prospective_keys_in_json(json_data, "responsibilities")
                    qualifications = minimum_qualifications.extend(preferred_qualifications)
                    qualifications.extend(responsibilities)
                    description = " ".join(qualifications)
                    return description
            except Exception as e:
                continue

    def scrape_careers_page(self, max_jobs=None):
        """
        Scrape job listings from Meta's careers page.
        
        Args:
            max_jobs: Optional maximum number of jobs to scrape
            
        Returns:
            Dictionary mapping job_id to job data, or None if scraping fails.
            Job data should be dictionaries that can be converted to DataFrame rows.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()

                total_jobs = 0
                jobs_found = []
                def handle_jobs_from_response(response):
                    if (
                        "graphql" in response.url and 
                        response.status == 200  and
                        response.request.headers.get("x-fb-friendly-name", "") == "CareersJobSearchResultsV3DataQuery"
                    ):
                        try:
                            response_data = response.json()
                            nonlocal total_jobs
                            nonlocal jobs_found
                            
                            json_data = response_data.get("data", {})
                            jobs_json = json_data.get("job_search_with_featured_jobs", {})
                            featured_jobs = jobs_json.get("featured_jobs", [])
                            all_jobs = jobs_json.get("all_jobs", [])
                            all_jobs.extend(featured_jobs)
                            jobs_found = all_jobs
                            total_jobs = len(jobs_found)
                        except:
                            pass
                
                page.on("response", handle_jobs_from_response)
                page.goto(self.primary_url, wait_until="networkidle")
                page.wait_for_load_state("domcontentloaded")

                page.wait_for_timeout(2000)

                browser.close()
                return jobs_found


        except Exception as e:
            print(f"Error scraping careers url: {self.primary_url}")
            print(f"Error details: {str(e)}")
            return None
    
    def _login(self, page):
        try:
            page.goto(self.applications_url, wait_until="networkidle")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            email_input = page.locator('input').first
            email_input.fill(self.login_email)
            
            login_with_password = page.get_by_text("Log in with your password").first
            login_with_password.click()
            page.wait_for_timeout(1000)
            
            password_input = page.locator('input').first
            password_input.fill(self.login_password)
            
            login_button = page.get_by_role("button", name="Log in").first
            login_button.click()
            page.wait_for_timeout(10000)
            
            # Wait for the page to fully load after login
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
        except Exception as e:
            print(f"Error logging in: {str(e)}")
            return None
                
    def print_application_details(self ):
        df = self.filter_and_find_applications()
        console = Console()
        if len(df) > 0:
            table = Table(title=f"Filtered Applications Found: {len(df)}", show_header=True, header_style="bold magenta")
            table.add_column("Job ID", style="cyan", no_wrap=True)
            table.add_column("Role", style="green")
            table.add_column("Apply Link", style="blue", no_wrap=False)
            
            for index, row in df.iterrows():
                job_code = str(row['id'])
                role = row['title']
                apply_link = f"https://www.metacareers.com/profile/job_details/{row['id']}"
                table.add_row(job_code, role, apply_link)
            
            console.print(table)
        else:
            console.print(f"[yellow]No filtered applications found.[/yellow]")
            
    def scrape_applied_page(self):
        """
        Scrape the user's applied jobs page.
        
        Returns:
            List of applied job data (format depends on Meta's structure), or None if scraping fails.
            This data will be used by update_applications() to mark jobs as applied.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                self._login(page)
                # Extract JSON data from script tags in the HTML
                application_data = None
                try:
                    # Find all script tags with type="application/json"
                    script_tags = page.query_selector_all('script[type="application/json"]')
                    
                    for script in script_tags:
                        try:
                            script_content = script.inner_text()
                            if script_content:
                                json_data = json.loads(script_content)
                                
                                def find_prospective_applications(obj, main_key, path=[]):
                                    if isinstance(obj, dict):
                                        if main_key in obj:
                                            return obj[main_key]
                                        for key, value in obj.items():
                                            result = find_prospective_applications(value, main_key, path + [key])
                                            if result is not None:
                                                return result
                                    elif isinstance(obj, list):
                                        for item in obj:
                                            result = find_prospective_applications(item, main_key, path)
                                            if result is not None:
                                                return result
                                    return None
                                
                                application_data = find_prospective_applications(json_data, "prospective_applications")
                                
                                # If application_data exists, real_job_data should also exist
                                if application_data is not None:
                                    real_job_data = find_prospective_applications(json_data, "prospectiveApplications")
                                    
                                    if real_job_data is not None:
                                        # Create a mapping from real_job_data by some identifier (e.g., job_title or index)
                                        # Update IDs in application_data with IDs from real_job_data
                                        for i, app_item in enumerate(application_data):
                                            if isinstance(app_item, dict) and i < len(real_job_data):
                                                real_item = real_job_data[i]
                                                if isinstance(real_item, dict) and 'id' in real_item:
                                                    # Update the ID in application_data with the correct ID from real_job_data
                                                    app_item['id'] = real_item['id']
                                    
                                    break
                                    
                        except Exception as e:
                            continue
                    
                    if application_data:
                        return application_data
                    else:
                        print("Could not find prospective_applications in the page data")
                        return None
                        
                except Exception as e:
                    print(f"Error extracting application data from page: {str(e)}")
                    return None
                
        except Exception as e:
            print(f"Error scraping applied page: {self.applications_url}")
            print(f"Error details: {str(e)}")
            return None
    
    def filter_and_find_applications(self):
        """
        Filter jobs based on criteria and display filtered results.
        
        This method should:
        1. Filter jobs based on name_filters, qualification_filters, and location_filters
        2. Display the filtered results in a formatted table
        3. Adapt the format to Meta's data structure
        """
        filtered_df = self.jobs_df[self.jobs_df['applied'] == False]

        include_mask = self.jobs_df['title'].str.contains('|'.join(self.name_filters['include']), case=False, na=False)
        exclude_mask = self.jobs_df['title'].str.contains('|'.join(self.name_filters['exclude']), case=False, na=False)
        final_mask = include_mask & ~exclude_mask
        
        # Filter by locations
        location_mask = pd.Series([False] * len(self.jobs_df), index=self.jobs_df.index)
        for index, row in self.jobs_df.iterrows():
            job_locations = row.get('locations', [])
            # Handle both string representation of list and actual list
            if isinstance(job_locations, str):
                try:
                    job_locations = ast.literal_eval(job_locations)
                except (ValueError, SyntaxError):
                    job_locations = []
            if isinstance(job_locations, list):
                # Check if any job location matches any of our desired locations
                for job_loc in job_locations:
                    if any(desired_loc in str(job_loc) for desired_loc in self.locations):
                        location_mask.at[index] = True
                        break
        
        final_mask = final_mask & location_mask
        filtered_df = filtered_df[final_mask]
        
        return filtered_df
    
    def find_application_status(self):
        filtered_df = self.filter_and_find_applications()
        total_updated = 0

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                # Login once before checking all application statuses
                self._login(page)
                
                # Check application status for all jobs using the same page
                for index, row in tqdm(filtered_df.iterrows(), total=len(filtered_df), desc="Checking application statuses"):
                    job_id = row['id']
                    applied = self.jobs_df.at[index, 'applied']
                    description = self.jobs_df.at[index, 'description']
                    if not applied:
                        applied = self._find_application_status(job_id, page)
                        if applied:
                            total_updated += 1
                    self.jobs_df.at[index, 'applied'] = applied
                    if len(description) == 0:
                        description = self.find_description_in_page(page)
                        breakpoint()
                        self.jobs_df.at[index, 'description'] = description
                
                browser.close()
            
            # Save the updated dataframe to CSV after all checks are done
            self.jobs_df.to_csv(self.file_path, index=False)
            print(f"Updated application status for {total_updated} jobs and saved to {self.file_path}")
        except Exception as e:
            print(f"Error finding application status: {str(e)}")
            return False    
        
    def _find_application_status(self, id, page):
        try:
            page.goto(f"https://www.metacareers.com/profile/job_details/{id}", wait_until="networkidle")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            
            # Check for "View application" span - means already applied
            view_application = page.locator('span:has-text("View application")').first
            if view_application.count() > 0:
                return True
            
            # Check for "Apply Now" - means not applied
            apply_now = page.locator('span:has-text("Apply Now")').first
            if apply_now.count() > 0:
                return False
            
            # If neither found, default to False (not applied)
            return False
        except Exception as e:
            print(f"Error finding application status: {str(e)}")
            return False    
    
    def update_applications(self, find_status=True):
        """
        Update the jobs dataframe to mark jobs as applied.
        
        This method should:
        1. Call scrape_applied_page() to get applied jobs
        2. Match applied jobs with jobs in self.jobs_df
        3. Update the 'applied' column in self.jobs_df
        4. Save the updated dataframe to CSV
        """
        # Find applications of interest using filtered df and check if the status is applied on the website
        if find_status:
            self.find_application_status()
        self.print_application_details()

    
    def scrape_and_save_jobs(self, max_jobs=None):
        """
        Scrape jobs and save them to CSV, avoiding duplicates.
        
        Args:
            max_jobs: Optional maximum number of jobs to scrape
        """
        jobs = self.scrape_careers_page(max_jobs=max_jobs)
        previous_jobs = set(str(id) for id in self.jobs_df["id"].values) if self.jobs_df is not None else set()
        new_jobs = {job['id']: job for job in jobs if str(job['id']) not in previous_jobs}

        if new_jobs:
            # convert jobs dictionary to dataframe
            jobs_list = list(new_jobs.values())
            new_jobs_df = pd.DataFrame(jobs_list)
            new_jobs_df["applied"] = False
            new_jobs_df['description'] = ""
            new_jobs_df["id"] = new_jobs_df["id"].astype(str)
            new_jobs_df["description"] = new_jobs_df["description"].astype(str)
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

