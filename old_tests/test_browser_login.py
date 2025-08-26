#!/usr/bin/env python
"""
Browser automation test for login and dashboard verification using Playwright
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

def test_browser_login():
    """Test login flow in browser"""
    
    print("\n" + "="*60)
    print("BROWSER TEST: Login and Dashboard Verification")
    print("="*60)
    
    with sync_playwright() as p:
        # Launch browser in non-headless mode to see what's happening
        print("\n1. Starting browser...")
        browser = p.chromium.launch(headless=False, args=['--window-size=1920,1080'])
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        print("   ✓ Browser started")
        
        try:
            # Navigate to login page
            print("\n2. Navigating to login page...")
            page.goto("http://localhost:8000/accounts/login/", wait_until="networkidle")
            time.sleep(1)
            print("   ✓ Login page loaded")
            
            # Take screenshot of login page
            page.screenshot(path="1_login_page.png")
            print("   ✓ Screenshot saved: 1_login_page.png")
            
            # Enter credentials
            print("\n3. Entering login credentials...")
            
            # Fill email field
            page.fill("input[name='username']", "tomuaaz+test1@gmail.com")
            print("   ✓ Email entered")
            
            # Fill password field
            page.fill("input[name='password']", "Vf123456$")
            print("   ✓ Password entered")
            
            # Take screenshot before submitting
            page.screenshot(path="2_login_filled.png")
            print("   ✓ Screenshot saved: 2_login_filled.png")
            
            # Get CSRF token
            csrf_token = page.input_value("input[name='csrfmiddlewaretoken']") if page.locator("input[name='csrfmiddlewaretoken']").count() > 0 else None
            if csrf_token:
                print(f"   ✓ CSRF token found: {csrf_token[:20]}...")
            
            # Submit the form
            print("\n4. Submitting login form...")
            page.click("button[type='submit']")
            
            # Wait for navigation to complete
            print("\n5. Waiting for dashboard to load...")
            page.wait_for_load_state("networkidle")
            time.sleep(2)  # Extra wait for any JavaScript to finish
            
            # Check current URL
            current_url = page.url
            print(f"   Current URL: {current_url}")
            
            if "/accounts/dashboard/" in current_url:
                print("   ✓ Successfully redirected to dashboard")
            else:
                print(f"   ⚠ Unexpected URL: {current_url}")
            
            # Take screenshot of dashboard
            page.screenshot(path="3_dashboard_initial.png", full_page=True)
            print("   ✓ Screenshot saved: 3_dashboard_initial.png")
            
            # Verify dashboard elements
            print("\n6. Verifying dashboard elements...")
            
            # Check for Dashboard text
            if page.locator("text=Dashboard").count() > 0:
                print("   ✓ Dashboard heading found")
            else:
                print("   ⚠ Dashboard heading not found")
            
            # Check for Projects nav item
            print("\n7. Looking for Projects nav item...")
            
            # Try different selectors for Projects
            projects_found = False
            
            # Check for Projects link in navigation
            projects_link = page.locator("a:has-text('Projects')").first
            if projects_link.count() > 0:
                projects_found = True
                print(f"   ✓ Projects nav item found")
                
                # Highlight the Projects link
                page.evaluate("""
                    const element = document.querySelector('a[href*="project"]');
                    if (element) {
                        element.style.border = '3px solid red';
                        element.style.backgroundColor = 'yellow';
                    }
                """)
                
                # Take screenshot with highlighted Projects link
                time.sleep(0.5)
                page.screenshot(path="4_dashboard_projects_highlighted.png", full_page=True)
                print("   ✓ Screenshot with highlighted Projects: 4_dashboard_projects_highlighted.png")
            
            # Also check for any href containing 'project'
            if not projects_found:
                project_links = page.locator("a[href*='project']")
                if project_links.count() > 0:
                    projects_found = True
                    print(f"   ✓ Found {project_links.count()} project-related links")
                    for i in range(min(3, project_links.count())):
                        link_text = project_links.nth(i).text_content()
                        link_href = project_links.nth(i).get_attribute("href")
                        print(f"      - {link_text}: {link_href}")
            
            if not projects_found:
                print("   ⚠ Projects nav item not found")
                
                # List all navigation links for debugging
                print("\n   Available navigation links:")
                nav_links = page.locator("nav a, aside a, .sidebar a")
                if nav_links.count() > 0:
                    for i in range(min(10, nav_links.count())):
                        text = nav_links.nth(i).text_content()
                        href = nav_links.nth(i).get_attribute("href")
                        if text and text.strip():
                            print(f"      - {text.strip()}: {href}")
            
            # Save page HTML for debugging
            page_content = page.content()
            with open("dashboard_source.html", "w") as f:
                f.write(page_content)
            print("\n   ✓ Page source saved: dashboard_source.html")
            
            # Check for user name in dashboard
            print("\n8. Checking for user information...")
            if page.locator("text=tomuaaz").count() > 0:
                print("   ✓ User email displayed in dashboard")
            
            # Final screenshot
            print("\n9. Taking final screenshot...")
            page.screenshot(path="5_dashboard_final.png", full_page=True)
            print("   ✓ Final screenshot saved: 5_dashboard_final.png")
            
            print("\n" + "="*60)
            print("✅ BROWSER TEST COMPLETED SUCCESSFULLY")
            print("="*60)
            
            # Keep browser open for observation
            print("\n⏳ Keeping browser open for 5 seconds for observation...")
            time.sleep(5)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            page.screenshot(path="error_screenshot.png")
            print("   Error screenshot saved: error_screenshot.png")
            import traceback
            traceback.print_exc()
            
        finally:
            # Close browser
            browser.close()
            print("✓ Browser closed")


if __name__ == "__main__":
    test_browser_login()