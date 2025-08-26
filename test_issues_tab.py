#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def test_issues_tab():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            # Bypass login by going directly to the audit page
            print("🔍 Testing Issues tab with test data...")
            await page.goto('http://localhost:8000/site-audit/13/', wait_until='networkidle')
            
            # Check page title
            title = await page.title()
            print(f"📄 Page title: {title}")
            
            # Take screenshot of initial state
            await page.screenshot(path='/tmp/tab_test_initial.png')
            print("📸 Initial screenshot: /tmp/tab_test_initial.png")
            
            # Find Issues tab
            issues_tab = page.locator('button.tab').filter(has_text='Issues')
            
            if await issues_tab.count() > 0:
                print("✅ Issues tab found!")
                
                # Check tab content before click
                issues_content = page.locator('#issues-tab')
                before_classes = await issues_content.get_attribute('class')
                print(f"📋 Issues content classes before: {before_classes}")
                
                # Click Issues tab
                print("🖱️  Clicking Issues tab...")
                await issues_tab.click()
                await page.wait_for_timeout(1000)
                
                # Check tab content after click
                after_classes = await issues_content.get_attribute('class')
                print(f"📋 Issues content classes after: {after_classes}")
                
                is_visible = await issues_content.is_visible()
                print(f"👀 Issues content visible: {is_visible}")
                
                if is_visible:
                    # Check for summary stats
                    critical_stat = page.locator('.stat-value.text-error')
                    if await critical_stat.count() > 0:
                        critical_text = await critical_stat.inner_text()
                        print(f"🔴 Critical issues: {critical_text}")
                    
                    # Check for issue cards
                    issue_cards = page.locator('.issue-card')
                    card_count = await issue_cards.count()
                    print(f"📊 Issue cards found: {card_count}")
                    
                    if card_count > 0:
                        # Get first issue details
                        first_card = issue_cards.first
                        first_text = await first_card.inner_text()
                        print(f"📋 First issue preview: {first_text[:100]}...")
                        
                        # Test expanding resolution
                        resolution_button = first_card.locator('button.btn-ghost').last
                        if await resolution_button.count() > 0:
                            print("🔧 Testing resolution expansion...")
                            await resolution_button.click()
                            await page.wait_for_timeout(500)
                    
                    # Take screenshot of Issues tab
                    await page.screenshot(path='/tmp/tab_test_issues.png')
                    print("📸 Issues tab screenshot: /tmp/tab_test_issues.png")
                    
                    print("✅ Issues tab working correctly!")
                    
                else:
                    print("❌ Issues content not visible after click")
                    
                    # Debug: check all tab contents
                    all_contents = page.locator('.tab-content')
                    for i in range(await all_contents.count()):
                        content = all_contents.nth(i)
                        content_id = await content.get_attribute('id')
                        content_classes = await content.get_attribute('class')
                        print(f"  Tab content {i}: {content_id} - {content_classes}")
            
            else:
                print("❌ Issues tab not found")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_issues_tab())