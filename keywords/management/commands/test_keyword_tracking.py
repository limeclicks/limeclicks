"""
Management command to test keyword tracking with location and R2 storage
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from keywords.models import Keyword, Rank
from keywords.utils import KeywordRankTracker
from project.models import Project
from accounts.models import User
from services.r2_storage import get_r2_service
import json


class Command(BaseCommand):
    help = 'Test keyword tracking with location support and R2 storage'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--keyword',
            type=str,
            default='coffee shops',
            help='Keyword to track'
        )
        parser.add_argument(
            '--location',
            type=str,
            help='Location for local search (e.g., "New York, NY, United States")'
        )
        parser.add_argument(
            '--country',
            type=str,
            default='US',
            help='Country code'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain to check ranking for'
        )
        parser.add_argument(
            '--view-results',
            action='store_true',
            help='View stored results from R2'
        )
    
    def handle(self, *args, **options):
        """Handle the command"""
        self.stdout.write(self.style.SUCCESS('🔍 Keyword Ranking Tracker Test'))
        self.stdout.write('=' * 60)
        
        # Get or create test user and project
        user, _ = User.objects.get_or_create(
            username='test_tracker',
            defaults={'email': 'tracker@test.com'}
        )
        
        domain = options['domain'] or 'example.com'
        project, _ = Project.objects.get_or_create(
            domain=domain,
            defaults={
                'user': user,
                'title': 'Test Tracking Project',
                'active': True
            }
        )
        
        self.stdout.write(f'\n📋 Project: {project.domain}')
        
        # Create or get keyword
        keyword_text = options['keyword']
        location = options['location']
        country = options['country']
        
        keyword, created = Keyword.objects.get_or_create(
            project=project,
            keyword=keyword_text,
            country=country,
            defaults={'location': location}
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'✅ Created new keyword: {keyword_text}'))
        else:
            self.stdout.write(f'📌 Using existing keyword: {keyword_text}')
            if location and not keyword.location:
                keyword.location = location
                keyword.save()
                self.stdout.write(f'   Updated location: {location}')
        
        self.stdout.write(f'\n🎯 Tracking Configuration:')
        self.stdout.write(f'   Keyword: {keyword.keyword}')
        self.stdout.write(f'   Country: {keyword.country}')
        self.stdout.write(f'   Location: {keyword.location or "Not specified"}')
        self.stdout.write(f'   Domain: {project.domain}')
        
        if options['view_results']:
            self.view_stored_results(keyword)
        else:
            self.track_keyword(keyword)
    
    def track_keyword(self, keyword):
        """Track the keyword and store results"""
        self.stdout.write(f'\n🚀 Starting keyword tracking...')
        
        try:
            tracker = KeywordRankTracker()
            result = tracker.track_keyword(keyword)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS('\n✅ Tracking completed successfully!'))
                self.stdout.write(f'   Rank: #{result["rank"]} {"(Organic)" if result["is_organic"] else "(Sponsored)"}')
                self.stdout.write(f'   Total Results: {result["total_results"]:,}')
                
                # Get the created rank
                rank = Rank.objects.filter(keyword=keyword).order_by('-created_at').first()
                if rank:
                    self.stdout.write(f'\n📊 Rank Details:')
                    self.stdout.write(f'   Position: #{rank.rank}')
                    self.stdout.write(f'   Has Map Results: {rank.has_map_result}')
                    self.stdout.write(f'   Has Video Results: {rank.has_video_result}')
                    self.stdout.write(f'   Has Image Results: {rank.has_image_result}')
                    
                    if rank.rank_file:
                        self.stdout.write(f'\n💾 R2 Storage:')
                        self.stdout.write(f'   Rank File: {rank.rank_file}')
                        
                        # Try to download and display rank data
                        r2 = get_r2_service()
                        rank_data = r2.download_json(rank.rank_file)
                        if rank_data:
                            self.stdout.write(self.style.SUCCESS('   ✅ Rank data successfully stored in R2'))
                            self.stdout.write(f'\n📈 SERP Features:')
                            for feature, has_feature in rank_data.get('serp_features', {}).items():
                                if has_feature:
                                    self.stdout.write(f'   • {feature.replace("has_", "").replace("_", " ").title()}')
                    
                    if rank.search_results_file:
                        self.stdout.write(f'   Results File: {rank.search_results_file}')
                
                # Show ranking history
                self.show_ranking_history(keyword)
                
            else:
                self.stdout.write(self.style.ERROR(f'\n❌ Tracking failed: {result.get("error")}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {str(e)}'))
    
    def view_stored_results(self, keyword):
        """View stored results from R2"""
        self.stdout.write(f'\n📂 Viewing stored results for: {keyword.keyword}')
        
        ranks = Rank.objects.filter(keyword=keyword).order_by('-created_at')[:5]
        
        if not ranks:
            self.stdout.write('   No ranking history found')
            return
        
        r2 = get_r2_service()
        
        for rank in ranks:
            self.stdout.write(f'\n📅 {rank.created_at.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write(f'   Rank: #{rank.rank}')
            
            if rank.rank_file:
                # Download and display rank data
                rank_data = r2.download_json(rank.rank_file)
                if rank_data:
                    self.stdout.write(f'   Location: {rank_data.get("location", "N/A")}')
                    self.stdout.write(f'   Organic Results: {rank_data.get("organic_count", 0)}')
                    self.stdout.write(f'   Sponsored Results: {rank_data.get("sponsored_count", 0)}')
                    
                    # Show top 3 results
                    top_results = rank_data.get('top_10_results', [])[:3]
                    if top_results:
                        self.stdout.write(f'   Top 3 Results:')
                        for i, result in enumerate(top_results, 1):
                            self.stdout.write(f'      {i}. {result.get("title", "N/A")[:50]}...')
                else:
                    self.stdout.write(f'   ⚠️  Could not retrieve rank data from R2')
    
    def show_ranking_history(self, keyword):
        """Show ranking history for the keyword"""
        ranks = Rank.objects.filter(keyword=keyword).order_by('-created_at')[:10]
        
        if len(ranks) > 1:
            self.stdout.write(f'\n📊 Ranking History (Last {len(ranks)} checks):')
            for rank in ranks:
                status = ''
                if keyword.rank_status == 'up':
                    status = '↑'
                elif keyword.rank_status == 'down':
                    status = '↓'
                elif keyword.rank_status == 'new':
                    status = '🆕'
                
                self.stdout.write(
                    f'   {rank.created_at.strftime("%Y-%m-%d %H:%M")}: '
                    f'#{rank.rank} {status}'
                )