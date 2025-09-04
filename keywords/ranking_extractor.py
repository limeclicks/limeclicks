"""
Ranking extraction service for processing SERP HTML and creating rank records
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

from services.google_search_parser import GoogleSearchParser
from services.r2_storage import get_r2_service
from .models import Keyword, Rank

logger = logging.getLogger(__name__)


class RankingExtractor:
    """
    Service for extracting rankings from SERP HTML and storing results
    """
    
    def __init__(self):
        self.parser = GoogleSearchParser()
        self.r2_service = get_r2_service()
    
    def process_serp_html(
        self,
        keyword: Keyword,
        html_content: str,
        scraped_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Process SERP HTML to extract rankings and create Rank record
        
        Args:
            keyword: Keyword model instance
            html_content: Raw SERP HTML
            scraped_date: Date when the SERP was scraped
        
        Returns:
            Dict with processing results or None if failed
        """
        try:
            # Parse HTML to extract search results
            parsed_results = self._parse_html(html_content)
            
            if not parsed_results:
                logger.error(f"Failed to parse HTML for keyword {keyword.id}")
                return None
            
            # Store parsed results in R2
            r2_path = self._store_results_in_r2(
                keyword,
                parsed_results,
                scraped_date
            )
            
            if not r2_path:
                logger.error(f"Failed to store results in R2 for keyword {keyword.id}")
                return None
            
            # Extract domain ranking
            rank_position, is_organic, rank_url = self._find_domain_rank(
                parsed_results,
                keyword.project.domain
            )
            
            # Detect SERP features
            serp_features = self._detect_serp_features(parsed_results)
            
            # Extract and store top 3 competitors in keyword
            self._update_keyword_competitors(keyword, parsed_results)
            
            # Track manual targets if any exist
            self._track_manual_targets(keyword, parsed_results)
            
            # Create Rank record
            rank = self._create_rank_record(
                keyword,
                rank_position,
                is_organic,
                serp_features,
                r2_path,
                scraped_date,
                rank_url
            )
            
            logger.info(
                f"Successfully processed ranking for keyword {keyword.id}: "
                f"rank={rank_position}, organic={is_organic}"
            )
            
            return {
                'success': True,
                'rank': rank_position,
                'is_organic': is_organic,
                'rank_id': rank.id,
                'r2_path': r2_path,
                'serp_features': serp_features
            }
            
        except Exception as e:
            logger.error(f"Error processing SERP for keyword {keyword.id}: {e}")
            return None
    
    def _parse_html(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        Parse HTML using GoogleSearchParser
        
        Args:
            html_content: Raw SERP HTML
        
        Returns:
            Parsed results dict or None if failed
        """
        try:
            parsed = self.parser.parse(html_content)
            return parsed
        except Exception as e:
            logger.error(f"HTML parsing error: {e}")
            return None
    
    def _store_results_in_r2(
        self,
        keyword: Keyword,
        parsed_results: Dict[str, Any],
        scraped_date: datetime
    ) -> Optional[str]:
        """
        Store parsed results in R2 storage
        
        Args:
            keyword: Keyword model instance
            parsed_results: Parsed search results
            scraped_date: Date of scraping
        
        Returns:
            R2 path or None if failed
        """
        try:
            # Build R2 path: domain/keyword/YYYY-MM-DD.json
            date_str = scraped_date.strftime('%Y-%m-%d')
            # Clean keyword for use in path (replace spaces and special chars)
            clean_keyword = keyword.keyword.lower().replace(' ', '-').replace('/', '-')
            r2_path = f"{keyword.project.domain}/{clean_keyword}/{date_str}.json"
            
            # Add metadata to results
            results_with_metadata = {
                'keyword': keyword.keyword,
                'project_id': keyword.project_id,
                'project_domain': keyword.project.domain,
                'country': keyword.country,
                'location': keyword.location,
                'scraped_at': scraped_date.isoformat(),
                'results': parsed_results
            }
            
            # Upload to R2
            result = self.r2_service.upload_json(
                results_with_metadata,
                r2_path
            )
            
            if result.get('success'):
                logger.info(f"Stored parsed results in R2: {r2_path}")
                return r2_path
            else:
                logger.error(f"Failed to upload to R2: {result.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Error storing results in R2: {e}")
            return None
    
    def _find_domain_rank(
        self,
        parsed_results: Dict[str, Any],
        domain: str
    ) -> Tuple[int, bool, Optional[str]]:
        """
        Find domain ranking in search results (1-100)
        
        Args:
            parsed_results: Parsed search results
            domain: Domain to search for (e.g., 'example.com')
        
        Returns:
            Tuple of (rank_position, is_organic, url)
            Returns (0, True, None) if not found
        """
        # Normalize domain (remove protocol, www, trailing slash)
        domain = self._normalize_domain(domain)
        
        # Check organic results first (1-100)
        organic_results = parsed_results.get('organic_results', [])
        for position, result in enumerate(organic_results[:100], 1):
            result_url = result.get('url', '')
            result_domain = self._extract_domain(result_url)
            
            if self._domains_match(domain, result_domain):
                logger.info(f"Found domain {domain} at organic position {position}")
                return position, True, result_url
        
        # Check sponsored results (also numbered 1-100 but marked as non-organic)
        sponsored_results = parsed_results.get('sponsored_results', [])
        for position, result in enumerate(sponsored_results[:100], 1):
            result_url = result.get('url', '')
            result_domain = self._extract_domain(result_url)
            
            if self._domains_match(domain, result_domain):
                logger.info(f"Found domain {domain} at sponsored position {position}")
                return position, False, result_url
        
        # Not found in top 100
        logger.info(f"Domain {domain} not found in top 100 results")
        return 0, True, None
    
    def _normalize_domain(self, domain: str) -> str:
        """
        Normalize domain for comparison
        
        Args:
            domain: Domain string
        
        Returns:
            Normalized domain
        """
        if not domain:
            return ''
        
        # Remove common prefixes and suffixes
        domain = domain.lower().strip()
        domain = domain.replace('http://', '').replace('https://', '')
        domain = domain.replace('www.', '')
        domain = domain.rstrip('/')
        
        return domain
    
    def _extract_domain(self, url: str) -> str:
        """
        Extract domain from URL
        
        Args:
            url: Full URL
        
        Returns:
            Domain part of URL
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            return self._normalize_domain(domain)
        except:
            return self._normalize_domain(url)
    
    def _domains_match(self, domain1: str, domain2: str) -> bool:
        """
        Check if two domains match
        
        Args:
            domain1: First domain (the project domain we're looking for)
            domain2: Second domain (from search results)
        
        Returns:
            True if domains match
        """
        # Exact match
        if domain1 == domain2:
            return True
        
        # Check if domain2 is a subdomain of domain1
        # e.g., domain1='example.com', domain2='www.example.com' or 'sub.example.com'
        if domain1 and domain2:
            # Ensure we're checking proper subdomain relationship
            if domain2.endswith('.' + domain1):
                return True
            # Also check if domain1 is a subdomain of domain2 (less common)
            if domain1.endswith('.' + domain2):
                return True
        
        return False
    
    def _detect_serp_features(self, parsed_results: Dict[str, Any]) -> Dict[str, bool]:
        """
        Detect SERP features present in results
        
        Args:
            parsed_results: Parsed search results
        
        Returns:
            Dict of feature flags
        """
        return {
            'has_map_result': bool(
                parsed_results.get('local_pack') or 
                parsed_results.get('map_results')
            ),
            'has_video_result': bool(
                parsed_results.get('videos') or
                parsed_results.get('video_results') or
                parsed_results.get('video_carousel')
            ),
            'has_image_result': bool(
                parsed_results.get('images') or
                parsed_results.get('image_results') or
                parsed_results.get('image_pack')
            ),
            'has_featured_snippet': bool(parsed_results.get('featured_snippet')),
            'has_knowledge_graph': bool(parsed_results.get('knowledge_graph')),
            'has_people_also_ask': bool(parsed_results.get('people_also_ask')),
            'has_shopping_results': bool(
                parsed_results.get('shopping') or
                parsed_results.get('shopping_results')
            ),
            'has_news_results': bool(parsed_results.get('news_results')),
            'has_related_searches': bool(parsed_results.get('related_searches')),
        }
    
    def _update_keyword_competitors(self, keyword: Keyword, parsed_results: Dict[str, Any]) -> None:
        """
        Update keyword's top 3 competitors (excluding own domain)
        Stores them directly in the keyword model instead of creating Target entries
        
        Args:
            keyword: Keyword model instance
            parsed_results: Parsed search results from GoogleSearchParser
        """
        try:
            # Get organic results
            organic_results = parsed_results.get('organic_results', [])
            
            if not organic_results:
                logger.debug(f"No organic results found for keyword {keyword.id}")
                keyword.top_competitors = []
                keyword.save(update_fields=['top_competitors'])
                return
            
            # Get project domain to exclude it
            project_domain = self._normalize_domain(keyword.project.domain)
            
            # Find top 3 unique competitors (excluding own domain)
            top_competitors = []
            seen_domains = set()
            
            for position, result in enumerate(organic_results[:20], 1):  # Check top 20 to find 3 competitors
                result_url = result.get('url', '')
                result_domain = self._extract_domain(result_url)
                
                # Skip if it's the project's own domain
                if self._domains_match(project_domain, result_domain):
                    continue
                
                # Skip if we already have this domain
                if result_domain in seen_domains:
                    continue
                
                seen_domains.add(result_domain)
                
                # Add to top competitors
                top_competitors.append({
                    'domain': result_domain,
                    'position': position,
                    'url': result_url
                })
                
                # Stop once we have 3 competitors
                if len(top_competitors) >= 3:
                    break
            
            logger.info(f"Found {len(top_competitors)} top competitors for keyword '{keyword.keyword}'")
            
            # Update keyword with top competitors
            keyword.top_competitors = top_competitors
            keyword.save(update_fields=['top_competitors'])
            
            # If we found fewer than 3 competitors in top 20, log it
            if len(top_competitors) < 3:
                logger.info(f"Only found {len(top_competitors)} competitors in top 20 for keyword '{keyword.keyword}'")
                        
        except Exception as e:
            logger.error(f"Error updating competitors for keyword {keyword.id}: {str(e)}")
            # Don't raise - competitor tracking shouldn't break main keyword tracking
    
    def _track_manual_targets(self, keyword: Keyword, parsed_results: Dict[str, Any]) -> None:
        """
        Track rankings for manually added targets
        
        Args:
            keyword: Keyword model instance
            parsed_results: Parsed search results from GoogleSearchParser
        """
        try:
            # Import here to avoid circular imports
            from competitors.models import Target, TargetKeywordRank
            
            # Get manual targets for this project
            manual_targets = Target.objects.filter(
                project=keyword.project,
                is_manual=True
            )
            
            if not manual_targets.exists():
                return
            
            # Get organic results
            organic_results = parsed_results.get('organic_results', [])
            
            for target in manual_targets:
                # Find target in results
                target_domain = self._normalize_domain(target.domain)
                found = False
                
                for position, result in enumerate(organic_results[:100], 1):
                    result_url = result.get('url', '')
                    result_domain = self._extract_domain(result_url)
                    
                    if self._domains_match(target_domain, result_domain):
                        # Found target ranking
                        TargetKeywordRank.objects.update_or_create(
                            target=target,
                            keyword=keyword,
                            defaults={
                                'rank': position,
                                'rank_url': result_url,
                                'scraped_at': timezone.now()
                            }
                        )
                        found = True
                        logger.info(f"Tracked manual target {target.domain} at position {position} for keyword '{keyword.keyword}'")
                        break
                
                if not found:
                    # Target not found in results - create entry with rank 0
                    TargetKeywordRank.objects.update_or_create(
                        target=target,
                        keyword=keyword,
                        defaults={
                            'rank': 0,
                            'rank_url': '',
                            'scraped_at': timezone.now()
                        }
                    )
                    logger.info(f"Manual target {target.domain} not found in top 100 for keyword '{keyword.keyword}'")
                        
        except Exception as e:
            logger.error(f"Error tracking manual targets for keyword {keyword.id}: {str(e)}")
            # Don't raise - target tracking shouldn't break main keyword tracking
    
    def _create_rank_record(
        self,
        keyword: Keyword,
        rank_position: int,
        is_organic: bool,
        serp_features: Dict[str, bool],
        r2_path: str,
        scraped_date: datetime,
        rank_url: Optional[str] = None
    ) -> Rank:
        """
        Create Rank record with extracted data
        
        Args:
            keyword: Keyword model instance
            rank_position: Position in search results (0 if not found)
            is_organic: True if organic, False if sponsored
            serp_features: Dictionary of SERP feature flags
            r2_path: Path to JSON file in R2
            scraped_date: Date when scraped
        
        Returns:
            Created Rank instance
        """
        # Ensure scraped_date is timezone-aware
        if timezone.is_naive(scraped_date):
            scraped_date = timezone.make_aware(scraped_date)
        
        # Create rank object and attach URL for the save method to use
        rank = Rank(
            keyword=keyword,
            rank=rank_position,
            is_organic=is_organic,
            has_map_result=serp_features.get('has_map_result', False),
            has_video_result=serp_features.get('has_video_result', False),
            has_image_result=serp_features.get('has_image_result', False),
            search_results_file=r2_path,
            created_at=scraped_date  # Use the scraping date as created_at
        )
        
        # Attach URL to be used in save method
        if rank_url:
            rank._rank_url = rank_url
        
        # Save the rank (this will trigger keyword.update_rank)
        rank.save()
        
        # The Rank model's save method will automatically update the keyword's rank
        logger.info(
            f"Created Rank record: id={rank.id}, keyword={keyword.id}, "
            f"position={rank_position}, date={scraped_date.date()}"
        )
        
        return rank


def process_stored_html(
    keyword_id: int,
    html_path: str,
    scraped_date: Optional[datetime] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to process stored HTML file
    
    Args:
        keyword_id: ID of the keyword
        html_path: Path to HTML file (relative to SCRAPE_DO_STORAGE_ROOT)
        scraped_date: Date when scraped (defaults to parsing from filename)
    
    Returns:
        Processing results or None if failed
    """
    try:
        keyword = Keyword.objects.get(id=keyword_id)
    except Keyword.DoesNotExist:
        logger.error(f"Keyword {keyword_id} not found")
        return None
    
    # Read HTML from local storage
    storage_root = Path(settings.SCRAPE_DO_STORAGE_ROOT)
    html_file = storage_root / html_path
    
    if not html_file.exists():
        logger.error(f"HTML file not found: {html_path}")
        return None
    
    html_content = html_file.read_text(encoding='utf-8')
    
    # Parse date from filename if not provided
    if not scraped_date:
        try:
            # Extract date from filename (assumes YYYY-MM-DD.html format)
            date_str = html_file.stem  # Gets filename without extension
            scraped_date = datetime.strptime(date_str, '%Y-%m-%d')
            scraped_date = timezone.make_aware(scraped_date)
        except:
            scraped_date = timezone.now()
    
    # Process the HTML
    extractor = RankingExtractor()
    return extractor.process_serp_html(keyword, html_content, scraped_date)