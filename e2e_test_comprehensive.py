#!/usr/bin/env python3

"""
Comprehensive E2E test cycles for Issues Tab functionality
This will run 5 complete test cycles to ensure professional quality
"""

import asyncio
from playwright.async_api import async_playwright
import time

async def run_comprehensive_e2e_test():
    test_results = []
    
    for cycle in range(1, 6):  # Cycles 1-5
        print(f"\n{'='*60}")
        print(f"🔄 RUNNING E2E TEST CYCLE {cycle} OF 5")
        print(f"{'='*60}")
        
        cycle_start = time.time()
        cycle_result = await run_single_test_cycle(cycle)
        cycle_duration = time.time() - cycle_start
        
        cycle_result['cycle'] = cycle
        cycle_result['duration'] = round(cycle_duration, 2)
        test_results.append(cycle_result)
        
        if cycle_result['success']:
            print(f"✅ CYCLE {cycle} PASSED ({cycle_duration:.2f}s)")
        else:
            print(f"❌ CYCLE {cycle} FAILED ({cycle_duration:.2f}s)")
            
        # Brief pause between cycles
        await asyncio.sleep(1)
    
    # Generate final report
    print(f"\n{'='*60}")
    print("📊 COMPREHENSIVE E2E TEST RESULTS")
    print(f"{'='*60}")
    
    passed = sum(1 for r in test_results if r['success'])
    failed = len(test_results) - passed
    
    print(f"Total Cycles: {len(test_results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/len(test_results)*100):.1f}%")
    
    print(f"\n📋 Detailed Results:")
    for result in test_results:
        status = "✅ PASS" if result['success'] else "❌ FAIL"
        print(f"  Cycle {result['cycle']}: {status} ({result['duration']}s) - {result.get('issues_found', 0)} issues")
    
    if passed == len(test_results):
        print(f"\n🎉 ALL CYCLES PASSED - PROFESSIONAL QUALITY ACHIEVED!")
        return True
    else:
        print(f"\n⚠️ Some cycles failed. Review and fix issues.")
        return False

