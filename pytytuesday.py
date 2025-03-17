"""
TidyTuesdayPy: Access the Weekly 'TidyTuesday' Project Dataset in Python

This package provides tools to easily download data from the TidyTuesday project,
a weekly data project by the Data Science Learning Community.
"""

import os
import re
import json
import datetime
import tempfile
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

import requests
import pandas as pd
from bs4 import BeautifulSoup


class TidyTuesdayPy:
    """Main class for TidyTuesdayPy package."""
    
    GITHUB_API_URL = "https://api.github.com/repos/rfordatascience/tidytuesday/contents/data"
    RAW_GITHUB_URL = "https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data"
    
    def __init__(self):
        """Initialize the TidyTuesdayPy class."""
        self.rate_limit_remaining = None
        self._update_rate_limit()
    
    def _update_rate_limit(self):
        """Check GitHub API rate limit."""
        try:
            response = requests.get("https://api.github.com/rate_limit")
            if response.status_code == 200:
                data = response.json()
                self.rate_limit_remaining = data["resources"]["core"]["remaining"]
        except Exception:
            self.rate_limit_remaining = None
    
    def rate_limit_check(self, quiet: bool = False) -> int:
        """
        Check the GitHub API rate limit.
        
        Args:
            quiet: If True, don't print rate limit info
            
        Returns:
            Number of requests remaining
        """
        self._update_rate_limit()
        
        if not quiet and self.rate_limit_remaining is not None:
            print(f"Requests remaining: {self.rate_limit_remaining}")
        
        return self.rate_limit_remaining if self.rate_limit_remaining is not None else 0
    
    def last_tuesday(self, date: Optional[str] = None) -> str:
        """
        Find the most recent Tuesday relative to a specified date.
        
        Args:
            date: A date string in YYYY-MM-DD format. Defaults to today's date.
            
        Returns:
            The TidyTuesday date in the same week as the specified date
        """
        if date is None:
            # Use New York timezone to match the R package
            now = datetime.datetime.now(datetime.timezone.utc)
            ny_offset = -4  # Simplified offset for Eastern Time
            now = now + datetime.timedelta(hours=ny_offset)
            date = now.strftime("%Y-%m-%d")
        
        # Convert string to datetime
        if isinstance(date, str):
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = date
        
        # Find the most recent Tuesday (weekday 1)
        days_since_tuesday = (date_obj.weekday() - 1) % 7
        last_tues = date_obj - datetime.timedelta(days=days_since_tuesday)
        
        return last_tues.strftime("%Y-%m-%d")
    
    def tt_available(self) -> Dict[str, List[Dict[str, str]]]:
        """
        List all available TidyTuesday datasets across all years.
        
        Returns:
            Dictionary with years as keys and lists of datasets as values
        """
        if self.rate_limit_check(quiet=True) < 5:
            print("GitHub API rate limit is too low. Try again later.")
            return {}
        
        try:
            # Get list of years
            response = requests.get(self.GITHUB_API_URL)
            if response.status_code != 200:
                print(f"Error fetching data: {response.status_code}")
                return {}
            
            years_data = response.json()
            years = [item["name"] for item in years_data if item["type"] == "dir"]
            
            # Get datasets for each year
            all_datasets = {}
            for year in years:
                datasets = self.tt_datasets(year, print_output=False)
                all_datasets[year] = datasets
            
            # Print the results
            print("Available TidyTuesday Datasets:")
            print("==============================")
            for year, datasets in all_datasets.items():
                print(f"\n{year}:")
                for dataset in datasets:
                    print(f"  {dataset['date']} - {dataset['title']}")
            
            return all_datasets
            
        except Exception as e:
            print(f"Error: {e}")
            return {}
    
    def tt_datasets(self, year: Union[str, int], print_output: bool = True) -> List[Dict[str, str]]:
        """
        List available TidyTuesday datasets for a specific year.
        
        Args:
            year: The year to get datasets for
            print_output: Whether to print the results
            
        Returns:
            List of dictionaries with dataset information
        """
        if self.rate_limit_check(quiet=True) < 5:
            print("GitHub API rate limit is too low. Try again later.")
            return []
        
        try:
            year = str(year)
            url = f"{self.GITHUB_API_URL}/{year}"
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"Error fetching data for year {year}: {response.status_code}")
                return []
            
            data = response.json()
            folders = [item for item in data if item["type"] == "dir"]
            
            datasets = []
            for folder in folders:
                week_name = folder["name"]
                # Try to extract date from folder name (format: YYYY-MM-DD)
                if re.match(r"^\d{4}-\d{2}-\d{2}$", week_name):
                    date = week_name
                    
                    # Try to get README to extract title
                    readme_url = f"{self.RAW_GITHUB_URL}/{year}/{date}/README.md"
                    readme_response = requests.get(readme_url)
                    
                    title = "Unknown"
                    if readme_response.status_code == 200:
                        readme_content = readme_response.text
                        # Try to extract title from the first heading
                        title_match = re.search(r"#\s+(.*?)(?:\n|$)", readme_content)
                        if title_match:
                            title = title_match.group(1).strip()
                    
                    datasets.append({
                        "date": date,
                        "title": title,
                        "path": f"{year}/{date}"
                    })
            
            # Sort by date
            datasets.sort(key=lambda x: x["date"])
            
            if print_output:
                print(f"Available TidyTuesday Datasets for {year}:")
                print("======================================")
                for dataset in datasets:
                    print(f"{dataset['date']} - {dataset['title']}")
            
            return datasets
            
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def tt_load_gh(self, date_or_year: Union[str, int], week: Optional[int] = None) -> Dict[str, Any]:
        """
        Load TidyTuesday metadata from GitHub.
        
        Args:
            date_or_year: Either a date string (YYYY-MM-DD) or a year (YYYY)
            week: If date_or_year is a year, which week number to use
            
        Returns:
            A dictionary with metadata about the TidyTuesday dataset
        """
        if self.rate_limit_check(quiet=True) < 5:
            print("GitHub API rate limit is too low. Try again later.")
            return {}
        
        try:
            # Handle year and week number
            if week is not None:
                year = str(date_or_year)
                # Get list of weeks for the year
                datasets = self.tt_datasets(year, print_output=False)
                if not datasets:
                    print(f"No datasets found for year {year}")
                    return {}
                
                if week < 1 or week > len(datasets):
                    print(f"Week number {week} is out of range for year {year}")
                    return {}
                
                # Adjust for 0-based indexing
                date = datasets[week - 1]["date"]
            else:
                # Handle direct date
                date = str(date_or_year)
                year = date[:4]
            
            # Get files for the week
            url = f"{self.GITHUB_API_URL}/{year}/{date}"
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"Error fetching data for {date}: {response.status_code}")
                return {}
            
            files_data = response.json()
            files = []
            
            for item in files_data:
                if item["type"] == "file" and not item["name"].lower().startswith("readme"):
                    files.append({
                        "name": item["name"],
                        "download_url": item["download_url"],
                        "path": item["path"]
                    })
            
            # Get README content
            readme_url = f"{self.RAW_GITHUB_URL}/{year}/{date}/README.md"
            readme_response = requests.get(readme_url)
            readme_content = readme_response.text if readme_response.status_code == 200 else ""
            
            # Create HTML version of README for display
            readme_html = self._markdown_to_html(readme_content)
            
            return {
                "date": date,
                "year": year,
                "files": files,
                "readme_content": readme_content,
                "readme_html": readme_html
            }
            
        except Exception as e:
            print(f"Error: {e}")
            return {}
    
    def tt_download_file(self, tt_data: Dict[str, Any], file_identifier: Union[str, int]) -> pd.DataFrame:
        """
        Download a specific file from a TidyTuesday dataset.
        
        Args:
            tt_data: TidyTuesday metadata from tt_load_gh
            file_identifier: Either the file name or index (0-based)
            
        Returns:
            A pandas DataFrame with the file contents
        """
        if not tt_data or "files" not in tt_data:
            print("Invalid TidyTuesday data. Use tt_load_gh first.")
            return pd.DataFrame()
        
        try:
            files = tt_data["files"]
            
            if isinstance(file_identifier, int):
                if file_identifier < 0 or file_identifier >= len(files):
                    print(f"File index {file_identifier} is out of range")
                    return pd.DataFrame()
                file_info = files[file_identifier]
            else:
                # Find by name
                file_info = next((f for f in files if f["name"] == file_identifier), None)
                if not file_info:
                    print(f"File '{file_identifier}' not found")
                    return pd.DataFrame()
            
            print(f"Downloading {file_info['name']}...")
            response = requests.get(file_info["download_url"])
            
            if response.status_code != 200:
                print(f"Error downloading file: {response.status_code}")
                return pd.DataFrame()
            
            # Determine file type and read accordingly
            file_name = file_info["name"].lower()
            
            # Save to a temporary file first
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            
            # Read the file based on its extension
            if file_name.endswith('.csv'):
                df = pd.read_csv(tmp_path)
            elif file_name.endswith('.tsv'):
                df = pd.read_csv(tmp_path, sep='\t')
            elif file_name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(tmp_path)
            elif file_name.endswith('.json'):
                df = pd.read_json(tmp_path)
            else:
                print(f"Unsupported file format: {file_name}")
                os.unlink(tmp_path)
                return pd.DataFrame()
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            print(f"Successfully loaded {file_info['name']}")
            return df
            
        except Exception as e:
            print(f"Error downloading file: {e}")
            return pd.DataFrame()
    
    def tt_download(self, tt_data: Dict[str, Any], files: Union[str, List[str]] = "All") -> Dict[str, pd.DataFrame]:
        """
        Download all or specific files from a TidyTuesday dataset.
        
        Args:
            tt_data: TidyTuesday metadata from tt_load_gh
            files: Either "All" to download all files, or a list of file names
            
        Returns:
            Dictionary mapping file names to pandas DataFrames
        """
        if not tt_data or "files" not in tt_data:
            print("Invalid TidyTuesday data. Use tt_load_gh first.")
            return {}
        
        try:
            available_files = tt_data["files"]
            
            if files == "All":
                files_to_download = available_files
            else:
                if isinstance(files, str):
                    files = [files]
                
                files_to_download = []
                for file_name in files:
                    file_info = next((f for f in available_files if f["name"] == file_name), None)
                    if file_info:
                        files_to_download.append(file_info)
                    else:
                        print(f"Warning: File '{file_name}' not found")
            
            result = {}
            for file_info in files_to_download:
                file_name = file_info["name"]
                print(f"Downloading {file_name}...")
                
                response = requests.get(file_info["download_url"])
                
                if response.status_code != 200:
                    print(f"Error downloading {file_name}: {response.status_code}")
                    continue
                
                # Save to a temporary file first
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name
                
                # Read the file based on its extension
                file_name_lower = file_name.lower()
                try:
                    if file_name_lower.endswith('.csv'):
                        df = pd.read_csv(tmp_path)
                    elif file_name_lower.endswith('.tsv'):
                        df = pd.read_csv(tmp_path, sep='\t')
                    elif file_name_lower.endswith(('.xls', '.xlsx')):
                        df = pd.read_excel(tmp_path)
                    elif file_name_lower.endswith('.json'):
                        df = pd.read_json(tmp_path)
                    else:
                        print(f"Unsupported file format: {file_name}")
                        continue
                    
                    # Store in result dictionary, using the name without extension as the key
                    key = os.path.splitext(file_name)[0]
                    result[key] = df
                    print(f"Successfully loaded {file_name}")
                    
                except Exception as e:
                    print(f"Error processing {file_name}: {e}")
                
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_path)
            
            return result
            
        except Exception as e:
            print(f"Error downloading files: {e}")
            return {}
    
    def tt_load(self, date_or_year: Union[str, int], week: Optional[int] = None, 
                files: Union[str, List[str]] = "All") -> Dict[str, Any]:
        """
        Load TidyTuesday data from GitHub.
        
        Args:
            date_or_year: Either a date string (YYYY-MM-DD) or a year (YYYY)
            week: If date_or_year is a year, which week number to use
            files: Either "All" to download all files, or a list of file names
            
        Returns:
            Dictionary with the downloaded data and metadata
        """
        # First get the metadata
        tt_data = self.tt_load_gh(date_or_year, week)
        
        if not tt_data:
            return {}
        
        # Then download the data
        data = self.tt_download(tt_data, files)
        
        # Combine metadata and data
        result = {
            "date": tt_data["date"],
            "year": tt_data["year"],
            "readme_content": tt_data["readme_content"],
            "readme_html": tt_data["readme_html"],
            **data  # Add all the dataframes
        }
        
        return result
    
    def readme(self, tt_data: Dict[str, Any]) -> None:
        """
        Display the README for a TidyTuesday dataset.
        
        Args:
            tt_data: TidyTuesday data from tt_load or tt_load_gh
        """
        if not tt_data or "readme_html" not in tt_data:
            print("No README available for this dataset.")
            return
        
        # Create a temporary HTML file and open it in the browser
        with tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w') as tmp:
            tmp.write(tt_data["readme_html"])
            tmp_path = tmp.name
        
        webbrowser.open(f"file://{tmp_path}")
        print(f"README opened in your browser.")
    
    def _markdown_to_html(self, markdown: str) -> str:
        """
        Convert markdown to HTML.
        
        Args:
            markdown: Markdown text
            
        Returns:
            HTML representation of the markdown
        """
        # Simple conversion for headings, links, and code blocks
        html = markdown
        
        # Convert headings
        html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        
        # Convert links
        html = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html)
        
        # Convert code blocks
        html = re.sub(r'```(.*?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
        
        # Convert line breaks
        html = html.replace('\n', '<br>')
        
        # Wrap in HTML document
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TidyTuesday README</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                h1, h2, h3 {{ color: #333; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; }}
                a {{ color: #0366d6; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        
        return html


# Convenience functions that create an instance and call the methods

def last_tuesday(date=None):
    """Find the most recent Tuesday relative to a specified date."""
    tt = TidyTuesdayPy()
    return tt.last_tuesday(date)

def tt_available():
    """List all available TidyTuesday datasets."""
    tt = TidyTuesdayPy()
    return tt.tt_available()

def tt_datasets(year):
    """List available TidyTuesday datasets for a specific year."""
    tt = TidyTuesdayPy()
    return tt.tt_datasets(year)

def tt_load_gh(date_or_year, week=None):
    """Load TidyTuesday metadata from GitHub."""
    tt = TidyTuesdayPy()
    return tt.tt_load_gh(date_or_year, week)

def tt_download_file(tt_data, file_identifier):
    """Download a specific file from a TidyTuesday dataset."""
    tt = TidyTuesdayPy()
    return tt.tt_download_file(tt_data, file_identifier)

def tt_download(tt_data, files="All"):
    """Download all or specific files from a TidyTuesday dataset."""
    tt = TidyTuesdayPy()
    return tt.tt_download(tt_data, files)

def tt_load(date_or_year, week=None, files="All"):
    """Load TidyTuesday data from GitHub."""
    tt = TidyTuesdayPy()
    return tt.tt_load(date_or_year, week, files)

def readme(tt_data):
    """Display the README for a TidyTuesday dataset."""
    tt = TidyTuesdayPy()
    return tt.readme(tt_data)

def rate_limit_check(quiet=False):
    """Check the GitHub API rate limit."""
    tt = TidyTuesdayPy()
    return tt.rate_limit_check(quiet)

def get_date(week):
    """
    Takes a week in string form and downloads the TidyTuesday data files from the Github repo.
    
    Args:
        week: Week in YYYY-MM-DD format
    """
    tt = TidyTuesdayPy()
    data = tt.tt_load(week)
    return data

def get_week(year, week_num):
    """
    Takes a year and a week number, and downloads the TidyTuesday data files from the Github repo.
    
    Args:
        year: Year (YYYY)
        week_num: Week number (1-based)
    """
    tt = TidyTuesdayPy()
    data = tt.tt_load(year, week=week_num)
    return data
