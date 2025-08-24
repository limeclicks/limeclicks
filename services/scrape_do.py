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
    DEFAULT_TIMEOUT = 30  # 30 seconds timeout for API requests
    CACHE_TTL = 3600  # 1 hour cache for successful responses
    
    # Scrape.do supported geoCode mapping (from documentation)
    SCRAPE_DO_GEO_CODES = {
        'AL': 'AL',  # Albania
        'ID': 'ID',  # Indonesia
        'LV': 'LV',  # Latvia
        'FI': 'FI',  # Finland
        'AU': 'AU',  # Australia
        'CA': 'CA',  # Canada
        'CL': 'CL',  # Chile
        'CN': 'CN',  # China
        'HR': 'HR',  # Croatia
        'ES': 'ES',  # Spain
        'LT': 'LT',  # Lithuania
        'DK': 'DK',  # Denmark
        'CZ': 'CZ',  # Czech Republic
        'US': 'US',  # United States
        'GB': 'GB',  # Great Britain
        'DE': 'DE',  # Germany
        'HU': 'HU',  # Hungary
        'EE': 'EE',  # Estonia
        'AR': 'AR',  # Argentina
        'RO': 'RO',  # Romania
        'JP': 'JP',  # Japan
        'MY': 'MY',  # Malaysia
        'AT': 'AT',  # Austria
        'TR': 'TR',  # Turkey
        'RU': 'RU',  # Russia
        'FR': 'FR',  # France
        'RS': 'RS',  # Serbia
        'IL': 'IL',  # Israel
        'PT': 'PT',  # Portugal
        'IN': 'IN',  # India
        'BR': 'BR',  # Brazil
        'BE': 'BE',  # Belgium
        'ZA': 'ZA',  # South Africa
        'UA': 'UA',  # Ukraine
        'PK': 'PK',  # Pakistan
        'HK': 'HK',  # Hong Kong
        'MT': 'MT',  # Malta
        'SE': 'SE',  # Sweden
        'PL': 'PL',  # Poland
        'NL': 'NL',  # Netherlands
        'NO': 'NO',  # Norway
        'AE': 'AE',  # United Arab Emirates
        'SA': 'SA',  # Saudi Arabia
        'MX': 'MX',  # Mexico
        'GR': 'GR',  # Greece
        'EG': 'EG',  # Egypt
        'SK': 'SK',  # Slovakia
        'CH': 'CH',  # Switzerland
        'IT': 'IT',  # Italy
        'SG': 'SG',  # Singapore
        # UK is an alias for GB
        'UK': 'GB',  # United Kingdom -> Great Britain
    }
    
    # Country-specific Google domains mapping
    GOOGLE_DOMAINS = {
        'US': 'www.google.com',
        'GB': 'www.google.co.uk',
        'UK': 'www.google.co.uk',  # Alias for GB
        'CA': 'www.google.ca',
        'JP': 'www.google.co.jp',
        'FR': 'www.google.fr',
        'AU': 'www.google.com.au',
        'IN': 'www.google.co.in',
        'IE': 'www.google.ie',
        'TR': 'www.google.com.tr',
        'BE': 'www.google.be',
        'GR': 'www.google.gr',
        'MX': 'www.google.com.mx',
        'DK': 'www.google.dk',
        'AR': 'www.google.com.ar',
        'CH': 'www.google.ch',
        'ES': 'www.google.es',
        'DE': 'www.google.de',
        'IT': 'www.google.it',
        'NL': 'www.google.nl',
        'BR': 'www.google.com.br',
        'PT': 'www.google.pt',
        'SE': 'www.google.se',
        'NO': 'www.google.no',
        'FI': 'www.google.fi',
        'PL': 'www.google.pl',
        'AT': 'www.google.at',
        'RU': 'www.google.ru',
        'KR': 'www.google.co.kr',
        'CN': 'www.google.com.hk',  # Google.cn redirects to HK
        'HK': 'www.google.com.hk',
        'TW': 'www.google.com.tw',
        'SG': 'www.google.com.sg',
        'NZ': 'www.google.co.nz',
        'ZA': 'www.google.co.za',
        'EG': 'www.google.com.eg',
        'AE': 'www.google.ae',
        'SA': 'www.google.com.sa',
        'IL': 'www.google.co.il',
        'TH': 'www.google.co.th',
        'ID': 'www.google.co.id',
        'MY': 'www.google.com.my',
        'PH': 'www.google.com.ph',
        'VN': 'www.google.com.vn',
        'CZ': 'www.google.cz',
        'HU': 'www.google.hu',
        'RO': 'www.google.ro',
        'BG': 'www.google.bg',
        'HR': 'www.google.hr',
        'RS': 'www.google.rs',
        'SK': 'www.google.sk',
        'SI': 'www.google.si',
        'LT': 'www.google.lt',
        'LV': 'www.google.lv',
        'EE': 'www.google.ee',
        'IS': 'www.google.is',
        'CL': 'www.google.cl',
        'CO': 'www.google.com.co',
        'PE': 'www.google.com.pe',
        'VE': 'www.google.co.ve',
        'EC': 'www.google.com.ec',
        'UY': 'www.google.com.uy',
        'PY': 'www.google.com.py',
        'BO': 'www.google.com.bo',
        'CR': 'www.google.co.cr',
        'PA': 'www.google.com.pa',
        'GT': 'www.google.com.gt',
        'HN': 'www.google.hn',
        'SV': 'www.google.com.sv',
        'NI': 'www.google.com.ni',
        'DO': 'www.google.com.do',
        'PR': 'www.google.com.pr',
        'JM': 'www.google.com.jm',
        'TT': 'www.google.tt',
        'CU': 'www.google.com.cu',
        'NG': 'www.google.com.ng',
        'KE': 'www.google.co.ke',
        'GH': 'www.google.com.gh',
        'UG': 'www.google.co.ug',
        'TZ': 'www.google.co.tz',
        'ZW': 'www.google.co.zw',
        'BW': 'www.google.co.bw',
        'MA': 'www.google.co.ma',
        'DZ': 'www.google.dz',
        'TN': 'www.google.tn',
        'LY': 'www.google.com.ly',
        'ET': 'www.google.com.et',
        'PK': 'www.google.com.pk',
        'BD': 'www.google.com.bd',
        'LK': 'www.google.lk',
        'NP': 'www.google.com.np',
        'MM': 'www.google.com.mm',
        'KH': 'www.google.com.kh',
        'LA': 'www.google.la',
        'KZ': 'www.google.kz',
        'UZ': 'www.google.co.uz',
        'KG': 'www.google.kg',
        'TJ': 'www.google.com.tj',
        'TM': 'www.google.tm',
        'AF': 'www.google.com.af',
        'MN': 'www.google.mn',
        'JO': 'www.google.jo',
        'LB': 'www.google.com.lb',
        'KW': 'www.google.com.kw',
        'BH': 'www.google.com.bh',
        'QA': 'www.google.com.qa',
        'OM': 'www.google.com.om',
        'PS': 'www.google.ps',
        'IQ': 'www.google.iq',
        'GE': 'www.google.ge',
        'AM': 'www.google.am',
        'AZ': 'www.google.az',
        'BY': 'www.google.by',
        'MD': 'www.google.md',
        'UA': 'www.google.com.ua',
        'BA': 'www.google.ba',
        'ME': 'www.google.me',
        'AL': 'www.google.al',
        'MK': 'www.google.mk',
        'MT': 'www.google.com.mt',
        'CY': 'www.google.com.cy',
        'LU': 'www.google.lu',
        'LI': 'www.google.li',
        'AD': 'www.google.ad',
        'MC': 'www.google.com.mc',
        'SM': 'www.google.sm',
        'VA': 'www.google.com.va'
    }
    
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
        waitUntil: Optional[str] = None,
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
                    params['waitUntil'] = wait_for
                elif waitUntil:
                    params['waitUntil'] = waitUntil
            
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
    
    def get_google_domain(self, country_code: str) -> str:
        """
        Get the Google domain for a specific country code
        
        Args:
            country_code: Two-letter country code (e.g., 'US', 'GB', 'FR')
        
        Returns:
            Google domain for the country (e.g., 'www.google.co.uk')
            Defaults to 'www.google.com' if country not found
        """
        country = country_code.upper() if country_code else 'US'
        return self.GOOGLE_DOMAINS.get(country, self.GOOGLE_DOMAINS['US'])
    
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
        country_code: Optional[str] = 'US',
        num_results: int = 100,
        location: Optional[str] = None,
        hl: Optional[str] = None,  # Interface language (e.g., 'en', 'es')
        safe: Optional[str] = None,  # Safe search ('active', 'moderate', 'off')
        use_exact_location: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Google search scraping with country-specific domains (single page only)
        
        Args:
            query: Search query
            country_code: Country code (determines Google domain and Scrape.do proxy)
            num_results: Number of results to fetch (default: 100)
            location: Location for UULE parameter (e.g., "New York,New York,United States")
            hl: Interface language code (e.g., 'en' for English)
            safe: Safe search setting ('active', 'moderate', 'off')
            use_exact_location: Whether to use UULE for exact location
        
        Returns:
            Scraped Google search results (first page only)
        
        Examples:
            # Search from USA
            scraper.scrape_google_search("python django", country_code='US')
            
            # Search from UK with British English
            scraper.scrape_google_search("python django", country_code='GB', hl='en-GB')
            
            # Search from Germany with German interface
            scraper.scrape_google_search("python django", country_code='DE', hl='de')
        """
        # Normalize country code
        country = (country_code or 'US').upper()
        
        # Get the appropriate Google domain for the country
        google_domain = self.GOOGLE_DOMAINS.get(country, self.GOOGLE_DOMAINS['US'])
        
        # Map country to Scrape.do geoCode (fallback to US if not supported)
        geo_code = self.SCRAPE_DO_GEO_CODES.get(country, 'US')
        
        # Build query parameters
        params = {
            'q': query,  # Search query
            'num': str(num_results),  # Number of results
        }
        
        # Add interface language
        if hl:
            params['hl'] = hl
        else:
            # Default language based on country
            default_languages = {
                'US': 'en', 'GB': 'en', 'UK': 'en', 'AU': 'en', 'CA': 'en',
                'FR': 'fr', 'DE': 'de', 'ES': 'es', 'IT': 'it', 'PT': 'pt',
                'JP': 'ja', 'CN': 'zh-CN', 'RU': 'ru', 'BR': 'pt-BR',
                'NL': 'nl', 'SE': 'sv', 'NO': 'no', 'DK': 'da', 'FI': 'fi',
                'PL': 'pl', 'TR': 'tr', 'GR': 'el', 'IN': 'en', 'IL': 'he',
                'SA': 'ar', 'AE': 'ar', 'EG': 'ar', 'MX': 'es-MX', 'AR': 'es'
            }
            params['hl'] = default_languages.get(country, 'en')
        
        # Add location-based search using UULE
        if location and use_exact_location:
            uule = self.encode_uule(location)
            params['uule'] = uule
            logger.info(f"Using UULE location: {location} -> {uule}")
        
        # Add safe search if specified
        if safe:
            params['safe'] = safe
        
        # Build the Google search URL with country-specific domain
        base_url = f"https://{google_domain}/search"
        query_string = urlencode(params, safe='', quote_via=quote)
        google_url = f"{base_url}?{query_string}"
        
        logger.info(f"Google search URL: {google_url}")
        logger.info(f"Using domain: {google_domain} | Scrape.do geoCode: {geo_code}")
        
        # Use Scrape.do to fetch the results with proper geoCode
        return self.scrape(
            google_url,
            country_code=geo_code,  # Use mapped geoCode for Scrape.do
            render=True,  # Google requires JS rendering
            waitUntil='networkidle2'  # Wait for network to be idle
        )
    
    
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