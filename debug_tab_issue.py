#!/usr/bin/env python3

"""
Debug script to identify why the Issues tab content is not showing
"""

import asyncio
from playwright.async_api import async_playwright

async def debug_tab_issue():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            # Navigate to the site audit page
            print("🔍 Navigating to site audit page...")
            await page.goto('http://localhost:8000/site-audit/1/', wait_until='networkidle')
            
            # Take a screenshot before clicking
            await page.screenshot(path='/tmp/before_issues_click.png')
            print("📸 Screenshot taken: /tmp/before_issues_click.png")
            
            # Check if Issues tab exists
            issues_tab = page.locator('button.tab').filter(has_text='Issues')
            if await issues_tab.count() > 0:
                print("✅ Issues tab button found")
                
                # Check if tab content exists
                issues_content = page.locator('#issues-tab')
                if await issues_content.count() > 0:
                    print("✅ Issues tab content element found")
                    
                    # Check if content is initially hidden
                    is_hidden = await issues_content.get_attribute('class')
                    print(f"📋 Issues tab classes: {is_hidden}")
                    
                    # Click the Issues tab
                    print("🖱️  Clicking Issues tab...")
                    await issues_tab.click()
                    
                    # Wait a moment for any transitions
                    await page.wait_for_timeout(1000)
                    
                    # Check if content is now visible
                    is_hidden_after = await issues_content.get_attribute('class')
                    print(f"📋 Issues tab classes after click: {is_hidden_after}")
                    
                    # Check if content is visible on screen
                    is_visible = await issues_content.is_visible()
                    print(f"👀 Is issues content visible: {is_visible}")
                    
                    # Check actual content inside
                    content_text = await issues_content.inner_text()
                    print(f"📝 Content length: {len(content_text)} characters")
                    
                    if len(content_text) > 0:
                        print("✅ Issues tab has content")
                        print(f"First 200 chars: {content_text[:200]}...")
                    else:
                        print("❌ Issues tab appears empty")
                    
                    # Take a screenshot after clicking
                    await page.screenshot(path='/tmp/after_issues_click.png')
                    print("📸 Screenshot taken: /tmp/after_issues_click.png")
                    
                    # Check console errors
                    print("\n🔍 Checking for JavaScript errors...")
                    page.on('console', lambda msg: print(f"🖥️  Console: {msg.text()}"))
                    page.on('pageerror', lambda error: print(f"❌ JS Error: {error}"))
                    
                else:
                    print("❌ Issues tab content element NOT found")
                    
            else:
                print("❌ Issues tab button NOT found")
                
        except Exception as e:
            print(f"❌ Error during debugging: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_tab_issue())