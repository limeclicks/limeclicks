#!/usr/bin/env python3
"""
Database Connection Monitor Script
Monitors PostgreSQL connections and alerts when thresholds are exceeded
"""

import os
import sys
import time
import logging
from datetime import datetime
import psycopg2
from psycopg2 import sql

# Configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'lime')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'LimeClicksPwd007')

# Thresholds
WARNING_THRESHOLD = 100  # Warn when connections exceed this
CRITICAL_THRESHOLD = 150  # Critical alert when connections exceed this
MAX_CONNECTIONS = 200  # PostgreSQL max_connections setting

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/new-limeclicks/logs/db_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_connection():
    """Create a database connection"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def check_connections():
    """Check current database connections and return metrics"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cur:
            # Get total connection count
            cur.execute("SELECT count(*) FROM pg_stat_activity")
            total_connections = cur.fetchone()[0]
            
            # Get connections by state
            cur.execute("""
                SELECT state, count(*) 
                FROM pg_stat_activity 
                WHERE state IS NOT NULL 
                GROUP BY state 
                ORDER BY count(*) DESC
            """)
            connections_by_state = dict(cur.fetchall())
            
            # Get connections by database
            cur.execute("""
                SELECT datname, count(*) 
                FROM pg_stat_activity 
                WHERE datname IS NOT NULL 
                GROUP BY datname 
                ORDER BY count(*) DESC
            """)
            connections_by_db = dict(cur.fetchall())
            
            # Get long-running idle connections (> 5 minutes)
            cur.execute("""
                SELECT count(*) 
                FROM pg_stat_activity 
                WHERE state = 'idle' 
                AND state_change < now() - interval '5 minutes'
            """)
            long_idle_connections = cur.fetchone()[0]
            
            # Get connections by application
            cur.execute("""
                SELECT application_name, count(*) 
                FROM pg_stat_activity 
                WHERE application_name != '' 
                GROUP BY application_name 
                ORDER BY count(*) DESC
            """)
            connections_by_app = dict(cur.fetchall())
            
            return {
                'total': total_connections,
                'by_state': connections_by_state,
                'by_database': connections_by_db,
                'by_application': connections_by_app,
                'long_idle': long_idle_connections,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error checking connections: {e}")
        return None
    finally:
        conn.close()


def close_idle_connections(max_idle_minutes=10):
    """Close connections that have been idle for too long"""
    conn = get_connection()
    if not conn:
        return 0
    
    try:
        with conn.cursor() as cur:
            # Terminate idle connections older than max_idle_minutes
            cur.execute("""
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE state = 'idle' 
                AND state_change < now() - interval '%s minutes'
                AND pid != pg_backend_pid()
            """, (max_idle_minutes,))
            
            terminated = cur.rowcount
            conn.commit()
            
            if terminated > 0:
                logger.warning(f"Terminated {terminated} idle connections older than {max_idle_minutes} minutes")
            
            return terminated
            
    except Exception as e:
        logger.error(f"Error closing idle connections: {e}")
        return 0
    finally:
        conn.close()


def monitor_loop(check_interval=30, auto_close_idle=True):
    """Main monitoring loop"""
    logger.info(f"Starting database connection monitor (check every {check_interval} seconds)")
    logger.info(f"Thresholds - Warning: {WARNING_THRESHOLD}, Critical: {CRITICAL_THRESHOLD}, Max: {MAX_CONNECTIONS}")
    
    while True:
        try:
            metrics = check_connections()
            
            if metrics:
                total = metrics['total']
                idle = metrics['by_state'].get('idle', 0)
                active = metrics['by_state'].get('active', 0)
                long_idle = metrics['long_idle']
                
                # Log current status
                status_msg = (
                    f"Connections: {total}/{MAX_CONNECTIONS} "
                    f"(Active: {active}, Idle: {idle}, Long Idle: {long_idle})"
                )
                
                # Determine severity
                if total >= CRITICAL_THRESHOLD:
                    logger.critical(f"CRITICAL: {status_msg}")
                    logger.critical(f"By Database: {metrics['by_database']}")
                    logger.critical(f"By Application: {metrics['by_application']}")
                    
                    # Auto-close long idle connections if enabled
                    if auto_close_idle and long_idle > 10:
                        closed = close_idle_connections(max_idle_minutes=5)
                        logger.info(f"Auto-closed {closed} idle connections")
                        
                elif total >= WARNING_THRESHOLD:
                    logger.warning(f"WARNING: {status_msg}")
                    logger.warning(f"By Database: {metrics['by_database']}")
                    
                else:
                    logger.info(status_msg)
                
                # Write metrics to file for external monitoring
                metrics_file = '/home/ubuntu/new-limeclicks/logs/db_metrics.json'
                try:
                    import json
                    with open(metrics_file, 'w') as f:
                        json.dump(metrics, f, indent=2)
                except Exception as e:
                    logger.error(f"Failed to write metrics file: {e}")
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
            break
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            time.sleep(check_interval)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor PostgreSQL connections')
    parser.add_argument('--interval', type=int, default=30, help='Check interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--auto-close', action='store_true', default=True, help='Auto-close long idle connections')
    parser.add_argument('--close-idle', action='store_true', help='Close idle connections and exit')
    
    args = parser.parse_args()
    
    if args.close_idle:
        # Just close idle connections and exit
        closed = close_idle_connections(max_idle_minutes=10)
        print(f"Closed {closed} idle connections")
        sys.exit(0)
    
    if args.once:
        # Run once and print results
        metrics = check_connections()
        if metrics:
            import json
            print(json.dumps(metrics, indent=2))
        sys.exit(0)
    
    # Run monitoring loop
    monitor_loop(check_interval=args.interval, auto_close_idle=args.auto_close)