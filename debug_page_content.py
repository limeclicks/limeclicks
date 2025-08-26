#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def debug_page_content():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()
        
        try:
            print("🔍 Navigating to home page...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            # Check page title
            title = await page.title()
            print(f"📄 Page title: {title}")
            
            # Check if we need to login
            if 'Login' in title or 'Sign' in title:
                print("🔐 Login required. Logging in...")
                
                # Login
                await page.fill('input[name="email"]', 'tomuaaz@gmail.com')
                await page.fill('input[name="password"]', 'Vf123456$')
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(2000)
                
                print("✅ Login attempted")
            
            # Now navigate to site audit
            print("🔍 Navigating to site audit list...")
            await page.goto('http://localhost:8000/site-audit/', wait_until='networkidle')
            
            # Check if we have any audits
            audit_links = page.locator('a').filter(has_text='badexample.com')
            if await audit_links.count() > 0:
                print("✅ Found audit for badexample.com")
                await audit_links.first.click()
                await page.wait_for_timeout(2000)
                
                # Check page title after navigation
                new_title = await page.title()
                print(f"📄 Audit page title: {new_title}")
                
                # Now check for Issues tab
                issues_tab = page.locator('button.tab').filter(has_text='Issues')
                tab_count = await issues_tab.count()
                print(f"🔍 Found {tab_count} Issues tab buttons")
                
                if tab_count > 0:
                    print("✅ Issues tab found!")
                    
                    # Check all tabs available
                    all_tabs = page.locator('button.tab')
                    all_count = await all_tabs.count()
                    print(f"📋 Total tabs found: {all_count}")
                    
                    for i in range(all_count):
                        tab_text = await all_tabs.nth(i).inner_text()
                        print(f"  Tab {i}: {tab_text}")
                    
                    # Take screenshot before click
                    await page.screenshot(path='/tmp/debug_before_click.png')
                    print("📸 Screenshot: /tmp/debug_before_click.png")
                    
                    # Click the Issues tab
                    await issues_tab.click()
                    await page.wait_for_timeout(1000)
                    
                    # Take screenshot after click
                    await page.screenshot(path='/tmp/debug_after_click.png')
                    print("📸 Screenshot: /tmp/debug_after_click.png")
                    
                    # Check content visibility
                    issues_content = page.locator('#issues-tab')
                    content_visible = await issues_content.is_visible()
                    print(f"👀 Issues content visible: {content_visible}")
                    
                    if content_visible:
                        content_text = await issues_content.inner_text()
                        print(f"📝 Content preview: {content_text[:200]}...")
                    else:
                        print("❌ Issues content not visible")
                        # Check all tab contents
                        all_contents = page.locator('.tab-content')
                        content_count = await all_contents.count()
                        print(f"📋 Total tab contents found: {content_count}")
                        
                        for i in range(content_count):
                            content_id = await all_contents.nth(i).get_attribute('id')
                            is_hidden = 'hidden' in (await all_contents.nth(i).get_attribute('class') or '')
                            print(f"  Content {i}: {content_id}, hidden: {is_hidden}")
                
            else:
                print("❌ No audit found for badexample.com")
                # List available audits
                audit_cards = page.locator('.card')
                card_count = await audit_cards.count()
                print(f"Found {card_count} audit cards")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page_content())