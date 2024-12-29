from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from threading import Thread
import time
import logging
import pyotp

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def selenium_login(username, password, totp_secret):
    """Function to perform automated OAuth2 login using Selenium"""
    driver = None
    try:
        logger.info("Starting selenium automation")
        
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # Initialize the Chrome WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome WebDriver initialized")
        
        # Navigate to getcode endpoint which redirects to OAuth2 authorization
        driver.get('http://127.0.0.1/getcode')
        logger.info("Navigated to /getcode endpoint")
        
        # Wait for login form
        form = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "login_form"))
        )
        logger.info("Login form found")
        
        # Find and fill username field
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "login_id"))
        )
        username_field.clear()
        username_field.send_keys(username)
        logger.info("Username entered")
        
        # Find and fill password field
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_field.clear()
        password_field.send_keys(password)
        logger.info("Password entered")
        
        # Find and click submit button
        submit_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[@type='submit']"))
        )
        submit_button.click()
        logger.info("Submit button clicked")
        
        # Try automatic TOTP first
        logger.info("Attempting automatic TOTP")
        totp = pyotp.TOTP(totp_secret)
        totp_code = totp.now()
        
        # Find and fill TOTP field
        totp_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
        )
        totp_field.clear()
        totp_field.send_keys(totp_code)
        logger.info("Automatic TOTP code entered")
        
        # Find and click TOTP submit button
        totp_submit = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[@type='submit']"))
        )
        totp_submit.click()
        logger.info("TOTP submitted")

        # Check for error message
        try:
            error_message = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Invalid TOTP')]"))
            )
            logger.warning("Automatic TOTP failed. Waiting for manual TOTP entry.")
            
            # Re-find the TOTP field for manual entry
            logger.info("Re-locating TOTP field for manual entry")
            totp_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
            )
            totp_field.clear()
            
            # Wait for manual entry and submission
            logger.info("Please enter TOTP code manually")
            WebDriverWait(driver, 120).until_not(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Invalid TOTP')]"))
            )
            logger.info("Manual TOTP entry completed")
        except TimeoutException:
            # No error message found, assume TOTP was accepted
            logger.info("TOTP accepted")

        # Wait for OAuth2 authorization to complete and redirect
        try:
            WebDriverWait(driver, 30).until(
                lambda driver: "see terminal for logs" in driver.page_source.lower()
            )
            logger.info("OAuth2 authorization completed successfully")
        except TimeoutException:
            logger.error("Timeout waiting for OAuth2 authorization to complete")
            raise
            
    except Exception as e:
        logger.error(f"Error during selenium automation: {str(e)}")
        raise
    finally:
        if driver:
            driver.close()
            driver.quit()
            logger.info("Chrome WebDriver closed")

def start_selenium_thread(username, password, totp_secret):
    """Function to start selenium automation in a separate thread"""
    selenium_thread = Thread(target=selenium_login, args=(username, password, totp_secret))
    selenium_thread.daemon = True  # Thread will be terminated when main thread exits
    selenium_thread.start()
    return selenium_thread
