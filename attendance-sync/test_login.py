"""
Test Aeries login with environment variables
"""

import os
import sys
from playwright.sync_api import sync_playwright

AERIES_URL = "https://adn.fjuhsd.org/Aeries.net/Login.aspx"
USERNAME = os.getenv('AERIES_USER')
PASSWORD = os.getenv('AERIES_PASS')

print(f"\n{'='*60}")
print("Testing Aeries Login")
print(f"{'='*60}\n")
print(f"URL: {AERIES_URL}")
print(f"Username: {USERNAME}")
print(f"Password: {'*' * len(PASSWORD) if PASSWORD else 'NOT SET'}")
print()

if not USERNAME or not PASSWORD:
    print("✗ ERROR: Environment variables not found!")
    print("   Make sure AERIES_USER and AERIES_PASS are set")
    print("   Close and reopen Command Prompt after setting them")
    sys.exit(1)  # Fixed: use sys.exit instead of exit

print("🌐 Opening browser and attempting login...\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # You'll see the browser
    page = browser.new_page()
    
    try:
        # Go to login page
        print("   1. Navigating to Aeries...")
        page.goto(AERIES_URL, timeout=30000)
        page.wait_for_timeout(2000)
        
        # Fill credentials
        print("   2. Filling in username...")
        page.fill('input[name="portalAccountUsername"], input[type="text"]', USERNAME)
        page.wait_for_timeout(500)
        
        print("   3. Filling in password...")
        page.fill('input[name="portalAccountPassword"], input[type="password"]', PASSWORD)
        page.wait_for_timeout(500)
        
        # Click login
        print("   4. Clicking login button...")
        page.click('button[type="submit"], input[type="submit"]')
        
        # Wait to see result
        print("   5. Waiting for login to complete...")
        page.wait_for_timeout(5000)
        
        # Check if we're logged in (look for any sign we're past login page)
        current_url = page.url
        print(f"\n   Current URL: {current_url}")
        
        if "Login.aspx" not in current_url:
            print("\n✓✓✓ LOGIN SUCCESSFUL! ✓✓✓")
            print("Browser will stay open for 10 seconds so you can verify...")
        else:
            print("\n⚠ Still on login page - check credentials or selectors")
            print("Taking screenshot...")
            page.screenshot(path='login_test.png')
            print("Screenshot saved as login_test.png")
        
        # Keep browser open so you can see
        page.wait_for_timeout(10000)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        page.screenshot(path='login_error.png')
        print("Screenshot saved as login_error.png")
    
    finally:
        browser.close()

print("\nTest complete!")
