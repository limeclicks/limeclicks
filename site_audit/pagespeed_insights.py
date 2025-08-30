"""
PageSpeed Insights API client for collecting performance data
"""

import requests
import logging
from typing import Dict, Optional, Union
from django.conf import settings

logger = logging.getLogger(__name__)


class PageSpeedInsightsClient:
    """Client for Google PageSpeed Insights API v5"""
    
    BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize PageSpeed Insights client
        
        Args:
            api_key: Google PageSpeed Insights API key. If None, will try to get from settings.GOOGLE_PSI_KEY
        """
        self.api_key = api_key or getattr(settings, 'GOOGLE_PSI_KEY', None)
        if not self.api_key:
            logger.warning("No Google PageSpeed Insights API key found. Some features may be limited.")
    
    def analyze_url(self, url: str, strategy: str = 'mobile', locale: str = 'en') -> Optional[Dict]:
        """
        Analyze a URL using PageSpeed Insights API
        
        Args:
            url: The URL to analyze
            strategy: 'mobile' or 'desktop'
            locale: Language code for the results
            
        Returns:
            Dict containing the analysis results, or None if failed
        """
        params = {
            'url': url,
            'strategy': strategy,
            'locale': locale,
            'category': ['PERFORMANCE', 'ACCESSIBILITY', 'BEST_PRACTICES', 'SEO', 'PWA']
        }
        
        if self.api_key:
            params['key'] = self.api_key
        
        try:
            logger.info(f"Analyzing {url} with strategy {strategy}")
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_pagespeed_data(data, strategy)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PageSpeed Insights API error for {url} ({strategy}): {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing PageSpeed Insights data for {url} ({strategy}): {e}")
            return None
    
    def _parse_pagespeed_data(self, raw_data: Dict, strategy: str) -> Dict:
        """
        Parse raw PageSpeed Insights API response into structured data
        
        Args:
            raw_data: Raw API response
            strategy: 'mobile' or 'desktop'
            
        Returns:
            Structured performance data
        """
        lighthouse_result = raw_data.get('lighthouseResult', {})
        loading_experience = raw_data.get('loadingExperience', {})
        origin_loading_experience = raw_data.get('originLoadingExperience', {})
        
        # Extract lighthouse categories (scores)
        categories = lighthouse_result.get('categories', {})
        scores = {
            'performance': self._get_score(categories.get('performance')),
            'accessibility': self._get_score(categories.get('accessibility')),
            'best_practices': self._get_score(categories.get('best-practices')),
            'seo': self._get_score(categories.get('seo')),
            'pwa': self._get_pwa_score(categories.get('pwa'))
        }
        
        # Extract lab metrics (from lighthouse audits)
        audits = lighthouse_result.get('audits', {})
        lab_metrics = self._extract_lab_metrics(audits)
        
        # Extract field data (Core Web Vitals from CrUX)
        field_data = self._extract_field_data(loading_experience, origin_loading_experience)
        
        return {
            'strategy': strategy,
            'analysis_timestamp': raw_data.get('analysisUTCTimestamp'),
            'scores': scores,
            'lab_metrics': lab_metrics,
            'field_data': field_data,
            'raw_data': {
                'final_url': lighthouse_result.get('finalUrl'),
                'lighthouse_version': lighthouse_result.get('lighthouseVersion'),
                'user_agent': lighthouse_result.get('userAgent')
            }
        }
    
    def _get_score(self, category_data: Optional[Dict]) -> Optional[int]:
        """Extract score from category data (0-100)"""
        if not category_data:
            return None
        score = category_data.get('score')
        return int(score * 100) if score is not None else None
    
    def _get_pwa_score(self, pwa_data: Optional[Dict]) -> Dict:
        """Extract PWA audit results (not a numeric score)"""
        if not pwa_data:
            return {'installable': None, 'pwa_optimized': None}
        
        # PWA is pass/fail based on individual audits
        return {
            'installable': pwa_data.get('score', 0) > 0.5,
            'pwa_optimized': pwa_data.get('score', 0) == 1.0
        }
    
    def _extract_lab_metrics(self, audits: Dict) -> Dict:
        """Extract lab metrics from Lighthouse audits"""
        metrics = {}
        
        # Core Web Vitals (Lab)
        lcp = audits.get('largest-contentful-paint', {})
        metrics['lcp'] = {
            'value': lcp.get('numericValue'),
            'display_value': lcp.get('displayValue'),
            'score': self._get_audit_score(lcp)
        }
        
        cls = audits.get('cumulative-layout-shift', {})
        metrics['cls'] = {
            'value': cls.get('numericValue'),
            'display_value': cls.get('displayValue'),
            'score': self._get_audit_score(cls)
        }
        
        # Other important metrics
        fcp = audits.get('first-contentful-paint', {})
        metrics['fcp'] = {
            'value': fcp.get('numericValue'),
            'display_value': fcp.get('displayValue'),
            'score': self._get_audit_score(fcp)
        }
        
        speed_index = audits.get('speed-index', {})
        metrics['speed_index'] = {
            'value': speed_index.get('numericValue'),
            'display_value': speed_index.get('displayValue'),
            'score': self._get_audit_score(speed_index)
        }
        
        tbt = audits.get('total-blocking-time', {})
        metrics['tbt'] = {
            'value': tbt.get('numericValue'),
            'display_value': tbt.get('displayValue'),
            'score': self._get_audit_score(tbt)
        }
        
        tti = audits.get('interactive', {})
        metrics['tti'] = {
            'value': tti.get('numericValue'),
            'display_value': tti.get('displayValue'),
            'score': self._get_audit_score(tti)
        }
        
        # Server response time
        server_response = audits.get('server-response-time', {})
        metrics['server_response_time'] = {
            'value': server_response.get('numericValue'),
            'display_value': server_response.get('displayValue'),
            'score': self._get_audit_score(server_response)
        }
        
        return metrics
    
    def _extract_field_data(self, loading_experience: Dict, origin_loading_experience: Dict) -> Dict:
        """Extract field data (real-world metrics from CrUX)"""
        field_data = {}
        
        # Page-level field data
        if loading_experience:
            field_data['page_level'] = self._parse_crux_data(loading_experience)
        
        # Origin-level field data
        if origin_loading_experience:
            field_data['origin_level'] = self._parse_crux_data(origin_loading_experience)
        
        return field_data
    
    def _parse_crux_data(self, crux_data: Dict) -> Dict:
        """Parse CrUX (Chrome User Experience Report) data"""
        metrics = crux_data.get('metrics', {})
        parsed = {}
        
        # Core Web Vitals from CrUX
        for metric_key, metric_name in [
            ('LARGEST_CONTENTFUL_PAINT_MS', 'lcp'),
            ('INTERACTION_TO_NEXT_PAINT', 'inp'),
            ('CUMULATIVE_LAYOUT_SHIFT_SCORE', 'cls'),
            ('FIRST_CONTENTFUL_PAINT_MS', 'fcp'),
            ('FIRST_INPUT_DELAY_MS', 'fid')  # Legacy, being replaced by INP
        ]:
            if metric_key in metrics:
                metric_data = metrics[metric_key]
                parsed[metric_name] = {
                    'percentile': metric_data.get('percentile'),
                    'distributions': metric_data.get('distributions', []),
                    'category': metric_data.get('category')  # FAST, AVERAGE, SLOW
                }
        
        return parsed
    
    def _get_audit_score(self, audit_data: Dict) -> Optional[float]:
        """Get score from audit data (0.0 - 1.0)"""
        return audit_data.get('score') if audit_data else None


def collect_pagespeed_data(url: str) -> Dict[str, Dict]:
    """
    Collect PageSpeed Insights data for both mobile and desktop
    
    Args:
        url: The URL to analyze
        
    Returns:
        Dict with 'mobile' and 'desktop' keys containing performance data
    """
    client = PageSpeedInsightsClient()
    results = {}
    
    logger.info(f"Starting PageSpeed Insights collection for {url}")
    
    # Collect mobile data
    logger.info(f"Collecting mobile PageSpeed data for {url}")
    mobile_data = client.analyze_url(url, strategy='mobile')
    if mobile_data:
        results['mobile'] = mobile_data
        logger.info(f"Mobile data collected successfully. Scores: {mobile_data.get('scores', {})}")
    else:
        logger.error(f"Failed to collect mobile PageSpeed data for {url}")
        results['mobile'] = {}
    
    # Collect desktop data
    logger.info(f"Collecting desktop PageSpeed data for {url}")
    desktop_data = client.analyze_url(url, strategy='desktop')
    if desktop_data:
        results['desktop'] = desktop_data
        logger.info(f"Desktop data collected successfully. Scores: {desktop_data.get('scores', {})}")
    else:
        logger.error(f"Failed to collect desktop PageSpeed data for {url}")
        results['desktop'] = {}
    
    logger.info(f"PageSpeed collection complete. Mobile: {bool(results.get('mobile'))}, Desktop: {bool(results.get('desktop'))}")
    
    return results