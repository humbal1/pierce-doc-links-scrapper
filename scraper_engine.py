"""
Headless Scraper Engine for Pierce County Documents
Runs Chrome in headless mode (no visible browser)
"""

import time
import os
import shutil
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from datetime import datetime

MAX_PAGES = 50  # Scrape all pages

def get_headless_driver():
    """Initialize headless Chrome driver with auto-binary detection"""
    options = Options()
    
    # 1. BASIC HEADLESS OPTIONS
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User agent to avoid detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 2. ATTEMPT TO FIND OR INSTALL CHROME BINARY
    # Check if we are on Render (Linux) or Local
    is_render = os.environ.get("RENDER") or os.path.exists("/opt/render")

    if is_render:
        print("🌍 Detected Render Environment")
        
        # Try to find standard chromium locations first
        possible_bins = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/opt/render/project/src/.chrome/chrome"  # Custom path if manually installed
        ]
        
        binary_location = None
        for bin_path in possible_bins:
            if os.path.exists(bin_path):
                binary_location = bin_path
                break
        
        if binary_location:
            print(f"✅ Found Chrome binary at: {binary_location}")
            options.binary_location = binary_location
        else:
            print("⚠️ No system Chrome found. Trusting webdriver_manager to handle it...")

    # 3. INSTALL DRIVER
    try:
        if is_render:
            # On Linux/Render, specify ChromeType.CHROMIUM to help match the binary
            service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        else:
            # Local Windows/Mac
            service = Service(ChromeDriverManager().install())
            
        driver = webdriver.Chrome(service=service, options=options)
        return driver
        
    except Exception as e:
        print(f"❌ CRITICAL DRIVER ERROR: {e}")
        # Fallback debug info
        import subprocess
        try:
            print("Debug: Searching for chrome...")
            print(subprocess.getoutput("which google-chrome"))
            print(subprocess.getoutput("which chromium"))
        except:
            pass
        raise e

def clear_input(element):
    """Clears date fields"""
    try:
        element.click()
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.DELETE)
        time.sleep(0.3)
    except:
        pass

