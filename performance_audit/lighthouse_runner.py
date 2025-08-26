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
                '--output', 'json',  # JSON only
                '--output-path', json_output,  # Full path with extension
                # Chrome flags for true headless mode (no browser window)
                '--chrome-flags=--headless=new --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-web-security --disable-features=site-per-process --disable-setuid-sandbox --disable-accelerated-2d-canvas --no-first-run --no-zygote --disable-background-timer-throttling --disable-extensions --disable-default-apps --disable-translate --disable-sync --no-default-browser-check --disable-background-networking --disable-background-mode --disable-plugins --disable-plugins-discovery',
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
        
        # Calculate overall score (average of all scores)
        scores = [
            results['performance_score'],
            results['accessibility_score'],
            results['best_practices_score'],
            results['seo_score'],
            results['pwa_score']
        ]
        results['overall_score'] = round(sum(scores) / len(scores))
        
        # Extract performance metrics
        audits = json_data.get('audits', {})
        
        # Core Web Vitals and additional metrics
        metrics_mapping = {
            'first-contentful-paint': 'first_contentful_paint',
            'largest-contentful-paint': 'largest_contentful_paint',
            'interactive': 'time_to_interactive',
            'speed-index': 'speed_index',
            'total-blocking-time': 'total_blocking_time',
            'cumulative-layout-shift': 'cumulative_layout_shift',
            'max-potential-fid': 'first_input_delay',  # FID approximation
            'server-response-time': 'time_to_first_byte',  # TTFB
        }
        
        for audit_key, result_key in metrics_mapping.items():
            audit_data = audits.get(audit_key, {})
            if audit_data and 'numericValue' in audit_data:
                value = audit_data['numericValue']
                # Convert milliseconds to seconds for time-based metrics except TBT, FID, TTFB
                if result_key not in ['cumulative_layout_shift', 'total_blocking_time', 'first_input_delay', 'time_to_first_byte']:
                    value = value / 1000.0
                results[result_key] = round(value, 3)
        
        # INP (Interaction to Next Paint) - approximated from TBT if available
        if 'total_blocking_time' in results:
            # Approximate INP from TBT (not exact but correlated)
            results['interaction_to_next_paint'] = results.get('total_blocking_time', 0) * 1.5
        
        # Extract errors from various sources
        results['errors'] = self._extract_errors(json_data)
        
        # Extract additional info
        results['fetch_time'] = json_data.get('fetchTime')
        results['final_url'] = json_data.get('finalUrl')
        results['runtime_error'] = json_data.get('runtimeError', {}).get('message')
        
        return results
    
    def _extract_errors(self, json_data: Dict) -> Dict:
        """Extract all errors from Lighthouse audit"""
        
        errors = {
            'js_errors': [],
            'css_errors': [],
            'console_errors': [],
            'network_errors': []
        }
        
        audits = json_data.get('audits', {})
        
        # Extract console errors
        console_messages = audits.get('errors-in-console', {})
        if console_messages and 'details' in console_messages:
            items = console_messages['details'].get('items', [])
            for item in items:
                error_entry = {
                    'source': item.get('source', 'console'),
                    'description': item.get('description', ''),
                    'url': item.get('url', ''),
                    'level': item.get('level', 'error')
                }
                errors['console_errors'].append(error_entry)
                
                # Categorize by type
                desc_lower = error_entry['description'].lower()
                if 'javascript' in desc_lower or '.js' in error_entry['url']:
                    errors['js_errors'].append(error_entry)
                elif 'css' in desc_lower or '.css' in error_entry['url']:
                    errors['css_errors'].append(error_entry)
        
        # Extract network errors (failed requests)
        network_requests = audits.get('network-requests', {})
        if network_requests and 'details' in network_requests:
            items = network_requests['details'].get('items', [])
            for item in items:
                if item.get('statusCode', 200) >= 400:
                    error_entry = {
                        'url': item.get('url', ''),
                        'statusCode': item.get('statusCode'),
                        'mimeType': item.get('mimeType', ''),
                        'resourceType': item.get('resourceType', ''),
                        'transferSize': item.get('transferSize', 0)
                    }
                    errors['network_errors'].append(error_entry)
                    
                    # Categorize JS and CSS errors
                    if item.get('resourceType') == 'Script' or '.js' in item.get('url', ''):
                        errors['js_errors'].append({
                            'source': 'network',
                            'description': f"Failed to load script: {item.get('statusCode')}",
                            'url': item.get('url', '')
                        })
                    elif item.get('resourceType') == 'Stylesheet' or '.css' in item.get('url', ''):
                        errors['css_errors'].append({
                            'source': 'network',
                            'description': f"Failed to load stylesheet: {item.get('statusCode')}",
                            'url': item.get('url', '')
                        })
        
        # Extract JavaScript execution errors
        js_errors_audit = audits.get('no-unload-listeners', {})
        if js_errors_audit and js_errors_audit.get('score', 1) < 1:
            errors['js_errors'].append({
                'source': 'audit',
                'description': 'Page uses unload listeners which can break back/forward cache',
                'url': json_data.get('finalUrl', '')
            })
        
        # Check for render-blocking resources
        render_blocking = audits.get('render-blocking-resources', {})
        if render_blocking and 'details' in render_blocking:
            items = render_blocking['details'].get('items', [])
            for item in items:
                url = item.get('url', '')
                if '.css' in url:
                    errors['css_errors'].append({
                        'source': 'performance',
                        'description': 'Render-blocking CSS',
                        'url': url,
                        'wastedMs': item.get('wastedMs', 0)
                    })
                elif '.js' in url:
                    errors['js_errors'].append({
                        'source': 'performance',
                        'description': 'Render-blocking JavaScript',
                        'url': url,
                        'wastedMs': item.get('wastedMs', 0)
                    })
        
        return errors
    
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
        performance_history.overall_score = results.get('overall_score')
        
        # Update Core Web Vitals and metrics
        performance_history.first_contentful_paint = results.get('first_contentful_paint')
        performance_history.largest_contentful_paint = results.get('largest_contentful_paint')
        performance_history.time_to_interactive = results.get('time_to_interactive')
        performance_history.speed_index = results.get('speed_index')
        performance_history.total_blocking_time = results.get('total_blocking_time')
        performance_history.cumulative_layout_shift = results.get('cumulative_layout_shift')
        
        # Update additional Web Vitals
        performance_history.interaction_to_next_paint = results.get('interaction_to_next_paint')
        performance_history.first_input_delay = results.get('first_input_delay')
        performance_history.time_to_first_byte = results.get('time_to_first_byte')
        
        # Store errors
        errors = results.get('errors', {})
        performance_history.js_errors = errors.get('js_errors', [])
        performance_history.css_errors = errors.get('css_errors', [])
        performance_history.console_errors = errors.get('console_errors', [])
        performance_history.network_errors = errors.get('network_errors', [])
        
        # Create the path structure for R2
        domain = performance_history.performance_page.project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON report to R2
        if results.get('json_content'):
            from django.core.files.base import ContentFile
            
            # Path: domain/lighthouseaudit/date/device_report.json
            filename = f"{domain}/lighthouseaudit/{date_str}/{performance_history.device_type}_report.json"
            
            performance_history.json_report.save(
                filename,
                ContentFile(results['json_content'].encode('utf-8')),
                save=False
            )
        
        # Save error report to R2
        if errors:
            import json
            from django.core.files.base import ContentFile
            
            error_report = {
                'audit_id': str(performance_history.id),
                'device_type': performance_history.device_type,
                'timestamp': timezone.now().isoformat(),
                'url': results.get('final_url', ''),
                'js_errors': errors.get('js_errors', []),
                'css_errors': errors.get('css_errors', []),
                'console_errors': errors.get('console_errors', []),
                'network_errors': errors.get('network_errors', []),
                'total_errors': {
                    'js': len(errors.get('js_errors', [])),
                    'css': len(errors.get('css_errors', [])),
                    'console': len(errors.get('console_errors', [])),
                    'network': len(errors.get('network_errors', []))
                }
            }
            
            # Path: domain/lighthouseaudit/date/device_errors.json
            filename = f"{domain}/lighthouseaudit/{date_str}/{performance_history.device_type}_errors.json"
            
            performance_history.error_report.save(
                filename,
                ContentFile(json.dumps(error_report, indent=2).encode('utf-8')),
                save=False
            )
        
        performance_history.save()
        
        # Update the audit page with latest results
        performance_history.performance_page.update_from_audit_results(performance_history)
        
        # Update consolidated errors
        self._update_consolidated_errors(performance_history)
        
        return performance_history
    
    def save_combined_audit_results(self, performance_history, results: Dict):
        """Save combined audit results (both mobile and desktop) to a single PerformanceHistory record"""
        
        # Update status and timestamps
        performance_history.status = 'completed'
        performance_history.started_at = performance_history.started_at or timezone.now()
        performance_history.completed_at = timezone.now()
        
        # Create the path structure for R2
        domain = performance_history.performance_page.project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        
        # Process mobile results if available
        if results.get('mobile'):
            mobile_data = results['mobile']
            
            # Update mobile scores
            performance_history.mobile_performance_score = mobile_data.get('performance_score')
            performance_history.mobile_accessibility_score = mobile_data.get('accessibility_score')
            performance_history.mobile_best_practices_score = mobile_data.get('best_practices_score')
            performance_history.mobile_seo_score = mobile_data.get('seo_score')
            performance_history.mobile_pwa_score = mobile_data.get('pwa_score')
            performance_history.mobile_overall_score = mobile_data.get('overall_score')
            
            # Update mobile Core Web Vitals and metrics
            performance_history.mobile_first_contentful_paint = mobile_data.get('first_contentful_paint')
            performance_history.mobile_largest_contentful_paint = mobile_data.get('largest_contentful_paint')
            performance_history.mobile_time_to_interactive = mobile_data.get('time_to_interactive')
            performance_history.mobile_speed_index = mobile_data.get('speed_index')
            performance_history.mobile_total_blocking_time = mobile_data.get('total_blocking_time')
            performance_history.mobile_cumulative_layout_shift = mobile_data.get('cumulative_layout_shift')
            
            # Update mobile additional Web Vitals
            performance_history.mobile_interaction_to_next_paint = mobile_data.get('interaction_to_next_paint')
            performance_history.mobile_first_input_delay = mobile_data.get('first_input_delay')
            performance_history.mobile_time_to_first_byte = mobile_data.get('time_to_first_byte')
            
            # Store mobile errors
            mobile_errors = mobile_data.get('errors', {})
            performance_history.mobile_js_errors = mobile_errors.get('js_errors', [])
            performance_history.mobile_css_errors = mobile_errors.get('css_errors', [])
            performance_history.mobile_console_errors = mobile_errors.get('console_errors', [])
            performance_history.mobile_network_errors = mobile_errors.get('network_errors', [])
            
            # Save mobile JSON report to R2
            if mobile_data.get('json_content'):
                from django.core.files.base import ContentFile
                filename = f"{domain}/lighthouseaudit/{date_str}/mobile_report.json"
                performance_history.mobile_json_report.save(
                    filename,
                    ContentFile(mobile_data['json_content'].encode('utf-8')),
                    save=False
                )
        
        # Process desktop results if available
        if results.get('desktop'):
            desktop_data = results['desktop']
            
            # Update desktop scores
            performance_history.desktop_performance_score = desktop_data.get('performance_score')
            performance_history.desktop_accessibility_score = desktop_data.get('accessibility_score')
            performance_history.desktop_best_practices_score = desktop_data.get('best_practices_score')
            performance_history.desktop_seo_score = desktop_data.get('seo_score')
            performance_history.desktop_pwa_score = desktop_data.get('pwa_score')
            performance_history.desktop_overall_score = desktop_data.get('overall_score')
            
            # Update desktop Core Web Vitals and metrics
            performance_history.desktop_first_contentful_paint = desktop_data.get('first_contentful_paint')
            performance_history.desktop_largest_contentful_paint = desktop_data.get('largest_contentful_paint')
            performance_history.desktop_time_to_interactive = desktop_data.get('time_to_interactive')
            performance_history.desktop_speed_index = desktop_data.get('speed_index')
            performance_history.desktop_total_blocking_time = desktop_data.get('total_blocking_time')
            performance_history.desktop_cumulative_layout_shift = desktop_data.get('cumulative_layout_shift')
            
            # Update desktop additional Web Vitals
            performance_history.desktop_interaction_to_next_paint = desktop_data.get('interaction_to_next_paint')
            performance_history.desktop_first_input_delay = desktop_data.get('first_input_delay')
            performance_history.desktop_time_to_first_byte = desktop_data.get('time_to_first_byte')
            
            # Store desktop errors
            desktop_errors = desktop_data.get('errors', {})
            performance_history.desktop_js_errors = desktop_errors.get('js_errors', [])
            performance_history.desktop_css_errors = desktop_errors.get('css_errors', [])
            performance_history.desktop_console_errors = desktop_errors.get('console_errors', [])
            performance_history.desktop_network_errors = desktop_errors.get('network_errors', [])
            
            # Save desktop JSON report to R2
            if desktop_data.get('json_content'):
                from django.core.files.base import ContentFile
                filename = f"{domain}/lighthouseaudit/{date_str}/desktop_report.json"
                performance_history.desktop_json_report.save(
                    filename,
                    ContentFile(desktop_data['json_content'].encode('utf-8')),
                    save=False
                )
        
        # Save consolidated error report combining both mobile and desktop
        all_errors = {
            'audit_id': str(performance_history.id),
            'timestamp': timezone.now().isoformat(),
            'mobile_errors': {
                'js': performance_history.mobile_js_errors,
                'css': performance_history.mobile_css_errors,
                'console': performance_history.mobile_console_errors,
                'network': performance_history.mobile_network_errors,
                'total': {
                    'js': len(performance_history.mobile_js_errors),
                    'css': len(performance_history.mobile_css_errors),
                    'console': len(performance_history.mobile_console_errors),
                    'network': len(performance_history.mobile_network_errors)
                }
            } if results.get('mobile') else None,
            'desktop_errors': {
                'js': performance_history.desktop_js_errors,
                'css': performance_history.desktop_css_errors,
                'console': performance_history.desktop_console_errors,
                'network': performance_history.desktop_network_errors,
                'total': {
                    'js': len(performance_history.desktop_js_errors),
                    'css': len(performance_history.desktop_css_errors),
                    'console': len(performance_history.desktop_console_errors),
                    'network': len(performance_history.desktop_network_errors)
                }
            } if results.get('desktop') else None
        }
        
        import json
        from django.core.files.base import ContentFile
        filename = f"{domain}/lighthouseaudit/{date_str}/consolidated_errors.json"
        performance_history.consolidated_error_report.save(
            filename,
            ContentFile(json.dumps(all_errors, indent=2).encode('utf-8')),
            save=False
        )
        
        performance_history.save()
        
        # Update the audit page with latest results (using mobile as primary)
        performance_history.performance_page.update_from_audit_results(performance_history)
        
        # Update consolidated errors with both mobile and desktop
        self._update_consolidated_errors_combined(performance_history)
        
        return performance_history
    
    def _update_consolidated_errors(self, performance_history):
        """Update consolidated errors across all audits"""
        from .models import ConsolidatedErrors
        import json
        from django.core.files.base import ContentFile
        
        # Get or create consolidated errors for this performance page
        consolidated, created = ConsolidatedErrors.objects.get_or_create(
            performance_page=performance_history.performance_page
        )
        
        # Helper function to merge unique errors
        def merge_unique_errors(existing, new):
            # Convert to set of JSON strings for uniqueness
            existing_set = {json.dumps(e, sort_keys=True) for e in existing}
            for error in new:
                error_str = json.dumps(error, sort_keys=True)
                if error_str not in existing_set:
                    existing_set.add(error_str)
                    existing.append(error)
            return existing
        
        # Merge errors from this audit
        consolidated.all_js_errors = merge_unique_errors(
            consolidated.all_js_errors,
            performance_history.js_errors
        )
        consolidated.all_css_errors = merge_unique_errors(
            consolidated.all_css_errors,
            performance_history.css_errors
        )
        consolidated.all_console_errors = merge_unique_errors(
            consolidated.all_console_errors,
            performance_history.console_errors
        )
        consolidated.all_network_errors = merge_unique_errors(
            consolidated.all_network_errors,
            performance_history.network_errors
        )
        
        # Update total count
        consolidated.total_unique_errors = (
            len(consolidated.all_js_errors) +
            len(consolidated.all_css_errors) +
            len(consolidated.all_console_errors) +
            len(consolidated.all_network_errors)
        )
        
        # Create consolidated error report
        domain = performance_history.performance_page.project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        consolidated_report = {
            'project': domain,
            'last_updated': timezone.now().isoformat(),
            'total_unique_errors': consolidated.total_unique_errors,
            'js_errors': {
                'count': len(consolidated.all_js_errors),
                'errors': consolidated.all_js_errors
            },
            'css_errors': {
                'count': len(consolidated.all_css_errors),
                'errors': consolidated.all_css_errors
            },
            'console_errors': {
                'count': len(consolidated.all_console_errors),
                'errors': consolidated.all_console_errors
            },
            'network_errors': {
                'count': len(consolidated.all_network_errors),
                'errors': consolidated.all_network_errors
            }
        }
        
        # Save consolidated report to R2
        filename = f"{domain}/lighthouseaudit/consolidated_errors.json"
        consolidated.consolidated_error_report.save(
            filename,
            ContentFile(json.dumps(consolidated_report, indent=2).encode('utf-8')),
            save=False
        )
        
        consolidated.save()
    
    def _update_consolidated_errors_combined(self, performance_history):
        """Update consolidated errors for combined mobile and desktop audits"""
        from .models import ConsolidatedErrors
        import json
        from django.core.files.base import ContentFile
        
        # Get or create consolidated errors for this performance page
        consolidated, created = ConsolidatedErrors.objects.get_or_create(
            performance_page=performance_history.performance_page
        )
        
        # Helper function to merge unique errors
        def merge_unique_errors(existing, new):
            # Convert to set of JSON strings for uniqueness
            existing_set = {json.dumps(e, sort_keys=True) for e in existing}
            for error in new:
                error_str = json.dumps(error, sort_keys=True)
                if error_str not in existing_set:
                    existing_set.add(error_str)
                    existing.append(error)
            return existing
        
        # Merge mobile errors
        consolidated.all_js_errors = merge_unique_errors(
            consolidated.all_js_errors,
            performance_history.mobile_js_errors
        )
        consolidated.all_css_errors = merge_unique_errors(
            consolidated.all_css_errors,
            performance_history.mobile_css_errors
        )
        consolidated.all_console_errors = merge_unique_errors(
            consolidated.all_console_errors,
            performance_history.mobile_console_errors
        )
        consolidated.all_network_errors = merge_unique_errors(
            consolidated.all_network_errors,
            performance_history.mobile_network_errors
        )
        
        # Merge desktop errors
        consolidated.all_js_errors = merge_unique_errors(
            consolidated.all_js_errors,
            performance_history.desktop_js_errors
        )
        consolidated.all_css_errors = merge_unique_errors(
            consolidated.all_css_errors,
            performance_history.desktop_css_errors
        )
        consolidated.all_console_errors = merge_unique_errors(
            consolidated.all_console_errors,
            performance_history.desktop_console_errors
        )
        consolidated.all_network_errors = merge_unique_errors(
            consolidated.all_network_errors,
            performance_history.desktop_network_errors
        )
        
        # Update total count
        consolidated.total_unique_errors = (
            len(consolidated.all_js_errors) +
            len(consolidated.all_css_errors) +
            len(consolidated.all_console_errors) +
            len(consolidated.all_network_errors)
        )
        
        # Create consolidated error report
        domain = performance_history.performance_page.project.domain.replace('https://', '').replace('http://', '').replace('/', '_')
        consolidated_report = {
            'project': domain,
            'last_updated': timezone.now().isoformat(),
            'total_unique_errors': consolidated.total_unique_errors,
            'js_errors': {
                'count': len(consolidated.all_js_errors),
                'errors': consolidated.all_js_errors
            },
            'css_errors': {
                'count': len(consolidated.all_css_errors),
                'errors': consolidated.all_css_errors
            },
            'console_errors': {
                'count': len(consolidated.all_console_errors),
                'errors': consolidated.all_console_errors
            },
            'network_errors': {
                'count': len(consolidated.all_network_errors),
                'errors': consolidated.all_network_errors
            },
            'breakdown': {
                'mobile': {
                    'js': len(performance_history.mobile_js_errors),
                    'css': len(performance_history.mobile_css_errors),
                    'console': len(performance_history.mobile_console_errors),
                    'network': len(performance_history.mobile_network_errors)
                },
                'desktop': {
                    'js': len(performance_history.desktop_js_errors),
                    'css': len(performance_history.desktop_css_errors),
                    'console': len(performance_history.desktop_console_errors),
                    'network': len(performance_history.desktop_network_errors)
                }
            }
        }
        
        # Save consolidated report to R2
        filename = f"{domain}/consolidated_error_report.json"
        consolidated.consolidated_error_report.save(
            filename,
            ContentFile(json.dumps(consolidated_report, indent=2).encode('utf-8')),
            save=False
        )
        
        consolidated.save()


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