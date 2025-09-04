#!/usr/bin/env python
"""
Test script for keyword reporting functionality
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from datetime import date, timedelta
from django.contrib.auth import get_user_model
from project.models import Project
from keywords.models import Keyword, Rank
from keywords.models_reports import KeywordReport, ReportSchedule
from keywords.report_generator import KeywordReportGenerator
from services.r2_storage import get_r2_service

User = get_user_model()

def test_report_creation():
    """Test creating a report"""
    print("\n=== Testing Report Creation ===")
    
    project = Project.objects.first()
    if not project:
        print("❌ No project found")
        return None
    
    print(f"✓ Using project: {project.domain}")
    
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("❌ No superuser found")
        return None
    
    print(f"✓ Using user: {user.email}")
    
    # Check if project has keywords
    keyword_count = Keyword.objects.filter(project=project, archive=False).count()
    print(f"✓ Project has {keyword_count} keywords")
    
    # Create report
    report = KeywordReport.objects.create(
        project=project,
        name=f"Test Report - {date.today()}",
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() - timedelta(days=1),
        report_format='both',
        fill_missing_ranks=True,
        include_graphs=True,
        created_by=user
    )
    
    print(f"✓ Created report ID: {report.id}")
    print(f"  - Status: {report.status}")
    print(f"  - Format: {report.report_format}")
    
    return report

def test_report_generation(report):
    """Test generating report content"""
    print("\n=== Testing Report Generation ===")
    
    if not report:
        print("❌ No report provided")
        return False
    
    try:
        # Initialize generator
        generator = KeywordReportGenerator(report)
        print("✓ Generator initialized")
        
        # Load data
        generator._load_keyword_data()
        print(f"✓ Loaded {len(generator.keywords_data)} keywords")
        
        generator._load_ranking_data()
        print(f"✓ Loaded ranking data for {len(generator.ranking_data)} keywords")
        
        generator._calculate_summary_stats()
        print(f"✓ Calculated summary stats:")
        for key, value in generator.summary_stats.items():
            print(f"  - {key}: {value}")
        
        # Generate CSV
        print("\n  Generating CSV...")
        csv_content = generator._generate_csv()
        print(f"✓ Generated CSV: {len(csv_content)} bytes")
        
        # Generate PDF
        print("\n  Generating PDF...")
        pdf_content = generator._generate_pdf()
        print(f"✓ Generated PDF: {len(pdf_content)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_r2_storage():
    """Test R2 storage connection"""
    print("\n=== Testing R2 Storage ===")
    
    try:
        r2_service = get_r2_service()
        print("✓ R2 service initialized")
        
        # Test upload
        test_content = b"Test content for R2"
        test_key = f"test/keyword_reports_test_{date.today().strftime('%Y%m%d')}.txt"
        
        result = r2_service.upload_file(
            file_obj=test_content,
            key=test_key,
            content_type='text/plain'
        )
        
        if result['success']:
            print(f"✓ Test file uploaded: {test_key}")
            
            # Test download
            downloaded = r2_service.download_file(test_key)
            if downloaded == test_content:
                print("✓ File downloaded successfully")
            
            # Clean up
            if r2_service.delete_file(test_key):
                print("✓ Test file deleted")
        else:
            print(f"❌ Failed to upload: {result.get('error')}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ R2 storage error: {e}")
        return False

def test_schedule_creation():
    """Test creating a report schedule"""
    print("\n=== Testing Schedule Creation ===")
    
    project = Project.objects.first()
    user = User.objects.filter(is_superuser=True).first()
    
    if not project or not user:
        print("❌ Missing project or user")
        return None
    
    schedule = ReportSchedule.objects.create(
        project=project,
        name="Test Weekly Schedule",
        frequency='weekly',
        day_of_week=1,  # Tuesday
        time_of_day="09:00",
        report_period_days=7,
        report_format='csv',
        fill_missing_ranks=True,
        created_by=user,
        is_active=True
    )
    
    print(f"✓ Created schedule ID: {schedule.id}")
    
    # Calculate next run
    schedule.calculate_next_run()
    schedule.save()
    
    print(f"✓ Next run at: {schedule.next_run_at}")
    
    return schedule

def main():
    """Run all tests"""
    print("=" * 50)
    print("KEYWORD REPORTING FUNCTIONALITY TEST")
    print("=" * 50)
    
    # Test report creation
    report = test_report_creation()
    
    # Test report generation
    if report:
        success = test_report_generation(report)
        if success:
            print("\n✅ Report generation working!")
    
    # Test R2 storage
    r2_ok = test_r2_storage()
    if r2_ok:
        print("\n✅ R2 storage working!")
    
    # Test schedule creation
    schedule = test_schedule_creation()
    if schedule:
        print("\n✅ Schedule creation working!")
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    total_reports = KeywordReport.objects.count()
    total_schedules = ReportSchedule.objects.count()
    
    print(f"Total reports in database: {total_reports}")
    print(f"Total schedules in database: {total_schedules}")
    
    # Check for issues
    print("\n" + "=" * 50)
    print("CHECKING FOR ISSUES")
    print("=" * 50)
    
    # Check if keywords have rank history
    from django.db.models import Count
    keywords_with_ranks = Keyword.objects.annotate(
        rank_count=Count('ranks')
    ).filter(rank_count__gt=0).count()
    
    total_keywords = Keyword.objects.count()
    
    print(f"Keywords with rank history: {keywords_with_ranks}/{total_keywords}")
    
    if keywords_with_ranks == 0:
        print("⚠️  No keywords have rank history - reports will be empty!")
        print("   You need to run keyword rank tracking first.")

if __name__ == "__main__":
    main()