def scrape_document_type(document_type, max_pages=50, progress_callback=None):
    """
    Scrape a single document type
    
    Args:
        document_type: Document type to scrape
        max_pages: Maximum number of pages to scrape
        progress_callback: Function to call with progress updates
    
    Returns:
        DataFrame with results
    """
    
    def log(message):
        """Log message and call progress callback"""
        print(message)
        if progress_callback:
            progress_callback(message)
    
    driver = None
    all_results = []
    
    try:
        driver = get_headless_driver()
        log(f"🚀 Starting scrape for: {document_type}")
        
        # Navigate to website
        driver.get("https://armsweb.co.pierce.wa.us/")
        log("   ✅ Loaded Pierce County website")
        
        # Accept disclaimer
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, "cph1_lnkAccept"))
            ).click()
            time.sleep(1)
            log("   ✅ Accepted disclaimer")
        except:
            log("   ℹ️ No disclaimer to accept")
        
        # Go to search page
        driver.get("https://armsweb.co.pierce.wa.us/RealEstate/SearchEntry.aspx")
        time.sleep(2)
        log("   ✅ Loaded search page")
        
        # Clear date filters
        try:
            date_from = driver.find_element(By.XPATH, 
                "//table[@id='cphNoMargin_f_ddcDateFiledFrom']//input")
            clear_input(date_from)
            
            date_to = driver.find_element(By.XPATH, 
                "//table[@id='cphNoMargin_f_ddcDateFiledTo']//input")
            clear_input(date_to)
            
            log("   ✅ Cleared date filters")
        except:
            log("   ⚠️ Could not clear dates")
        
        # Select document type
        log(f"   🔍 Selecting '{document_type}'...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "cphNoMargin_f_dclDocType"))
        )
        
        labels = driver.find_elements(By.XPATH, 
            "//table[@id='cphNoMargin_f_dclDocType']//label")
        
        found = False
        for label in labels:
            if label.text.strip() == document_type:
                chk_id = label.get_attribute("for")
                chk = driver.find_element(By.ID, chk_id)
                driver.execute_script("arguments[0].scrollIntoView(true);", chk)
                time.sleep(0.5)
                
                if not chk.is_selected():
                    driver.execute_script("arguments[0].click();", chk)
                
                found = True
                log(f"   ✅ Selected: {document_type}")
                break
        
        if not found:
            log(f"   ❌ Document type not found: {document_type}")
            return pd.DataFrame()
        
        # Submit search
        driver.find_element(By.ID, "cphNoMargin_SearchButtons2_btnSearch").click()
        time.sleep(5)
        log("   ✅ Search submitted")
        
        # Scrape all pages
        page = 1
        while page <= max_pages:
            log(f"   📄 Scraping page {page}...")
            
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "cphNoMargin_cphNoMargin_g_G1"))
                )
            except:
                log("   ⚠️ Results table not found")
                break
            
            time.sleep(3)
            
            # Parse page HTML
            page_source = driver.page_source
            rows = page_source.split('<tr data-ig')
            
            page_count = 0
            for row_html in rows:
                if 'lblTor' not in row_html:
                    continue
                
                page_count += 1
                
                # Extract instrument number
                inst = re.search(r'id="[^"]*Label1">\s*([^<]+)\s*</span>', row_html)
                inst = inst.group(1).strip() if inst else "Unknown"
                
                # Extract date
                date_match = re.search(r'>(\d{2}/\d{2}/\d{4})<', row_html)
                rec_date = date_match.group(1) if date_match else ""
                
                # Extract grantor
                grantor = re.search(r'id="[^"]*lblTor">([^<]+)</span>', row_html)
                grantor = grantor.group(1).strip() if grantor else ""
                
                # Extract grantee
                grantee = re.search(r'id="[^"]*lblTee">([^<]+)', row_html)
                grantee = grantee.group(1).strip() if grantee else ""
                
                # Find global ID for image link
                global_id_match = re.search(r'OPR(\d+)', row_html)
                has_image = 'paper.gif' in row_html
                
                direct_link = ""
                if has_image and global_id_match:
                    raw_id = global_id_match.group(1)
                    full_id = f"OPR{raw_id}"
                    direct_link = f"https://armsweb.co.pierce.wa.us/RealEstate/SearchResults.aspx?global_id={full_id}&type=img"
                
                all_results.append({
                    "Instrument": inst,
                    "Date Recorded": rec_date,
                    "Document Type": document_type,
                    "Grantor": grantor,
                    "Grantee": grantee,
                    "Image Link": direct_link
                })
            
            log(f"      → Extracted {page_count} records from page {page}")
            
            # Check if we should continue
            if page >= max_pages:
                log("   🛑 Reached page limit")
                break
            
            # Try to go to next page
            try:
                next_btn = driver.find_element(By.XPATH, 
                    "//input[contains(@src, 'nextsmall.gif')]")
                
                if "disabled" in next_btn.get_attribute("src"):
                    log("   🏁 No more pages")
                    break
                
                next_btn.click()
                time.sleep(5)
                page += 1
                
            except:
                log("   ℹ️ Next button not found")
                break
        
        log(f"✅ Scraping complete! Total records: {len(all_results)}")

        # Save session cookies for image proxy reuse
        try:
            import pickle
            cookies = driver.get_cookies()
            with open("session_cookies.pkl", "wb") as f:
                pickle.dump(cookies, f)
        except:
            pass
        
    except Exception as e:
        log(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if driver:
            driver.quit()
            log("   🔚 Browser closed")
    
    return pd.DataFrame(all_results)


def save_results(df, document_type, output_folder="results"):
    """Save results to CSV file"""
    
    if df.empty:
        return None
    
    # Create output folder if doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_doc_type = re.sub(r'[^\w\s-]', '', document_type).strip().replace(' ', '_')
    filename = f"{safe_doc_type}_{timestamp}.csv"
    filepath = os.path.join(output_folder, filename)
    
    # Save to CSV
    df.to_csv(filepath, index=False)
    print(f"💾 Saved results to: {filepath}")
    
    # Return only the filename (not full path) so the download URL works on any OS/server
    return filename


def run_scraper_for_document(document_type, progress_callback=None):
    """
    Main function to scrape a document type and save results
    
    Args:
        document_type: Document type to scrape
        progress_callback: Optional callback for progress updates
    
    Returns:
        dict with status and filepath
    """
    
    try:
        # Scrape the data
        df = scrape_document_type(document_type, MAX_PAGES, progress_callback)
        
        if df.empty:
            return {
                "status": "error",
                "message": "No data found",
                "filepath": None,
                "record_count": 0
            }
        
        # Save results
        filepath = save_results(df, document_type)
        
        return {
            "status": "success",
            "message": f"Successfully scraped {len(df)} records",
            "filepath": filepath,
            "record_count": len(df)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "filepath": None,
            "record_count": 0
        }


if __name__ == "__main__":
    # Test the scraper
    result = run_scraper_for_document("TRUSTEE SALE")
    print(f"\nResult: {result}")
