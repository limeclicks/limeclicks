"""
Scrape.do API Service for web scraping functionality
Documentation: https://scrape.do/documentation/
"""

import logging
import requests
from urllib.parse import quote, urlencode
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
import hashlib
import json
import base64

logger = logging.getLogger(__name__)


class ScrapeDoService:
    """
    Service class for interacting with Scrape.do API
    
    Usage:
        scraper = ScrapeDoService()
        result = scraper.scrape("https://example.com", country_code="us")
    """
    
    BASE_URL = "https://api.scrape.do"
    DEFAULT_TIMEOUT = 60  # Increased to 60 seconds for Google searches
    CACHE_TTL = 3600  # 1 hour cache for successful responses
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Scrape.do service
        
        Args:
            api_key: Optional API key. If not provided, uses SCRAPPER_API_KEY from settings
        """
        self.api_key = api_key or getattr(settings, 'SCRAPPER_API_KEY', None)
        if not self.api_key:
            raise ValueError("SCRAPPER_API_KEY not found in settings or environment")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'LimeClicks-Scraper/1.0'
        })
    
    def scrape(
        self, 
        url: str, 
        country_code: Optional[str] = None,
        render: bool = False,
        wait_for: Optional[int] = None,
        block_resources: Optional[bool] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape a URL using Scrape.do API
        
        Args:
            url: The URL to scrape (will be properly encoded)
            country_code: Optional country code for geo-location (e.g., 'us', 'uk', 'de')
            render: Whether to render JavaScript (default: False)
            wait_for: Wait time in milliseconds for JS rendering
            block_resources: Block images/css to speed up scraping
            custom_headers: Additional headers to send with the request
            use_cache: Whether to use cached results (default: True)
            **kwargs: Additional parameters to pass to Scrape.do API
        
        Returns:
            Dict containing the scraped data or None if failed
            {
                'html': str,  # The scraped HTML content
                'status_code': int,  # HTTP status code
                'headers': dict,  # Response headers
                'url': str,  # Final URL after redirects
            }
        """
        try:
            # Generate cache key if caching is enabled
            if use_cache:
                cache_key = self._generate_cache_key(url, country_code, render, **kwargs)
                cached_result = cache.get(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for URL: {url}")
                    return cached_result
            
            # Build parameters
            params = {
                'token': self.api_key,
                'url': url,  # URL will be encoded by requests library
            }
            
            # Add optional parameters
            if country_code:
                params['geoCode'] = country_code
            
            if render:
                params['render'] = 'true'
                if wait_for:
                    params['waitFor'] = wait_for
            
            if block_resources:
                params['blockResources'] = 'true'
            
            # Add custom headers if provided
            if custom_headers:
                for key, value in custom_headers.items():
                    params[f'customHeaders[{key}]'] = value
            
            # Add any additional kwargs
            params.update(kwargs)
            
            # Log the request (hide API key)
            log_params = params.copy()
            log_params['token'] = '***hidden***'
            logger.info(f"Scraping URL: {url} with params: {log_params}")
            
            # Make the request
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            # Check if request was successful
            if response.status_code == 200:
                result = {
                    'html': response.text,
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'url': response.url,
                    'success': True
                }
                
                # Cache successful results if caching is enabled
                if use_cache:
                    cache.set(cache_key, result, self.CACHE_TTL)
                    logger.info(f"Cached result for URL: {url}")
                
                logger.info(f"Successfully scraped URL: {url}")
                return result
            else:
                logger.error(f"Failed to scrape URL: {url}, Status: {response.status_code}")
                return {
                    'html': None,
                    'status_code': response.status_code,
                    'error': response.text,
                    'success': False
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while scraping URL: {url}")
            return {'error': 'Request timeout', 'success': False}
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while scraping URL: {url}, Error: {str(e)}")
            return {'error': str(e), 'success': False}
        
        except Exception as e:
            logger.error(f"Unexpected error while scraping URL: {url}, Error: {str(e)}")
            return {'error': str(e), 'success': False}
    
    def scrape_batch(
        self, 
        urls: list, 
        country_code: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Scrape multiple URLs in batch
        
        Args:
            urls: List of URLs to scrape
            country_code: Optional country code for all requests
            **kwargs: Additional parameters to pass to scrape method
        
        Returns:
            Dict mapping URLs to their scraped results
        """
        results = {}
        for url in urls:
            results[url] = self.scrape(url, country_code=country_code, **kwargs)
        return results
    
    def scrape_with_retry(
        self, 
        url: str, 
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape with automatic retry on failure
        
        Args:
            url: The URL to scrape
            max_retries: Maximum number of retry attempts
            **kwargs: Parameters to pass to scrape method
        
        Returns:
            Scraped data or None if all retries failed
        """
        for attempt in range(max_retries):
            result = self.scrape(url, use_cache=False, **kwargs)
            if result and result.get('success'):
                return result
            
            logger.warning(f"Retry {attempt + 1}/{max_retries} for URL: {url}")
        
        logger.error(f"All retries failed for URL: {url}")
        return None
    
    def encode_uule(self, location: str) -> str:
        """
        Encode location string to Google's UULE format
        
        The UULE parameter is used by Google to specify exact location for search results.
        Format: w+CAIQICI{encoded_location}
        
        Args:
            location: Location string (e.g., "New York,New York,United States")
        
        Returns:
            UULE encoded string
        """
        # Create the canonical location string
        canonical_name = location.strip()
        
        # Encode the location
        encoded = base64.b64encode(canonical_name.encode('utf-8')).decode('ascii')
        
        # Remove padding and make URL-safe
        encoded = encoded.rstrip('=').replace('+', '-').replace('/', '_')
        
        # Create UULE parameter
        # The prefix "w+CAIQICI" is Google's standard for location targeting
        uule = f"w+CAIQICI{chr(len(canonical_name))}{canonical_name}"
        
        return uule
    
    def scrape_google_search(
        self, 
        query: str, 
        country_code: Optional[str] = 'us',
        num_results: int = 100,  # Increased default to 100
        location: Optional[str] = None,
        language: Optional[str] = None,
        gl: Optional[str] = None,  # Country for results (e.g., 'us', 'uk')
        hl: Optional[str] = None,  # Interface language (e.g., 'en', 'es')
        safe: Optional[str] = None,  # Safe search ('active', 'moderate', 'off')
        start: int = 0,  # Starting position for results
        use_exact_location: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Enhanced Google search scraping with location and language support
        
        Args:
            query: Search query
            country_code: Country code for Scrape.do proxy location
            num_results: Number of results to fetch (default: 100)
            location: Location for UULE parameter (e.g., "New York,New York,United States")
            language: Language for search results (deprecated, use hl instead)
            gl: Country code for Google results (e.g., 'us' for USA)
            hl: Interface language code (e.g., 'en' for English)
            safe: Safe search setting ('active', 'moderate', 'off')
            start: Starting position for pagination
            use_exact_location: Whether to use UULE for exact location
        
        Returns:
            Scraped Google search results
        
        Examples:
            # Search from USA in English
            scraper.scrape_google_search("python django", gl='us', hl='en')
            
            # Search from Germany in German
            scraper.scrape_google_search("python django", gl='de', hl='de')
            
            # Search with exact location (New York)
            scraper.scrape_google_search(
                "restaurants", 
                location="New York,New York,United States",
                use_exact_location=True
            )
        """
        # Build query parameters
        params = {
            'q': query,  # Search query
            'num': str(num_results),  # Number of results
        }
        
        # Add country for results (affects which Google domain and results)
        if gl:
            params['gl'] = gl
        elif country_code:
            params['gl'] = country_code
            
        # Add interface language
        if hl:
            params['hl'] = hl
        elif language:
            params['hl'] = language
        else:
            params['hl'] = 'en'  # Default to English
        
        # Add location-based search using UULE
        if location and use_exact_location:
            uule = self.encode_uule(location)
            params['uule'] = uule
            logger.info(f"Using UULE location: {location} -> {uule}")
        
        # Add safe search if specified
        if safe:
            params['safe'] = safe
            
        # Add start position for pagination
        if start > 0:
            params['start'] = str(start)
        
        # Build the Google search URL with all parameters
        base_url = "https://www.google.com/search"
        query_string = urlencode(params, safe='', quote_via=quote)
        google_url = f"{base_url}?{query_string}"
        
        logger.info(f"Google search URL: {google_url}")
        
        # Use Scrape.do to fetch the results
        # Pass country_code for proxy location
        return self.scrape(
            google_url,
            country_code=country_code,
            render=True,  # Google requires JS rendering
            wait_for=3000,  # Wait 3 seconds for results to load
            timeout=60000  # 60 second timeout for Google searches
        )
    
    def scrape_google_search_pages(
        self,
        query: str,
        pages: int = 1,
        results_per_page: int = 100,
        **kwargs
    ) -> list:
        """
        Scrape multiple pages of Google search results
        
        Args:
            query: Search query
            pages: Number of pages to fetch
            results_per_page: Results per page (max 100)
            **kwargs: Additional parameters for scrape_google_search
        
        Returns:
            List of scraped results from all pages
        """
        all_results = []
        
        for page in range(pages):
            start = page * results_per_page
            result = self.scrape_google_search(
                query,
                num_results=results_per_page,
                start=start,
                **kwargs
            )
            
            if result and result.get('success'):
                all_results.append(result)
            else:
                logger.warning(f"Failed to fetch page {page + 1} for query: {query}")
                break
        
        return all_results
    
    def _generate_cache_key(self, url: str, *args, **kwargs) -> str:
        """
        Generate a cache key for the request
        
        Args:
            url: The URL being scraped
            *args: Additional arguments
            **kwargs: Additional keyword arguments
        
        Returns:
            A unique cache key string
        """
        # Create a unique key based on all parameters
        key_data = {
            'url': url,
            'args': args,
            'kwargs': kwargs
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"scrape_do_{key_hash}"
    
    def clear_cache(self, url: Optional[str] = None):
        """
        Clear cached results
        
        Args:
            url: Optional URL to clear specific cache. If None, clears all scrape.do cache
        """
        if url:
            # Clear specific URL cache (would need to match exact parameters)
            cache_key = self._generate_cache_key(url)
            cache.delete(cache_key)
            logger.info(f"Cleared cache for URL: {url}")
        else:
            # Clear all scrape.do cache (pattern-based, requires cache backend support)
            logger.info("Cache clearing requires specific implementation based on cache backend")
    
    def get_usage(self) -> Optional[Dict[str, Any]]:
        """
        Get API usage statistics (if supported by Scrape.do)
        
        Returns:
            Usage statistics or None if not available
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/usage",
                params={'token': self.api_key},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Failed to get usage stats: {str(e)}")
            return None


# Singleton instance for easy import
_default_scraper = None

def get_scraper(api_key: Optional[str] = None) -> ScrapeDoService:
    """
    Get a singleton instance of ScrapeDoService
    
    Args:
        api_key: Optional API key to use
    
    Returns:
        ScrapeDoService instance
    """
    global _default_scraper
    if _default_scraper is None or api_key:
        _default_scraper = ScrapeDoService(api_key)
    return _default_scraper