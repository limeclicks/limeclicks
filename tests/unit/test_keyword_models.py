"""
Unit tests for Keyword and Rank models
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from keywords.models import Keyword, Rank
from project.models import Project
from accounts.models import User


class KeywordModelTest(TestCase):
    """Test cases for Keyword model"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test project
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        
        # Create test keyword
        self.keyword = Keyword.objects.create(
            project=self.project,
            keyword='python django',
            country='US'
        )
    
    def test_keyword_creation(self):
        """Test keyword creation with defaults"""
        self.assertEqual(self.keyword.keyword, 'python django')
        self.assertEqual(self.keyword.country, 'US')
        self.assertEqual(self.keyword.rank, 0)
        self.assertEqual(self.keyword.rank_status, 'no_change')
        self.assertFalse(self.keyword.on_map)
        self.assertFalse(self.keyword.processing)
        self.assertFalse(self.keyword.archive)
    
    def test_keyword_str_representation(self):
        """Test keyword string representation"""
        expected = f"python django - example.com (US)"
        self.assertEqual(str(self.keyword), expected)
    
    def test_update_rank_new_keyword(self):
        """Test updating rank for new keyword"""
        self.keyword.update_rank(5)
        
        self.assertEqual(self.keyword.rank, 5)
        self.assertEqual(self.keyword.rank_status, 'new')
        self.assertEqual(self.keyword.initial_rank, 5)
        self.assertEqual(self.keyword.highest_rank, 5)
        self.assertIsNotNone(self.keyword.scraped_at)
    
    def test_update_rank_improvement(self):
        """Test rank improvement (lower number is better)"""
        # Set initial rank
        self.keyword.rank = 10
        self.keyword.save()
        
        # Update with better rank
        self.keyword.update_rank(3)
        
        self.assertEqual(self.keyword.rank, 3)
        self.assertEqual(self.keyword.rank_status, 'up')
        self.assertEqual(self.keyword.rank_diff_from_last_time, 7)
    
    def test_update_rank_decline(self):
        """Test rank decline (higher number is worse)"""
        # Set initial rank
        self.keyword.rank = 5
        self.keyword.save()
        
        # Update with worse rank
        self.keyword.update_rank(15)
        
        self.assertEqual(self.keyword.rank, 15)
        self.assertEqual(self.keyword.rank_status, 'down')
        self.assertEqual(self.keyword.rank_diff_from_last_time, -10)
    
    def test_update_rank_no_change(self):
        """Test rank with no change"""
        # Set initial rank
        self.keyword.rank = 10
        self.keyword.save()
        
        # Update with same rank
        self.keyword.update_rank(10)
        
        self.assertEqual(self.keyword.rank, 10)
        self.assertEqual(self.keyword.rank_status, 'no_change')
        self.assertEqual(self.keyword.rank_diff_from_last_time, 0)
    
    def test_highest_rank_tracking(self):
        """Test that highest rank is properly tracked"""
        # Set initial rank
        self.keyword.update_rank(10)
        self.assertEqual(self.keyword.highest_rank, 10)
        
        # Update with better rank
        self.keyword.update_rank(3)
        self.assertEqual(self.keyword.highest_rank, 3)
        
        # Update with worse rank (highest should not change)
        self.keyword.update_rank(7)
        self.assertEqual(self.keyword.highest_rank, 3)
    
    def test_unique_constraint(self):
        """Test unique constraint on keyword, country, project"""
        # Try to create duplicate keyword
        with self.assertRaises(Exception):
            Keyword.objects.create(
                project=self.project,
                keyword='python django',
                country='US'
            )
    
    def test_keyword_with_different_country(self):
        """Test that same keyword can exist with different country"""
        # This should work - same keyword but different country
        keyword_uk = Keyword.objects.create(
            project=self.project,
            keyword='python django',
            country='GB'
        )
        
        self.assertIsNotNone(keyword_uk)
        self.assertEqual(keyword_uk.country, 'GB')
    
    def test_json_fields(self):
        """Test JSON fields work correctly"""
        self.keyword.tags = ['seo', 'important', 'homepage']
        self.keyword.scrape_do_files = ['file1.json', 'file2.json']
        self.keyword.save()
        
        # Reload from database
        keyword = Keyword.objects.get(pk=self.keyword.pk)
        self.assertEqual(keyword.tags, ['seo', 'important', 'homepage'])
        self.assertEqual(keyword.scrape_do_files, ['file1.json', 'file2.json'])


