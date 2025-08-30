"""
Crawl Overview Parser for Screaming Frog crawl_overview.csv
"""

import csv
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CrawlOverviewParser:
    """Parser for crawl_overview.csv from Screaming Frog"""
    
    def __init__(self, temp_audit_dir, site_audit=None):
        self.temp_audit_dir = temp_audit_dir
        self.site_audit = site_audit
        self.crawl_overview_file = Path(temp_audit_dir) / 'crawl_overview.csv'
    
    def parse(self):
        """
        Parse crawl_overview.csv and extract required fields.
        If site_audit is provided, also saves the data to the model.
        
        Returns:
            dict: Parsed crawl overview data
        """
        if not self.crawl_overview_file.exists():
            logger.error(f"crawl_overview.csv not found at: {self.crawl_overview_file}")
            return None
        
        try:
            crawl_data = {
                'total_urls_encountered': 0,
                'total_urls_crawled': 0,
                'top_20_inlinks': []
            }
            
            with open(self.crawl_overview_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                
                # Extract data from each row
                for row in reader:
                    if len(row) >= 2:
                        key = row[0].strip().strip('"')
                        value = row[1].strip().strip('"')
                        
                        # Look for total URLs encountered and crawled
                        if key == 'Total URLs Encountered':
                            try:
                                crawl_data['total_urls_encountered'] = int(value)
                            except (ValueError, TypeError):
                                pass
                        
                        if key == 'Total URLs Crawled':
                            try:
                                crawl_data['total_urls_crawled'] = int(value)
                            except (ValueError, TypeError):
                                pass
                        
                        # Extract URLs for top inlinks (look for URL-like patterns)
                        if (value.startswith('http') and 
                            len(crawl_data['top_20_inlinks']) < 20 and
                            value not in crawl_data['top_20_inlinks']):
                            crawl_data['top_20_inlinks'].append(value)
            
            logger.info(f"Parsed crawl overview: {crawl_data['total_urls_crawled']} URLs crawled")
            
            # Save data to site_audit if provided
            if self.site_audit and crawl_data:
                from django.utils import timezone
                
                print(f"✅ Parsed crawl overview data: {crawl_data}")
                
                # Save crawl overview data
                self.site_audit.crawl_overview = crawl_data
                
                # Update total_pages_crawled from crawl overview
                if crawl_data.get('total_urls_crawled'):
                    self.site_audit.total_pages_crawled = crawl_data['total_urls_crawled']
                    print(f"📊 Updated pages crawled: {self.site_audit.total_pages_crawled}")
                
                # Update timestamp but NOT status (let issues_overview handle that)
                self.site_audit.last_audit_date = timezone.now()
                
                # Save only the fields we've updated (not health score or status)
                self.site_audit.save(update_fields=['crawl_overview', 'total_pages_crawled', 'last_audit_date'])
                logger.info(f"Saved crawl overview data to site_audit: {self.site_audit.id}")
            
            return crawl_data
            
        except Exception as e:
            logger.error(f"Error parsing crawl_overview.csv: {e}")
            if self.site_audit:
                self.site_audit.status = 'failed'
                self.site_audit.save()
            return None
    
    def extract_top_inlinks_from_internal_csv(self):
        """
        Extract top 20 inlinks from internal_all.csv as fallback
        
        Returns:
            list: Top 20 internal URLs
        """
        internal_file = Path(self.temp_audit_dir) / 'internal_all.csv'
        
        if not internal_file.exists():
            logger.warning("internal_all.csv not found for inlinks extraction")
            return []
        
        try:
            inlinks = []
            with open(internal_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for i, row in enumerate(reader):
                    if i >= 20:  # Limit to top 20
                        break
                    
                    url = row.get('Address', '').strip()
                    if url:
                        inlinks.append(url)
            
            logger.info(f"Extracted {len(inlinks)} inlinks from internal_all.csv")
            return inlinks
            
        except Exception as e:
            logger.error(f"Error extracting inlinks from internal_all.csv: {e}")
            return []