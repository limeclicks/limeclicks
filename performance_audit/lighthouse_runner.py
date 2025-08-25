import json
import subprocess
import tempfile
import os
from typing import Dict, Optional, Tuple
from django.core.files.base import ContentFile
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class LighthouseRunner:
    """Executes Lighthouse audits and processes results"""
    
    def __init__(self):
        self.lighthouse_path = self._find_lighthouse()
    
    def _find_lighthouse(self) -> str:
        """Find the lighthouse executable"""
        # Try to find lighthouse in different locations
        try:
            # Check if lighthouse is in PATH
            result = subprocess.run(['which', 'lighthouse'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        # Check common npm locations
        npm_paths = [
            '/usr/local/bin/lighthouse',
            '/usr/bin/lighthouse',
            os.path.expanduser('~/.npm-global/bin/lighthouse'),
            './node_modules/.bin/lighthouse'
        ]
        
        for path in npm_paths:
            if os.path.exists(path):
                return path
        
        # Default to hoping it's in PATH
        return 'lighthouse'
    
    def run_audit(self, url: str, device_type: str = 'desktop') -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Run a Lighthouse audit on the specified URL
        
        Args:
            url: The URL to audit
            device_type: Either 'desktop' or 'mobile'
        
        Returns:
            Tuple of (success, result_dict, error_message)
        """
        
        # Create temporary directory for output
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = os.path.join(temp_dir, 'report.json')
            html_output = os.path.join(temp_dir, 'report.html')
            
            # Build lighthouse command for headless server environment
            cmd = [
                self.lighthouse_path,
                url,
                '--output', 'json',  # JSON only, no HTML
                '--output-path', os.path.join(temp_dir, 'report'),
                # Chrome flags for true headless mode (no browser window)
                '--chrome-flags="--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-web-security --disable-features=site-per-process --disable-setuid-sandbox --disable-accelerated-2d-canvas --no-first-run --no-zygote --disable-background-timer-throttling --disable-extensions --disable-default-apps --disable-translate --disable-sync --no-default-browser-check --disable-background-networking --disable-background-mode --disable-plugins --disable-plugins-discovery"',
                '--quiet',
                '--no-enable-error-reporting',
                '--no-update-notifier',
                '--skip-audits', 'bf-cache'  # Skip audits that require GUI
            ]
            
            # Add device-specific flags
            if device_type == 'mobile':
                cmd.extend(['--preset', 'perf'])
                cmd.extend(['--emulated-form-factor', 'mobile'])
            else:
                cmd.extend(['--preset', 'desktop'])
                cmd.extend(['--emulated-form-factor', 'desktop'])
            
            # Add performance and best practice flags
            cmd.extend([
                '--throttling-method', 'simulate',
                '--only-categories', 'performance,accessibility,best-practices,seo,pwa'
            ])
            
            try:
                logger.info(f"Running Lighthouse audit for {url} ({device_type})")
                
                # Run lighthouse
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout
                )
                
                if result.returncode != 0:
                    error_msg = f"Lighthouse failed with code {result.returncode}: {result.stderr}"
                    logger.error(error_msg)
                    return False, None, error_msg
                
                # Check what files were generated
                generated_files = os.listdir(temp_dir)
                logger.info(f"Generated files: {generated_files}")
                
                # Try alternate file names (Lighthouse might append .report)
                if not os.path.exists(json_output):
                    # Try with .report suffix
                    alt_json = os.path.join(temp_dir, 'report.report.json')
                    if os.path.exists(alt_json):
                        json_output = alt_json
                        html_output = os.path.join(temp_dir, 'report.report.html')
                    else:
                        return False, None, f"Lighthouse did not generate expected files. Found: {generated_files}"
                
                with open(json_output, 'r') as f:
                    json_data = json.load(f)
                
                # Extract key metrics
                results = self._extract_metrics(json_data)
                results['json_content'] = json.dumps(json_data)
                
                return True, results, None
                
            except subprocess.TimeoutExpired:
                error_msg = "Lighthouse audit timed out after 120 seconds"
                logger.error(error_msg)
                return False, None, error_msg
            except Exception as e:
                error_msg = f"Error running Lighthouse: {str(e)}"
                logger.error(error_msg)
                return False, None, error_msg
    
    def _extract_metrics(self, json_data: Dict) -> Dict:
        """Extract key metrics from Lighthouse JSON result"""
        
        results = {}
        
        # Extract category scores (0-100)
        categories = json_data.get('categories', {})
        results['performance_score'] = int(categories.get('performance', {}).get('score', 0) * 100)
        results['accessibility_score'] = int(categories.get('accessibility', {}).get('score', 0) * 100)
        results['best_practices_score'] = int(categories.get('best-practices', {}).get('score', 0) * 100)
        results['seo_score'] = int(categories.get('seo', {}).get('score', 0) * 100)
        results['pwa_score'] = int(categories.get('pwa', {}).get('score', 0) * 100)
        
        # Extract performance metrics
        audits = json_data.get('performance_audit', {})
        
        # Core Web Vitals and other metrics
        metrics_mapping = {
            'first-contentful-paint': 'first_contentful_paint',
            'largest-contentful-paint': 'largest_contentful_paint',
            'interactive': 'time_to_interactive',
            'speed-index': 'speed_index',
            'total-blocking-time': 'total_blocking_time',
            'cumulative-layout-shift': 'cumulative_layout_shift'
        }
        
        for audit_key, result_key in metrics_mapping.items():
            audit_data = performance_audit.get(audit_key, {})
            if audit_data and 'numericValue' in audit_data:
                value = audit_data['numericValue']
                # Convert milliseconds to seconds for time-based metrics
                if result_key != 'cumulative_layout_shift' and result_key != 'total_blocking_time':
                    value = value / 1000.0
                results[result_key] = round(value, 3)
        
        # Extract additional info
        results['fetch_time'] = json_data.get('fetchTime')
        results['final_url'] = json_data.get('finalUrl')
        results['runtime_error'] = json_data.get('runtimeError', {}).get('message')
        
        return results
    
    def save_audit_results(self, performance_history, results: Dict):
        """Save audit results to the PerformanceHistory model"""
        
        # Update status and timestamps
        performance_history.status = 'completed'
        performance_history.started_at = performance_history.started_at or timezone.now()
        performance_history.completed_at = timezone.now()
        
        # Update scores
        performance_history.performance_score = results.get('performance_score')
        performance_history.accessibility_score = results.get('accessibility_score')
        performance_history.best_practices_score = results.get('best_practices_score')
        performance_history.seo_score = results.get('seo_score')
        performance_history.pwa_score = results.get('pwa_score')
        
        # Update metrics
        performance_history.first_contentful_paint = results.get('first_contentful_paint')
        performance_history.largest_contentful_paint = results.get('largest_contentful_paint')
        performance_history.time_to_interactive = results.get('time_to_interactive')
        performance_history.speed_index = results.get('speed_index')
        performance_history.total_blocking_time = results.get('total_blocking_time')
        performance_history.cumulative_layout_shift = results.get('cumulative_layout_shift')
        
        # Save JSON report to R2 with proper directory structure
        # Format: project.domain/lighthouseaudit/date/report.json
        if results.get('json_content'):
            from django.core.files.base import ContentFile
            
            # Create the path structure
            domain = performance_history.performance_page.project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
            date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
            
            # Path: domain/lighthouseaudit/date/device_report.json
            filename = f"{domain}/lighthouseaudit/{date_str}/{performance_history.device_type}_report.json"
            
            performance_history.json_report.save(
                filename,
                ContentFile(results['json_content'].encode('utf-8')),
                save=False
            )
        
        # Don't save HTML report - JSON only as requested
        
        performance_history.save()
        
        # Update the audit page with latest results
        performance_history.performance_page.update_from_audit_results(performance_history)
        
        return performance_history


class LighthouseService:
    """High-level service for managing Lighthouse audits"""
    
    @staticmethod
    def check_lighthouse_installed() -> bool:
        """Check if Lighthouse is installed"""
        try:
            result = subprocess.run(
                ['lighthouse', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    @staticmethod
    def install_lighthouse():
        """Install Lighthouse globally via npm"""
        try:
            logger.info("Installing Lighthouse...")
            result = subprocess.run(
                ['npm', 'install', '-g', 'lighthouse'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                logger.info("Lighthouse installed successfully")
                return True
            else:
                logger.error(f"Failed to install Lighthouse: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error installing Lighthouse: {str(e)}")
            return False