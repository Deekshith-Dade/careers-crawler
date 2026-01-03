import os
from abc import ABC, abstractmethod
import pandas as pd


class BaseCareersScraper(ABC):
    """
    Abstract base class for career page scrapers.
    
    Subclasses must implement the abstract methods to define company-specific
    scraping logic while inheriting common functionality.
    """
    
    def __init__(self, company_name: str, base_url: str, file_path: str = None, locations: list = None):
        """
        Initialize the base scraper.
        
        Args:
            company_name: Name of the company (used for file paths and identification)
            base_url: Base URL of the company's careers page
            file_path: Optional custom file path for CSV storage. If None, uses default format.
            locations: List of location names to filter by
        """
        self.company_name = company_name
        self.base_url = base_url
        
        # Set up file path
        if file_path is None:
            self.file_path = f"data/{company_name.lower()}_careers/{company_name.lower()}_jobs.csv"
        else:
            self.file_path = file_path
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        
        # Set up locations
        self.locations = locations if locations is not None else []
        self.location_filters = self.locations
        
        # Initialize filters (subclasses can override these)
        self.name_filters = {
            "include": [],
            "exclude": []
        }
        self.qualification_filters = {
            "include": [],
            "exclude": []
        }
        
        # Load existing jobs dataframe
        if os.path.exists(self.file_path):
            self.jobs_df = pd.read_csv(self.file_path, dtype={"id": str})
        else:
            self.jobs_df = None
    
    @abstractmethod
    def scrape_careers_page(self, max_jobs=None):
        """
        Scrape job listings from the company's careers page.
        
        Args:
            max_jobs: Optional maximum number of jobs to scrape
            
        Returns:
            Dictionary mapping job_id to job data, or None if scraping fails.
            Job data should be dictionaries that can be converted to DataFrame rows.
        """
        pass
    
    @abstractmethod
    def scrape_applied_page(self):
        """
        Scrape the user's applied jobs page.
        
        Returns:
            List of applied job data (format depends on company), or None if scraping fails.
            This data will be used by update_applications() to mark jobs as applied.
        """
        pass
    
    @abstractmethod
    def filter_and_find_applications(self):
        """
        Filter jobs based on criteria and display filtered results.
        
        This method should:
        1. Filter jobs based on name_filters, qualification_filters, and location_filters
        2. Display the filtered results in a formatted table
        3. The format and data structure may vary by company
        """
        pass
    
    @abstractmethod
    def update_applications(self):
        """
        Update the jobs dataframe to mark jobs as applied.
        
        This method should:
        1. Call scrape_applied_page() to get applied jobs
        2. Match applied jobs with jobs in self.jobs_df
        3. Update the 'applied' column in self.jobs_df
        4. Save the updated dataframe to CSV
        """
        pass
    
    @abstractmethod
    def scrape_and_save_jobs(self, max_jobs=None):
        """
        Scrape jobs and save them to CSV, avoiding duplicates.
        
        Args:
            max_jobs: Optional maximum number of jobs to scrape
            
        Note: Implementation may vary by company based on their data structure
        and scraping requirements.
        """
        pass

