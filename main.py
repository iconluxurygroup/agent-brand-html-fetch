import sys
import uuid
import boto3
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail,Personalization,To,Cc
from selenium import webdriver
import traceback

from selenium.common.exceptions import TimeoutException

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import requests
import re
import os
import datetime
import logging
import logging.handlers
import time
import csv
from bs4 import BeautifulSoup
from fastapi import FastAPI, BackgroundTasks
import uvicorn
# from dotenv import load_dotenv
#
# load_dotenv()
app = FastAPI()
class PageExpander:

    def __init__(self,job_id, brand_id,url):
        # Initially set all necessary variables
        self.result_url = None
        self.log_url = None
        self.product_count = 0
        self.brand_id = brand_id
        self.url = url
        self.code = str(uuid.uuid4())
        #Start Logging
        self.job_id=job_id
        self.brand_id = brand_id
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        current_directory = os.getcwd()
        self.output_dir = os.path.join(current_directory, 'Outputs', self.brand_id, time_stamp,self.code)
        os.makedirs(self.output_dir)
        self.setup_logging()

        #Set ChromeOptions for driver
        options = webdriver.ChromeOptions()
        options.add_argument("--auto-open-devtools-for-tabs")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_argument("--enable-javascript")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--headless=new")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=options)

        #Get and Load Data
        settings=self.fetch_settings()
        self.data = settings[brand_id] if settings else {}
        self.load_data()
        self.job_id=job_id

    def start(self):
        try:
            if self.method == "Click":
                self.expand_page_click()
            elif self.method == "Scroll":
                self.expand_page_scroll()
            elif self.method == "Hybrid":
                self.expand_page_hybrid()
            elif self.method == "Pages":
                self.expand_page_pages()
            else:
                send_email(f"Error occurred while starting\nID:{self.brand_id}\nMethod:{self.method}",subject=f"{self.brand_id} Error - Start Job")
                self.logger.critical(f"Error occurred while starting\nID:{self.brand_id}\nMethod:{self.method}")
        except:
            send_email(f"Error occurred while starting\nID:{self.brand_id}\nMethod:{self.method}",
                       subject=f"{self.brand_id} Error - Start Job")
            self.logger.critical(f"Error occurred while starting\nID:{self.brand_id}\nMethod:{self.method}")




    def load_data(self):
        try:
            self.brand_name=self.data.get("BRAND_NAME","")
            self.ELEMENT_LOCATOR = self.data.get("ELEMENT_LOCATOR","")
            self.POPUP_TEXT = self.data.get("POPUP_TEXT", [])
            self.POPUP_ID = self.data.get("POPUP_ID", [])
            self.POPUP_CLASS = self.data.get("POPUP_CLASS", [])
            self.POPUP_XPATH = self.data.get("POPUP_XPATH", [])
            self.BY_XPATH = self.data.get("BY_XPATH", False)
            self.method = self.data.get("METHOD", "NOT VALID")
            self.PRODUCTS_PER_HTML_TAG = self.data.get("PRODUCTS_PER_HTML_TAG", "")
            self.LOCATOR_TYPE = By.XPATH if self.BY_XPATH else By.CSS_SELECTOR
            self.IMAGES_LOAD = self.data.get("IMAGES_LOAD", False)
            self.POPUP_WAIT_TIME = int(self.data.get("POPUP_WAIT_TIME", 5))
            self.GENERAL_WAIT_TIME = int(self.data.get("GENERAL_WAIT_TIME", 5))
            self.MAX_RETRIES = int(self.data.get("MAX_RETRIES", 10))
            self.INITIAL_SCROLL_BACK_AMOUNT = int(self.data.get("INITIAL_SCROLL_BACK_AMOUNT", 300))
            self.SCROLL_BACK_CHANGE = int(self.data.get("SCROLL_BACK_CHANGE", 100))
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred while loading data:\nJSON CONVERSION FAILURE OR MISSING KEY\n{str(exception_f)}",subject=f"{self.brand_id} Error - Settings")
            self.logger.critical(f"Error occurred while loading data: {exception_f}")

    def fetch_settings(self):
        try:
            settings_url = os.getenv("SETTINGS_URL")
            self.logger.info(settings_url)
            response = requests.get(settings_url)
            json_response = response.json()
            response.raise_for_status()  # Raises an HTTPError for bad responses

            self.logger.info(f"This is the settings file\n{json_response}")

            self.logger.info(response.status_code)
            return json_response
        except Exception:
            exception_f = traceback.format_exc()
            self.logger.critical(f"Error occurred while fetching settings:\n{str(exception_f)}")
            send_email(f"Error occurred while loading data:\n{str(exception_f)}",subject=f"{self.brand_id} Error - Settings")
            return None

    def setup_logging(self):
        #Create the location of the log file
        path = self.url.split("//")[-1]
        path = re.sub(r'[<>:"\\|?*]', '_', path)
        path_parts = path.split("/")
        logging_dir = os.path.join(self.output_dir, *path_parts[:-1])
        os.makedirs(logging_dir, exist_ok=True)
        log_filename = path_parts[-1] + ".log" if path_parts[-1] else path_parts[-2] + ".log"
        self.logging_file_path = os.path.join(logging_dir, log_filename)

        # Initially get a unique logger using a UUID, brand ID, and job ID
        logger_name = f"Brand ID: {self.brand_id}, Job ID: {self.job_id}, UUID: {self.code}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.DEBUG)  # Set logger to DEBUG to capture all messages
        self.logger.propagate = False  # Prevent propagation to root logger

        # Set formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create handler for logs that go to the file on the debug level
        self.log_file_handler = logging.handlers.RotatingFileHandler(self.logging_file_path)
        self.log_file_handler.setFormatter(formatter)
        self.log_file_handler.setLevel(logging.DEBUG)

        # Create handler for logs that go to the console on the info level
        self.log_console_handler = logging.StreamHandler(sys.stdout)
        self.log_console_handler.setFormatter(formatter)
        self.log_console_handler.setLevel(logging.INFO)

        self.logger.addHandler(self.log_file_handler)
        self.logger.addHandler(self.log_console_handler)

        # Initial test that the logger is instantiated and working properly
        self.logger.debug("This is a debug message (should appear in file only)")
        self.logger.info("This is an info message (should appear in both file and console)")
        self.logger.warning("This is a warning message (should appear in both file and console)")
        self.logger.error("This is an error message (should appear in both file and console)")
        self.logger.critical("This is a critical message (should appear in both file and console)")

    def close_popup(self):
        if not self.POPUP_TEXT and not self.POPUP_ID and not self.POPUP_CLASS and not self.POPUP_XPATH:
            return
        try:
            popup_closed = False
            webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            webdriver.ActionChains(self.driver).move_by_offset(1, 1).click().perform()
            self.logger.info(f"Tried to close popup using simulated escape key and click in top left corner")

            for popup_class,popup_text,popup_xpath,popup_id in zip(self.POPUP_CLASS,self.POPUP_TEXT,self.POPUP_XPATH,self.POPUP_CLASS):
                retries = 0
                while not popup_closed and retries < self.MAX_RETRIES:
                    if popup_text:
                        try:
                            self.logger.info(f"{self.brand_name}: Trying to close popup with text: {popup_text}")
                            close_button = WebDriverWait(self.driver, self.POPUP_WAIT_TIME).until(
                                EC.element_to_be_clickable((By.XPATH, f'//button[contains(text(), "{popup_text}")]'))
                            )
                            self.logger.info(close_button)
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", close_button)
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for scrolling to complete

                            # Click the close button
                            close_button.click()
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for the popup to close
                            popup_closed = True
                            self.logger.info(f"{self.brand_name}: Popup closed successfully")
                            # return popup_closed
                            continue

                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"{self.brand_name}: Popup not found or not clickable: {exception_f}")
                            retries += 1
                            self.logger.info(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait a bit before retrying

                    if self.POPUP_ID:
                        try:
                            self.logger.info(f"{self.brand_name}: Trying to close popup with ID: {popup_id}")
                            close_button = WebDriverWait(self.driver, self.POPUP_WAIT_TIME).until(
                                EC.element_to_be_clickable((By.ID, popup_id))
                            )
                            self.logger.info(close_button)
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", close_button)
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for scrolling to complete

                            # Click the close button
                            close_button.click()
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for the popup to close
                            popup_closed = True
                            self.logger.info(f"{self.brand_name}: Popup closed successfully")
                            # return popup_closed
                            continue

                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"{self.brand_name}: Popup not found or not clickable: {exception_f}")
                            retries += 1
                            self.logger.info(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait a bit before retrying

                    if self.POPUP_CLASS:
                        try:

                            self.logger.info(f"{self.brand_name}: Trying to close popup with class: {popup_class}")
                            close_button = WebDriverWait(self.driver, self.POPUP_WAIT_TIME).until(
                                EC.element_to_be_clickable((By.CLASS_NAME, popup_class))
                            )
                            self.logger.info(close_button)
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", close_button)
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for scrolling to complete

                            # Click the close button
                            close_button.click()
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for the popup to close
                            popup_closed = True
                            self.logger.info(f"{self.brand_name}: Popup closed successfully")
                            # return popup_closed
                            continue

                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"{self.brand_name}: Popup not found or not clickable: {exception_f}")
                            retries += 1
                            self.logger.info(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait a bit before retrying

                    if self.POPUP_XPATH:
                        try:

                            # Handle specific popup structure
                            self.logger.info(f"{self.brand_name}: Trying to close popup with XPATH: {popup_xpath}")
                            close_button = WebDriverWait(self.driver, self.POPUP_WAIT_TIME).until(
                                EC.element_to_be_clickable((By.XPATH, popup_xpath))
                            )
                            self.logger.info(close_button)
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", close_button)
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for scrolling to complete

                            # Click the close button
                            close_button.click()
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait for the popup to close
                            popup_closed = True
                            self.logger.info(f"{self.brand_name}: Popup closed successfully")
                            # return popup_closed
                            continue
                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"{self.brand_name}: Popup not found or not clickable: {exception_f}")
                            retries += 1
                            self.logger.info(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
                            time.sleep(self.POPUP_WAIT_TIME)  # Wait a bit before retrying
                            # Scroll the button into view

                webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                webdriver.ActionChains(self.driver).move_by_offset(1, 1).click().perform()
                self.logger.info(f"Tried to close popup using simulated escape key and click in top left corner")
                if not popup_closed:
                    self.logger.info(f"Failed to close the popup after several retries. popup_class: {popup_class}, popup_text: {popup_text}, popup_xpath: {popup_xpath}, popup_id:{popup_id}")

            if not popup_closed:
                self.logger.error(f"Error occurred while Settings have wrong values:\nPOPUP_CLASS: {self.POPUP_CLASS}, POPUP_TEXT: {self.POPUP_TEXT}, POPUP_XPATH: {self.POPUP_XPATH}, POPUP_ID:{self.POPUP_ID}")
                send_email(f"Error occurred while Settings have wrong values:\nPOPUP_CLASS: {self.POPUP_CLASS}, POPUP_TEXT: {self.POPUP_TEXT}, POPUP_XPATH: {self.POPUP_XPATH}, POPUP_ID:{self.POPUP_ID}",subject=f"{self.brand_name} Error - POPUP")

        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred while Settings has wrong structure:\n{str(exception_f)}",subject=f"{self.brand_name} Error - POPUP")
            self.logger.critical(f"Error occurred while Settings has wrong structure:\n{str(exception_f)}")


    def expand_page_pages(self):
        page_sources=[]
        self.logger.info(f"The pages method is being used for:{self.brand_id}\n{self.brand_name}")
        try:
            self.driver.get(self.url)
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Pages Method")
            self.logger.critical(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}")

        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))  # Wait for the page to load
        #Necessary Variables
        retries=0
        page_number=1
        check_button_clicked = False
        while retries<self.MAX_RETRIES:
            self.logger.info(f"Pop Up Settings Values for: {self.brand_id}\n{self.brand_name}\n{self.POPUP_TEXT}\n{self.POPUP_ID}\n{self.POPUP_CLASS}\n{self.POPUP_XPATH}")
            self.close_popup()
            page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
            page_sources.append(page_source)
            try:
                # Scroll to the bottom in order to allow items to load
                load_more_button = None
                next_url=None
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                if type(self.ELEMENT_LOCATOR) == list:
                    for locator in self.ELEMENT_LOCATOR:
                        try:
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.element_to_be_clickable((self.LOCATOR_TYPE, locator))
                            )
                            next_url = load_more_button.get_attribute('href')
                            if next_url:
                                try:
                                    self.driver.get(next_url)
                                except Exception:
                                    exception_f = traceback.format_exc()
                                    send_email(f"Error occurred when sending the get request for:{self.brand_id}\n {next_url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Pages Method")

                                    self.logger.critical(f"Error occurred when sending the get request for:{self.brand_id}\n{next_url}\n{exception_f}")
                            else:
                                raise TypeError
                            break
                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"Load More button not found for:{self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{locator}\n{exception_f}")
                            continue
                        except TypeError:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"Load More button does not contain an href for:{self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{locator}\n{exception_f}")
                            continue
                else:
                    try:
                        load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                            EC.element_to_be_clickable((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                        )
                        next_url = load_more_button.get_attribute('href')
                        if next_url:
                            try:
                                self.driver.get(next_url)
                            except Exception:
                                exception_f = traceback.format_exc()
                                send_email(f"Error occurred when sending the get request for: {next_url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Pages Method")

                                self.logger.critical(f"Error occurred when sending the get request for: {self.brand_id}\n{next_url}\n{exception_f}")
                        else:
                            raise TypeError
                        break
                    except TimeoutException:
                        exception_f = traceback.format_exc()
                        self.logger.info(f"Load More button not found for:{self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{self.ELEMENT_LOCATOR}\n{exception_f}")
                    except TypeError:
                        exception_f = traceback.format_exc()
                        self.logger.info(f"Load More button does not contain an href for:{self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{self.ELEMENT_LOCATOR}\n{exception_f}")
                if not load_more_button:
                    raise Exception("NO_LOAD_BUTTON_EXCEPT")
                # Wait for the expand button to be present and clickable
                if not next_url and load_more_button:
                    time.sleep(self.GENERAL_WAIT_TIME)
                    # Scroll the button into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                    time.sleep(self.GENERAL_WAIT_TIME)  # Wait for scrolling to complete
                    # Click the expand button using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", load_more_button)
                    self.logger.info(f"Managed to load by clicking on:{self.brand_name}\n{load_more_button}")




                # Wait a bit for the page to load more content
                time.sleep(self.GENERAL_WAIT_TIME)
                retries=0
                page_number+=1
                check_button_clicked=True
                self.logger.info(f"{self.brand_name} Retries have been reset to 0")
                self.logger.info(f"Button Click Check set to True: {check_button_clicked}")
            except Exception as e:
                self.logger.info(f"{self.brand_name}: Error occurred:\n{e}")
                time.sleep(self.GENERAL_WAIT_TIME)
                retries+=1
                self.logger.info(f"Load More button not found for:{self.brand_id}\n{self.brand_name}\nAttempt {retries}/{self.MAX_RETRIES}")

        all_html_string=self.write_html_to_file(page_sources)
        html_filepath = self.save_html_file(self.url, all_html_string, self.output_dir)
        self.result_url=self.save_html_s3(html_filepath)
        self.log_url=self.upload_file_to_space(self.logging_file_path,self.logging_file_path)
        self.product_count=self.count_substring_occurrences(all_html_string,self.PRODUCTS_PER_HTML_TAG)
        if not check_button_clicked:
            self.logger.error(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}")
            send_email(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}",subject=f"{self.brand_name} Error - Page Pages Method")

        self.update_complete()
        self.driver.close()
        return page_sources

    def expand_page_click(self):
        self.logger.info(f"The click method is being used for:{self.brand_id}\n{self.brand_name}")
        try:
            self.driver.get(self.url)
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Click Method")

            self.logger.critical(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}")


        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))  # Wait for the page to load
        # for text, id_, class_, xpath in zip(self.POPUP_TEXT, self.POPUP_ID, self.POPUP_CLASS, self.POPUP_XPATH):
        self.logger.info(f"Pop Up Settings Values for: {self.brand_id}\n{self.brand_name}\n{self.POPUP_TEXT}\n{self.POPUP_ID}\n{self.POPUP_CLASS}\n{self.POPUP_XPATH}")
        self.close_popup()
        self.logger.info(f"This is the currently used element locator {self.ELEMENT_LOCATOR}")
        retries = 0
        check_button_clicked=False
        while retries<self.MAX_RETRIES:
            try:
                load_more_button = None
                # If there is no button to click stop
                if isinstance(self.ELEMENT_LOCATOR,list):
                    for locator in self.ELEMENT_LOCATOR:
                        try:
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.element_to_be_clickable((self.LOCATOR_TYPE, locator))
                            )
                            break
                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"Load More button not found for: {self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{locator}\n{exception_f}")
                            continue
                else:
                    try:
                        load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                            EC.element_to_be_clickable((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                        )
                    except TimeoutException:
                        exception_f = traceback.format_exc()
                        self.logger.info(f"Load More button not found for: {self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{self.ELEMENT_LOCATOR}\n{exception_f}")
                if not load_more_button:
                    raise Exception("NO_LOAD_BUTTON_EXCEPT")
                check_button_clicked=True
                self.logger.info(f"{self.brand_name} managed to load using:\n {load_more_button}")
                # Wait for the expand button to be present and clickable
                time.sleep(self.GENERAL_WAIT_TIME)
                # Scroll the button into view
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)  # Wait for scrolling to complete
                # Click the expand button using JavaScript to avoid interception
                self.driver.execute_script("arguments[0].click();", load_more_button)
                # Scroll through entire page so images load
                if self.IMAGES_LOAD:
                    current_height = self.driver.execute_script("return window.pageYOffset + window.innerHeight")
                    while current_height > 100:
                        self.driver.execute_script("window.scrollBy(0, -arguments[0]);", self.INITIAL_SCROLL_BACK_AMOUNT)
                        current_height = self.driver.execute_script("return window.pageYOffset + window.innerHeight")
                        time.sleep(0.25)
                        self.logger.info(f"This is the current scroll height {current_height}\n{self.brand_id}\n{self.brand_name}")
                    self.logger.info("Scrolled back up to the top slowly, images should now be loaded")
                # Wait a bit for the page to load more content
                time.sleep(self.GENERAL_WAIT_TIME)
                self.logger.info(f"{self.brand_name} Retries have been reset to 0")
                retries = 0

            except Exception as e:
                self.logger.info(f"{self.brand_name}: Error occurred:\n{e}")
                time.sleep(self.GENERAL_WAIT_TIME)
                retries += 1
                self.logger.info(f"Load More button not found for: {self.brand_id}\n{self.brand_name}\nAttempt {retries}/{self.MAX_RETRIES}")

        if not check_button_clicked:
            self.logger.error(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}")
            send_email(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}",subject=f"{self.brand_name} Error - Page Click Method")

        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        self.html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url = self.save_html_s3(self.html_filepath)
        self.log_url=self.upload_file_to_space(self.logging_file_path,self.logging_file_path)
        self.product_count = self.count_substring_occurrences(page_source, self.PRODUCTS_PER_HTML_TAG)
        
        self.update_complete()
        self.driver.close()


    def expand_page_hybrid(self):
        self.logger.info(f"{self.brand_name} The hybrid method is being used")
        try:
            self.driver.get(self.url)
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred when sending the get request for: {self.brand_id}\n {self.url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Hybrid Method")

            self.logger.critical(f"Error occurred when sending the get request for: {self.brand_id}\n {self.url}\n{exception_f}")
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Handle popups
        self.logger.info(f"Pop Up Settings Values for: {self.brand_id}\n {self.brand_name}\n{self.POPUP_TEXT}\n{self.POPUP_ID}\n{self.POPUP_CLASS}\n{self.POPUP_XPATH}")
        self.close_popup()


        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_changes_count = 0
        scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT
        check_button_clicked=False
        while no_changes_count < self.MAX_RETRIES:

            # Try to click the "load more" button if it exists
            try:
                load_more_button=None
                if type(self.ELEMENT_LOCATOR) == list:
                    for locator in self.ELEMENT_LOCATOR:
                        try:
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.element_to_be_clickable((self.LOCATOR_TYPE, locator))
                            )
                            break
                        except TimeoutException:
                            exception_f = traceback.format_exc()
                            self.logger.info(f"Load More button not found for: {self.brand_id}\n {self.brand_name}\n{self.LOCATOR_TYPE}\n{locator}\n{exception_f}")
                            continue
                else:
                    try:
                        load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                            EC.element_to_be_clickable((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                        )
                    except TimeoutException:
                        exception_f = traceback.format_exc()
                        self.logger.info(f"Load More button not found for: {self.brand_id}\n{self.brand_name}\n{self.LOCATOR_TYPE}\n{locator}\n{exception_f}")
                if not load_more_button:
                    raise Exception("NO_LOAD_BUTTON_EXCEPT")
                self.logger.info(f"{self.brand_name} managed to load using: {load_more_button}")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)
                self.driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)  # Wait for new content to load
                self.logger.info(f"{self.brand_name}: Clicked 'load more' button")
                no_changes_count = 0  # Reset no changes count
                check_button_clicked=True
            except Exception as e:
                self.logger.info(f"{self.brand_name}: No 'load more' button found or not clickable: {e}")

                # If button not found, scroll to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(self.GENERAL_WAIT_TIME)
                self.driver.execute_script("window.scrollBy(0, -arguments[0]);", scroll_back_amount)
                time.sleep(self.GENERAL_WAIT_TIME)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                self.logger.info(f"The current scroll height is {new_height} and the last height was {last_height} for: {self.brand_id}\n{self.brand_name}")
                if new_height == last_height:
                    no_changes_count += 1
                    scroll_back_amount += self.SCROLL_BACK_CHANGE
                    self.logger.exception(f"{self.brand_name}: No change in height. Attempt {no_changes_count}/{self.MAX_RETRIES}")
                    if no_changes_count == self.MAX_RETRIES:
                        self.logger.exception(f"{self.brand_name} Reached the bottom of the page or no more content loading")
                else:
                    scroll_back_amount=self.INITIAL_SCROLL_BACK_AMOUNT
                    no_changes_count = 0  # Reset count if height changed
                    check_button_clicked=True
                    self.logger.info(f"{self.brand_name} Successfully scrolled to bottom loading new items.")

                # Scroll through entire page so images load
                if self.IMAGES_LOAD:
                    current_height = self.driver.execute_script("return document.body.scrollHeight")
                    while current_height > last_height-1000:
                        self.driver.execute_script("window.scrollBy(0, -arguments[0]);", self.INITIAL_SCROLL_BACK_AMOUNT)
                        current_height = self.driver.execute_script("return window.pageYOffset + window.innerHeight")
                        time.sleep(0.25)
                        self.logger.info(f"This is the current scroll height {current_height}")
                    self.logger.info("Scrolled back up to the top slowly, images should now be loaded")
                last_height = new_height



        if not check_button_clicked:
            self.logger.error(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}")
            send_email(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}",subject=f"{self.brand_name} Error - Page Hybrid Method")
        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        self.html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url = self.save_html_s3(self.html_filepath)
        self.log_url=self.upload_file_to_space(self.logging_file_path,self.logging_file_path)
        self.product_count = self.count_substring_occurrences(page_source, self.PRODUCTS_PER_HTML_TAG)
        
        self.update_complete()
        self.driver.close()

    def expand_page_scroll(self):
        self.logger.info(f"{self.brand_name} The scroll method is being used")
        try:
            self.driver.get(self.url)
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}",subject=f"{self.brand_name} Error - Page Hybrid Method")

            self.logger.critical(f"Error occurred when sending the get request for: {self.brand_id}\n{self.url}\n{exception_f}")
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        self.logger.info(f"Pop Up Settings Values for: {self.brand_id}\n{self.brand_name}\n{self.POPUP_TEXT}\n{self.POPUP_ID}\n{self.POPUP_CLASS}\n{self.POPUP_XPATH}")
        self.close_popup()


        last_height = self.driver.execute_script("return document.body.scrollHeight")
        retry_count = 0
        scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT
        check_button_clicked=False
        while retry_count < self.MAX_RETRIES:
            # Scroll to the bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.GENERAL_WAIT_TIME)

            # Scroll back up by the set amount
            self.driver.execute_script("window.scrollBy(0, -arguments[0]);", scroll_back_amount)
            time.sleep(self.GENERAL_WAIT_TIME)

            # Check if the page height has changed
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            self.logger.info(f"The current scroll height is {new_height} and the last height was {last_height} for: {self.brand_id}\n{self.brand_name}")
            if new_height == last_height:
                retry_count += 1
                scroll_back_amount += self.SCROLL_BACK_CHANGE  # Increase scroll back amount to ensure it's not missing content
                self.logger.info(f"{self.brand_name}: No change in height. Attempt {retry_count}/{self.MAX_RETRIES}")
                if retry_count >= self.MAX_RETRIES:
                    break
            else:
                scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT
                check_button_clicked=True
                retry_count = 0  # Reset retry count if new content is loaded
                self.logger.info(f"{self.brand_name}: Successfully Scrolled")

            # Scroll through entire page so images load
            if self.IMAGES_LOAD:
                current_height = self.driver.execute_script("return window.pageYOffset + window.innerHeight")
                while current_height > last_height - 1000:
                    self.driver.execute_script("window.scrollBy(0, -arguments[0]);", self.INITIAL_SCROLL_BACK_AMOUNT)
                    current_height = self.driver.execute_script("return window.pageYOffset + window.innerHeight")
                    time.sleep(0.25)
                    self.logger.info(f"This is the current scroll height {current_height}")
                self.logger.info("Scrolled back up to the top slowly, images should now be loaded")
            last_height = new_height

            # Scroll to the bottom again just in case
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.GENERAL_WAIT_TIME)
        if not check_button_clicked:
            self.logger.error(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}")
            send_email(f"Error occurred while Settings have wrong values for: {self.brand_id}\n{self.brand_name}\nELEMENT_LOCATOR: {self.ELEMENT_LOCATOR}\n{self.LOCATOR_TYPE}",subject=f"{self.brand_name} Error - Page Scroll Method")
        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        self.html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url=self.save_html_s3(self.html_filepath)
        self.log_url=self.upload_file_to_space(self.logging_file_path,self.logging_file_path)
        self.product_count=self.count_substring_occurrences(page_source,self.PRODUCTS_PER_HTML_TAG)
        
        self.update_complete()
        self.driver.close()

    def write_html_to_file(self,html_list, delimiter='*********************************HTML #{page}*********************************'):
        result = []
        self.logger.info(f"Writing {len(html_list)} HTML strings to {self.output_dir}")
        for index, html in enumerate(html_list, start=1):
            if index > 1:
                result.append(delimiter.format(page=index - 1))
            result.append(html)

        # Add the final delimiter after the last HTML
        result.append(delimiter.format(page=len(html_list)))

        # Join all parts with newlines
        combined_html = '\n'.join(result)

        # Write to file
        try:
            with open(self.output_dir, encoding='utf-8') as file:
                file.write(combined_html)
            self.logger.info(f"Successfully wrote {len(html_list)} HTML strings to {self.output_dir}")
        except IOError:
            exception_f = traceback.format_exc()
            send_email(f"Error occured when trying to write the file of combined HTML's{exception_f}",subject=f"{self.brand_name} Error - Write File Pages Method")

            self.logger.critical(f"Error occured when trying to write the file of combined HTML's{exception_f}")
        return combined_html

    def save_html_file(self, url, html_content, base_directory):
        # Extract the path from the URL
        self.logger.info(f"Saving HTML file for {url}")
        path = url.split("//")[-1]  # Remove protocol and get the path
        path = re.sub(r'[<>:"\\|?*]', '_', path)
        path_parts = path.split("/")
        # Construct the full directory path
        full_dir_path = os.path.join(base_directory, *path_parts[:-1])

        # Create the directory if it doesn't exist
        os.makedirs(full_dir_path, exist_ok=True)

        # Construct the file path
        filename = path_parts[-1] + ".html" if path_parts[-1] else path_parts[-2] + ".html"
        filepath = os.path.join(full_dir_path, filename)

        # Write the HTML content to the file
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(html_content)

        self.logger.info(f"HTML file saved successfully to {filepath}")
        return filepath

    def save_html_s3(self, html_filepath):
        self.logger.info(f"Creating S3 filepath for {self.brand_name}")
        path_parts=html_filepath.split("/")[-3:]
        if len(path_parts)>=2:
            path_parts[-2] =self.code
        elif isinstance(path_parts,list):
            path_parts[-1] = self.code
        else:
            path_parts=[self.code]
        path="_".join(path_parts) + ".html"
        return self.upload_file_to_space(html_filepath,path)

    def get_s3_client(self):
        self.logger.info("Creating spaces client")
        try:
            session = boto3.session.Session()
            client = boto3.client(service_name='s3',
                                    region_name=os.getenv('REGION'),
                                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
            # client = boto3.client(service_name='s3',
            #                       region_name=REGION,
            #                       aws_access_key_id=AWS_ACCESS_KEY_ID,
            #                       aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
            self.logger.info("S3 client created successfully")
            return client
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred while creating S3 client:\n{str(exception_f)}",subject=f"{self.brand_name} Error - S3 Client")
            self.logger.info(f"Error occurred while creating S3 client:\n{str(exception_f)}")

    def upload_file_to_space(self,file_src, save_as,is_public=True):
        self.logger.info(f"Uploading file to space: {save_as}\n From: {file_src}")
        spaces_client = self.get_s3_client()
        space_name = 'iconluxurygroup-s3'  # Your space name
        try:
            spaces_client.upload_file(str(file_src), space_name, str(save_as), ExtraArgs={'ACL': 'public-read'})
        except Exception:
            exception_f = traceback.format_exc()
            send_email(f"Error occurred while uploading file to space:\n{str(exception_f)}",subject=f"{self.brand_name} Error - Upload File")
            self.logger.info(f"Error occurred while uploading file to space:\n{str(exception_f)}")


        self.logger.info(f"File uploaded successfully to {space_name}/{save_as}")
        # Generate and return the public URL if the file is public

            # upload_url = f"{str(os.getenv('SPACES_ENDPOINT'))}/{space_name}/{save_as}"
        if is_public:
            # upload_url = f"{str(os.getenv('SPACES_ENDPOINT'))}/{space_name}/{save_as}"
            upload_url = f"https://iconluxurygroup-s3.s3.us-east-2.amazonaws.com/{save_as}"
            print(f"Public URL: {upload_url}")
            return upload_url

    def count_substring_occurrences(self, main_string, substring):
        if not substring:
            return 0

        count = 0
        start = 0
        while True:
            start = main_string.find(substring, start)
            if start == -1:  # substring not found
                return count
            count += 1
            start += 1  # move past the last found substring

    def update_complete(self):
        self.logger.info(f"Updating job as complete for {self.brand_name}: \n{self.result_url}\n{self.log_url}\n{self.product_count}")
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
        }

        params = {
            'job_id': f"{self.job_id}",
            'resultUrl': f"{self.result_url}",
            'logUrl': f"{self.log_url}",
            'count' : self.product_count
        }
        self.logger.info(f"Params: {params}")
        self.logger.info(f"Headers: {headers}")
        self.logger.info(f"Deleting Logging file:{self.logging_file_path}\nOutput directory: {self.output_dir}\nFor {self.job_id}")
        os.remove(self.html_filepath)
        os.remove(self.logging_file_path)
        os.rmdir(self.output_dir)
        self.logger.info(f"Sending output to {send_out_endpoint} with params {params}")
        requests.post(f"{send_out_endpoint}/job_complete", params=params, headers=headers)
        


