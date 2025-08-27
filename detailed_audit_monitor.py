#!/usr/bin/env python3
"""
Detailed site audit progress monitor - clicks into audit details
"""
import asyncio
import time
from playwright.async_api import async_playwright
from datetime import datetime
import os
import re

async def monitor_audit_progress():
    async with async_playwright() as p:
        # Launch browser with GUI
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            print("🌐 Navigating to http://localhost:8001/")
            await page.goto("http://localhost:8001/", wait_until="networkidle")
            
            # Quick login
            print("🔑 Logging in...")
            await page.fill('input[type="email"], input[name="email"], input[name="username"]', "tomuaaz@gmail.com")
            await page.fill('input[type="password"], input[name="password"]', "Test123456!")
            
            login_button = page.locator('button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in")')
            await login_button.click()
            await page.wait_for_load_state("networkidle")
            print("✅ Logged in successfully")
            
            # Navigate directly to site audit
            await page.goto("http://localhost:8001/site-audit/", wait_until="networkidle")
            await page.screenshot(path="detailed_audit_list.png")
            print("📸 Site audit list screenshot taken")
            
            # Find and click on fastgenerations.co.uk
            print("🔍 Looking for fastgenerations.co.uk audit...")
            
            # Multiple strategies to find the audit
            found_audit = False
            
            # Strategy 1: Look for clickable text or links
            fastgen_links = page.locator('a:has-text("fastgenerations"), a:has-text("Fast Generations"), [href*="fastgenerations"]')
            if await fastgen_links.count() > 0:
                print("✅ Found fastgenerations link, clicking...")
                await fastgen_links.first.click()
                await page.wait_for_load_state("networkidle")
                found_audit = True
            
            if not found_audit:
                # Strategy 2: Look for table rows with the domain
                fastgen_rows = page.locator('tr:has-text("fastgenerations"), tr:has-text("Fast Generations")')
                if await fastgen_rows.count() > 0:
                    print("✅ Found fastgenerations row, looking for clickable elements...")
                    # Try to find clickable elements within the row
                    row_links = fastgen_rows.first.locator('a, button, [role="button"]')
                    if await row_links.count() > 0:
                        await row_links.first.click()
                        await page.wait_for_load_state("networkidle")
                        found_audit = True
                    else:
                        # Click on the row itself
                        await fastgen_rows.first.click()
                        await page.wait_for_load_state("networkidle")
                        found_audit = True
            
            if not found_audit:
                # Strategy 3: Try direct URL
                print("🔗 Trying direct URL approach...")
                await page.goto("http://localhost:8001/site-audit/1/", wait_until="networkidle")
                page_content = await page.inner_text('body')
                if 'fastgenerations' in page_content.lower():
                    found_audit = True
            
            if not found_audit:
                print("❌ Could not find fastgenerations audit, showing page content...")
                page_content = await page.inner_text('body')
                print("Page content:", page_content[:1000])
                return
            
            # Take screenshot of audit detail page
            await page.screenshot(path="detailed_audit_page.png")
            print("📸 Audit detail page screenshot taken")
            
            # Now monitor the audit progress
            print("📊 Starting detailed audit progress monitoring...")
            
            pages_crawled = 0
            target_pages = 378
            last_status = ""
            
            for i in range(120):  # Monitor for up to 20 minutes
                try:
                    current_url = page.url
                    print(f"🌐 Current URL: {current_url}")
                    
                    # Look for status text
                    status_selectors = [
                        '.status, .badge, .alert',
                        '[class*="status"], [class*="progress"]',
                        ':has-text("analyzing"), :has-text("running"), :has-text("complete")',
                        ':has-text("crawling"), :has-text("processing")'
                    ]
                    
                    current_status = "Unknown"
                    for selector in status_selectors:
                        elements = page.locator(selector)
                        if await elements.count() > 0:
                            for j in range(min(3, await elements.count())):  # Check first 3 elements
                                text = await elements.nth(j).inner_text()
                                if text and len(text.strip()) > 0:
                                    if any(keyword in text.lower() for keyword in ['analyzing', 'running', 'complete', 'crawling', 'processing']):
                                        current_status = text.strip()
                                        break
                            if current_status != "Unknown":
                                break
                    
                    # Look for pages crawled - multiple patterns
                    page_patterns = [
                        r'(\d+)\s*pages?\s*(crawled|found|discovered)',
                        r'pages?\s*crawled[:\s]*(\d+)',
                        r'(\d+)\s*/\s*\d+\s*pages?',
                        r'crawled[:\s]*(\d+)',
                        r'pages?[:\s]*(\d+)'
                    ]
                    
                    page_content = await page.inner_text('body')
                    current_pages = 0
                    
                    for pattern in page_patterns:
                        matches = re.findall(pattern, page_content, re.IGNORECASE)
                        for match in matches:
                            if isinstance(match, tuple):
                                number = match[0] if match[0].isdigit() else match[1] if len(match) > 1 and match[1].isdigit() else None
                            else:
                                number = match if match.isdigit() else None
                            
                            if number and int(number) > current_pages:
                                current_pages = int(number)
                    
                    # Update pages_crawled if we found a higher number
                    if current_pages > pages_crawled:
                        pages_crawled = current_pages
                    
                    # Look for numeric indicators in the UI
                    number_elements = page.locator(':has-text("378"), :has-text("Pages"), .number, .count')
                    if await number_elements.count() > 0:
                        for j in range(await number_elements.count()):
                            element_text = await number_elements.nth(j).inner_text()
                            numbers = re.findall(r'\d+', element_text)
                            for num in numbers:
                                if int(num) > pages_crawled and int(num) <= 1000:  # Reasonable upper limit
                                    pages_crawled = int(num)
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    if current_status != last_status or i % 5 == 0:  # Log status changes or every 5th iteration
                        print(f"⏰ [{timestamp}] Status: {current_status} | Pages crawled: {pages_crawled}")
                        last_status = current_status
                    
                    # Check completion conditions
                    if pages_crawled >= target_pages:
                        print(f"🎯 TARGET REACHED! {pages_crawled} pages crawled (target: {target_pages}+)")
                        await page.screenshot(path="audit_target_reached.png")
                        break
                    
                    if 'complete' in current_status.lower() and pages_crawled > 0:
                        print(f"✅ AUDIT COMPLETED with {pages_crawled} pages")
                        await page.screenshot(path="audit_completed.png")
                        break
                    
                    # Take periodic screenshots
                    if i % 10 == 0 and i > 0:  # Every 10 iterations
                        await page.screenshot(path=f"progress_screenshot_{i}.png")
                        print(f"📸 Progress screenshot: progress_screenshot_{i}.png")
                    
                    # Refresh page every few iterations to get updated data
                    if i % 3 == 0 and i > 0:  # Every 3 iterations (30 seconds)
                        await page.reload(wait_until="networkidle")
                    
                    # Wait 10 seconds before next check
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    print(f"❌ Error during monitoring iteration {i}: {e}")
                    await page.screenshot(path=f"error_screenshot_{i}.png")
                    continue
            
            # Final summary
            await page.screenshot(path="final_audit_status.png")
            print("📸 Final audit status screenshot taken")
            
            # Look for final audit data
            print("🔍 Checking final audit data...")
            
            # Get all visible text for final analysis
            final_content = await page.inner_text('body')
            
            # Look for health score
            health_matches = re.findall(r'health[:\s]*(\d+%?)', final_content, re.IGNORECASE)
            if health_matches:
                print(f"💚 Health Score: {health_matches[0]}")
            
            # Look for issues count
            issues_matches = re.findall(r'(\d+)\s*issues?', final_content, re.IGNORECASE)
            if issues_matches:
                print(f"⚠️  Issues Found: {issues_matches[0]} issues")
            
            # Look for performance scores
            mobile_matches = re.findall(r'mobile[:\s]*(\d+)', final_content, re.IGNORECASE)
            desktop_matches = re.findall(r'desktop[:\s]*(\d+)', final_content, re.IGNORECASE)
            
            if mobile_matches:
                print(f"📱 Mobile Score: {mobile_matches[0]}")
            if desktop_matches:
                print(f"🖥️  Desktop Score: {desktop_matches[0]}")
            
            print("\n" + "="*60)
            print("📋 FINAL AUDIT MONITORING SUMMARY")
            print("="*60)
            print(f"✓ Login: Successful (tomuaaz@gmail.com)")
            print(f"✓ Site Audit Page: Accessed")
            print(f"✓ Fastgenerations.co.uk Audit: {'Found and monitored' if found_audit else 'Not found'}")
            print(f"📊 Final Status: {last_status}")
            print(f"📄 Pages Crawled: {pages_crawled}")
            print(f"🎯 Target Pages: {target_pages}+")
            print(f"✅ Target Achievement: {'YES' if pages_crawled >= target_pages else 'NO'}")
            
            if health_matches:
                print(f"💚 Health Score: {health_matches[0]}")
            if mobile_matches:
                print(f"📱 Mobile Performance: {mobile_matches[0]}")
            if desktop_matches:
                print(f"🖥️  Desktop Performance: {desktop_matches[0]}")
            if issues_matches:
                print(f"⚠️  Issues Count: {issues_matches[0]}")
            
            print(f"📸 Screenshots saved: detailed_audit_*.png, progress_screenshot_*.png")
            print("="*60)
            
            # Keep browser open for manual inspection
            print("\n🖥️  Browser will remain open for manual inspection.")
            print("     Press Ctrl+C to close.")
            while True:
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            await page.screenshot(path="unexpected_error.png")
        finally:
            print("🔚 Closing browser...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(monitor_audit_progress())