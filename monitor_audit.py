#!/usr/bin/env python3
import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright

async def monitor_site_audit():
    async with async_playwright() as p:
        # Launch browser with visible UI
        browser = await p.chromium.launch(headless=False, args=['--disable-web-security'])
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Opening localhost:8001...")
            
            # Navigate to the site
            await page.goto('http://localhost:8001/')
            await page.wait_for_load_state('networkidle')
            
            # Take initial screenshot
            await page.screenshot(path='audit_monitor_01_homepage.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Homepage loaded, screenshot saved")
            
            # Login
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to login...")
            
            # Look for login form or link
            try:
                # Check if we're already logged in by looking for logout link or user menu
                logout_element = page.locator('text=Logout').first
                if await logout_element.is_visible(timeout=2000):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Already logged in")
                else:
                    raise Exception("Need to login")
            except:
                # Need to login - look for login link/button
                login_selectors = [
                    'a[href*="login"]',
                    'button:has-text("Login")',
                    'text=Login'
                ]
                login_link = None
                for selector in login_selectors:
                    try:
                        login_link = page.locator(selector).first
                        if await login_link.is_visible(timeout=2000):
                            break
                    except:
                        continue
                if login_link and await login_link.is_visible(timeout=5000):
                    await login_link.click()
                    await page.wait_for_load_state('networkidle')
                
                # Fill login form
                await page.fill('input[name="email"], input[type="email"]', 'tomuaaz@gmail.com')
                await page.fill('input[name="password"], input[type="password"]', 'Test123456!')
                
                # Submit form
                submit_button = page.locator('button[type="submit"], input[type="submit"]').first
                await submit_button.click()
                await page.wait_for_load_state('networkidle')
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Login submitted")
            
            # Navigate to Site Audits page
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to Site Audits...")
            
            # Look for Site Audits link in navigation
            site_audits_selectors = [
                'a:has-text("Site Audits")',
                'a[href*="site-audit"]',
                'a[href*="audit"]'
            ]
            site_audits_link = None
            for selector in site_audits_selectors:
                try:
                    site_audits_link = page.locator(selector).first
                    if await site_audits_link.is_visible(timeout=2000):
                        break
                except:
                    continue
            if site_audits_link and await site_audits_link.is_visible(timeout=5000):
                await site_audits_link.click()
                await page.wait_for_load_state('networkidle')
            else:
                # Try direct URL
                await page.goto('http://localhost:8001/site-audit/')
                await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='audit_monitor_02_site_audits_page.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Site Audits page loaded")
            
            # Look for fastgenerations.co.uk audit
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Looking for fastgenerations.co.uk audit...")
            
            # Try different selectors for the audit link
            fastgen_selectors = [
                'a:has-text("fastgenerations.co.uk")',
                'td:has-text("fastgenerations.co.uk")',
                'tr:has-text("fastgenerations.co.uk") a'
            ]
            fastgen_link = None
            for selector in fastgen_selectors:
                try:
                    fastgen_link = page.locator(selector).first
                    if await fastgen_link.is_visible(timeout=2000):
                        break
                except:
                    continue
            
            if fastgen_link and await fastgen_link.is_visible(timeout=5000):
                await fastgen_link.click()
                await page.wait_for_load_state('networkidle')
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Clicked on fastgenerations.co.uk audit")
            else:
                # If not found, list all audits for debugging
                audits = await page.locator('table tr, .audit-item, a[href*="audit"]').all()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(audits)} potential audit elements")
                
                # Try to find any audit with fastgenerations in it
                for audit in audits[:5]:  # Check first 5
                    text = await audit.inner_text() if audit else ""
                    if 'fastgenerations' in text.lower():
                        await audit.click()
                        await page.wait_for_load_state('networkidle')
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Found and clicked fastgenerations audit")
                        break
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not find fastgenerations audit, continuing with first available audit")
                    if audits:
                        await audits[0].click()
                        await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='audit_monitor_03_audit_detail.png', full_page=True)
            
            # Monitor the audit progress
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting audit monitoring...")
            print("=" * 60)
            
            start_time = time.time()
            max_duration = 5 * 60  # 5 minutes
            check_interval = 30  # 30 seconds
            
            screenshot_count = 4
            
            while time.time() - start_time < max_duration:
                try:
                    # Refresh the page to get latest data
                    await page.reload()
                    await page.wait_for_load_state('networkidle')
                    
                    # Extract audit status information
                    status_text = "Unknown"
                    pages_crawled = "Unknown"
                    
                    # Look for status indicators
                    status_elements = await page.locator('.status, .audit-status, [class*="status"], [id*="status"]').all()
                    for element in status_elements:
                        text = await element.inner_text()
                        if any(keyword in text.lower() for keyword in ['analyzing', 'running', 'completed', 'failed', 'pending']):
                            status_text = text.strip()
                            break
                    
                    # Look for page count
                    page_elements = await page.locator('text=/\\d+ pages?/, text=/crawled.*\\d+/, text=/\\d+.*crawled/').all()
                    for element in page_elements:
                        text = await element.inner_text()
                        if any(keyword in text.lower() for keyword in ['pages', 'crawled']):
                            pages_crawled = text.strip()
                            break
                    
                    # Also check for any progress indicators
                    progress_elements = await page.locator('.progress, [class*="progress"], .percentage, [class*="percent"]').all()
                    progress_info = []
                    for element in progress_elements:
                        text = await element.inner_text()
                        if text.strip():
                            progress_info.append(text.strip())
                    
                    # Take screenshot
                    screenshot_name = f'audit_monitor_{screenshot_count:02d}_progress.png'
                    await page.screenshot(path=screenshot_name, full_page=True)
                    
                    # Print status update
                    current_time = datetime.now().strftime('%H:%M:%S')
                    elapsed = int(time.time() - start_time)
                    
                    print(f"[{current_time}] AUDIT STATUS UPDATE (Elapsed: {elapsed}s)")
                    print(f"  Status: {status_text}")
                    print(f"  Pages Crawled: {pages_crawled}")
                    if progress_info:
                        print(f"  Progress Info: {', '.join(progress_info)}")
                    print(f"  Screenshot: {screenshot_name}")
                    
                    # Check for completion
                    if any(keyword in status_text.lower() for keyword in ['completed', 'finished', 'done']):
                        print(f"[{current_time}] AUDIT COMPLETED!")
                        break
                    
                    # Check if we've reached the target page count
                    if 'pages' in pages_crawled.lower():
                        try:
                            # Extract number from pages crawled text
                            import re
                            numbers = re.findall(r'\d+', pages_crawled)
                            if numbers and int(numbers[0]) >= 378:
                                print(f"[{current_time}] TARGET PAGE COUNT REACHED! ({numbers[0]} pages)")
                                break
                        except:
                            pass
                    
                    print("-" * 40)
                    screenshot_count += 1
                    
                    # Wait for next check
                    if time.time() - start_time < max_duration:
                        await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error during monitoring: {e}")
                    await page.screenshot(path=f'audit_monitor_error_{screenshot_count}.png', full_page=True)
                    await asyncio.sleep(check_interval)
                    screenshot_count += 1
            
            print("=" * 60)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring completed")
            
            # Final screenshot
            await page.screenshot(path='audit_monitor_final.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Final screenshot saved")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
            await page.screenshot(path='audit_monitor_error.png', full_page=True)
            
        finally:
            # Keep browser open for a moment to see final state
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(monitor_site_audit())