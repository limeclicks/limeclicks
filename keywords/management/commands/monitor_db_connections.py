"""
Management command to monitor database connections and prevent exhaustion
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
import psycopg2
from datetime import datetime


class Command(BaseCommand):
    help = 'Monitor and manage database connections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Check current database connection status',
        )
        parser.add_argument(
            '--kill-idle',
            action='store_true',
            help='Kill idle database connections older than 5 minutes',
        )
        parser.add_argument(
            '--reset-stuck',
            action='store_true',
            help='Reset stuck keywords and kill their connections',
        )

    def handle(self, *args, **options):
        try:
            # Parse database URL to get connection params
            import dj_database_url
            db_config = dj_database_url.parse(settings.DATABASES['default']['NAME'] if isinstance(settings.DATABASES['default'], dict) and 'NAME' in settings.DATABASES['default'] else connection.settings_dict['NAME'])
            
            # Use Django's connection settings
            conn_params = connection.get_connection_params()
            
            # Connect to PostgreSQL
            with connection.cursor() as cursor:
                if options['check'] or not any([options['kill_idle'], options['reset_stuck']]):
                    # Check current connections
                    cursor.execute("""
                        SELECT 
                            count(*) as total,
                            sum(case when state = 'active' then 1 else 0 end) as active,
                            sum(case when state = 'idle' then 1 else 0 end) as idle,
                            sum(case when state = 'idle in transaction' then 1 else 0 end) as idle_in_transaction
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                    """)
                    
                    stats = cursor.fetchone()
                    self.stdout.write(f"\nDatabase Connection Status:")
                    self.stdout.write(f"  Total connections: {stats[0]}")
                    self.stdout.write(f"  Active: {stats[1]}")
                    self.stdout.write(f"  Idle: {stats[2]}")
                    self.stdout.write(f"  Idle in transaction: {stats[3]}")
                    
                    # Get max connections
                    cursor.execute("SHOW max_connections")
                    max_conn = cursor.fetchone()[0]
                    self.stdout.write(f"  Max connections: {max_conn}")
                    
                    usage_percent = (stats[0] / int(max_conn)) * 100
                    if usage_percent > 80:
                        self.stdout.write(
                            self.style.WARNING(f"  ⚠️  Connection usage: {usage_percent:.1f}% - HIGH!")
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f"  ✓ Connection usage: {usage_percent:.1f}%")
                        )
                    
                    # Show long-running queries
                    cursor.execute("""
                        SELECT 
                            pid,
                            now() - query_start as duration,
                            state,
                            query
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                            AND state != 'idle'
                            AND now() - query_start > interval '1 minute'
                        ORDER BY duration DESC
                        LIMIT 5
                    """)
                    
                    long_queries = cursor.fetchall()
                    if long_queries:
                        self.stdout.write("\nLong-running queries (>1 minute):")
                        for pid, duration, state, query in long_queries:
                            query_preview = query[:100] + '...' if len(query) > 100 else query
                            self.stdout.write(f"  PID {pid} ({state}): {duration} - {query_preview}")
                
                if options['kill_idle']:
                    # Kill idle connections older than 5 minutes
                    cursor.execute("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                            AND state = 'idle'
                            AND now() - state_change > interval '5 minutes'
                    """)
                    
                    killed = cursor.rowcount
                    self.stdout.write(
                        self.style.SUCCESS(f"Killed {killed} idle connections")
                    )
                
                if options['reset_stuck']:
                    # Reset stuck keywords
                    from keywords.models import Keyword
                    from django.utils import timezone
                    from datetime import timedelta
                    
                    stuck_cutoff = timezone.now() - timedelta(minutes=10)
                    stuck_keywords = Keyword.objects.filter(
                        processing=True,
                        scraped_at__lt=stuck_cutoff
                    )
                    stuck_count = stuck_keywords.update(processing=False)
                    
                    if stuck_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"Reset {stuck_count} stuck keywords")
                        )
                    
                    # Kill connections from Celery workers that might be stuck
                    cursor.execute("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                            AND application_name LIKE '%celery%'
                            AND state = 'idle in transaction'
                            AND now() - state_change > interval '10 minutes'
                    """)
                    
                    killed = cursor.rowcount
                    if killed > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"Killed {killed} stuck Celery connections")
                        )
                        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error: {e}")
            )