class RankModelTest(TestCase):
    """Test cases for Rank model"""
    
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test project
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
        
        # Create test keyword
        self.keyword = Keyword.objects.create(
            project=self.project,
            keyword='python django',
            country='US'
        )
    
    def test_rank_creation(self):
        """Test rank creation with defaults"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=5
        )
        
        self.assertEqual(rank.rank, 5)
        self.assertTrue(rank.is_organic)
        self.assertFalse(rank.has_map_result)
        self.assertFalse(rank.has_video_result)
        self.assertFalse(rank.has_image_result)
        self.assertEqual(rank.number_of_results, 0)
    
    def test_rank_str_representation(self):
        """Test rank string representation"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=5,
            is_organic=True
        )
        
        expected = f"Organic Rank #5 for python django on {rank.created_at.strftime('%Y-%m-%d %H:%M')}"
        self.assertEqual(str(rank), expected)
    
    def test_sponsored_rank_str(self):
        """Test sponsored rank string representation"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=2,
            is_organic=False
        )
        
        expected = f"Sponsored Rank #2 for python django on {rank.created_at.strftime('%Y-%m-%d %H:%M')}"
        self.assertEqual(str(rank), expected)
    
    def test_rank_updates_keyword(self):
        """Test that creating a rank updates the parent keyword"""
        initial_rank = self.keyword.rank
        
        # Create new rank
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=7
        )
        
        # Reload keyword from database
        self.keyword.refresh_from_db()
        
        # Check that keyword was updated
        self.assertEqual(self.keyword.rank, 7)
        self.assertIsNotNone(self.keyword.scraped_at)
    
    def test_rank_with_special_results(self):
        """Test rank with special result types"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=3,
            has_map_result=True,
            has_video_result=True,
            has_image_result=False
        )
        
        self.assertTrue(rank.has_map_result)
        self.assertTrue(rank.has_video_result)
        self.assertFalse(rank.has_image_result)
    
    def test_rank_history(self):
        """Test that we can track rank history"""
        # Create multiple rank entries over time
        ranks = []
        for i in range(5):
            rank = Rank.objects.create(
                keyword=self.keyword,
                rank=10 - i  # Improving rank over time
            )
            ranks.append(rank)
        
        # Check that we have 5 rank entries
        self.assertEqual(self.keyword.ranks.count(), 5)
        
        # Check that they're ordered by created_at (newest first)
        rank_list = list(self.keyword.ranks.all())
        for i in range(len(rank_list) - 1):
            self.assertGreater(
                rank_list[i].created_at,
                rank_list[i + 1].created_at
            )
    
    def test_number_of_results(self):
        """Test storing number of search results"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=5,
            number_of_results=1234567890
        )
        
        self.assertEqual(rank.number_of_results, 1234567890)
    
    def test_search_results_file(self):
        """Test storing reference to search results file"""
        rank = Rank.objects.create(
            keyword=self.keyword,
            rank=5,
            search_results_file='results/2024/01/search_12345.json'
        )
        
        self.assertEqual(rank.search_results_file, 'results/2024/01/search_12345.json')


class KeywordRankIntegrationTest(TestCase):
    """Integration tests for Keyword and Rank models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.project = Project.objects.create(
            user=self.user,
            domain='example.com',
            title='Test Project',
            active=True
        )
    
    def test_keyword_rank_workflow(self):
        """Test complete workflow of keyword ranking"""
        # Create keyword
        keyword = Keyword.objects.create(
            project=self.project,
            keyword='django rest framework',
            country='US'
        )
        
        # Initial state
        self.assertEqual(keyword.rank, 0)
        self.assertEqual(keyword.rank_status, 'no_change')
        
        # First ranking
        rank1 = Rank.objects.create(
            keyword=keyword,
            rank=15,
            is_organic=True,
            number_of_results=5000000
        )
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 15)
        self.assertEqual(keyword.rank_status, 'new')
        self.assertEqual(keyword.initial_rank, 15)
        self.assertEqual(keyword.highest_rank, 15)
        
        # Second ranking (improvement)
        rank2 = Rank.objects.create(
            keyword=keyword,
            rank=8,
            is_organic=True,
            number_of_results=5100000
        )
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 8)
        self.assertEqual(keyword.rank_status, 'up')
        self.assertEqual(keyword.highest_rank, 8)
        self.assertEqual(keyword.rank_diff_from_last_time, 7)
        
        # Third ranking (decline)
        rank3 = Rank.objects.create(
            keyword=keyword,
            rank=12,
            is_organic=True,
            number_of_results=5200000
        )
        
        keyword.refresh_from_db()
        self.assertEqual(keyword.rank, 12)
        self.assertEqual(keyword.rank_status, 'down')
        self.assertEqual(keyword.highest_rank, 8)  # Still 8
        self.assertEqual(keyword.rank_diff_from_last_time, -4)
        
        # Check rank history
        self.assertEqual(keyword.ranks.count(), 3)
        latest_rank = keyword.ranks.first()
        self.assertEqual(latest_rank.rank, 12)