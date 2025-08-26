"""
Tests for UK rankings with realistic SERP data for fastgenerations.co.uk
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone

from keywords.models import Keyword, Rank
from keywords.ranking_extractor import RankingExtractor
from project.models import Project
from accounts.models import User


def create_uk_serp_results(domain="fastgenerations.co.uk", keyword="pay per click agency brixton", rank_position=1):
    """
    Create realistic UK SERP results for digital marketing keywords
    """
    
    # UK competitor domains for digital marketing
    uk_competitors = [
        "digitalmarketing.co.uk",
        "clickslice.co.uk", 
        "exposure-ninja.com",
        "digitalagency.london",
        "wearegrow.com",
        "digitalboost.co.uk",
        "marketingagency.london",
        "seoworks.co.uk",
        "blueclaw.co.uk",
        "digitalstorm.co.uk",
        "webpresence.co.uk",
        "searchberg.com",
        "absolutedigital.co.uk",
        "digitalmarketing247.co.uk",
        "londondigitalagency.com"
    ]
    
    organic_results = []
    
    # Generate 100 organic results
    for i in range(1, 101):
        if rank_position and i == rank_position:
            # Insert our domain at the specified position
            if "pay per click" in keyword.lower():
                title = f"Expert PPC Agency in Brixton | Fast Generations"
                description = "Leading Pay Per Click agency in Brixton. We deliver ROI-focused PPC campaigns with proven results. Google Ads certified experts. Get a free PPC audit today!"
            elif "seo agency" in keyword.lower():
                title = f"Top SEO Agency in Wandsworth | Fast Generations"
                description = "Award-winning SEO agency in Wandsworth. Boost your rankings with our proven SEO strategies. Local SEO specialists. Free SEO consultation available."
            else:
                title = f"Digital Marketing Agency Clapham | Fast Generations"
                description = "Full-service digital marketing agency in Clapham. SEO, PPC, Social Media & Web Design. Transform your online presence. Get started today!"
            
            organic_results.append({
                'position': i,
                'title': title,
                'url': f"https://{domain}/services/{keyword.replace(' ', '-')}/",
                'displayed_url': f"{domain} › services › {keyword.replace(' ', '-')}",
                'description': description,
                'favicon': f"https://{domain}/favicon.ico",
                'cached_url': f"https://webcache.googleusercontent.com/search?q=cache:uk{i}:{domain}",
                'date': None,
                'sitelinks': [
                    {'title': 'Our Work', 'url': f'https://{domain}/case-studies/'},
                    {'title': 'About Us', 'url': f'https://{domain}/about/'},
                    {'title': 'Contact', 'url': f'https://{domain}/contact/'},
                    {'title': 'Free Audit', 'url': f'https://{domain}/free-audit/'}
                ] if i == 1 else []
            })
        else:
            # Generate competitor result
            comp_domain = uk_competitors[(i - 1) % len(uk_competitors)]
            location = keyword.split()[-1].title() if any(loc in keyword for loc in ['brixton', 'wandsworth', 'clapham']) else 'London'
            
            organic_results.append({
                'position': i,
                'title': f"Digital Marketing Services {location} | {comp_domain.split('.')[0].title()}",
                'url': f"https://{comp_domain}/{keyword.replace(' ', '-')}/",
                'displayed_url': f"{comp_domain} › {keyword.replace(' ', '-')}",
                'description': f"Professional digital marketing services in {location}. We help businesses grow online through SEO, PPC, and social media marketing.",
                'favicon': f"https://{comp_domain}/favicon.ico",
                'cached_url': f"https://webcache.googleusercontent.com/search?q=cache:uk{i}:{comp_domain}",
                'date': None,
                'sitelinks': []
            })
    
    # Generate sponsored results
    sponsored_results = [
        {
            'position': 1,
            'title': "Digital Marketing London - Get 20% Off First Month",
            'url': "https://www.digitalboost.co.uk/offer",
            'displayed_url': "Ad · www.digitalboost.co.uk",
            'description': "Top-rated digital marketing agency. SEO, PPC & Social Media. Free consultation.",
            'is_ad': True,
            'extensions': {
                'callout': ['Free Audit', '5 Star Reviews', 'No Setup Fees'],
                'sitelinks': [
                    {'title': 'SEO Services', 'url': 'https://digitalboost.co.uk/seo'},
                    {'title': 'PPC Management', 'url': 'https://digitalboost.co.uk/ppc'}
                ]
            }
        },
        {
            'position': 2,
            'title': "PPC Management Services - ROI Guaranteed",
            'url': "https://www.clickmanage.co.uk",
            'displayed_url': "Ad · www.clickmanage.co.uk",
            'description': "Google Ads experts. Reduce CPC by 30%. Free account review. No contracts.",
            'is_ad': True
        },
        {
            'position': 3,
            'title': "Local SEO Experts - Rank #1 Locally",
            'url': "https://www.localseouk.com",
            'displayed_url': "Ad · www.localseouk.com",
            'description': "Dominate local search results. Google My Business optimization. Call now!",
            'is_ad': True
        }
    ]
    
    # Add UK-specific SERP features
    response = {
        'organic_results': organic_results,
        'sponsored_results': sponsored_results,
        'total_results': "About 2,340,000 results",
        'search_time': "0.52 seconds",
        'organic_count': len(organic_results),
        'sponsored_count': len(sponsored_results),
        'results': organic_results,  # Backward compatibility
        
        # Related searches specific to UK digital marketing
        'related_searches': [
            f"{keyword} reviews",
            f"best {keyword}",
            f"{keyword} prices",
            f"affordable {keyword}",
            f"{keyword} near me",
            f"top rated {keyword}",
            f"{keyword} cost",
            f"cheap {keyword}"
        ],
        
        # People Also Ask - UK focused
        'people_also_ask': [
            {
                'question': f"How much does a {keyword.replace('agency', '').strip()} cost in the UK?",
                'snippet': f"The average cost for {keyword.replace('agency', 'services')} in the UK ranges from £500 to £5000 per month depending on the scope of work.",
                'source': "marketingweek.com",
                'source_url': "https://marketingweek.com/digital-agency-costs"
            },
            {
                'question': f"What should I look for in a {keyword}?",
                'snippet': "Look for proven results, transparent pricing, industry experience, and good communication. Check their case studies and client testimonials.",
                'source': "digitalmarketinginstitute.com",
                'source_url': "https://digitalmarketinginstitute.com/blog/choosing-agency"
            },
            {
                'question': f"How long does it take to see results from {keyword.split('agency')[0].strip()}?",
                'snippet': "SEO typically takes 3-6 months, PPC can show results immediately, and social media marketing usually takes 1-3 months to build momentum.",
                'source': "hubspot.com",
                'source_url': "https://blog.hubspot.com/marketing/timeline-results"
            }
        ],
        
        # Local pack for London areas
        'local_pack': [
            {
                'name': "Fast Generations Digital Marketing",
                'rating': 4.9,
                'reviews': 127,
                'address': f"123 High Street, {keyword.split()[-1].title()}, London SW1A 1AA",
                'phone': "020 7123 4567",
                'hours': "Mon-Fri 9AM-6PM",
                'website': f"https://{domain}",
                'type': "Digital marketing agency"
            },
            {
                'name': "Digital Boost London",
                'rating': 4.7,
                'reviews': 89,
                'address': f"456 Market Road, {keyword.split()[-1].title()}, London SW2B 2BB",
                'phone': "020 7987 6543",
                'hours': "Mon-Fri 8:30AM-5:30PM",
                'website': "https://digitalboost.co.uk",
                'type': "Marketing agency"
            },
            {
                'name': "Click Metrics Agency",
                'rating': 4.6,
                'reviews': 64,
                'address': f"789 Business Park, {keyword.split()[-1].title()}, London SW3C 3CC",
                'phone': "020 7456 1234",
                'hours': "Mon-Fri 9AM-5PM",
                'website': "https://clickmetrics.co.uk",
                'type': "Internet marketing service"
            }
        ]
    }
    
    # Add featured snippet if ranking #1
    if rank_position == 1:
        response['featured_snippet'] = {
            'text': f"Fast Generations is a leading {keyword} offering comprehensive digital marketing solutions including SEO, PPC, social media marketing, and web design. With over 10 years of experience and a proven track record of delivering results for local businesses, they are the go-to agency for companies looking to grow their online presence in {keyword.split()[-1].title()}.",
            'source': domain,
            'source_url': f"https://{domain}/services/",
            'type': "paragraph"
        }
    
    return response


class UKRankingTestCase(TestCase):
    """Test cases for UK rankings with fastgenerations.co.uk"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='uk_seo_manager',
            email='seo@fastgenerations.co.uk',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='fastgenerations.co.uk',
            title='Fast Generations Digital Marketing',
            active=True
        )
        
        # Create UK keywords
        self.keywords = {
            'ppc_brixton': Keyword.objects.create(
                project=self.project,
                keyword='pay per click agency brixton',
                country='UK',
                country_code='GB',
                location='Brixton, London, United Kingdom'
            ),
            'seo_wandsworth': Keyword.objects.create(
                project=self.project,
                keyword='seo agency wandsworth',
                country='UK',
                country_code='GB',
                location='Wandsworth, London, United Kingdom'
            ),
            'digital_clapham': Keyword.objects.create(
                project=self.project,
                keyword='digital marketing agency clapham',
                country='UK',
                country_code='GB',
                location='Clapham, London, United Kingdom'
            ),
        }
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_fastgenerations_ranks_1_for_ppc_brixton(self, mock_r2_service, mock_parser_class):
        """Test that fastgenerations.co.uk ranks #1 for 'pay per click agency brixton'"""
        keyword = self.keywords['ppc_brixton']
        
        # Setup mocks with realistic UK data
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_uk_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=1
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>UK SERP HTML</html>',
            timezone.now()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['rank'], 1)
        self.assertTrue(result['is_organic'])
        
        # Check Rank was created
        rank = Rank.objects.get(keyword=keyword)
        self.assertEqual(rank.rank, 1)
        self.assertTrue(rank.is_organic)
        self.assertTrue(rank.has_map_result)  # Local pack should be present
        
        # Check R2 data structure
        call_args = mock_r2.upload_json.call_args[0][0]
        self.assertEqual(call_args['keyword'], 'pay per click agency brixton')
        self.assertEqual(call_args['project_domain'], 'fastgenerations.co.uk')
        self.assertEqual(call_args['location'], 'Brixton, London, United Kingdom')
        self.assertEqual(call_args['country'], 'UK')
        
        # Verify results structure
        results = call_args['results']
        self.assertIn('organic_results', results)
        self.assertIn('sponsored_results', results)
        self.assertIn('local_pack', results)
        self.assertIn('featured_snippet', results)
        self.assertIn('people_also_ask', results)
        
        # Check organic results populated correctly
        self.assertEqual(len(results['organic_results']), 100)
        self.assertEqual(len(results['sponsored_results']), 3)
        self.assertEqual(len(results['local_pack']), 3)
        
        # Verify our domain is at position 1
        first_result = results['organic_results'][0]
        self.assertEqual(first_result['position'], 1)
        self.assertIn('fastgenerations.co.uk', first_result['url'])
        self.assertIn('PPC', first_result['title'])
        self.assertIn('Brixton', first_result['title'])
        
        # Check featured snippet exists since we're #1
        self.assertIsNotNone(results['featured_snippet'])
        self.assertIn('Fast Generations', results['featured_snippet']['text'])
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_fastgenerations_ranks_1_for_seo_wandsworth(self, mock_r2_service, mock_parser_class):
        """Test that fastgenerations.co.uk ranks #1 for 'seo agency wandsworth'"""
        keyword = self.keywords['seo_wandsworth']
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_uk_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=1
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>UK SERP HTML</html>',
            timezone.now()
        )
        
        # Assertions
        self.assertEqual(result['rank'], 1)
        self.assertTrue(result['is_organic'])
        
        # Check keyword was updated
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 1)
        self.assertEqual(keyword.rank_status, 'new')
        self.assertEqual(keyword.initial_rank, 1)
        
        # Verify R2 path uses new format
        expected_path = f"fastgenerations.co.uk/seo-agency-wandsworth/{timezone.now().strftime('%Y-%m-%d')}.json"
        self.assertEqual(result['r2_path'], expected_path)
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_fastgenerations_ranks_1_for_digital_clapham(self, mock_r2_service, mock_parser_class):
        """Test that fastgenerations.co.uk ranks #1 for 'digital marketing agency clapham'"""
        keyword = self.keywords['digital_clapham']
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        mock_parser.parse.return_value = create_uk_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=1
        )
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.return_value = {'success': True}
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>UK SERP HTML</html>',
            timezone.now()
        )
        
        # Check all expected fields in R2 data
        call_args = mock_r2.upload_json.call_args[0][0]
        results = call_args['results']
        
        # Verify comprehensive data structure
        self.assertIn('organic_results', results)
        self.assertIn('sponsored_results', results)
        self.assertIn('total_results', results)
        self.assertIn('search_time', results)
        self.assertIn('related_searches', results)
        self.assertIn('people_also_ask', results)
        self.assertIn('local_pack', results)
        self.assertIn('featured_snippet', results)
        
        # Check data is not empty
        self.assertGreater(len(results['organic_results']), 0)
        self.assertGreater(len(results['related_searches']), 0)
        self.assertGreater(len(results['people_also_ask']), 0)
        
        # Verify metadata
        self.assertEqual(call_args['keyword'], 'digital marketing agency clapham')
        self.assertEqual(call_args['project_domain'], 'fastgenerations.co.uk')
        self.assertEqual(call_args['country'], 'UK')
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_complete_json_structure_for_uk_serp(self, mock_r2_service, mock_parser_class):
        """Test that the complete JSON structure is correct for UK SERP data"""
        keyword = self.keywords['ppc_brixton']
        
        # Setup mocks
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        serp_data = create_uk_serp_results(
            domain=self.project.domain,
            keyword=keyword.keyword,
            rank_position=1
        )
        mock_parser.parse.return_value = serp_data
        
        # Capture the R2 upload
        uploaded_data = None
        def capture_upload(data, path):
            nonlocal uploaded_data
            uploaded_data = data
            return {'success': True}
        
        mock_r2 = Mock()
        mock_r2_service.return_value = mock_r2
        mock_r2.upload_json.side_effect = capture_upload
        
        # Execute
        extractor = RankingExtractor()
        result = extractor.process_serp_html(
            keyword,
            '<html>UK SERP HTML</html>',
            timezone.now()
        )
        
        # Verify the uploaded JSON structure
        self.assertIsNotNone(uploaded_data)
        
        # Check top-level metadata
        self.assertEqual(uploaded_data['keyword'], 'pay per click agency brixton')
        self.assertEqual(uploaded_data['project_id'], self.project.id)
        self.assertEqual(uploaded_data['project_domain'], 'fastgenerations.co.uk')
        self.assertEqual(uploaded_data['country'], 'UK')
        self.assertEqual(uploaded_data['location'], 'Brixton, London, United Kingdom')
        self.assertIn('scraped_at', uploaded_data)
        
        # Check results structure
        results = uploaded_data['results']
        
        # Organic results should have 100 entries
        self.assertEqual(len(results['organic_results']), 100)
        first_organic = results['organic_results'][0]
        self.assertEqual(first_organic['position'], 1)
        self.assertIn('title', first_organic)
        self.assertIn('url', first_organic)
        self.assertIn('description', first_organic)
        self.assertIn('displayed_url', first_organic)
        self.assertIn('sitelinks', first_organic)
        
        # Sponsored results
        self.assertEqual(len(results['sponsored_results']), 3)
        first_ad = results['sponsored_results'][0]
        self.assertIn('title', first_ad)
        self.assertIn('url', first_ad)
        self.assertIn('is_ad', first_ad)
        self.assertTrue(first_ad['is_ad'])
        
        # SERP features
        self.assertEqual(len(results['people_also_ask']), 3)
        self.assertEqual(len(results['related_searches']), 8)
        self.assertEqual(len(results['local_pack']), 3)
        
        # Local pack structure
        first_local = results['local_pack'][0]
        self.assertIn('name', first_local)
        self.assertIn('rating', first_local)
        self.assertIn('reviews', first_local)
        self.assertIn('address', first_local)
        self.assertIn('phone', first_local)
        
        # Featured snippet (should exist since rank #1)
        self.assertIsNotNone(results['featured_snippet'])
        self.assertIn('text', results['featured_snippet'])
        self.assertIn('source', results['featured_snippet'])
        
        # Counts
        self.assertEqual(results['organic_count'], 100)
        self.assertEqual(results['sponsored_count'], 3)
        
        # Print sample for verification
        print("\n📄 Sample JSON structure:")
        print(json.dumps({
            'keyword': uploaded_data['keyword'],
            'project_domain': uploaded_data['project_domain'],
            'results': {
                'organic_results': results['organic_results'][:2],  # First 2 only
                'sponsored_results': results['sponsored_results'][:1],  # First 1 only
                'local_pack': results['local_pack'][:1],  # First 1 only
                'featured_snippet': results['featured_snippet'],
                'organic_count': results['organic_count'],
                'sponsored_count': results['sponsored_count']
            }
        }, indent=2))
    
    @patch('keywords.ranking_extractor.GoogleSearchParser')
    @patch('keywords.ranking_extractor.get_r2_service')
    def test_uk_serp_with_different_rankings(self, mock_r2_service, mock_parser_class):
        """Test UK SERP with domain at different positions"""
        # Create a separate project for this test to avoid duplicates
        test_project = Project.objects.create(
            user=self.user,
            domain='testdomain.co.uk',
            title='Test Domain UK',
            active=True
        )
        
        test_cases = [
            ('london seo services', 1, True),         # Rank #1
            ('uk ppc management', 5, True),           # Rank #5
            ('british digital marketing', 25, True),  # Rank #25
            ('web design manchester', 0, True),       # Not ranked
        ]
        
        for keyword_text, expected_rank, is_organic in test_cases:
            with self.subTest(keyword=keyword_text, rank=expected_rank):
                # Create keyword
                keyword = Keyword.objects.create(
                    project=test_project,
                    keyword=keyword_text,
                    country='UK',
                    country_code='GB'
                )
                
                # Setup mocks
                mock_parser = Mock()
                mock_parser_class.return_value = mock_parser
                
                if expected_rank > 0:
                    mock_parser.parse.return_value = create_uk_serp_results(
                        domain=test_project.domain,
                        keyword=keyword_text,
                        rank_position=expected_rank
                    )
                else:
                    # Not ranked - use different domain
                    mock_parser.parse.return_value = create_uk_serp_results(
                        domain='competitor.co.uk',
                        keyword=keyword_text,
                        rank_position=None
                    )
                
                mock_r2 = Mock()
                mock_r2_service.return_value = mock_r2
                mock_r2.upload_json.return_value = {'success': True}
                
                # Execute
                extractor = RankingExtractor()
                result = extractor.process_serp_html(
                    keyword,
                    '<html>UK SERP HTML</html>',
                    timezone.now()
                )
                
                # Verify ranking
                self.assertEqual(result['rank'], expected_rank)
                self.assertEqual(result['is_organic'], is_organic)
                
                # Check keyword update
                keyword.refresh_from_db()
                self.assertEqual(keyword.rank, expected_rank)