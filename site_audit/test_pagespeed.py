"""
Test script to verify PageSpeed Insights integration works correctly
"""

from site_audit.pagespeed_insights import PageSpeedInsightsClient
from site_audit.models import SiteAudit
import time


def test_pagespeed_structure():
    """Test that the PageSpeed Insights data structure works as expected"""
    
    # Create mock data that represents what we'd get from the API
    mock_psi_data = {
        'mobile': {
            'strategy': 'mobile',
            'analysis_timestamp': '2025-08-30T05:45:00.000Z',
            'scores': {
                'performance': 67,
                'accessibility': 89,
                'best_practices': 92,
                'seo': 95,
                'pwa': {'installable': True, 'pwa_optimized': False}
            },
            'lab_metrics': {
                'lcp': {'value': 2340, 'display_value': '2.3 s', 'score': 0.78},
                'cls': {'value': 0.12, 'display_value': '0.12', 'score': 0.65},
                'fcp': {'value': 1200, 'display_value': '1.2 s', 'score': 0.85},
                'speed_index': {'value': 3400, 'display_value': '3.4 s', 'score': 0.72},
                'tbt': {'value': 150, 'display_value': '150 ms', 'score': 0.89},
                'tti': {'value': 4200, 'display_value': '4.2 s', 'score': 0.68}
            },
            'field_data': {
                'page_level': {
                    'lcp': {'percentile': 2100, 'category': 'FAST'},
                    'inp': {'percentile': 45, 'category': 'FAST'},
                    'cls': {'percentile': 0.05, 'category': 'FAST'}
                }
            }
        },
        'desktop': {
            'strategy': 'desktop',
            'analysis_timestamp': '2025-08-30T05:45:00.000Z',
            'scores': {
                'performance': 89,
                'accessibility': 92,
                'best_practices': 96,
                'seo': 98,
                'pwa': {'installable': True, 'pwa_optimized': True}
            },
            'lab_metrics': {
                'lcp': {'value': 1200, 'display_value': '1.2 s', 'score': 0.95},
                'cls': {'value': 0.03, 'display_value': '0.03', 'score': 0.98},
                'fcp': {'value': 800, 'display_value': '0.8 s', 'score': 0.98},
                'speed_index': {'value': 1800, 'display_value': '1.8 s', 'score': 0.92},
                'tbt': {'value': 50, 'display_value': '50 ms', 'score': 0.98},
                'tti': {'value': 2100, 'display_value': '2.1 s', 'score': 0.89}
            },
            'field_data': {
                'origin_level': {
                    'lcp': {'percentile': 1800, 'category': 'FAST'},
                    'inp': {'percentile': 38, 'category': 'FAST'},
                    'cls': {'percentile': 0.02, 'category': 'FAST'}
                }
            }
        }
    }
    
    print("=== MOCK PAGESPEED INSIGHTS DATA TEST ===")
    print("\n📱 Mobile Performance Data:")
    mobile = mock_psi_data['mobile']
    print(f"  Performance Score: {mobile['scores']['performance']}")
    print(f"  Accessibility Score: {mobile['scores']['accessibility']}")  
    print(f"  SEO Score: {mobile['scores']['seo']}")
    print(f"  LCP: {mobile['lab_metrics']['lcp']['display_value']} (score: {mobile['lab_metrics']['lcp']['score']})")
    print(f"  CLS: {mobile['lab_metrics']['cls']['display_value']} (score: {mobile['lab_metrics']['cls']['score']})")
    print(f"  Speed Index: {mobile['lab_metrics']['speed_index']['display_value']}")
    
    print("\n🖥️  Desktop Performance Data:")
    desktop = mock_psi_data['desktop']
    print(f"  Performance Score: {desktop['scores']['performance']}")
    print(f"  Accessibility Score: {desktop['scores']['accessibility']}")
    print(f"  SEO Score: {desktop['scores']['seo']}")
    print(f"  LCP: {desktop['lab_metrics']['lcp']['display_value']} (score: {desktop['lab_metrics']['lcp']['score']})")
    print(f"  CLS: {desktop['lab_metrics']['cls']['display_value']} (score: {desktop['lab_metrics']['cls']['score']})")
    print(f"  Speed Index: {desktop['lab_metrics']['speed_index']['display_value']}")
    
    # Test updating a site audit with this data
    try:
        site_audit = SiteAudit.objects.get(id=17)
        
        # Update with mock data
        site_audit.mobile_performance = mock_psi_data['mobile']
        site_audit.desktop_performance = mock_psi_data['desktop']
        site_audit.performance_score_mobile = mock_psi_data['mobile']['scores']['performance']
        site_audit.performance_score_desktop = mock_psi_data['desktop']['scores']['performance']
        
        site_audit.save(update_fields=[
            'mobile_performance', 
            'desktop_performance', 
            'performance_score_mobile', 
            'performance_score_desktop'
        ])
        
        # Recalculate overall score
        site_audit.calculate_overall_score()
        site_audit.save(update_fields=['overall_site_health_score'])
        
        print(f"\n✅ Successfully updated SiteAudit {site_audit.id}")
        print(f"   Mobile Score: {site_audit.performance_score_mobile}")
        print(f"   Desktop Score: {site_audit.performance_score_desktop}")
        print(f"   Overall Health Score: {site_audit.overall_site_health_score:.1f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error updating site audit: {e}")
        return False


def test_api_with_delay():
    """Test actual API call with delay to avoid rate limiting"""
    print("\n=== REAL API TEST (with delay) ===")
    
    client = PageSpeedInsightsClient()
    
    # Test with a simpler URL that might be less rate-limited
    test_url = "https://example.com"
    
    print(f"Testing PageSpeed Insights API with: {test_url}")
    print("Waiting 10 seconds to avoid rate limiting...")
    time.sleep(10)
    
    # Try mobile first
    mobile_data = client.analyze_url(test_url, strategy='mobile')
    if mobile_data:
        print("✅ Mobile data collected successfully")
        print(f"   Performance Score: {mobile_data.get('scores', {}).get('performance', 'N/A')}")
        print(f"   Strategy: {mobile_data.get('strategy', 'N/A')}")
    else:
        print("❌ Failed to collect mobile data")
    
    print("Waiting another 10 seconds...")
    time.sleep(10)
    
    # Try desktop
    desktop_data = client.analyze_url(test_url, strategy='desktop')
    if desktop_data:
        print("✅ Desktop data collected successfully")
        print(f"   Performance Score: {desktop_data.get('scores', {}).get('performance', 'N/A')}")
        print(f"   Strategy: {desktop_data.get('strategy', 'N/A')}")
    else:
        print("❌ Failed to collect desktop data")
    
    return mobile_data or desktop_data


if __name__ == "__main__":
    # Test the data structure with mock data
    structure_test = test_pagespeed_structure()
    
    # Optionally test real API (commented out to avoid rate limiting during development)
    # api_test = test_api_with_delay()
    
    print(f"\n=== TEST SUMMARY ===")
    print(f"Structure Test: {'✅ PASSED' if structure_test else '❌ FAILED'}")
    # print(f"API Test: {'✅ PASSED' if api_test else '❌ FAILED'}")