def read_file_to_list(file_path):
    with open(file_path, 'r') as file:
        lines = file.read().splitlines()
    return lines

def count_products(html_content, tag):
    if not tag:
        return 0
    soup = BeautifulSoup(html_content, 'html.parser')
    products = soup.find_all(class_=tag)
    print(f"Number of products found: {len(products)}")
    return len(products)

def save_to_csv(brand_name, url_product_counts):
    brand_name=brand_name.lower()
    filename = os.path.join(os.getcwd(),"Product_Counts", f"{brand_name}_product_counts.csv")
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['URL', 'Product Count'])
        for url, count in url_product_counts:
            writer.writerow([url, count])


def read_file_to_list(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file]



def process_remote_run(job_id,brand_id, scan_url):
    expander = PageExpander(job_id, brand_id,scan_url)
    result = expander.start()


def send_email(message_text, to_emails='samuel@shlyam.com', subject="Error - HTML Step"):

    message_with_breaks = message_text.replace("\n", "<br>")

    html_content = f"""
<html>
<body>
<div class="container">
    <!-- Use the modified message with <br> for line breaks -->
    <p>Message details:<br>{message_with_breaks}</p>
</div>
</body>
</html>
"""
    message = Mail(
        from_email='distrotool@iconluxurygroup.com',
        subject=subject,
        html_content=html_content
    )

    cc_recipient = 'notifications@popovtech.com'
    personalization = Personalization()
    personalization.add_cc(Cc(cc_recipient))
    personalization.add_to(To(to_emails))
    message.add_personalization(personalization)
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e)
@app.post("/run_html")
async def brand_batch_endpoint(job_id:str, brand_id: str, scan_url:str,send_out_endpoint_local:str, background_tasks: BackgroundTasks):
    global send_out_endpoint
    send_out_endpoint=send_out_endpoint_local
    background_tasks.add_task(process_remote_run,job_id,brand_id,scan_url)
    return {"message": "Notification sent in the background"}
@app.post("/")
async def health_check():
    return {"message": "Hello"}


if __name__ == "__main__":
    uvicorn.run("main:app", port=8080,host="0.0.0.0", log_level="info")