async def run_single_test_cycle(cycle_num):
    """Run a single comprehensive test cycle"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)  # Headless for speed
        page = await browser.new_page()
        
        try:
            # Test steps for each cycle
            result = {
                'success': False,
                'login_success': False,
                'navigation_success': False,
                'tab_switching_success': False,
                'issues_loaded': False,
                'severity_stats_correct': False,
                'filtering_works': False,
                'resolution_expansion_works': False,
                'issues_found': 0,
                'error_messages': []
            }
            
            # Step 1: Login
            print(f"  🔐 Step 1: Logging in...")
            await page.goto('http://localhost:8000/', wait_until='networkidle')
            
            username_field = page.locator('input[name="username"]')
            if await username_field.count() > 0:
                await username_field.fill('tomuaaz@gmail.com')
                password_field = page.locator('input[name="password"]')
                await password_field.fill('Vf123456$')
                submit_btn = page.locator('button[type="submit"]')
                await submit_btn.click()
                await page.wait_for_timeout(3000)
                
                if 'dashboard' in page.url.lower():
                    result['login_success'] = True
                    print("    ✅ Login successful")
                else:
                    result['error_messages'].append("Login failed")
                    
            # Step 2: Navigate to audit
            if result['login_success']:
                print(f"  🔍 Step 2: Navigating to audit...")
                await page.goto('http://localhost:8000/site-audit/13/', wait_until='networkidle')
                
                # Check for successful navigation (wait for page to load)
                await page.wait_for_timeout(2000)
                title = await page.title()
                url = page.url
                
                # Check if we're on the audit page (either by title or URL)
                if 'badexample.com' in title or 'Site Audit Details' in title or '/site-audit/13/' in url:
                    result['navigation_success'] = True
                    print(f"    ✅ Navigation successful (Title: {title})")
                else:
                    result['error_messages'].append(f"Navigation failed - Title: {title}, URL: {url}")
            
            # Step 3: Test tab switching
            if result['navigation_success']:
                print(f"  📋 Step 3: Testing tab switching...")
                
                # Test Overview tab first
                overview_content = page.locator('#overview-tab')
                if await overview_content.is_visible():
                    print("    ✅ Overview tab visible by default")
                    
                    # Test switching to Issues tab
                    issues_tab = page.locator('button.tab').filter(has_text='Issues')
                    if await issues_tab.count() > 0:
                        await issues_tab.click()
                        await page.wait_for_timeout(1000)
                        
                        issues_content = page.locator('#issues-tab')
                        if await issues_content.is_visible():
                            result['tab_switching_success'] = True
                            print("    ✅ Issues tab switching works")
                        else:
                            result['error_messages'].append("Issues tab not visible after click")
                    else:
                        result['error_messages'].append("Issues tab button not found")
                else:
                    result['error_messages'].append("Overview tab not visible by default")
            
            # Step 4: Validate Issues content
            if result['tab_switching_success']:
                print(f"  📊 Step 4: Validating Issues content...")
                
                # Check severity stats
                severity_stats = page.locator('#issues-tab .stat-value')
                stat_count = await severity_stats.count()
                
                if stat_count >= 5:  # Should have 5 severity categories
                    # Verify we have the expected numbers from our test data
                    critical_count = await severity_stats.nth(0).inner_text()
                    high_count = await severity_stats.nth(1).inner_text()
                    
                    if critical_count == "4" and high_count == "10":
                        result['severity_stats_correct'] = True
                        print("    ✅ Severity stats are correct")
                    else:
                        result['error_messages'].append(f"Unexpected severity stats: Critical={critical_count}, High={high_count}")
                
                # Check issue cards
                issue_cards = page.locator('#issues-tab .issue-card')
                card_count = await issue_cards.count()
                result['issues_found'] = card_count
                
                if card_count >= 20:  # Should have many issues from our test data
                    result['issues_loaded'] = True
                    print(f"    ✅ Issues loaded ({card_count} issues)")
                else:
                    result['error_messages'].append(f"Too few issues loaded: {card_count}")
            
            # Step 5: Test filtering
            if result['issues_loaded']:
                print(f"  🔍 Step 5: Testing filtering...")
                
                # Test severity filter
                severity_filter = page.locator('#severity-filter')
                if await severity_filter.count() > 0:
                    await severity_filter.select_option('critical')
                    await page.wait_for_timeout(500)
                    
                    # Check if filtering worked (should show fewer cards)
                    visible_cards = page.locator('#issues-tab .issue-card:visible')
                    visible_count = await visible_cards.count()
                    
                    if visible_count < result['issues_found'] and visible_count >= 4:  # Should show 4 critical issues
                        result['filtering_works'] = True
                        print(f"    ✅ Filtering works ({visible_count} critical issues shown)")
                        
                        # Reset filter
                        await severity_filter.select_option('')
                        await page.wait_for_timeout(500)
                    else:
                        result['error_messages'].append(f"Filtering didn't work correctly: {visible_count} vs {result['issues_found']}")
            
            # Step 6: Test resolution expansion
            if result['filtering_works']:
                print(f"  🔧 Step 6: Testing resolution expansion...")
                
                # Click expand button on first issue
                first_card = page.locator('#issues-tab .issue-card').first
                expand_btn = first_card.locator('button.btn-ghost').last
                
                if await expand_btn.count() > 0:
                    await expand_btn.click()
                    await page.wait_for_timeout(500)
                    
                    # Check if resolution section appeared
                    resolution_section = first_card.locator('[id^="resolution-"]')
                    if await resolution_section.count() > 0 and await resolution_section.is_visible():
                        result['resolution_expansion_works'] = True
                        print("    ✅ Resolution expansion works")
                    else:
                        result['error_messages'].append("Resolution section not visible")
            
            # Determine overall success
            result['success'] = all([
                result['login_success'],
                result['navigation_success'], 
                result['tab_switching_success'],
                result['issues_loaded'],
                result['severity_stats_correct'],
                result['filtering_works'],
                result['resolution_expansion_works']
            ])
            
            # Take final screenshot for this cycle
            await page.screenshot(path=f'/tmp/e2e_cycle_{cycle_num}_final.png')
            
        except Exception as e:
            result['error_messages'].append(f"Exception: {str(e)}")
            
        finally:
            await browser.close()
            
        return result

if __name__ == "__main__":
    start_time = time.time()
    success = asyncio.run(run_comprehensive_e2e_test())
    total_time = time.time() - start_time
    
    print(f"\n⏱️ Total test duration: {total_time:.2f} seconds")
    
    if success:
        print("🎉 COMPREHENSIVE E2E TESTING COMPLETED SUCCESSFULLY!")
        print("🚀 Issues Tab is ready for production - Professional quality achieved!")
    else:
        print("⚠️ Some tests failed. Please review and fix issues before production.")