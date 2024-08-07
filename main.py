import uuid
import boto3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import requests
import re
import os
import datetime
import logging
import time
import csv
from bs4 import BeautifulSoup
from fastapi import FastAPI, BackgroundTasks
import uvicorn
# from dotenv import load_dotenv
from fastapi import FastAPI

# load_dotenv()
app = FastAPI()

class PageExpander:

    def __init__(self,job_id, brand_id,url):
        self.result_url = None
        self.log_url=None
        self.product_count=0
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument("--headless=new")
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument("--auto-open-devtools-for-tabs")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        options.add_argument("--start-maximized")
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        
        time_stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        current_directory=os.getcwd()
        self.output_dir = os.getcwd()
        self.driver = webdriver.Chrome(options=options)
        self.brand_id=brand_id
        self.url=url
        self.data=self.fetch_settings()[brand_id]
        self.load_data()
        self.output_dir = os.path.join(current_directory, 'Outputs', self.brand_name, time_stamp)
        self.setup_logging()
        self.job_id=job_id


    def start(self):
        if self.method == "Click":
            self.expand_page_click()
        elif self.method == "Scroll":
            self.expand_page_scroll()
        elif self.method == "Hybrid":
            self.expand_page_hybrid()
        elif self.method == "Pages":
            self.expand_page_pages()
    def load_data(self):
        self.brand_name=self.data.get("DIRECTORY","")
        self.ELEMENT_LOCATOR = self.data.get("ELEMENT_LOCATOR","")
        self.POPUP_TEXT = self.data.get("POPUP_TEXT", [])
        self.POPUP_ID = self.data.get("POPUP_ID", [])
        self.POPUP_CLASS = self.data.get("POPUP_CLASS", [])
        self.POPUP_XPATH = self.data.get("POPUP_XPATH", [])
        self.BY_XPATH = self.data.get("BY_XPATH", False)
        self.method = self.data.get("METHOD", "Click")
        self.PRODUCTS_PER_HTML_TAG = self.data.get("PRODUCTS_PER_HTML_TAG", "")
        self.LOCATOR_TYPE = self.BY_XPATH if self.BY_XPATH else By.CSS_SELECTOR

        self.POPUP_WAIT_TIME = int(self.data.get("POPUP_WAIT_TIME", 5))
        self.GENERAL_WAIT_TIME = int(self.data.get("GENERAL_WAIT_TIME", 5))
        self.MAX_RETRIES = int(self.data.get("MAX_RETRIES", 10))
        self.INITIAL_SCROLL_BACK_AMOUNT = int(self.data.get("INITIAL_SCROLL_BACK_AMOUNT", 300))
        self.SCROLL_BACK_CHANGE = int(self.data.get("SCROLL_BACK_CHANGE", 100))

    def fetch_settings(self):
        try:
            response = requests.get(os.getenv('SETTINGS_URL'))
            response.raise_for_status()  # Raises an HTTPError for bad responses
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching settings: {e}")
            return None
    def setup_logging(self):
        # Setup logging in correct file location
        path = self.url.split("//")[-1]
        path = re.sub(r'[<>:"\\|?*]', '_', path)
        path_parts = path.split("/")
        logging_dir = os.path.join(self.output_dir, *path_parts)
        os.makedirs(logging_dir, exist_ok=True)
        log_filename = path_parts[-1] + ".log" if path_parts[-1] else path_parts[-2] + ".log"
        self.logging_file_path = os.path.join(logging_dir, log_filename)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(self.logging_file_path),
                logging.StreamHandler()
            ])

        self.logger = logging.getLogger(__name__)
        self.logger.info("This is a log message from the gg script")
    def close_popup(self):
        if not self.POPUP_TEXT and not self.POPUP_ID and not self.POPUP_CLASS and not self.POPUP_XPATH:
            return
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
                        return popup_closed
                    except Exception as e:
                        self.logger.exception(f"{self.brand_name}: Popup not found or not clickable: {e}")
                        retries += 1
                        self.logger.exception(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
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
                        return popup_closed
                    except Exception as e:
                        self.logger.exception(f"{self.brand_name}: Popup not found or not clickable: {e}")
                        retries += 1
                        self.logger.exception(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
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
                        return popup_closed

                    except Exception as e:
                        self.logger.exception(f"{self.brand_name}: Popup not found or not clickable: {e}")
                        retries += 1
                        self.logger.exception(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
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
                        return popup_closed
                    except Exception as e:
                        self.logger.exception(f"{self.brand_name}: Popup not found or not clickable: {e}")
                        retries += 1
                        self.logger.exception(f"{self.brand_name}: Attempt {retries}/{self.MAX_RETRIES}")
                        time.sleep(self.POPUP_WAIT_TIME)  # Wait a bit before retrying
                        # Scroll the button into view

            webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            webdriver.ActionChains(self.driver).move_by_offset(1, 1).click().perform()
            self.logger.info(f"Tried to close popup using simulated escape key and click in top left corner")
            if not popup_closed:
                self.logger.exception(f"Failed to close the popup after several retries. popup_class: {popup_class}, popup_text: {popup_text}, popup_xpath: {popup_xpath}, popup_id:{popup_id}")


        if not popup_closed:
            self.logger.exception(f"Failed to close all popups after several retries. POPUP_CLASS: {self.POPUP_CLASS}, POPUP_TEXT: {self.POPUP_TEXT}, POPUP_XPATH: {self.POPUP_XPATH}, POPUP_ID:{self.POPUP_ID}")
            return False

    def expand_page_pages(self):
        page_sources=[]
        print("The pages method is being used")
        self.driver.get(self.url)
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))  # Wait for the page to load
        #Necessary Variables
        retries=0
        page_number=1

        while True:
            # Closing Popups
            for text, id_, class_, xpath in zip(self.POPUP_TEXT, self.POPUP_ID, self.POPUP_CLASS, self.POPUP_XPATH):
                self.logger.info(f"{self.brand_name} {text},{id_}, {class_}, {xpath}")
                self.close_popup()
            page_source = self.driver.page_source
            page_sources.append(page_source)
            try:
                # Scroll to the bottom in order to allow items to load
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                if type(self.ELEMENT_LOCATOR) == list:
                    for locator in self.ELEMENT_LOCATOR:
                        self.logger.info(locator)
                        try:
                            for text, id_, class_, xpath in zip(self.POPUP_TEXT, self.POPUP_ID, self.POPUP_CLASS, self.POPUP_XPATH):
                                self.logger.info(f"{self.brand_name} {text},{id_}, {class_}, {xpath}")
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.presence_of_element_located((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                            )
                            next_url = load_more_button.get_attribute('href')
                            self.driver.get(next_url)
                            self.logger.info(f"{self.brand_name} The next page has been opened for {self.brand_name}")
                            time.sleep(self.GENERAL_WAIT_TIME)  # Wait for the page to load
                        except Exception as e:
                            self.logger.exception(e)
                            break
                else:
                    try:
                        load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.presence_of_element_located((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                            )
                        next_url = load_more_button.get_attribute('href')
                        self.driver.get(next_url)
                        time.sleep(self.GENERAL_WAIT_TIME)  # Wait for the page to load
                    except Exception as e:
                        self.logger.exception(e)
                        break
                if not load_more_button:
                    raise Exception("No load more button found")
                # Wait for the expand button to be present and clickable
                if not next_url and load_more_button:
                    self.logger.info(f"{self.brand_name} managed to load using:\n {load_more_button}")
                    time.sleep(self.GENERAL_WAIT_TIME)
                    # Scroll the button into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                    time.sleep(self.GENERAL_WAIT_TIME)  # Wait for scrolling to complete
                    # Click the expand button using JavaScript to avoid interception
                    self.driver.execute_script("arguments[0].click();", load_more_button)



                # Wait a bit for the page to load more content
                time.sleep(self.GENERAL_WAIT_TIME)
                retries=0
                page_number+=1

            except Exception as e:
                    self.logger.exception(f"{self.brand_name}: Error occurred:\n{e}")
                    time.sleep(self.GENERAL_WAIT_TIME)
                    retries+=1
                    self.logger.exception(f"{self.brand_name} Attempt {retries}/{self.MAX_RETRIES}")
                    #If button not exist 10 times give up
                    if retries>=self.MAX_RETRIES:
                        break
        all_html_string=self.write_html_to_file(page_sources)
        self.result_url=self.save_html_s3(self.output_dir)
        self.log_url = self.save_html_s3(self.logging_file_path)
        self.product_count=self.count_substring_occurrences(all_html_string,self.PRODUCTS_PER_HTML_TAG)
        self.update_complete()
        self.driver.close()
        return page_sources

    def expand_page_click(self):
        self.logger.info(f"{self.brand_name} The click method is being used")
        self.driver.get(self.url)
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))  # Wait for the page to load
        for text, id_, class_, xpath in zip(self.POPUP_TEXT, self.POPUP_ID, self.POPUP_CLASS, self.POPUP_XPATH):
            self.logger.info(f"{self.brand_name} {text},{id_}, {class_}, {xpath}")
            self.close_popup()
        self.logger.info(f"This is the currently used element locator {self.ELEMENT_LOCATOR}")
        retries = 0
        while True:
            try:
                # If there is no button to click stop
                if type(self.ELEMENT_LOCATOR) == list:
                    for locator in self.ELEMENT_LOCATOR:
                        try:
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.element_to_be_clickable((self.LOCATOR_TYPE, locator))
                            )
                            break
                        except:
                            continue
                else:
                    load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                        EC.element_to_be_clickable((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                    )
                if not load_more_button:
                    raise Exception("No load more button found")
                self.logger.info(f"{self.brand_name} managed to load using:\n {load_more_button}")
                # Wait for the expand button to be present and clickable
                time.sleep(self.GENERAL_WAIT_TIME)
                # Scroll the button into view
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)  # Wait for scrolling to complete
                # Click the expand button using JavaScript to avoid interception
                self.driver.execute_script("arguments[0].click();", load_more_button)

                # Wait a bit for the page to load more content
                time.sleep(self.GENERAL_WAIT_TIME)
                self.logger.info(f"{self.brand_name} Retries have been reset to 0")
                retries = 0

            except Exception as e:
                self.logger.exception(f"{self.brand_name}: Error occurred:\n{e}")
                time.sleep(self.GENERAL_WAIT_TIME)
                retries += 1
                self.logger.exception(f"{self.brand_name} Attempt {retries}/{self.MAX_RETRIES}")
                # If button not exist 10 times give up
                if retries >= self.MAX_RETRIES:
                    break

        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url = self.save_html_s3(html_filepath)
        self.log_url = self.save_html_s3(self.logging_file_path)
        self.product_count = self.count_substring_occurrences(page_source, self.PRODUCTS_PER_HTML_TAG)
        self.update_complete()
        self.driver.close()
    def expand_page_hybrid(self):
        self.logger.info(f"{self.brand_name} The hybrid method is being used")
        self.driver.get(self.url)
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Handle popups
        for text, id_, class_, xpath in zip(self.POPUP_TEXT or [], self.POPUP_ID or [], self.POPUP_CLASS or [], self.POPUP_XPATH or []):
            self.logger.info(f"{self.brand_name} {text},{id_}, {class_}, {xpath}")
            self.close_popup()


        last_height = self.driver.execute_script("return document.body.scrollHeight")
        no_changes_count = 0
        scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT

        while True:

            # Try to click the "load more" button if it exists
            try:
                if type(self.ELEMENT_LOCATOR) == list:
                    for locator in self.ELEMENT_LOCATOR:
                        try:
                            load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                                EC.element_to_be_clickable((self.LOCATOR_TYPE, locator))
                            )
                            break
                        except:
                            continue
                else:
                    load_more_button = WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(
                        EC.element_to_be_clickable((self.LOCATOR_TYPE, self.ELEMENT_LOCATOR))
                    )
                if not load_more_button:
                    raise Exception("No load more button found")
                self.logger.info(f"{self.brand_name} managed to load using: {load_more_button}")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)
                self.driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(self.GENERAL_WAIT_TIME)  # Wait for new content to load
                self.logger.info(f"{self.brand_name}: Clicked 'load more' button")
                no_changes_count = 0  # Reset no changes count
            except Exception as e:
                self.logger.exception(f"{self.brand_name}: No 'load more' button found or not clickable: {e}")

                # If button not found, scroll to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(self.GENERAL_WAIT_TIME)
                self.driver.execute_script("window.scrollBy(0, -arguments[0]);", scroll_back_amount)
                time.sleep(self.GENERAL_WAIT_TIME)

                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    no_changes_count += 1
                    scroll_back_amount += self.SCROLL_BACK_CHANGE
                    self.logger.exception(f"{self.brand_name}: No change in height. Attempt {no_changes_count}/{self.MAX_RETRIES}")
                    if no_changes_count >= self.MAX_RETRIES:
                        self.logger.exception(f"{self.brand_name} Reached the bottom of the page or no more content loading")
                        break
                else:
                    scroll_back_amount=self.INITIAL_SCROLL_BACK_AMOUNT
                    no_changes_count = 0  # Reset count if height changed
                    self.logger.exception(f"{self.brand_name} Successfully scrolled to bottom loading new items.")

                last_height = new_height


        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url = self.save_html_s3(html_filepath)
        self.log_url = self.save_html_s3(self.logging_file_path)
        self.product_count = self.count_substring_occurrences(page_source, self.PRODUCTS_PER_HTML_TAG)
        self.update_complete()
        self.driver.close()

    def expand_page_scroll(self):
        self.logger.info(f"{self.brand_name} The scroll method is being used")
        self.driver.get(self.url)
        WebDriverWait(self.driver, self.GENERAL_WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        for text, id_, class_, xpath in zip(self.POPUP_TEXT, self.POPUP_ID, self.POPUP_CLASS, self.POPUP_XPATH):
            self.logger.info(f"{self.brand_name} {text},{id_}, {class_}, {xpath}")
            self.close_popup()


        last_height = self.driver.execute_script("return document.body.scrollHeight")
        retry_count = 0
        scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT
        while True:
            # Scroll to the bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.GENERAL_WAIT_TIME)

            # Scroll back up by the set amount
            self.driver.execute_script("window.scrollBy(0, -arguments[0]);", scroll_back_amount)
            time.sleep(self.GENERAL_WAIT_TIME)

            # Scroll to the bottom again
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.GENERAL_WAIT_TIME)

            # Check if the page height has changed
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                retry_count += 1
                scroll_back_amount += self.SCROLL_BACK_CHANGE  # Increase scroll back amount to ensure it's not missing content
                self.logger.info(f"{self.brand_name}: No change in height. Attempt {retry_count}/{self.MAX_RETRIES}")
                if retry_count >= self.MAX_RETRIES:
                    break
            else:
                scroll_back_amount = self.INITIAL_SCROLL_BACK_AMOUNT
                retry_count = 0  # Reset retry count if new content is loaded
                self.logger.info(f"{self.brand_name}: Successfully Scrolled")
            last_height = new_height

        page_source = self.driver.execute_script("return document.documentElement.outerHTML;")
        html_filepath=self.save_html_file(self.url, page_source, self.output_dir)
        self.result_url=self.save_html_s3(html_filepath)
        self.log_url=self.save_html_s3(self.logging_file_path)
        self.product_count=self.count_substring_occurrences(page_source,self.PRODUCTS_PER_HTML_TAG)
        self.update_complete()
        self.driver.close()

    def write_html_to_file(self,html_list, delimiter='*********************************HTML #{page}*********************************'):
        result = []
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
            with open(self.output_dir, 'w', encoding='utf-8') as file:
                file.write(combined_html)
            self.logger.info(f"Successfully wrote {len(html_list)} HTML strings to {self.output_dir}")
        except IOError as e:
            self.logger.debug(f"An error occurred while writing to the file: {e}")

        return combined_html
    def save_html_file(self, url, html_content, base_directory):
        # Extract the path from the URL
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

        print(f"Saved: {filepath}")
        return filepath
    def save_html_s3(self, html_filepath):
        path_parts=html_filepath.split("/")[-3:]
        path_parts[-2] = str(uuid.uuid4())
        path="_".join(path_parts)
        return self.upload_file_to_space(html_filepath,path)

    def get_s3_client(self):
        self.logger.info("Creating spaces client")
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

    def upload_file_to_space(self,file_src, save_as, is_public=True):
        spaces_client = self.get_s3_client()
        space_name = 'iconluxurygroup-s3'  # Your space name

        spaces_client.upload_file(file_src, space_name, save_as, ExtraArgs={'ACL': 'public-read'})
        print(f"File uploaded successfully to {space_name}/{save_as}")
        # Generate and return the public URL if the file is public
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

        requests.post(f"{os.getenv('MANAGER_ENDPOINT')}/job_complete", params=params, headers=headers)
        


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
    # expander = PageExpander.remote(job_id, brand_id,scan_url)
    # result = ray.get(expander.start.remote())
    expander = PageExpander(job_id, brand_id,scan_url)
    expander.start()

@app.post("/run_html")
async def brand_batch_endpoint(job_id:str, brand_id: str, scan_url:str, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_remote_run,job_id,brand_id,scan_url)

    return {"message": "Notification sent in the background"}

@app.post("/")
async def check():
    return {"message": "Alive"}

if __name__ == "__main__":
    uvicorn.run("main:app", port=8080, log_level="info",host='0.0.0.0')