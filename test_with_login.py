#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def test_with_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        try:
            print("🔐 Logging in to test Issues tab...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            # Look for email/username field
            email_field = page.locator('input[name="email"], input[name="username"], input[type="email"]')
            if await email_field.count() > 0:
                await email_field.fill('tomuaaz@gmail.com')
                
                password_field = page.locator('input[name="password"], input[type="password"]')
                await password_field.fill('Vf123456$')
                
                # Find submit button
                submit_btn = page.locator('button[type="submit"], input[type="submit"]')
                if await submit_btn.count() > 0:
                    await submit_btn.first.click()
                    await page.wait_for_timeout(3000)
                    
                    print("✅ Login attempted")
                    
                    # Check if we're logged in
                    current_url = page.url
                    print(f"📄 Current URL: {current_url}")
                    
                    if 'login' not in current_url.lower() and 'sign' not in current_url.lower():
                        print("✅ Login successful, navigating to audit...")
                        
                        # Go to specific audit
                        await page.goto('http://localhost:8000/site-audit/13/', wait_until='networkidle')
                        
                        # Take screenshot
                        await page.screenshot(path='/tmp/logged_in_audit.png')
                        print("📸 Screenshot: /tmp/logged_in_audit.png")
                        
                        # Test Issues tab
                        await test_issues_tab_functionality(page)
                    else:
                        print("❌ Login failed")
                        await page.screenshot(path='/tmp/login_failed.png')
                else:
                    print("❌ Submit button not found")
                    await page.screenshot(path='/tmp/no_submit.png')
            else:
                print("❌ Email field not found")
                await page.screenshot(path='/tmp/no_email_field.png')
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

async def test_issues_tab_functionality(page):
    """Test the Issues tab functionality"""
    print("\n🔍 Testing Issues tab functionality...")
    
    # Find Issues tab
    issues_tab = page.locator('button.tab').filter(has_text='Issues')
    
    if await issues_tab.count() > 0:
        print("✅ Issues tab found!")
        
        # Click Issues tab
        await issues_tab.click()
        await page.wait_for_timeout(1000)
        
        # Check if content is visible
        issues_content = page.locator('#issues-tab')
        is_visible = await issues_content.is_visible()
        print(f"👀 Issues content visible: {is_visible}")
        
        if is_visible:
            # Check severity stats
            stats = page.locator('.stat-value')
            stat_count = await stats.count()
            print(f"📊 Found {stat_count} severity stats")
            
            for i in range(min(5, stat_count)):  # Check first 5 stats
                stat_text = await stats.nth(i).inner_text()
                print(f"  Stat {i}: {stat_text}")
            
            # Check issue cards
            issue_cards = page.locator('.issue-card')
            card_count = await issue_cards.count()
            print(f"📋 Found {card_count} issue cards")
            
            if card_count > 0:
                print("✅ Issues tab working correctly!")
                
                # Test first issue expansion
                first_card = issue_cards.first
                expand_btn = first_card.locator('button.btn-ghost').last
                if await expand_btn.count() > 0:
                    print("🔧 Testing resolution expansion...")
                    await expand_btn.click()
                    await page.wait_for_timeout(500)
                    
                    # Take final screenshot
                    await page.screenshot(path='/tmp/issues_tab_working.png')
                    print("📸 Final screenshot: /tmp/issues_tab_working.png")
                    
                    print("✅ Issues tab test completed successfully!")
                    return True
            else:
                print("❌ No issue cards found")
        else:
            print("❌ Issues content not visible")
    else:
        print("❌ Issues tab not found")
        
        # Debug: show all available tabs
        all_tabs = page.locator('button.tab')
        tab_count = await all_tabs.count()
        print(f"Available tabs ({tab_count}):")
        for i in range(tab_count):
            tab_text = await all_tabs.nth(i).inner_text()
            print(f"  - {tab_text}")
    
    return False

if __name__ == "__main__":
    asyncio.run(test_with_login())