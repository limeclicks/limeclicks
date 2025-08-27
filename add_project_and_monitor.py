#!/usr/bin/env python3
import asyncio
import time
import re
from datetime import datetime
from playwright.async_api import async_playwright

async def add_project_and_monitor():
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
            await page.screenshot(path='project_add_01_homepage.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Homepage loaded")
            
            # Login with the admin credentials
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Logging in as admin...")
            
            # Fill login form
            await page.fill('input[name="username"], input[name="email"], input[type="email"]', 'tomuaaz@gmail.com')
            await page.fill('input[name="password"], input[type="password"]', 'Vf123456$')
            
            # Submit form
            submit_button = page.locator('button[type="submit"], input[type="submit"]').first
            await submit_button.click()
            await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='project_add_02_logged_in.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Logged in successfully")
            
            # Navigate to Projects page to add new project
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to Projects page...")
            
            # Navigate directly to add project page
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to Add Project page...")
            await page.goto('http://localhost:8001/project/add/')
            await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='project_add_04_add_form.png', full_page=True)
            
            # Fill in the project form
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Filling project form for fastgenerations.co.uk...")
            
            # Try to fill domain field with various possible selectors
            try:
                # First try the most specific selector
                domain_filled = False
                for selector in ['input[name="domain"]', 'input[id*="domain"]', 'input[placeholder*="domain"]', 'input[type="url"]']:
                    try:
                        field = page.locator(selector).first
                        if await field.is_visible(timeout=1000):
                            await field.fill('https://fastgenerations.co.uk/')
                            domain_filled = True
                            print(f"  Filled domain field using: {selector}")
                            break
                    except:
                        continue
                
                if not domain_filled:
                    # If specific selectors fail, try the first text input
                    await page.locator('input[type="text"]').first.fill('https://fastgenerations.co.uk/')
                    print("  Filled domain field using first text input")
            except Exception as e:
                print(f"  Error filling domain: {e}")
            
            # Try to fill title field if it exists
            try:
                for selector in ['input[name="title"]', 'input[id*="title"]', 'input[placeholder*="title"]']:
                    try:
                        field = page.locator(selector).first
                        if await field.is_visible(timeout=1000):
                            await field.fill('Fast Generations UK')
                            print(f"  Filled title field using: {selector}")
                            break
                    except:
                        continue
            except Exception as e:
                print(f"  Could not fill title field: {e}")
            
            await page.screenshot(path='project_add_05_form_filled.png', full_page=True)
            
            # Submit the form
            submit_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("Save"), button:has-text("Add")').first
            await submit_button.click()
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Project submitted, waiting for response...")
            await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='project_add_06_project_created.png', full_page=True)
            
            # Now navigate to Site Audit page
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Navigating to Site Audit page...")
            
            site_audit_link = page.locator('a:has-text("Site Audit"), a[href*="site-audit"]').first
            if await site_audit_link.is_visible(timeout=5000):
                await site_audit_link.click()
                await page.wait_for_load_state('networkidle')
            else:
                # Try direct navigation
                await page.goto('http://localhost:8001/site-audit/')
                await page.wait_for_load_state('networkidle')
            
            await page.screenshot(path='project_add_07_site_audit_list.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Site Audit page loaded")
            
            # Look for fastgenerations.co.uk in the audit list
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Looking for fastgenerations.co.uk audit...")
            
            # Click on the audit detail page
            fastgen_link = page.locator('a:has-text("fastgenerations.co.uk"), td:has-text("fastgenerations.co.uk") a').first
            if await fastgen_link.is_visible(timeout=10000):
                await fastgen_link.click()
                await page.wait_for_load_state('networkidle')
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Opened fastgenerations.co.uk audit detail page")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not find fastgenerations.co.uk in audit list")
                # Take screenshot of what's on the page
                await page.screenshot(path='project_add_debug_audit_list.png', full_page=True)
            
            # Monitor the audit progress
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting audit monitoring...")
            print("=" * 60)
            
            start_time = time.time()
            max_duration = 10 * 60  # 10 minutes
            check_interval = 15  # 15 seconds
            
            screenshot_count = 8
            target_pages = 378
            pages_reached = False
            
            while time.time() - start_time < max_duration:
                try:
                    # Refresh the page to get latest data
                    await page.reload()
                    await page.wait_for_load_state('networkidle')
                    
                    # Extract audit status information
                    status_text = "Unknown"
                    pages_crawled_num = 0
                    
                    # Look for pages crawled number
                    pages_text_elements = await page.locator('text=/\\d+ pages?/, text=/crawled.*\\d+/, text=/\\d+.*crawled/, text=/Pages.*\\d+/').all()
                    for element in pages_text_elements:
                        text = await element.inner_text()
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            pages_crawled_num = int(numbers[0])
                            if pages_crawled_num > 0:
                                break
                    
                    # Look for status
                    status_elements = await page.locator('.status, [class*="status"], text=/analyzing/i, text=/running/i, text=/completed/i').all()
                    for element in status_elements[:5]:  # Check first 5 elements
                        text = await element.inner_text()
                        if any(keyword in text.lower() for keyword in ['analyzing', 'running', 'completed', 'finished']):
                            status_text = text.strip()
                            break
                    
                    # Take screenshot
                    screenshot_name = f'project_add_{screenshot_count:02d}_audit_progress.png'
                    await page.screenshot(path=screenshot_name, full_page=True)
                    
                    # Print status update
                    current_time = datetime.now().strftime('%H:%M:%S')
                    elapsed = int(time.time() - start_time)
                    
                    print(f"[{current_time}] AUDIT STATUS (Elapsed: {elapsed}s)")
                    print(f"  Status: {status_text}")
                    print(f"  Pages Crawled: {pages_crawled_num}")
                    print(f"  Screenshot: {screenshot_name}")
                    
                    # Check if target reached
                    if pages_crawled_num >= target_pages:
                        print(f"[{current_time}] ✅ TARGET REACHED! {pages_crawled_num} pages crawled (target: {target_pages})")
                        pages_reached = True
                        break
                    
                    # Check for completion
                    if any(keyword in status_text.lower() for keyword in ['completed', 'finished', 'done']):
                        if pages_crawled_num < target_pages:
                            print(f"[{current_time}] ⚠️ Audit completed but only {pages_crawled_num} pages crawled (target: {target_pages})")
                        else:
                            print(f"[{current_time}] ✅ Audit completed with {pages_crawled_num} pages!")
                        break
                    
                    print("-" * 40)
                    screenshot_count += 1
                    
                    # Wait for next check
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error during monitoring: {e}")
                    await page.screenshot(path=f'project_add_error_{screenshot_count}.png', full_page=True)
                    await asyncio.sleep(check_interval)
                    screenshot_count += 1
            
            print("=" * 60)
            
            if pages_reached:
                # Now check the Issues page
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking Issues tab...")
                
                # Click on Issues tab
                issues_tab = page.locator('a:has-text("Issues"), button:has-text("Issues"), [role="tab"]:has-text("Issues")').first
                if await issues_tab.is_visible(timeout=5000):
                    await issues_tab.click()
                    await asyncio.sleep(2)  # Wait for content to load
                    
                    await page.screenshot(path='project_add_final_issues_tab.png', full_page=True)
                    
                    # Count issues
                    issue_elements = await page.locator('.issue, [class*="issue-item"], tr:has(td)').all()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(issue_elements)} issue elements on the page")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not find Issues tab")
            
            # Final screenshot
            await page.screenshot(path='project_add_final_status.png', full_page=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring completed")
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
            await page.screenshot(path='project_add_error_final.png', full_page=True)
            
        finally:
            # Keep browser open for inspection
            await asyncio.sleep(10)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(add_project_and_monitor())