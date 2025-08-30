#!/usr/bin/env python
"""
Test script for Screaming Frog CSV parsers
Tests parsing, storage, and verification of issue counts
"""

import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'limeclicks.settings')
django.setup()

from django.utils import timezone
from site_audit.models import SiteAudit, SiteIssue
from site_audit.parsers.issue_parser_manager import IssueParserManager
from accounts.models import User
from project.models import Project


def create_test_audit():
    """Create a test site audit for testing parsers"""
    # Get or create test user
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='testuser_parser',
            email='test_parser@example.com'
        )
    
    # Get or create test project
    project, _ = Project.objects.get_or_create(
        user=user,
        domain='test-site.com',
        defaults={'title': 'Test Site', 'active': True}
    )
    
    # Create site audit
    audit = SiteAudit.objects.create(
        project=project,
        overall_site_health_score=0,
        total_pages_crawled=0
    )
    
    return audit


def test_parser(output_dir):
    """
    Test the parser with actual Screaming Frog output
    
    Args:
        output_dir: Path to directory containing CSV files
    """
    print("\n" + "=" * 80)
    print("🧪 SCREAMING FROG PARSER TEST")
    print("=" * 80)
    
    # Check if directory exists
    if not os.path.exists(output_dir):
        print(f"❌ Error: Directory not found: {output_dir}")
        print("\nPlease provide a valid path to Screaming Frog CSV output directory")
        return
    
    # List CSV files in directory
    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
    print(f"\n📁 Found {len(csv_files)} CSV files in {output_dir}")
    
    if not csv_files:
        print("❌ No CSV files found in directory")
        return
    
    print("\n📄 CSV Files Found:")
    for i, file in enumerate(sorted(csv_files)[:20], 1):  # Show first 20
        print(f"  {i:2d}. {file}")
    if len(csv_files) > 20:
        print(f"  ... and {len(csv_files) - 20} more files")
    
    # Create test audit
    print("\n🏗️ Creating test site audit...")
    audit = create_test_audit()
    print(f"  ✅ Created audit ID: {audit.id} for {audit.project.domain}")
    
    # Initialize parser manager
    print("\n🔍 Initializing parser manager...")
    parser_manager = IssueParserManager(output_dir, audit)
    
    # Parse all issues
    print("\n🚀 Starting parsing process...")
    print("=" * 60)
    
    try:
        results = parser_manager.parse_all_issues()
        
        # Display parsing results
        print("\n" + "=" * 60)
        print("📊 PARSING RESULTS")
        print("=" * 60)
        
        print(f"\n✅ Total Issues Parsed: {results['total_issues']}")
        
        print("\n📂 Issues by Parser Category:")
        for category, count in results['issues_by_category'].items():
            if count > 0:
                print(f"  • {category.replace('_', ' ').title()}: {count}")
        
        print("\n🚨 Issues by Severity:")
        for severity, count in results['issues_by_severity'].items():
            if count > 0:
                emoji = {
                    'critical': '🔴',
                    'high': '🟠',
                    'medium': '🟡',
                    'low': '🔵',
                    'info': 'ℹ️'
                }.get(severity, '•')
                print(f"  {emoji} {severity.capitalize()}: {count}")
        
        # Save issues to database
        print("\n💾 Saving issues to database...")
        saved_count = parser_manager.save_all_issues()
        
        # Verify database storage
        print("\n✅ VERIFICATION")
        print("=" * 60)
        
        # Count issues in database
        db_issues = SiteIssue.objects.filter(site_audit=audit)
        db_count = db_issues.count()
        
        print(f"  📊 Issues parsed: {results['total_issues']}")
        print(f"  💾 Issues saved to database: {saved_count}")
        print(f"  🔍 Issues found in database: {db_count}")
        
        if db_count == results['total_issues']:
            print(f"  ✅ SUCCESS: All issues stored correctly!")
        else:
            print(f"  ⚠️ WARNING: Count mismatch!")
        
        # Show issue type distribution
        print("\n📊 Top 10 Issue Types in Database:")
        from django.db.models import Count
        top_issues = db_issues.values('issue_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        for i, issue in enumerate(top_issues, 1):
            print(f"  {i:2d}. {issue['issue_type']}: {issue['count']}")
        
        # Show sample issues
        print("\n📋 Sample Issues (first 5):")
        sample_issues = db_issues[:5]
        for i, issue in enumerate(sample_issues, 1):
            print(f"\n  Issue #{i}:")
            print(f"    URL: {issue.url}")
            print(f"    Type: {issue.issue_type}")
            print(f"    Category: {issue.issue_category}")
            print(f"    Severity: {issue.severity}")
            if issue.issue_data:
                print(f"    Data Keys: {', '.join(list(issue.issue_data.keys())[:5])}")
        
        # Get summary statistics
        print("\n📈 SUMMARY STATISTICS")
        print("=" * 60)
        summary = parser_manager.get_issue_summary()
        
        print("\n📂 Issues by Category:")
        for item in summary['by_category']:
            print(f"  • {item['issue_category']}: {item['count']}")
        
        print("\n🔝 Pages with Most Issues (Top 5):")
        for i, item in enumerate(summary['pages_with_most_issues'][:5], 1):
            print(f"  {i}. {item['url'][:60]}... ({item['count']} issues)")
        
        # Show audit statistics
        audit.refresh_from_db()
        print("\n🏥 Site Audit Statistics:")
        print(f"  • Total Issues: {db_count}")
        print(f"  • Health Score: {audit.overall_site_health_score}%")
        print(f"  • Total Pages Crawled: {audit.total_pages_crawled}")
        print(f"  • Status: {audit.status}")
        
        # Calculate specific issue type counts from database
        missing_titles = db_issues.filter(issue_type='missing_title').count()
        duplicate_titles = db_issues.filter(issue_type='duplicate_title').count() 
        missing_meta = db_issues.filter(issue_type='missing_meta_description').count()
        duplicate_meta = db_issues.filter(issue_type='duplicate_meta_description').count()
        broken_links = db_issues.filter(issue_type__in=['broken_internal_link', 'broken_external_link']).count()
        
        print(f"  • Missing Titles: {missing_titles}")
        print(f"  • Duplicate Titles: {duplicate_titles}")
        print(f"  • Missing Meta Descriptions: {missing_meta}")
        print(f"  • Duplicate Meta Descriptions: {duplicate_meta}")
        print(f"  • Broken Links: {broken_links}")
        
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR during parsing: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup on error
        print("\n🧹 Cleaning up test data...")
        if 'audit' in locals():
            audit.delete()
            print("  ✅ Test audit deleted")


def main():
    """Main function to run the test"""
    print("\n" + "=" * 80)
    print("🧪 SCREAMING FROG CSV PARSER TEST UTILITY")
    print("=" * 80)
    
    # Check if path was provided
    if len(sys.argv) < 2:
        print("\n📌 Usage: python test_parser.py <path_to_csv_directory>")
        print("\nExample:")
        print("  python test_parser.py /tmp/sf_crawl_xyz/2025.08.29.15.15.03/issues_reports")
        
        # Try to find recent crawl directories
        print("\n🔍 Looking for recent Screaming Frog outputs...")
        tmp_dirs = []
        
        # Check /tmp for SF directories
        if os.path.exists('/tmp'):
            for dir_name in os.listdir('/tmp'):
                if dir_name.startswith('sf_crawl_'):
                    full_path = os.path.join('/tmp', dir_name)
                    if os.path.isdir(full_path):
                        # Look for subdirectories with timestamps
                        for subdir in os.listdir(full_path):
                            subdir_path = os.path.join(full_path, subdir)
                            issues_path = os.path.join(subdir_path, 'issues_reports')
                            if os.path.exists(issues_path):
                                tmp_dirs.append(issues_path)
        
        if tmp_dirs:
            print("\n📁 Found recent crawl directories:")
            for i, path in enumerate(tmp_dirs[-5:], 1):  # Show last 5
                print(f"  {i}. {path}")
            print("\nRun the test with one of these paths")
        else:
            print("\n⚠️ No recent Screaming Frog outputs found in /tmp")
        
        return
    
    # Get the directory path
    csv_directory = sys.argv[1]
    
    # Run the test
    test_parser(csv_directory)


if __name__ == "__main__":
    main()