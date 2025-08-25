#!/usr/bin/env python
"""
Chrome browser automation test for login and dashboard verification
"""

import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

def test_chrome_login():
    """Test login flow in Chrome browser"""
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Remove headless to see the browser
    # chrome_options.add_argument("--headless")
    
    # Initialize Chrome driver
    print("\n" + "="*60)
    print("CHROME BROWSER TEST: Login and Dashboard Verification")
    print("="*60)
    
    try:
        print("\n1. Starting Chrome browser...")
        driver = webdriver.Chrome(options=chrome_options)
        wait = WebDriverWait(driver, 10)
        print("   ✓ Chrome browser started")
        
        # Navigate to login page
        print("\n2. Navigating to login page...")
        driver.get("http://localhost:8000/accounts/login/")
        time.sleep(2)
        print("   ✓ Login page loaded")
        
        # Take screenshot of login page
        driver.save_screenshot("login_page.png")
        print("   ✓ Screenshot saved: login_page.png")
        
        # Enter credentials
        print("\n3. Entering login credentials...")
        
        # Find and fill email field
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        email_field.clear()
        email_field.send_keys("tomuaaz+test1@gmail.com")
        print("   ✓ Email entered")
        
        # Find and fill password field
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys("Vf123456$")
        print("   ✓ Password entered")
        
        # Take screenshot before submitting
        driver.save_screenshot("login_filled.png")
        print("   ✓ Screenshot saved: login_filled.png")
        
        # Submit the form
        print("\n4. Submitting login form...")
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_button.click()
        
        # Wait for redirect to dashboard
        print("\n5. Waiting for dashboard to load...")
        time.sleep(3)  # Give it time to redirect
        
        # Check if we're on the dashboard
        current_url = driver.current_url
        print(f"   Current URL: {current_url}")
        
        if "/accounts/dashboard/" in current_url:
            print("   ✓ Successfully redirected to dashboard")
        else:
            print(f"   ⚠ Unexpected URL: {current_url}")
        
        # Wait for dashboard elements to load
        print("\n6. Verifying dashboard elements...")
        
        # Check for dashboard title or heading
        try:
            dashboard_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Dashboard')]"))
            )
            print("   ✓ Dashboard heading found")
        except TimeoutException:
            print("   ⚠ Dashboard heading not found")
        
        # Check for Projects nav item
        print("\n7. Looking for Projects nav item...")
        try:
            # Try multiple possible selectors for Projects link
            projects_selectors = [
                "//a[contains(text(), 'Projects')]",
                "//a[contains(@href, '/project')]",
                "//nav//a[contains(text(), 'Projects')]",
                "//*[@id='sidebar']//a[contains(text(), 'Projects')]",
                "//aside//a[contains(text(), 'Projects')]"
            ]
            
            projects_found = False
            for selector in projects_selectors:
                try:
                    projects_link = driver.find_element(By.XPATH, selector)
                    if projects_link:
                        projects_found = True
                        print(f"   ✓ Projects nav item found: {projects_link.text}")
                        # Highlight the element
                        driver.execute_script("arguments[0].style.border='3px solid red'", projects_link)
                        break
                except:
                    continue
            
            if not projects_found:
                print("   ⚠ Projects nav item not found with standard selectors")
                # List all links found
                all_links = driver.find_elements(By.TAG_NAME, "a")
                print(f"   Found {len(all_links)} links on page")
                for link in all_links:
                    text = link.text.strip()
                    if text and "project" in text.lower():
                        print(f"   - Link with 'project': {text}")
        
        except Exception as e:
            print(f"   ⚠ Error finding Projects nav: {e}")
        
        # Take final screenshot
        print("\n8. Taking final screenshot...")
        driver.save_screenshot("dashboard_loaded.png")
        print("   ✓ Screenshot saved: dashboard_loaded.png")
        
        # Get page source for debugging
        with open("dashboard_source.html", "w") as f:
            f.write(driver.page_source)
        print("   ✓ Page source saved: dashboard_source.html")
        
        # List all nav items found
        print("\n9. Listing all navigation items...")
        nav_items = driver.find_elements(By.CSS_SELECTOR, "nav a, aside a, .sidebar a, #sidebar a")
        if nav_items:
            print(f"   Found {len(nav_items)} navigation items:")
            for item in nav_items[:10]:  # Show first 10
                text = item.text.strip()
                href = item.get_attribute("href")
                if text:
                    print(f"   - {text}: {href}")
        
        print("\n" + "="*60)
        print("✅ CHROME TEST COMPLETED")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Keep browser open for 5 seconds to observe
        print("\n⏳ Keeping browser open for observation...")
        time.sleep(5)
        
        # Close the browser
        try:
            driver.quit()
            print("✓ Browser closed")
        except:
            pass


if __name__ == "__main__":
    # Check if Selenium is installed
    try:
        import selenium
        print(f"Selenium version: {selenium.__version__}")
    except ImportError:
        print("Installing Selenium...")
        os.system("pip install selenium")
        
    # Run the test
    test_chrome_login()