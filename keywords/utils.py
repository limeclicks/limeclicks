"""
Utility functions for keywords app
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from services.r2_storage import get_r2_service
from services.scrape_do import ScrapeDoService
from services.google_search_parser import GoogleSearchParser
from .models import Keyword, Rank

logger = logging.getLogger(__name__)


class KeywordRankTracker:
    """
    Service for tracking keyword rankings and storing results in R2
    """
    
    def __init__(self):
        self.r2_service = get_r2_service()
        self.scraper = ScrapeDoService()
        self.parser = GoogleSearchParser()
    
    def track_keyword(self, keyword: Keyword) -> Dict[str, Any]:
        """
        Track ranking for a keyword and store results
        
        Args:
            keyword: Keyword model instance
        
        Returns:
            Dict with tracking results
        """
        try:
            # Mark keyword as processing
            keyword.processing = True
            keyword.save()
            
            # Scrape Google search results
            scrape_result = self.scraper.scrape_google_search(
                query=keyword.keyword,
                country_code=keyword.country,
                num_results=100,
                location=keyword.location if keyword.location else None,
                use_exact_location=bool(keyword.location)
            )
            
            if not scrape_result or not scrape_result.get('success'):
                # Update keyword with error
                keyword.error = scrape_result.get('error', 'Failed to scrape')
                keyword.failed_api_hit_count += 1
                keyword.processing = False
                keyword.save()
                
                return {
                    'success': False,
                    'error': keyword.error
                }
            
            # Parse the HTML
            html = scrape_result.get('html', '')
            parsed_results = self.parser.parse(html)
            
            # Find domain ranking
            domain_rank = self._find_domain_rank(
                parsed_results,
                keyword.project.domain
            )
            
            # Store raw results in R2
            storage_result = self._store_search_results(
                keyword,
                parsed_results,
                html
            )
            
            # Store rank-specific data in R2
            rank_data_key = self._store_rank_data(
                keyword,
                domain_rank,
                parsed_results
            )
            
            # Create rank entry
            rank = Rank.objects.create(
                keyword=keyword,
                rank=domain_rank['position'] if domain_rank else 0,
                is_organic=domain_rank.get('is_organic', True) if domain_rank else True,
                has_map_result=bool(parsed_results.get('local_pack')),
                has_video_result=bool(parsed_results.get('video_results')),
                has_image_result=bool(parsed_results.get('image_results')),
                number_of_results=parsed_results.get('total_results', 0),
                search_results_file=storage_result.get('results_key', ''),
                rank_file=rank_data_key
            )
            
            # Update keyword stats
            keyword.success_api_hit_count += 1
            keyword.processing = False
            keyword.error = ''
            
            # Update ranking URL if found
            if domain_rank:
                keyword.rank_url = domain_rank.get('url', '')
                keyword.on_map = domain_rank.get('in_map', False)
            
            keyword.save()
            
            return {
                'success': True,
                'rank': rank.rank,
                'is_organic': rank.is_organic,
                'storage_keys': storage_result,
                'total_results': rank.number_of_results
            }
            
        except Exception as e:
            logger.error(f"Error tracking keyword {keyword.keyword}: {str(e)}")
            
            # Update keyword with error
            keyword.error = str(e)
            keyword.failed_api_hit_count += 1
            keyword.processing = False
            keyword.save()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _find_domain_rank(
        self,
        parsed_results: Dict[str, Any],
        domain: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find domain ranking in search results
        
        Args:
            parsed_results: Parsed search results
            domain: Domain to search for
        
        Returns:
            Dict with ranking info or None if not found
        """
        # Clean domain (remove www, http, etc.)
        domain = domain.lower().replace('www.', '').replace('http://', '').replace('https://', '')
        
        # Check organic results
        organic_results = parsed_results.get('organic_results', [])
        for i, result in enumerate(organic_results, 1):
            result_url = result.get('url', '').lower()
            if domain in result_url:
                return {
                    'position': i,
                    'url': result.get('url'),
                    'title': result.get('title'),
                    'is_organic': True,
                    'in_map': False
                }
        
        # Check sponsored results
        sponsored_results = parsed_results.get('sponsored_results', [])
        for i, result in enumerate(sponsored_results, 1):
            result_url = result.get('url', '').lower()
            if domain in result_url:
                return {
                    'position': i,
                    'url': result.get('url'),
                    'title': result.get('title'),
                    'is_organic': False,
                    'in_map': False
                }
        
        # Check local pack/map results
        local_pack = parsed_results.get('local_pack', [])
        for i, result in enumerate(local_pack, 1):
            # Local pack might have website URLs
            website = result.get('website', '').lower()
            if domain in website:
                return {
                    'position': i,
                    'url': website,
                    'title': result.get('title'),
                    'is_organic': True,
                    'in_map': True
                }
        
        return None
    
    def _store_search_results(
        self,
        keyword: Keyword,
        parsed_results: Dict[str, Any],
        raw_html: str
    ) -> Dict[str, str]:
        """
        Store search results in R2
        
        Args:
            keyword: Keyword model instance
            parsed_results: Parsed search results
            raw_html: Raw HTML from search
        
        Returns:
            Dict with storage keys
        """
        # Create folder structure
        date_path = self.r2_service.create_folder_structure('search-results')
        
        # Generate unique keys
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{keyword.project.id}_{keyword.id}_{timestamp}"
        
        results = {}
        
        # Store parsed JSON results
        json_key = f"{date_path}/{base_name}_parsed.json"
        json_result = self.r2_service.upload_json(parsed_results, json_key)
        if json_result['success']:
            results['results_key'] = json_key
        
        # Store raw HTML (compressed)
        html_key = f"{date_path}/{base_name}_raw.html"
        html_result = self.r2_service.upload_file(
            raw_html.encode('utf-8'),
            html_key,
            content_type='text/html',
            metadata={
                'keyword': keyword.keyword,
                'country': keyword.country,
                'project_id': str(keyword.project.id),
                'keyword_id': str(keyword.id)
            }
        )
        if html_result['success']:
            results['html_key'] = html_key
        
        # Update keyword with storage references
        if keyword.scrape_do_files is None:
            keyword.scrape_do_files = []
        
        keyword.scrape_do_files.extend([
            results.get('results_key'),
            results.get('html_key')
        ])
        keyword.scrape_do_at = datetime.now()
        keyword.save()
        
        return results
    
    def _store_rank_data(
        self,
        keyword: Keyword,
        domain_rank: Optional[Dict[str, Any]],
        parsed_results: Dict[str, Any]
    ) -> str:
        """
        Store detailed rank data in R2
        
        Args:
            keyword: Keyword model instance
            domain_rank: Domain ranking info
            parsed_results: Parsed search results
        
        Returns:
            R2 storage key for the rank data file
        """
        # Create folder structure
        date_path = self.r2_service.create_folder_structure('rank-data')
        
        # Generate unique key
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rank_key = f"{date_path}/{keyword.project.id}_{keyword.id}_{timestamp}_rank.json"
        
        # Prepare rank data
        rank_data = {
            'keyword': keyword.keyword,
            'country': keyword.country,
            'location': keyword.location,
            'project_domain': keyword.project.domain,
            'timestamp': timestamp,
            'rank_info': domain_rank if domain_rank else {'position': 0, 'found': False},
            'serp_features': {
                'total_results': parsed_results.get('total_results', 0),
                'has_featured_snippet': bool(parsed_results.get('featured_snippet')),
                'has_knowledge_graph': bool(parsed_results.get('knowledge_graph')),
                'has_people_also_ask': bool(parsed_results.get('people_also_ask')),
                'has_local_pack': bool(parsed_results.get('local_pack')),
                'has_video_results': bool(parsed_results.get('video_results')),
                'has_image_results': bool(parsed_results.get('image_results')),
                'has_shopping_results': bool(parsed_results.get('shopping_results')),
                'has_news_results': bool(parsed_results.get('news_results')),
            },
            'organic_count': len(parsed_results.get('organic_results', [])),
            'sponsored_count': len(parsed_results.get('sponsored_results', [])),
            'top_10_results': parsed_results.get('organic_results', [])[:10],
            'related_searches': parsed_results.get('related_searches', []),
        }
        
        # Store in R2
        result = self.r2_service.upload_json(rank_data, rank_key)
        
        if result['success']:
            return rank_key
        else:
            logger.error(f"Failed to store rank data: {result.get('error')}")
            return ''


def bulk_track_keywords(keyword_ids: List[int]) -> Dict[str, Any]:
    """
    Track multiple keywords in bulk
    
    Args:
        keyword_ids: List of keyword IDs to track
    
    Returns:
        Dict with tracking results
    """
    tracker = KeywordRankTracker()
    results = {
        'success': [],
        'failed': [],
        'total': len(keyword_ids)
    }
    
    for keyword_id in keyword_ids:
        try:
            keyword = Keyword.objects.get(id=keyword_id)
            result = tracker.track_keyword(keyword)
            
            if result['success']:
                results['success'].append({
                    'keyword_id': keyword_id,
                    'keyword': keyword.keyword,
                    'rank': result['rank']
                })
            else:
                results['failed'].append({
                    'keyword_id': keyword_id,
                    'keyword': keyword.keyword,
                    'error': result['error']
                })
                
        except Keyword.DoesNotExist:
            results['failed'].append({
                'keyword_id': keyword_id,
                'error': 'Keyword not found'
            })
        except Exception as e:
            results['failed'].append({
                'keyword_id': keyword_id,
                'error': str(e)
            })
    
    return results