"""
Google Search Results Parser Service
Extracts structured data from Google search HTML with robust selectors
"""

import logging
import re
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class GoogleSearchParser:
    """
    Parser for Google search results HTML
    Extracts structured data with multiple fallback selectors
    """
    
    def __init__(self):
        """Initialize the parser with selector configurations"""
        # Multiple selector strategies for robustness
        self.result_selectors = [
            # Primary selectors
            {'selector': 'div.g', 'type': 'standard'},
            {'selector': 'div[data-hveid]', 'type': 'data-attribute'},
            {'selector': 'div.tF2Cxc', 'type': 'class-based'},
            {'selector': 'div[class*="g "]', 'type': 'partial-class'},
            # Fallback selectors
            {'selector': 'div[jscontroller][jsdata][jsmodel]', 'type': 'js-attributes'},
            {'selector': 'div[data-sokoban-container]', 'type': 'container'},
        ]
        
        # Title selectors with priority
        self.title_selectors = [
            'h3',
            'h3.LC20lb',
            'h3.DKV0Md',
            'div[role="heading"]',
            'a h3',
            '[data-header-feature] h3',
            '.yuRUbf h3',
        ]
        
        # URL selectors
        self.url_selectors = [
            'a[href][data-ved]',
            'a[ping]',
            '.yuRUbf a',
            'a[data-jsarwt]',
            'cite',
            'div.TbwUpd cite',
        ]
        
        # Description selectors
        self.description_selectors = [
            'div.VwiC3b',
            'span.aCOpRe',
            'div.IsZvec',
            'div.s3v9rd',
            'div[data-content-feature] span',
            'div.lEBKkf',
            'span.st',
            'div.ITZIwc',
        ]
        
        # Favicon selectors
        self.favicon_selectors = [
            'img.XNo5Ab',
            'img.eA0Zlc',
            'img[data-iml]',
            'img[alt*="favicon"]',
            'img[src*="favicon"]',
            'g-img img',
            'img.rISBZc',
        ]
    
    def parse(self, html: str) -> Dict[str, Any]:
        """
        Parse Google search results HTML
        
        Args:
            html: Raw HTML from Google search
            
        Returns:
            Dictionary containing:
            - organic_results: List of organic search results
            - sponsored_results: List of sponsored/ad results
            - total_results: Estimated total results
            - search_time: Search execution time
            - related_searches: Related search suggestions
        """
        if not html:
            logger.error("No HTML content provided")
            return {'organic_results': [], 'sponsored_results': [], 'error': 'No HTML content'}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract both organic and sponsored results
            organic_results, sponsored_results = self._extract_all_results(soup)
            
            # Extract metadata
            total_results = self._extract_total_results(soup)
            search_time = self._extract_search_time(soup)
            
            # Extract additional elements
            related_searches = self._extract_related_searches(soup)
            people_also_ask = self._extract_people_also_ask(soup)
            
            # Extract featured snippet if present
            featured_snippet = self._extract_featured_snippet(soup)
            
            # Extract knowledge panel if present
            knowledge_panel = self._extract_knowledge_panel(soup)
            
            # Extract ALL additional SERP features
            local_pack = self._extract_local_pack(soup)
            top_stories = self._extract_top_stories(soup)
            video_results = self._extract_video_results(soup)
            image_pack = self._extract_image_pack(soup)
            twitter_results = self._extract_twitter_results(soup)
            top_questions = self._extract_top_questions(soup)
            recipes = self._extract_recipes(soup)
            shopping_results = self._extract_shopping_results(soup)
            flights = self._extract_flights(soup)
            hotels = self._extract_hotels(soup)
            jobs = self._extract_jobs(soup)
            events = self._extract_events(soup)
            calculators = self._extract_calculators(soup)
            definitions = self._extract_definitions(soup)
            translations = self._extract_translations(soup)
            weather = self._extract_weather(soup)
            sports_results = self._extract_sports_results(soup)
            stock_info = self._extract_stock_info(soup)
            currency_converter = self._extract_currency_converter(soup)
            time_info = self._extract_time_info(soup)
            
            # Build comprehensive response
            response = {
                'organic_results': organic_results,
                'sponsored_results': sponsored_results,
                'total_results': total_results,
                'search_time': search_time,
                'related_searches': related_searches,
                'people_also_ask': people_also_ask,
                'featured_snippet': featured_snippet,
                'knowledge_panel': knowledge_panel,
                'organic_count': len(organic_results),
                'sponsored_count': len(sponsored_results),
                # Keep 'results' for backward compatibility
                'results': organic_results
            }
            
            # Add SERP features if present
            if local_pack:
                response['local_pack'] = local_pack
            if top_stories:
                response['top_stories'] = top_stories
            if video_results:
                response['videos'] = video_results
            if image_pack:
                response['images'] = image_pack
            if twitter_results:
                response['twitter'] = twitter_results
            if top_questions:
                response['top_questions'] = top_questions
            if recipes:
                response['recipes'] = recipes
            if shopping_results:
                response['shopping'] = shopping_results
            if flights:
                response['flights'] = flights
            if hotels:
                response['hotels'] = hotels
            if jobs:
                response['jobs'] = jobs
            if events:
                response['events'] = events
            if calculators:
                response['calculator'] = calculators
            if definitions:
                response['definitions'] = definitions
            if translations:
                response['translation'] = translations
            if weather:
                response['weather'] = weather
            if sports_results:
                response['sports'] = sports_results
            if stock_info:
                response['stocks'] = stock_info
            if currency_converter:
                response['currency'] = currency_converter
            if time_info:
                response['time'] = time_info
            
            return response
            
        except Exception as e:
            logger.error(f"Error parsing Google search HTML: {str(e)}")
            return {'organic_results': [], 'sponsored_results': [], 'error': str(e)}
    
    def _extract_all_results(self, soup: BeautifulSoup) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract both organic and sponsored search results
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Tuple of (organic_results, sponsored_results)
        """
        organic_results = []
        sponsored_results = []
        organic_position = 1
        sponsored_position = 1
        
        # Try each selector strategy
        result_elements = []
        for selector_config in self.result_selectors:
            selector = selector_config['selector']
            elements = soup.select(selector)
            
            if elements:
                logger.info(f"Found {len(elements)} total results using selector: {selector}")
                result_elements = elements
                break
        
        # Also look for dedicated ad containers
        ad_selectors = [
            'div[data-text-ad]',
            'div.uEierd',  # Shopping ads
            'div[aria-label*="Ad"]',
            'div[data-rw]',  # Text ads
            'div.commercial-unit',
            'div.ads-ad',
            'li.ads-ad',
        ]
        
        ad_elements = []
        for ad_selector in ad_selectors:
            ad_elements.extend(soup.select(ad_selector))
        
        # Process ad elements first
        for element in ad_elements:
            result = self._parse_sponsored_result(element, sponsored_position)
            if result and result.get('url'):
                result['result_type'] = 'sponsored'
                result['ad_format'] = self._detect_ad_format(element)
                sponsored_results.append(result)
                sponsored_position += 1
        
        # Process all elements
        for element in result_elements:
            # Check if it's an ad/sponsored result
            if self._is_ad(element):
                # Parse as sponsored result
                result = self._parse_sponsored_result(element, sponsored_position)
                if result and result.get('url'):
                    result['result_type'] = 'sponsored'
                    result['ad_format'] = self._detect_ad_format(element)
                    # Avoid duplicates
                    if not any(r['url'] == result['url'] for r in sponsored_results):
                        sponsored_results.append(result)
                        sponsored_position += 1
            elif not self._is_special_result(element):
                # Parse as organic result
                result = self._parse_single_result(element, organic_position)
                if result and result.get('url'):
                    result['result_type'] = 'organic'
                    organic_results.append(result)
                    organic_position += 1
        
        logger.info(f"Extracted {len(organic_results)} organic and {len(sponsored_results)} sponsored results")
        return organic_results, sponsored_results
    
    def _parse_sponsored_result(self, element: BeautifulSoup, position: int) -> Optional[Dict[str, Any]]:
        """
        Parse a sponsored/ad search result
        
        Args:
            element: BeautifulSoup element for one ad
            position: Position in sponsored results
            
        Returns:
            Dictionary with sponsored result data
        """
        try:
            # Similar to organic but with ad-specific fields
            result = self._parse_single_result(element, position)
            
            if result:
                # Add ad-specific metadata
                result['is_sponsored'] = True
                
                # Look for "Ad" or "Sponsored" label
                ad_label = self._extract_ad_label(element)
                if ad_label:
                    result['ad_label'] = ad_label
                
                # Extract advertiser info if available
                advertiser = self._extract_advertiser(element)
                if advertiser:
                    result['advertiser'] = advertiser
                
                # Check for ad extensions (sitelinks, callouts, etc.)
                extensions = self._extract_ad_extensions(element)
                if extensions:
                    result['ad_extensions'] = extensions
            
            return result
            
        except Exception as e:
            logger.debug(f"Error parsing sponsored result: {str(e)}")
            return None
    
    def _detect_ad_format(self, element: BeautifulSoup) -> str:
        """
        Detect the format/type of ad
        
        Returns:
            Ad format type (text, shopping, local, etc.)
        """
        # Check for shopping ads
        if element.select_one('.commercial-unit-desktop-rhs, .commercial-unit-desktop-top'):
            return 'shopping'
        
        # Check for local ads (with map pins, addresses)
        if element.select_one('[data-local-attribute], .rllt__details'):
            return 'local'
        
        # Check for call ads
        if element.select_one('[data-fci], [aria-label*="Call"]'):
            return 'call'
        
        # Default to text ad
        return 'text'
    
    def _extract_ad_label(self, element: BeautifulSoup) -> Optional[str]:
        """Extract the ad label (Ad, Sponsored, etc.)"""
        # Look for ad labels
        label_selectors = [
            'span:contains("Ad")',
            'span:contains("Sponsored")',
            'div[aria-label*="Ad"]',
            '.ads-label',
            '.D1fz0e',  # Google's ad label class
        ]
        
        for selector in label_selectors:
            try:
                label_elem = element.select_one(selector)
                if label_elem:
                    return label_elem.get_text(strip=True)
            except:
                continue
        
        # Check for text containing "Ad" or "Sponsored"
        text = element.get_text()
        if ' Ad ' in text or text.startswith('Ad '):
            return 'Ad'
        if 'Sponsored' in text:
            return 'Sponsored'
        
        return None
    
    def _extract_advertiser(self, element: BeautifulSoup) -> Optional[str]:
        """Extract advertiser information"""
        # Look for advertiser domain or name
        advertiser_selectors = [
            '.visibleUrl',
            '.UdQCqe',  # Advertiser domain
            'cite.iUh30',
            'div[data-pcu]',
        ]
        
        for selector in advertiser_selectors:
            adv_elem = element.select_one(selector)
            if adv_elem:
                return adv_elem.get_text(strip=True)
        
        return None
    
    def _extract_ad_extensions(self, element: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract ad extensions (sitelinks, callouts, etc.)"""
        extensions = {}
        
        # Extract sitelinks
        sitelinks = []
        sitelink_elements = element.select('div.MhgNwc a, table.nrDZPe a')
        for link in sitelink_elements[:4]:  # Usually max 4 sitelinks
            sitelink = {
                'text': link.get_text(strip=True),
                'url': self._clean_google_url(link.get('href', ''))
            }
            if sitelink['text'] and sitelink['url']:
                sitelinks.append(sitelink)
        
        if sitelinks:
            extensions['sitelinks'] = sitelinks
        
        # Extract callout extensions
        callouts = []
        callout_elements = element.select('.Lu0opc, .callout')
        for callout in callout_elements:
            text = callout.get_text(strip=True)
            if text:
                callouts.append(text)
        
        if callouts:
            extensions['callouts'] = callouts
        
        # Extract structured snippets
        snippets = element.select('.e1ycic')
        if snippets:
            extensions['structured_snippets'] = [s.get_text(strip=True) for s in snippets]
        
        # Extract price extensions
        price_elem = element.select_one('.price, .d1C4gb')
        if price_elem:
            extensions['price'] = price_elem.get_text(strip=True)
        
        # Extract rating
        rating_elem = element.select_one('.z3HNkc, g-review-stars')
        if rating_elem:
            rating_text = rating_elem.get('aria-label', '')
            if not rating_text:
                rating_text = rating_elem.get_text(strip=True)
            if rating_text:
                extensions['rating'] = rating_text
        
        # Extract phone number
        phone_elem = element.select_one('[data-fci], [aria-label*="Call"]')
        if phone_elem:
            phone_text = phone_elem.get_text(strip=True)
            if phone_text:
                extensions['phone'] = phone_text
        
        return extensions if extensions else None
    
    def _parse_single_result(self, element: BeautifulSoup, position: int) -> Optional[Dict[str, Any]]:
        """
        Parse a single search result element
        
        Args:
            element: BeautifulSoup element for one result
            position: Position in search results
            
        Returns:
            Dictionary with result data or None
        """
        try:
            # Extract title
            title = self._extract_title(element)
            
            # Extract URL
            url = self._extract_url(element)
            
            # Extract description
            description = self._extract_description(element)
            
            # Extract domain
            domain = self._extract_domain(url) if url else None
            
            # Extract favicon
            favicon = self._extract_favicon(element)
            
            # Extract additional metadata
            breadcrumbs = self._extract_breadcrumbs(element)
            date = self._extract_date(element)
            
            # Only return if we have at least URL and title
            if url and title:
                return {
                    'position': position,
                    'title': title,
                    'url': url,
                    'domain': domain,
                    'description': description,
                    'favicon': favicon,
                    'breadcrumbs': breadcrumbs,
                    'date': date,
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing single result: {str(e)}")
            return None
    
    def _extract_title(self, element: BeautifulSoup) -> Optional[str]:
        """Extract title with multiple fallback selectors"""
        for selector in self.title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                # Get text, handling nested elements
                title = title_elem.get_text(strip=True)
                if title:
                    return title
        
        # Fallback: look for any heading
        heading = element.find(['h1', 'h2', 'h3', 'h4'])
        if heading:
            return heading.get_text(strip=True)
        
        return None
    
    def _extract_url(self, element: BeautifulSoup) -> Optional[str]:
        """Extract URL with multiple strategies"""
        # Strategy 1: Direct href
        for selector in self.url_selectors:
            url_elem = element.select_one(selector)
            if url_elem:
                if url_elem.name == 'a' and url_elem.get('href'):
                    url = url_elem['href']
                    # Clean Google redirect URLs
                    clean_url = self._clean_google_url(url)
                    if clean_url and not clean_url.startswith('/search'):
                        return clean_url
                elif url_elem.name == 'cite':
                    # Extract from cite text
                    cite_text = url_elem.get_text(strip=True)
                    if cite_text and (cite_text.startswith('http') or '.' in cite_text):
                        return self._normalize_url(cite_text)
        
        # Strategy 2: Look for any link with ping attribute
        ping_link = element.find('a', {'ping': True})
        if ping_link and ping_link.get('href'):
            return self._clean_google_url(ping_link['href'])
        
        # Strategy 3: Data attributes
        link_with_data = element.find('a', {'data-ved': True})
        if link_with_data and link_with_data.get('href'):
            return self._clean_google_url(link_with_data['href'])
        
        return None
    
    def _extract_description(self, element: BeautifulSoup) -> Optional[str]:
        """Extract description with multiple fallback selectors"""
        for selector in self.description_selectors:
            desc_elem = element.select_one(selector)
            if desc_elem:
                # Get text, removing ellipsis and extra spaces
                description = desc_elem.get_text(separator=' ', strip=True)
                if description:
                    # Clean up description
                    description = re.sub(r'\s+', ' ', description)
                    description = description.replace(' ...', '...')
                    return description
        
        # Fallback: look for any text-containing div or span
        text_containers = element.find_all(['div', 'span'])
        for container in text_containers:
            text = container.get_text(strip=True)
            # Check if it looks like a description (not too short, not a URL)
            if text and len(text) > 50 and not text.startswith('http'):
                return re.sub(r'\s+', ' ', text)[:500]  # Limit length
        
        return None
    
    def _extract_favicon(self, element: BeautifulSoup) -> Optional[str]:
        """Extract favicon URL"""
        for selector in self.favicon_selectors:
            favicon_elem = element.select_one(selector)
            if favicon_elem and favicon_elem.get('src'):
                favicon_url = favicon_elem['src']
                # Make absolute URL if relative
                if favicon_url.startswith('//'):
                    favicon_url = 'https:' + favicon_url
                elif favicon_url.startswith('/'):
                    favicon_url = 'https://www.google.com' + favicon_url
                return favicon_url
        
        # Alternative: Google's favicon service
        url = self._extract_url(element)
        if url:
            domain = self._extract_domain(url)
            if domain:
                return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
        
        return None
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split('/')[0]
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return None
    
    def _extract_breadcrumbs(self, element: BeautifulSoup) -> Optional[str]:
        """Extract breadcrumb navigation if present"""
        # Look for breadcrumb container
        breadcrumb_elem = element.select_one('.TbwUpd, .iUh30, cite')
        if breadcrumb_elem:
            breadcrumb_text = breadcrumb_elem.get_text(strip=True)
            if ' › ' in breadcrumb_text or ' > ' in breadcrumb_text:
                return breadcrumb_text
        return None
    
    def _extract_date(self, element: BeautifulSoup) -> Optional[str]:
        """Extract date if present in result"""
        # Common date patterns in Google results
        date_patterns = [
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',
            r'\b\d{4}-\d{2}-\d{2}\b',
            r'\b\d+\s+(?:hours?|days?|weeks?|months?)\s+ago\b',
        ]
        
        text = element.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # Look for specific date elements
        date_elem = element.select_one('.f, .slp, .LEwnzc')
        if date_elem:
            date_text = date_elem.get_text(strip=True)
            if any(word in date_text.lower() for word in ['ago', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                return date_text
        
        return None
    
    def _extract_total_results(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract total results count"""
        # Look for results stats
        stats_elem = soup.select_one('#result-stats, .LHJvCe')
        if stats_elem:
            stats_text = stats_elem.get_text(strip=True)
            # Extract number pattern
            match = re.search(r'About ([\d,]+) results', stats_text)
            if match:
                return match.group(1)
            # Alternative pattern
            match = re.search(r'([\d,]+) results', stats_text)
            if match:
                return match.group(1)
        return None
    
    def _extract_search_time(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract search execution time"""
        stats_elem = soup.select_one('#result-stats, .LHJvCe')
        if stats_elem:
            stats_text = stats_elem.get_text(strip=True)
            # Extract time pattern
            match = re.search(r'\(([\d.]+) seconds?\)', stats_text)
            if match:
                return match.group(1)
        return None
    
    def _extract_related_searches(self, soup: BeautifulSoup) -> List[str]:
        """Extract related search suggestions"""
        related = []
        
        # Multiple possible selectors for related searches
        selectors = [
            'div.s75CSd a',
            'div[data-ved] a.k8XOCe',
            'a.gL9Hy',
            'div.AJLUJb a',
            'div[role="list"] a',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and text not in related:
                        related.append(text)
                break
        
        return related[:8]  # Limit to 8 suggestions
    
    def _extract_people_also_ask(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract 'People also ask' questions"""
        questions = []
        
        # Look for PAA container
        paa_elements = soup.select('div[data-ved] div[role="button"]')
        if not paa_elements:
            paa_elements = soup.select('div.related-question-pair')
        
        for elem in paa_elements[:4]:  # Usually 4 questions
            question_text = elem.get_text(strip=True)
            if question_text and '?' in question_text:
                questions.append({
                    'question': question_text,
                    'expanded': False  # Would need JavaScript to get answer
                })
        
        return questions
    
    def _extract_featured_snippet(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract featured snippet if present"""
        # Look for featured snippet container
        snippet_selectors = [
            'div.xpdopen',
            'div[data-tts="answers"]',
            'div.kp-blk',
            'div.IZ6rdc',
        ]
        
        for selector in snippet_selectors:
            snippet_elem = soup.select_one(selector)
            if snippet_elem:
                return {
                    'content': snippet_elem.get_text(strip=True)[:500],
                    'source': self._extract_url(snippet_elem),
                    'title': self._extract_title(snippet_elem),
                }
        
        return None
    
    def _extract_knowledge_panel(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract knowledge panel/graph if present"""
        # Look for knowledge panel
        panel_elem = soup.select_one('div.kp-wholepage, div[data-attrid="kc:/"], div.knowledge-panel')
        
        if panel_elem:
            panel_data = {
                'title': None,
                'subtitle': None,
                'description': None,
                'image': None,
                'facts': []
            }
            
            # Extract title
            title_elem = panel_elem.select_one('h2, div[data-attrid="title"]')
            if title_elem:
                panel_data['title'] = title_elem.get_text(strip=True)
            
            # Extract description
            desc_elem = panel_elem.select_one('div[data-attrid="description"] span, div.kno-rdesc span')
            if desc_elem:
                panel_data['description'] = desc_elem.get_text(strip=True)
            
            # Extract image
            img_elem = panel_elem.select_one('img[data-atf], g-img img')
            if img_elem and img_elem.get('src'):
                panel_data['image'] = img_elem['src']
            
            return panel_data
        
        return None
    
    def _is_ad(self, element: BeautifulSoup) -> bool:
        """Check if element is an ad"""
        # Check for ad indicators
        ad_indicators = [
            'span:contains("Ad")',
            'span:contains("Sponsored")',
            'div[data-hveid][aria-label*="Ad"]',
            'div.uEierd',  # Shopping ads
        ]
        
        for indicator in ad_indicators:
            if element.select_one(indicator):
                return True
        
        # Check for ad classes
        element_classes = element.get('class', [])
        if any('ad' in cls.lower() for cls in element_classes):
            return True
        
        return False
    
    def _is_special_result(self, element: BeautifulSoup) -> bool:
        """Check if element is a special result (video, news, etc.)"""
        # Check for special result types
        special_classes = ['g-blk', 'kno-kp', 'hp-xpdbox', 'g-inner-card']
        element_classes = element.get('class', [])
        
        if any(cls in element_classes for cls in special_classes):
            return True
        
        # Check for video results
        if element.select_one('div[data-vid], g-scrolling-carousel'):
            return True
        
        return False
    
    def _clean_google_url(self, url: str) -> Optional[str]:
        """Clean Google redirect URLs"""
        if not url:
            return None
        
        # Handle relative URLs
        if url.startswith('/'):
            if url.startswith('/url?'):
                # Extract actual URL from Google redirect
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'q' in params:
                    return params['q'][0]
                if 'url' in params:
                    return params['url'][0]
            return None
        
        # Handle Google redirect URLs
        if 'google.com/url?' in url:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'q' in params:
                return params['q'][0]
            if 'url' in params:
                return params['url'][0]
        
        return url
    
    def _normalize_url(self, url_text: str) -> str:
        """Normalize URL from cite text"""
        url_text = url_text.strip()
        
        # Remove trailing › or >
        url_text = re.sub(r'[›>].*$', '', url_text).strip()
        
        # Add protocol if missing
        if not url_text.startswith(('http://', 'https://')):
            url_text = 'https://' + url_text
        
        return url_text
    
    def _extract_local_pack(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Local Pack / Places results (Map listings)"""
        local_pack = {
            'title': 'Places',
            'places': []
        }
        
        # Look for local pack container
        local_selectors = [
            'div[jscontroller][data-loc]',
            'div.VkpGBb',  # Local pack container
            'div[data-attrid="kc:/local"]',
            'div.rllt__link',
            'div[aria-label*="Results for"]'
        ]
        
        for selector in local_selectors:
            local_elements = soup.select(selector)
            if local_elements:
                break
        
        # Also check for individual place cards
        place_cards = soup.select('div[data-cid], div.rllt__link, div.VkpGBb')
        
        for card in place_cards[:10]:  # Limit to 10 places
            place = {}
            
            # Extract place name
            name_elem = card.select_one('div[role="heading"], span.OSrXXb, div.dbg0pd')
            if name_elem:
                place['name'] = name_elem.get_text(strip=True)
            
            # Extract rating
            rating_elem = card.select_one('span[aria-label*="star"], span.yi40Hd')
            if rating_elem:
                rating_text = rating_elem.get('aria-label', '') or rating_elem.get_text(strip=True)
                place['rating'] = rating_text
            
            # Extract review count
            review_elem = card.select_one('span.RDApEe, span[aria-label*="review"]')
            if review_elem:
                place['reviews'] = review_elem.get_text(strip=True)
            
            # Extract address
            address_elem = card.select_one('span.rllt__details, div.W4Efsd:last-child')
            if address_elem:
                place['address'] = address_elem.get_text(strip=True)
            
            # Extract phone
            phone_elem = card.select_one('span[aria-label*="Call"], span.LrzXr')
            if phone_elem:
                place['phone'] = phone_elem.get_text(strip=True)
            
            # Extract hours
            hours_elem = card.select_one('div.W4Efsd span:contains("Open"), span.ZkP5Je')
            if hours_elem:
                place['hours'] = hours_elem.get_text(strip=True)
            
            # Extract type/category
            type_elem = card.select_one('span.rllt__details span:first-child')
            if type_elem:
                place['type'] = type_elem.get_text(strip=True)
            
            # Extract website link
            link_elem = card.select_one('a[data-cid], a.yYlJEf')
            if link_elem and link_elem.get('href'):
                place['url'] = self._clean_google_url(link_elem['href'])
            
            if place.get('name'):
                local_pack['places'].append(place)
        
        return local_pack if local_pack['places'] else None
    
    def _extract_top_stories(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Top Stories / News results"""
        stories = []
        
        # Look for news container
        news_selectors = [
            'g-section-with-header:has(div[aria-label*="Top stories"])',
            'div[data-attrid="kc:/news"]',
            'g-scrolling-carousel[data-title*="news"]',
            'div.ftSUBd'  # News carousel
        ]
        
        news_container = None
        for selector in news_selectors:
            news_container = soup.select_one(selector)
            if news_container:
                break
        
        if not news_container:
            # Try individual news items
            news_container = soup
        
        # Extract individual stories
        story_elements = news_container.select('g-inner-card, div[role="listitem"], article, div.xuvV6b')
        
        for story in story_elements[:10]:
            item = {}
            
            # Title
            title_elem = story.select_one('div[role="heading"], h3, div.mCBkyc')
            if title_elem:
                item['title'] = title_elem.get_text(strip=True)
            
            # Source
            source_elem = story.select_one('div.CEMjEf, span.xQ82C, div.pDavDe')
            if source_elem:
                item['source'] = source_elem.get_text(strip=True)
            
            # Time
            time_elem = story.select_one('span.hvbAAd, span.WG9SHc, time')
            if time_elem:
                item['published'] = time_elem.get_text(strip=True)
            
            # URL
            link_elem = story.select_one('a[href]')
            if link_elem:
                item['url'] = self._clean_google_url(link_elem.get('href', ''))
            
            # Thumbnail
            img_elem = story.select_one('img[src], g-img img')
            if img_elem and img_elem.get('src'):
                item['thumbnail'] = img_elem['src']
            
            if item.get('title'):
                stories.append(item)
        
        return stories if stories else None
    
    def _extract_video_results(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Video results"""
        videos = []
        
        # Look for video container
        video_selectors = [
            'div[data-attrid="kc:/film"]',
            'g-scrolling-carousel:has(div[data-vid])',
            'div.VibNM',  # Video carousel
            'div[jscontroller][data-init-vis]'
        ]
        
        video_container = None
        for selector in video_selectors:
            video_container = soup.select_one(selector)
            if video_container:
                break
        
        if not video_container:
            video_container = soup
        
        # Extract individual videos
        video_elements = video_container.select('div[data-vid], g-inner-card:has(cite), div.RzdJxc')
        
        for video in video_elements[:10]:
            item = {}
            
            # Title
            title_elem = video.select_one('div[role="heading"], h3, div.DKV0Md')
            if title_elem:
                item['title'] = title_elem.get_text(strip=True)
            
            # Platform (YouTube, Vimeo, etc.)
            platform_elem = video.select_one('cite, span.xQ82C')
            if platform_elem:
                platform_text = platform_elem.get_text(strip=True)
                if 'youtube' in platform_text.lower():
                    item['platform'] = 'YouTube'
                elif 'vimeo' in platform_text.lower():
                    item['platform'] = 'Vimeo'
                else:
                    item['platform'] = platform_text
            
            # Duration
            duration_elem = video.select_one('span.mNr4H, span[aria-label*="Duration"]')
            if duration_elem:
                item['duration'] = duration_elem.get_text(strip=True)
            
            # Upload date
            date_elem = video.select_one('span.wpKvBc, span.fG8Fp')
            if date_elem:
                item['uploaded'] = date_elem.get_text(strip=True)
            
            # URL
            link_elem = video.select_one('a[href]')
            if link_elem:
                item['url'] = self._clean_google_url(link_elem.get('href', ''))
            
            # Thumbnail
            img_elem = video.select_one('img[src]')
            if img_elem and img_elem.get('src'):
                item['thumbnail'] = img_elem['src']
            
            # Video ID (if YouTube)
            if video.get('data-vid'):
                item['video_id'] = video['data-vid']
            
            if item.get('title'):
                videos.append(item)
        
        return videos if videos else None
    
    def _extract_image_pack(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Image Pack results"""
        images = {
            'title': 'Images',
            'images': []
        }
        
        # Look for image container
        img_container = soup.select_one('div[data-attrid="kc:/images"], g-section-with-header:has(g-img)')
        
        if img_container:
            img_elements = img_container.select('div[data-ri], g-img')
            
            for img in img_elements[:10]:
                item = {}
                
                # Image URL
                img_elem = img.select_one('img[src], img[data-src]')
                if img_elem:
                    item['url'] = img_elem.get('src') or img_elem.get('data-src')
                
                # Title/Alt text
                if img_elem and img_elem.get('alt'):
                    item['title'] = img_elem['alt']
                
                # Source
                source_elem = img.select_one('cite, span.LAA3yd')
                if source_elem:
                    item['source'] = source_elem.get_text(strip=True)
                
                # Link
                link_elem = img.select_one('a[href]')
                if link_elem:
                    item['link'] = self._clean_google_url(link_elem.get('href', ''))
                
                if item.get('url'):
                    images['images'].append(item)
        
        return images if images['images'] else None
    
    def _extract_twitter_results(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Twitter/X results"""
        tweets = []
        
        # Look for Twitter container
        twitter_container = soup.select_one('div[data-attrid*="twitter"], g-section-with-header:has(cite:contains("twitter.com"))')
        
        if twitter_container:
            tweet_elements = twitter_container.select('g-inner-card, div[data-hveid]')
            
            for tweet in tweet_elements[:10]:
                item = {}
                
                # Author
                author_elem = tweet.select_one('div.oUAcPd, cite')
                if author_elem:
                    author_text = author_elem.get_text(strip=True)
                    if '@' in author_text:
                        item['author'] = author_text
                
                # Tweet content
                content_elem = tweet.select_one('div.xcQxgd, span.f')
                if content_elem:
                    item['content'] = content_elem.get_text(strip=True)
                
                # Date
                date_elem = tweet.select_one('span.f, span.dwsObb')
                if date_elem:
                    item['date'] = date_elem.get_text(strip=True)
                
                # URL
                link_elem = tweet.select_one('a[href*="twitter.com"], a[href*="x.com"]')
                if link_elem:
                    item['url'] = link_elem.get('href', '')
                
                if item.get('content'):
                    tweets.append(item)
        
        return tweets if tweets else None
    
    def _extract_top_questions(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract expanded People Also Ask questions with answers"""
        questions = []
        
        # Find PAA container
        paa_container = soup.select_one('div[data-attrid="PeopleAlsoAsk"], div.related-question-pair')
        
        if paa_container:
            question_elements = paa_container.select('div[data-q], div.dnXCYb')
            
            for q_elem in question_elements[:10]:
                item = {}
                
                # Question
                question_text = q_elem.get('data-q', '')
                if not question_text:
                    q_span = q_elem.select_one('span.CSkcDe, div[role="button"]')
                    if q_span:
                        question_text = q_span.get_text(strip=True)
                
                if question_text:
                    item['question'] = question_text
                
                # Try to get answer (if expanded in HTML)
                answer_elem = q_elem.select_one('div.wDYxhc, span.hgKElc')
                if answer_elem:
                    item['answer'] = answer_elem.get_text(strip=True)[:500]
                
                # Source for answer
                source_elem = q_elem.select_one('cite, a.l')
                if source_elem:
                    item['source'] = source_elem.get_text(strip=True)
                
                if item.get('question'):
                    questions.append(item)
        
        return questions if questions else None
    
    def _extract_recipes(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Recipe results"""
        recipes = []
        
        recipe_container = soup.select_one('div[data-attrid*="recipe"], g-section-with-header:has(span:contains("recipe"))')
        
        if recipe_container:
            recipe_elements = recipe_container.select('g-inner-card, div.MUs7Tc')
            
            for recipe in recipe_elements[:10]:
                item = {}
                
                # Recipe name
                name_elem = recipe.select_one('div[role="heading"], h3')
                if name_elem:
                    item['name'] = name_elem.get_text(strip=True)
                
                # Cook time
                time_elem = recipe.select_one('span.wHYlTd')
                if time_elem:
                    item['cook_time'] = time_elem.get_text(strip=True)
                
                # Rating
                rating_elem = recipe.select_one('span[aria-label*="star"]')
                if rating_elem:
                    item['rating'] = rating_elem.get('aria-label', '')
                
                # Source
                source_elem = recipe.select_one('cite, span.ILOuge')
                if source_elem:
                    item['source'] = source_elem.get_text(strip=True)
                
                # Ingredients (if shown)
                ingredients = recipe.select('span.YrbPuc')
                if ingredients:
                    item['ingredients'] = [i.get_text(strip=True) for i in ingredients]
                
                if item.get('name'):
                    recipes.append(item)
        
        return recipes if recipes else None
    
    def _extract_shopping_results(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Shopping results (different from shopping ads)"""
        products = []
        
        shopping_container = soup.select_one('div[data-attrid*="shopping"], div.commercial-unit')
        
        if shopping_container:
            product_elements = shopping_container.select('div.pla-unit, div.mnr-c')
            
            for product in product_elements[:10]:
                item = {}
                
                # Product name
                name_elem = product.select_one('h3, div.pygFLb')
                if name_elem:
                    item['name'] = name_elem.get_text(strip=True)
                
                # Price
                price_elem = product.select_one('span.e10twf, span.a8Pemb')
                if price_elem:
                    item['price'] = price_elem.get_text(strip=True)
                
                # Store
                store_elem = product.select_one('span.vjtvZc, cite')
                if store_elem:
                    item['store'] = store_elem.get_text(strip=True)
                
                # Rating
                rating_elem = product.select_one('span[aria-label*="star"]')
                if rating_elem:
                    item['rating'] = rating_elem.get('aria-label', '')
                
                # Image
                img_elem = product.select_one('img[src]')
                if img_elem:
                    item['image'] = img_elem.get('src', '')
                
                if item.get('name'):
                    products.append(item)
        
        return products if products else None
    
    def _extract_flights(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Flight information"""
        flight_elem = soup.select_one('div[data-attrid*="flight"], div.flight-module')
        
        if flight_elem:
            flight_info = {
                'type': 'flights'
            }
            
            # Extract flight details
            details = flight_elem.get_text(strip=True)
            if details:
                flight_info['details'] = details
            
            return flight_info
        
        return None
    
    def _extract_hotels(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Hotel results"""
        hotels = []
        
        hotel_container = soup.select_one('div[data-attrid*="hotel"], div.hotels-module')
        
        if hotel_container:
            hotel_elements = hotel_container.select('div.BTPx6e, g-inner-card')
            
            for hotel in hotel_elements[:10]:
                item = {}
                
                # Hotel name
                name_elem = hotel.select_one('h3, div[role="heading"]')
                if name_elem:
                    item['name'] = name_elem.get_text(strip=True)
                
                # Price
                price_elem = hotel.select_one('span.prHGWc, span.price')
                if price_elem:
                    item['price'] = price_elem.get_text(strip=True)
                
                # Rating
                rating_elem = hotel.select_one('span[aria-label*="star"]')
                if rating_elem:
                    item['rating'] = rating_elem.get('aria-label', '')
                
                # Location
                location_elem = hotel.select_one('span.rllt__details')
                if location_elem:
                    item['location'] = location_elem.get_text(strip=True)
                
                if item.get('name'):
                    hotels.append(item)
        
        return hotels if hotels else None
    
    def _extract_jobs(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Job listings"""
        jobs = []
        
        job_container = soup.select_one('div[data-attrid*="job"], div.jobs-module')
        
        if job_container:
            job_elements = job_container.select('g-inner-card, div.iFjolb')
            
            for job in job_elements[:10]:
                item = {}
                
                # Job title
                title_elem = job.select_one('div[role="heading"], h3')
                if title_elem:
                    item['title'] = title_elem.get_text(strip=True)
                
                # Company
                company_elem = job.select_one('div.Qk80Jf, span.company')
                if company_elem:
                    item['company'] = company_elem.get_text(strip=True)
                
                # Location
                location_elem = job.select_one('span.Qk80Jf:last-child')
                if location_elem:
                    item['location'] = location_elem.get_text(strip=True)
                
                # Posted date
                date_elem = job.select_one('span.LL4CDc')
                if date_elem:
                    item['posted'] = date_elem.get_text(strip=True)
                
                # Platform (Indeed, LinkedIn, etc.)
                platform_elem = job.select_one('cite')
                if platform_elem:
                    item['platform'] = platform_elem.get_text(strip=True)
                
                if item.get('title'):
                    jobs.append(item)
        
        return jobs if jobs else None
    
    def _extract_events(self, soup: BeautifulSoup) -> Optional[List[Dict[str, Any]]]:
        """Extract Event listings"""
        events = []
        
        event_container = soup.select_one('div[data-attrid*="event"], g-section-with-header:has(div.event)')
        
        if event_container:
            event_elements = event_container.select('div.PaEvOc, g-inner-card')
            
            for event in event_elements[:10]:
                item = {}
                
                # Event name
                name_elem = event.select_one('div[role="heading"], h3')
                if name_elem:
                    item['name'] = name_elem.get_text(strip=True)
                
                # Date/Time
                date_elem = event.select_one('div.cEPPT')
                if date_elem:
                    item['date'] = date_elem.get_text(strip=True)
                
                # Location
                location_elem = event.select_one('span.LrzXr')
                if location_elem:
                    item['location'] = location_elem.get_text(strip=True)
                
                if item.get('name'):
                    events.append(item)
        
        return events if events else None
    
    def _extract_calculators(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Calculator widget"""
        calc_elem = soup.select_one('div[data-attrid="calculator"], div.vk_c.card')
        
        if calc_elem:
            return {
                'type': 'calculator',
                'expression': calc_elem.select_one('span.vUGUtc, span.cwclet')
            }
        
        return None
    
    def _extract_definitions(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Dictionary definitions"""
        definition_elem = soup.select_one('div[data-attrid="define"], div.knowledge-panel:has(audio)')
        
        if definition_elem:
            definition = {
                'word': '',
                'phonetic': '',
                'meanings': []
            }
            
            # Word
            word_elem = definition_elem.select_one('span.JCvguc, div[data-attrid="title"]')
            if word_elem:
                definition['word'] = word_elem.get_text(strip=True)
            
            # Phonetic
            phonetic_elem = definition_elem.select_one('span.LTKOO')
            if phonetic_elem:
                definition['phonetic'] = phonetic_elem.get_text(strip=True)
            
            # Meanings
            meaning_elements = definition_elem.select('div[data-attrid="definition"]')
            for meaning in meaning_elements[:5]:
                definition['meanings'].append(meaning.get_text(strip=True))
            
            return definition if definition['word'] else None
        
        return None
    
    def _extract_translations(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Translation widget"""
        translate_elem = soup.select_one('div[data-attrid="translate"], div.tw-src')
        
        if translate_elem:
            translation = {
                'source_language': '',
                'target_language': '',
                'source_text': '',
                'translation': ''
            }
            
            # Get translation text
            result_elem = translate_elem.select_one('pre.tw-data-text, span.Y2IQFc')
            if result_elem:
                translation['translation'] = result_elem.get_text(strip=True)
            
            return translation if translation['translation'] else None
        
        return None
    
    def _extract_weather(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Weather widget"""
        weather_elem = soup.select_one('div[data-attrid="weather"], div.wob_wc')
        
        if weather_elem:
            weather = {
                'location': '',
                'temperature': '',
                'condition': '',
                'forecast': []
            }
            
            # Temperature
            temp_elem = weather_elem.select_one('span.wob_t, span.q8U8x')
            if temp_elem:
                weather['temperature'] = temp_elem.get_text(strip=True)
            
            # Condition
            condition_elem = weather_elem.select_one('div.wob_dcp, span.wob_dc')
            if condition_elem:
                weather['condition'] = condition_elem.get_text(strip=True)
            
            # Location
            location_elem = weather_elem.select_one('div.wob_loc')
            if location_elem:
                weather['location'] = location_elem.get_text(strip=True)
            
            return weather if weather['temperature'] else None
        
        return None
    
    def _extract_sports_results(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Sports scores/results"""
        sports_elem = soup.select_one('div[data-attrid*="sports"], div.imso-hov')
        
        if sports_elem:
            return {
                'type': 'sports',
                'content': sports_elem.get_text(strip=True)[:500]
            }
        
        return None
    
    def _extract_stock_info(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Stock market information"""
        stock_elem = soup.select_one('div[data-attrid="finance"], g-card-section:has(span.IsqQVc)')
        
        if stock_elem:
            stock = {
                'symbol': '',
                'price': '',
                'change': '',
                'change_percent': ''
            }
            
            # Stock symbol
            symbol_elem = stock_elem.select_one('span.HfMth')
            if symbol_elem:
                stock['symbol'] = symbol_elem.get_text(strip=True)
            
            # Price
            price_elem = stock_elem.select_one('span.IsqQVc')
            if price_elem:
                stock['price'] = price_elem.get_text(strip=True)
            
            # Change
            change_elem = stock_elem.select_one('span.WlRRw')
            if change_elem:
                change_text = change_elem.get_text(strip=True)
                stock['change'] = change_text
            
            return stock if stock['price'] else None
        
        return None
    
    def _extract_currency_converter(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Currency converter widget"""
        currency_elem = soup.select_one('div[data-attrid="currency"], div.currency-converter')
        
        if currency_elem:
            return {
                'type': 'currency_converter',
                'content': currency_elem.get_text(strip=True)[:200]
            }
        
        return None
    
    def _extract_time_info(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract Time/timezone information"""
        time_elem = soup.select_one('div[data-attrid="time"], div.gsrt.vk_bk')
        
        if time_elem:
            time_info = {
                'time': '',
                'timezone': '',
                'location': ''
            }
            
            # Time
            time_text = time_elem.select_one('div.gsrt.vk_bk, div.vk_c.vk_gy')
            if time_text:
                time_info['time'] = time_text.get_text(strip=True)
            
            return time_info if time_info['time'] else None
        
        return None


class GoogleSearchService:
    """
    High-level service for Google search with parsing
    """
    
    def __init__(self, scrape_service=None):
        """
        Initialize with scrape service
        
        Args:
            scrape_service: Instance of ScrapeDoService
        """
        self.parser = GoogleSearchParser()
        self.scrape_service = scrape_service
    
    def search(
        self,
        query: str,
        country_code: str = 'US',
        num_results: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform Google search and parse results
        
        Args:
            query: Search query
            country_code: Country code for localization
            num_results: Number of results to request
            **kwargs: Additional parameters for scrape_google_search
            
        Returns:
            Parsed search results with separated organic and sponsored results
        """
        if not self.scrape_service:
            from services.scrape_do import get_scraper
            self.scrape_service = get_scraper()
        
        # Perform search
        raw_result = self.scrape_service.scrape_google_search(
            query=query,
            country_code=country_code,
            num_results=num_results,
            **kwargs
        )
        
        if not raw_result or not raw_result.get('success'):
            return {
                'success': False,
                'error': raw_result.get('error', 'Search failed'),
                'organic_results': [],
                'sponsored_results': []
            }
        
        # Parse HTML
        html = raw_result.get('html', '')
        parsed = self.parser.parse(html)
        
        # Combine raw and parsed data
        return {
            'success': True,
            'query': query,
            'country_code': country_code,
            'organic_results': parsed.get('organic_results', []),
            'sponsored_results': parsed.get('sponsored_results', []),
            'results': parsed.get('results', []),  # Backward compatibility
            'total_results': parsed.get('total_results'),
            'search_time': parsed.get('search_time'),
            'related_searches': parsed.get('related_searches', []),
            'people_also_ask': parsed.get('people_also_ask', []),
            'featured_snippet': parsed.get('featured_snippet'),
            'knowledge_panel': parsed.get('knowledge_panel'),
            'organic_count': parsed.get('organic_count', 0),
            'sponsored_count': parsed.get('sponsored_count', 0),
            'result_count': len(parsed.get('organic_results', [])),
            'raw_html_length': len(html),
            'search_params': raw_result.get('search_params', {})
        }
    
    def search_and_filter(
        self,
        query: str,
        country_code: str = 'US',
        num_results: int = 10,
        domain_filter: Optional[str] = None,
        exclude_domains: Optional[List[str]] = None,
        include_sponsored: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search and apply filters to results
        
        Args:
            query: Search query
            country_code: Country code
            num_results: Number of results
            domain_filter: Only include results from this domain
            exclude_domains: Exclude results from these domains
            include_sponsored: Whether to include sponsored results
            **kwargs: Additional search parameters
            
        Returns:
            Filtered search results
        """
        # Perform search
        results = self.search(query, country_code, num_results, **kwargs)
        
        if not results.get('success'):
            return results
        
        # Apply filters to organic results
        filtered_organic = []
        for result in results.get('organic_results', []):
            domain = result.get('domain', '')
            
            # Apply domain filter
            if domain_filter and domain_filter not in domain:
                continue
            
            # Apply exclusion filter
            if exclude_domains and any(excl in domain for excl in exclude_domains):
                continue
            
            filtered_organic.append(result)
        
        # Apply filters to sponsored results if included
        filtered_sponsored = []
        if include_sponsored:
            for result in results.get('sponsored_results', []):
                domain = result.get('domain', '')
                
                # Apply domain filter
                if domain_filter and domain_filter not in domain:
                    continue
                
                # Apply exclusion filter
                if exclude_domains and any(excl in domain for excl in exclude_domains):
                    continue
                
                filtered_sponsored.append(result)
        
        results['organic_results'] = filtered_organic
        results['sponsored_results'] = filtered_sponsored
        results['results'] = filtered_organic  # Backward compatibility
        results['organic_count'] = len(filtered_organic)
        results['sponsored_count'] = len(filtered_sponsored)
        results['result_count'] = len(filtered_organic)
        results['filters_applied'] = {
            'domain_filter': domain_filter,
            'exclude_domains': exclude_domains,
            'include_sponsored': include_sponsored
        }
        
        return results