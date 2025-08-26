#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def debug_tab_detailed():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            # Login first
            print("🔐 Logging in...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            email_field = page.locator('input[name="email"], input[name="username"], input[type="email"]')
            await email_field.fill('tomuaaz@gmail.com')
            
            password_field = page.locator('input[name="password"], input[type="password"]')
            await password_field.fill('Vf123456$')
            
            submit_btn = page.locator('button[type="submit"], input[type="submit"]')
            await submit_btn.first.click()
            await page.wait_for_timeout(3000)
            
            # Navigate to audit
            print("🔍 Navigating to badexample.com audit...")
            await page.goto('http://localhost:8000/site-audit/13/', wait_until='networkidle')
            
            # Take screenshot of initial state
            await page.screenshot(path='/tmp/debug_initial.png')
            print("📸 Initial: /tmp/debug_initial.png")
            
            # Debug all tabs
            print("\n📋 Analyzing all tabs:")
            all_tabs = page.locator('button.tab')
            tab_count = await all_tabs.count()
            print(f"Total tabs: {tab_count}")
            
            for i in range(tab_count):
                tab = all_tabs.nth(i)
                tab_text = await tab.inner_text()
                tab_classes = await tab.get_attribute('class')
                print(f"  Tab {i}: '{tab_text}' - Classes: {tab_classes}")
            
            # Debug all tab contents
            print("\n📋 Analyzing all tab contents:")
            all_contents = page.locator('.tab-content')
            content_count = await all_contents.count()
            print(f"Total tab contents: {content_count}")
            
            for i in range(content_count):
                content = all_contents.nth(i)
                content_id = await content.get_attribute('id')
                content_classes = await content.get_attribute('class')
                is_visible = await content.is_visible()
                print(f"  Content {i}: ID='{content_id}' - Classes: {content_classes} - Visible: {is_visible}")
            
            # Find Issues tab specifically
            issues_tab = page.locator('button.tab').filter(has_text='Issues')
            if await issues_tab.count() > 0:
                print("\n✅ Issues tab found!")
                
                # Check Issues content specifically
                issues_content = page.locator('#issues-tab')
                if await issues_content.count() > 0:
                    print("✅ Issues content element exists")
                    
                    before_classes = await issues_content.get_attribute('class')
                    before_visible = await issues_content.is_visible()
                    print(f"Before click - Classes: {before_classes}")
                    print(f"Before click - Visible: {before_visible}")
                    
                    # Click the Issues tab
                    print("\n🖱️  Clicking Issues tab...")
                    await issues_tab.click()
                    await page.wait_for_timeout(1000)
                    
                    # Check after click
                    after_classes = await issues_content.get_attribute('class')
                    after_visible = await issues_content.is_visible()
                    print(f"After click - Classes: {after_classes}")
                    print(f"After click - Visible: {after_visible}")
                    
                    # Take screenshot after click
                    await page.screenshot(path='/tmp/debug_after_click.png')
                    print("📸 After click: /tmp/debug_after_click.png")
                    
                    if after_visible:
                        print("✅ Issues content is visible!")
                        
                        # Check for specific elements
                        severity_stats = page.locator('#issues-tab .stat-value')
                        stat_count = await severity_stats.count()
                        print(f"📊 Severity stats found: {stat_count}")
                        
                        if stat_count > 0:
                            for i in range(min(5, stat_count)):
                                stat_value = await severity_stats.nth(i).inner_text()
                                print(f"  Stat {i}: {stat_value}")
                        
                        issue_cards = page.locator('#issues-tab .issue-card')
                        card_count = await issue_cards.count()
                        print(f"📋 Issue cards found: {card_count}")
                        
                        if card_count > 0:
                            print("✅ Issues tab fully working!")
                        else:
                            print("⚠️ Issues tab visible but no issue cards")
                    else:
                        print("❌ Issues content still not visible after click")
                        
                        # Debug JavaScript errors
                        page.on('console', lambda msg: print(f"🖥️ Console: {msg.type}: {msg.text}"))
                        page.on('pageerror', lambda error: print(f"❌ JS Error: {error}"))
                        
                        # Try clicking again
                        print("🔄 Trying to click again...")
                        await issues_tab.click()
                        await page.wait_for_timeout(1000)
                        
                        final_visible = await issues_content.is_visible()
                        print(f"Final visible state: {final_visible}")
                
                else:
                    print("❌ Issues content element (#issues-tab) not found")
            else:
                print("❌ Issues tab button not found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_tab_detailed())