#!/usr/bin/env python3

import asyncio
from playwright.async_api import async_playwright

async def check_login_form():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()
        
        try:
            print("🔍 Checking login form...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            # Take screenshot
            await page.screenshot(path='/tmp/login_form_check.png')
            print("📸 Screenshot: /tmp/login_form_check.png")
            
            # Check page title
            title = await page.title()
            print(f"📄 Title: {title}")
            
            # Look for different input field patterns
            email_selectors = [
                'input[name="email"]',
                'input[name="username"]', 
                'input[type="email"]',
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
                'input[id*="email"]',
                'input[id*="username"]'
            ]
            
            print("🔍 Looking for email/username fields...")
            for selector in email_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"✅ Found: {selector} ({count} elements)")
                    
            # Look for password field
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[placeholder*="password"]',
                'input[placeholder*="Password"]'
            ]
            
            print("🔍 Looking for password fields...")
            for selector in password_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"✅ Found: {selector} ({count} elements)")
            
            # Look for submit buttons
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Login")',
                'button:has-text("Submit")'
            ]
            
            print("🔍 Looking for submit buttons...")
            for selector in submit_selectors:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"✅ Found: {selector} ({count} elements)")
                    
            # Get all form elements
            all_inputs = page.locator('input')
            input_count = await all_inputs.count()
            print(f"\n📊 Total inputs found: {input_count}")
            
            for i in range(min(input_count, 10)):  # Check first 10 inputs
                input_elem = all_inputs.nth(i)
                name = await input_elem.get_attribute('name') or 'no-name'
                type_attr = await input_elem.get_attribute('type') or 'no-type'
                placeholder = await input_elem.get_attribute('placeholder') or 'no-placeholder'
                print(f"  Input {i}: name={name}, type={type_attr}, placeholder={placeholder}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_login_form())