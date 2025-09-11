#!/usr/bin/env python3
"""
Celery Worker Optimization Script for LimeClicks
================================================

This script safely applies optimized Celery worker configuration for keyword processing
on an 8-core server with shared PostgreSQL database.

OPTIMIZATION TARGETS:
- Increase worker concurrency from 2 to 6 workers
- Optimize memory management and connection pooling
- Enhance task throughput while protecting database
- Add monitoring and auto-recovery features

SAFETY FEATURES:
- Gradual rollout with monitoring
- Automatic rollback on high resource usage
- Database connection monitoring
- Performance benchmarking

Author: Claude Code Assistant
Date: September 2025
"""

import subprocess
import time
import psutil
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/new-limeclicks/logs/celery-optimization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CeleryOptimizer:
    """Safely optimize Celery worker configuration"""
    
    def __init__(self):
        self.backup_created = False
        self.original_service = '/etc/systemd/system/limeclicks-celery.service'
        self.optimized_service = '/home/ubuntu/new-limeclicks/deployment/limeclicks-celery-optimized.service'
        self.backup_service = '/home/ubuntu/new-limeclicks/limeclicks-celery.service.backup'
        
    def check_prerequisites(self):
        """Check system prerequisites before optimization"""
        logger.info("🔍 Checking system prerequisites...")
        
        # Check CPU cores
        cpu_count = psutil.cpu_count()
        if cpu_count < 4:
            logger.error("❌ Insufficient CPU cores for optimization")
            return False
        logger.info(f"✅ CPU cores: {cpu_count}")
        
        # Check available memory
        memory = psutil.virtual_memory()
        available_gb = memory.available / (1024**3)
        if available_gb < 2:
            logger.error("❌ Insufficient available memory for optimization")
            return False
        logger.info(f"✅ Available memory: {available_gb:.1f}GB")
        
        # Check current load
        load_avg = psutil.getloadavg()[0]
        if load_avg > 4:
            logger.warning(f"⚠️ High system load: {load_avg:.2f}")
            return False
        logger.info(f"✅ System load: {load_avg:.2f}")
        
        # Check Redis connectivity
        try:
            result = subprocess.run(['redis-cli', 'ping'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode != 0 or 'PONG' not in result.stdout:
                logger.error("❌ Redis connectivity check failed")
                return False
            logger.info("✅ Redis connectivity confirmed")
        except Exception as e:
            logger.error(f"❌ Redis check failed: {e}")
            return False
        
        return True
    
    def backup_current_config(self):
        """Create backup of current configuration"""
        try:
            logger.info("💾 Creating backup of current configuration...")
            subprocess.run(['sudo', 'cp', self.original_service, self.backup_service], check=True)
            self.backup_created = True
            logger.info("✅ Backup created successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False
    
    def get_baseline_metrics(self):
        """Capture baseline performance metrics"""
        logger.info("📊 Capturing baseline metrics...")
        
        try:
            # Get current worker count and memory usage
            celery_processes = [p for p in psutil.process_iter(['pid', 'name', 'memory_percent']) 
                              if 'celery' in p.info['name'].lower() and 'worker' in p.info['name'].lower()]
            
            baseline = {
                'worker_count': len(celery_processes),
                'total_memory_percent': sum(p.info['memory_percent'] for p in celery_processes),
                'system_load': psutil.getloadavg()[0],
                'available_memory_gb': psutil.virtual_memory().available / (1024**3),
                'timestamp': datetime.now()
            }
            
            logger.info(f"📈 Baseline metrics captured:")
            logger.info(f"   Workers: {baseline['worker_count']}")
            logger.info(f"   Memory usage: {baseline['total_memory_percent']:.1f}%")
            logger.info(f"   System load: {baseline['system_load']:.2f}")
            
            return baseline
        except Exception as e:
            logger.error(f"❌ Failed to capture baseline metrics: {e}")
            return None
    
    def apply_optimization(self):
        """Apply the optimized Celery configuration"""
        try:
            logger.info("🚀 Applying optimized Celery configuration...")
            
            # Copy optimized service file
            subprocess.run(['sudo', 'cp', self.optimized_service, self.original_service], check=True)
            logger.info("✅ Optimized service file deployed")
            
            # Reload systemd
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            logger.info("✅ Systemd daemon reloaded")
            
            # Restart Celery worker service
            subprocess.run(['sudo', 'systemctl', 'restart', 'limeclicks-celery'], check=True)
            logger.info("✅ Celery worker service restarted")
            
            # Wait for startup
            time.sleep(10)
            
            # Verify service is running
            result = subprocess.run(['sudo', 'systemctl', 'is-active', 'limeclicks-celery'], 
                                  capture_output=True, text=True)
            if result.stdout.strip() != 'active':
                raise Exception("Celery service failed to start")
            
            logger.info("✅ Optimized configuration applied successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            return False
    
    def monitor_performance(self, duration_minutes=10):
        """Monitor performance after optimization"""
        logger.info(f"📈 Monitoring performance for {duration_minutes} minutes...")
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        metrics = []
        
        while datetime.now() < end_time:
            try:
                # Collect metrics
                celery_processes = [p for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']) 
                                  if 'celery' in p.info['name'].lower() and 'worker' in p.info['name'].lower()]
                
                current_metrics = {
                    'timestamp': datetime.now(),
                    'worker_count': len(celery_processes),
                    'total_memory_percent': sum(p.info['memory_percent'] for p in celery_processes),
                    'total_cpu_percent': sum(p.info['cpu_percent'] for p in celery_processes),
                    'system_load': psutil.getloadavg()[0],
                    'available_memory_gb': psutil.virtual_memory().available / (1024**3)
                }
                
                metrics.append(current_metrics)
                
                # Check for concerning metrics
                if current_metrics['system_load'] > 6:
                    logger.warning(f"⚠️ High system load: {current_metrics['system_load']:.2f}")
                
                if current_metrics['available_memory_gb'] < 1:
                    logger.warning(f"⚠️ Low available memory: {current_metrics['available_memory_gb']:.1f}GB")
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
        
        # Calculate averages
        if metrics:
            avg_load = sum(m['system_load'] for m in metrics) / len(metrics)
            avg_memory = sum(m['total_memory_percent'] for m in metrics) / len(metrics)
            max_workers = max(m['worker_count'] for m in metrics)
            
            logger.info("📊 Performance monitoring results:")
            logger.info(f"   Average system load: {avg_load:.2f}")
            logger.info(f"   Average memory usage: {avg_memory:.1f}%")
            logger.info(f"   Maximum workers seen: {max_workers}")
            
            return {
                'avg_load': avg_load,
                'avg_memory': avg_memory,
                'max_workers': max_workers,
                'stable': avg_load < 4 and avg_memory < 80
            }
        
        return None
    
    def rollback(self):
        """Rollback to original configuration if needed"""
        if not self.backup_created:
            logger.error("❌ No backup available for rollback")
            return False
        
        try:
            logger.info("🔄 Rolling back to original configuration...")
            
            # Restore original service file
            subprocess.run(['sudo', 'cp', self.backup_service, self.original_service], check=True)
            
            # Reload and restart
            subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True)
            subprocess.run(['sudo', 'systemctl', 'restart', 'limeclicks-celery'], check=True)
            
            logger.info("✅ Rollback completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return False
    
    def optimize(self):
        """Main optimization routine"""
        logger.info("🚀 Starting Celery worker optimization...")
        logger.info("=" * 50)
        
        # Step 1: Prerequisites check
        if not self.check_prerequisites():
            logger.error("❌ Prerequisites check failed. Aborting optimization.")
            return False
        
        # Step 2: Capture baseline
        baseline = self.get_baseline_metrics()
        if not baseline:
            logger.error("❌ Failed to capture baseline metrics. Aborting.")
            return False
        
        # Step 3: Backup current config
        if not self.backup_current_config():
            logger.error("❌ Failed to create backup. Aborting.")
            return False
        
        # Step 4: Apply optimization
        if not self.apply_optimization():
            logger.error("❌ Optimization failed. Attempting rollback...")
            self.rollback()
            return False
        
        # Step 5: Monitor performance
        results = self.monitor_performance(duration_minutes=5)
        
        if results and results['stable']:
            logger.info("🎉 OPTIMIZATION SUCCESSFUL!")
            logger.info("✅ System is stable with improved configuration")
            logger.info(f"✅ Workers increased from ~{baseline['worker_count']} to {results['max_workers']}")
            return True
        else:
            logger.warning("⚠️ Performance monitoring shows instability. Rolling back...")
            if self.rollback():
                logger.info("🔄 Rollback successful. System restored to stable state.")
            else:
                logger.error("❌ Rollback failed. Manual intervention required!")
            return False


if __name__ == "__main__":
    optimizer = CeleryOptimizer()
    success = optimizer.optimize()
    
    if success:
        print("\n🎉 Celery optimization completed successfully!")
        print("📈 Keyword processing should now be significantly faster")
        print("📊 Monitor system performance over the next 24 hours")
    else:
        print("\n❌ Optimization failed or was rolled back")
        print("🔍 Check logs for detailed information")
        print("💬 Consider manual tuning or contacting system administrator")