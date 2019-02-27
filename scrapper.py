from requests import get
from bs4 import BeautifulSoup
from contextlib import closing
from requests.exceptions import RequestException
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import json
from os import mkdir, path, getenv
from dotenv import load_dotenv
import wget
import ssl
from page_utils import wait_for
from urllib.parse import parse_qs

load_dotenv()


def simple_get(url):
    """
    Attempts to get the content at `url` by making an HTTP GET request.
    If the content-type of response is some kind of HTML/XML, return the
    text content, otherwise return None.
    """
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                return None

    except RequestException as e:
        log_error('Error during requests to {0} : {1}'.format(url, str(e)))
        return None


def is_good_response(resp):
    """
    Returns True if the response seems to be HTML, False otherwise.
    """
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200
            and content_type is not None
            and content_type.find('html') > -1)


def log_error(e):
    """
    It is always a good idea to log errors.
    This function just prints them, but you can
    make it do anything.
    """
    print(e)


class SeleniumCoursera:
    def __init__(self, driver, subdriver, timeout):
        self.driver = driver
        self.subdriver = subdriver
        self.timeout = timeout
        self.old_current_id = 0
        self.old_subcurrent_id = 0

        self.coursera_base = 'https://www.coursera.org/learn/'

    def driver_change(self, new_path):
        self.driver.get(new_path)
        wait_for(self.driver_loaded, self.timeout)
        self.old_current_id = self.current_id
        print('Main', new_path, self.current_id)

    def subdriver_change(self, new_path):
        self.subdriver.get(new_path)
        wait_for(self.subdriver_loaded, self.timeout)
        self.old_subcurrent_id = self.subcurrent_id
        print('Sub', new_path, self.subcurrent_id)

    def driver_loaded(self):
        self.current_id = self.driver.find_element_by_tag_name('html').id
        return self.old_current_id != self.current_id

    def subdriver_loaded(self):
        self.subcurrent_id = self.subdriver.find_element_by_tag_name('html').id
        return self.old_subcurrent_id != self.subcurrent_id

    def week_loaded(self):
        try:
            self.driver.find_element_by_class_name('rc-NamedItemList')
            if self.driver.current_url.split('/')[-1] == str(self.week):
                return True
            else:
                return False
        except:
            return False

    def video_loaded(self):
        try:
            self.subdriver.find_element_by_id('c-video_html5_api')
            return True
        except:
            return False

    def login(self, email, password):
        if path.isfile('temp/cookies.json'):
            cookies = []
            self.driver_change('https://www.coursera.org')
            with open('temp/cookies.json') as json_file:
                self.cookies = json.load(json_file)

            for cookie in self.cookies:
                self.driver.add_cookie(cookie)

            self.set_sub_driver()

            return True

        self.driver_change('https://www.coursera.org/?authMode=login')
        inputs = self.driver.find_elements_by_tag_name('input')
        buttons = self.driver.find_elements_by_tag_name('button')

        input_email = self.find_by_attribute(inputs, 'type', 'email')
        input_email.send_keys(email)

        input_password = self.find_by_attribute(inputs, 'type', 'password')
        input_password.send_keys(password)

        button_login = self.find_by_attribute(
            buttons, 'data-courselenium', 'login-form-submit-button')
        button_login.click()

        input("Confirm that you are not a robot in the driver. Once logged in, Press Enter to continue...")
        cookies_list = self.driver.get_cookies()

        try:
            mkdir('temp')
        except:
            pass

        with open('temp/cookies.json', 'w') as file:
            json.dump(cookies_list, file)

        self.set_sub_driver()

    def set_sub_driver(self):
        self.subdriver_change('https://www.coursera.org')
        with open('temp/cookies.json') as json_file:
            self.cookies = json.load(json_file)

        for cookie in self.cookies:
            self.subdriver.add_cookie(cookie)
        self.subdriver_change('https://www.coursera.org')

    @staticmethod
    def find_by_attribute(list_elements, attribute, value):
        for element in list_elements:
            if element.get_attribute(attribute) == value:
                return element
        return None

    def download_courses(self, courses):
        for course in courses:
            self.download_course(course)

    def download_course(self, course):
        self.create_folder('downloads')
        has_week = True
        week = 1
        self.week = week

        week_base = '/home/week/'
        while(has_week):
            self.driver.get(self.coursera_base +
                            course + week_base + str(week))
            try:
                wait_for(self.week_loaded, self.timeout)
            except:
                has_week = False
                break

            print('Week page loaded')

            titles = self.driver.find_elements_by_class_name(
                'rc-NamedItemList')

            if len(titles) == 0:
                has_week = False
                break

            for i, title in enumerate(titles):
                title_text = title.find_element_by_tag_name('h3').text
                folder_name = str(i) + '_' + self.format_name(title_text)
                print(folder_name)
                items = title.find_elements_by_tag_name('li')
                for j, item in enumerate(items):
                    try:
                        item_type = item.find_element_by_tag_name(
                            'strong').text
                        if "Video:" in item_type:
                            name = item.find_element_by_class_name(
                                'rc-WeekItemName').text
                            href = item.find_element_by_tag_name(
                                'a').get_attribute('href')
                            name = str(j) + '_' + self.format_name(name)
                            self.download_video(course, str(
                                week), folder_name, name, href)
                    except:
                        pass
            week += 1
            self.week += 1

    @staticmethod
    def format_name(name):
        return name.replace(':', '_').replace('?', '').replace('\n', '_').replace('-', '_').replace('/', '_')

    def download_video(self, course, week, folder_name, video, href):
        self.subdriver.get(href)
        try:
            wait_for(self.video_loaded, self.timeout)
        except:
            return False
        video_links = []
        subtitles_links = []
        try:
            video_element = self.subdriver.find_element_by_id(
                'c-video_html5_api')
            video_links = video_element.find_elements_by_tag_name('source')
        except:
            pass
        try:
            video_element = self.subdriver.find_element_by_id(
                'c-video_html5_api')
            subtitles_links = video_element.find_elements_by_tag_name('track')
        except:
            pass

        if len(video_links) > 0:
            for link in video_links:
                extension = link.get_attribute('type').split('/')[-1]
                href = link.get_attribute('src')
                self.save_resource(course, week, folder_name,
                                   video + '.' + extension, href)
        if len(subtitles_links) > 0:
            for link in subtitles_links:
                qs = parse_qs(link.get_attribute('src'))
                extension = qs['fileExtension'][0]
                language = link.get_attribute('label')
                href = link.get_attribute('src')
                self.save_resource(course, week, folder_name,
                                   video + '_' + language + '.' + extension, href)

    def save_resource(self, course, week, folder_name, resource, link):
        self.create_folder('downloads/' + course)
        self.create_folder('downloads/' + course + '/' + week)
        self.create_folder('downloads/' + course + '/' +
                           week + '/' + folder_name)

        ssl._create_default_https_context = ssl._create_unverified_context
        print('Downloading: ', 'downloads/' + course + '/' + week +
              '/' + folder_name + '/' + resource)
        print('')
        wget.download(link, 'downloads/' + course +
                      '/' + week + '/' + folder_name + '/' + resource)
        print('')

    @staticmethod
    def create_folder(folder):
        try:
            mkdir(folder)
        except:
            pass
            # print('Folder: ' + folder + '. Already created.')


with open('courses.json') as json_file:
    courses = json.load(json_file)

driver = webdriver.Chrome("./chromedriver")
subdriver = webdriver.Chrome("./chromedriver")
coursera = SeleniumCoursera(driver, subdriver, timeout=60)

EMAIL = getenv("EMAIL")
PASSWORD = getenv("PASSWORD")
coursera.login(EMAIL, PASSWORD)

coursera.download_courses(courses)
