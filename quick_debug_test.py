#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def quick_debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        try:
            print("🔐 Quick login test...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            # Login
            await page.fill('input[name="username"]', 'tomuaaz@gmail.com')
            await page.fill('input[name="password"]', 'Vf123456$')
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(3000)
            
            print(f"📍 After login - URL: {page.url}")
            
            # Navigate to audit
            print("🔍 Navigating to audit...")
            await page.goto('http://localhost:8000/site-audit/13/', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            title = await page.title()
            url = page.url
            print(f"📄 Title: {title}")
            print(f"📍 URL: {url}")
            
            # Check if Issues tab exists and works
            issues_tab = page.locator('button.tab').filter(has_text='Issues')
            if await issues_tab.count() > 0:
                print("✅ Issues tab found!")
                await issues_tab.click()
                await page.wait_for_timeout(1000)
                
                # Check visibility
                issues_content = page.locator('#issues-tab')
                is_visible = await issues_content.is_visible()
                print(f"👀 Issues visible: {is_visible}")
                
                if is_visible:
                    # Quick check for issue cards
                    cards = page.locator('.issue-card')
                    card_count = await cards.count()
                    print(f"📊 Issue cards: {card_count}")
                    
                    # Check stats
                    stats = page.locator('.stat-value')
                    if await stats.count() >= 5:
                        critical = await stats.nth(0).inner_text()
                        high = await stats.nth(1).inner_text()
                        print(f"📈 Critical: {critical}, High: {high}")
                    
                    print("✅ QUICK TEST PASSED!")
                    
                    # Take screenshot
                    await page.screenshot(path='/tmp/quick_test_success.png')
                    print("📸 Screenshot: /tmp/quick_test_success.png")
                    
                    return True
            else:
                print("❌ Issues tab not found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()
    
    return False

if __name__ == "__main__":
    success = asyncio.run(quick_debug())
    if success:
        print("🎉 Quick test successful - ready for full E2E!")
    else:
        print("❌ Quick test failed")