# -*- coding: utf-8 -*-
import collections
import itertools
#from random import shuffle
import time
import re
import sys, traceback, logging
import random
import requests
from requests.exceptions import ProxyError, ConnectTimeout, SSLError, ReadTimeout
import json
import os
from urllib.parse import urlparse
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import hashlib
from shutil import copyfile
from PIL import Image
import numpy as np
#from selenium import webdriver
#from selenium.webdriver.support import expected_conditions as ec
#from selenium.webdriver import ChromeOptions
#
import browsercookie #
from datetime import datetime
from bs4 import BeautifulSoup
import PyPDF2
#
import settings
import dbutils
import scihub
if settings.PARAMS.get("sci_hub_files") and\
    not settings.PARAMS.get("sci_hub_show_captcha"):
    import compaund_model

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

CHECK_CONN_URL = "https://www.google.com/"
REQUEST_STATISTIC = {'count_requests': 0, 'failed_requests':list()}
LAST_CAPTCHA_SOLVE_TIME = datetime.now()
CAPTCHA_STATISTIC = {
        "total" : 0,
        "not_solved" : 0,
        "solved_by_several_attempts" : 0,
        "total_attempts" : 0,
    }
# dict for save count response with same status code != 200
dict_bad_status_code = collections.defaultdict(lambda: 0)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class DoubleDict(dict):
    """ Access and delete dictionary elements by key or value. """ 
    def __getitem__(self, key):
        if key not in self:
            inv_dict = {v:k for k,v in self.items()}
            return inv_dict[key]
        return dict.__getitem__(self, key)

    def __delitem__(self, key):
        if key not in self:
            inv_dict = {v:k for k,v in self.items()}
            dict.__delitem__(self, inv_dict[key])
        else:
            dict.__delitem__(self, key)

class Switch(object):
    """SWITCHER"""
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        yield self.match
        raise StopIteration

    def match(self, *args):
        if self.fall or not args:
            return True
        elif self.value in args:
            self.fall = True
            return True
        return False

class ProxyManager:
    """ Class for manage with proxies for each host name: load, get current, set next from inf list """
    def __init__(self):
        self.MIN_PROXIES_COUNT = settings.MIN_PROXIES_COUNT
        self.file_name = settings.PROXY_FILE
        self.current_proxy_num = 0
        self.proxies_count = 0
        self.scan_proxy_files_count = 0
        self.current_proxy = dict()
        self.current_proxy_ip = None
        self._proxy_list = self.load_proxies()
        self.set_next_proxy()

    def load_proxies(self):
        """ load proxies from txt file to generator"""
        logger.debug("Load proxies list from '{0}'".format(self.file_name))
        with open(self.file_name, 'r') as f:
            proxies_list = f.readlines()
            self.proxies_count = len(proxies_list)
            #shuffle(proxies_list)
            proxies_list = itertools.cycle(proxies_list)
            logger.debug("USE SSL PROXIES ONLY!!!")
        return ({"https": proxy.strip()} for proxy in proxies_list) # SSL PROXIES ONLY!!!

    def set_next_proxy(self):
        """ change current proxy for specific host name """
        self.current_proxy = next(self._proxy_list)
        self.current_proxy_num = self.current_proxy_num % self.proxies_count + 1
        if self.current_proxy_num == 1: self.scan_proxy_files_count += 1
        logger.debug("Change proxy to {} #{} (total {})".format(
            self.current_proxy, self.current_proxy_num, self.proxies_count))
        self.current_proxy_ip = self.current_proxy["https"]
        return 0

    def get_proxy(self):
        """ get current proxy for specific host name """
        logger.debug("Get current proxy.")
        logger.debug("Proxy: {0}".format(self.current_proxy))
        self.set_next_proxy()
        return self.current_proxy

# init proxy
PROXY_OBJ = ProxyManager()


def create_new_session():
    session = requests.session()
    logger.debug("Create new session")
    session.headers = {
        'User-Agent' : _get_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate'
    }
    logger.debug("New headers: {}".format(json.dumps(session.headers)))
    google_id = hashlib.md5(str(random.randint(0, 16**16)).encode()).hexdigest () [: 16]
    cookie = {"domain":".scholar.google.com", "expires" : time.time() + 60 * 60, "name" : "GSP", "value":'ID={}:CF=3'.format(google_id), "httpOnly":False}
    logger.debug("New cookies: {}".format(json.dumps(cookie)))
    session.cookies.set(cookie['name'], cookie['value'])
    session.HTTP_requests = 0
    return session

# Region for work with good cookies
DONT_TOUCH_KEYS_IN_COOKIES = ['SSID', 'SID', 'HSID']

def process_many_bad_status_code(host, change_proxy=True):
    """ Function for check count response with same status code.
        If count for some status is big (parameter in control file),
        than reload cookies."""
    function_answer = False
    # status by count appearance and select status with biggest value
    if dict_bad_status_code:
        list_status = dict_bad_status_code.items()
        code_with_biggest_value, biggest_appearance_count = sorted(list_status, key=lambda x: x[1])[-1]
        if biggest_appearance_count >= int(settings.PARAMS['limit_resp_for_one_code']):
            logger.debug("Status code {0} has {1} appearance.".format(code_with_biggest_value,
                                                       biggest_appearance_count))
            if change_proxy:
                if SESSIONS.get(PROXY_OBJ.current_proxy_ip) is not None:
                    SESSIONS[PROXY_OBJ.current_proxy_ip].HTTP_requests = 0
                PROXY_OBJ.get_proxy()
                ip = PROXY_OBJ.current_proxy_ip
                if SESSIONS.get(ip) is None:
                    logger.debug("Create new session for proxy {}".format(ip))
                    SESSIONS[ip] = create_new_session()
                logger.debug("HTTP ERROR {}. Change proxy to #{} (total {}): {}".format(code_with_biggest_value, 
                                                       PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
                settings.print_message("HTTP ERROR {}. Change proxy to #{} (total {}): {}".format(code_with_biggest_value, 
                                                       PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
            dict_bad_status_code.clear()
            function_answer = True
    return function_answer


def soup2file(soup, file_name):
    """Save soup to file"""
    html = soup.prettify("utf-8")
    f = open(file_name, "bw")
    f.write(html)
    f.close()


def _get_user_agent():
    """Generate new UA for header"""
    logger.debug("Generate User-Agent.")
    platform = random.choice(['Macintosh', 'Windows', 'X11'])
    if platform == 'Macintosh':
        os  = random.choice(['68K', 'PPC'])
    elif platform == 'Windows':
        os  = random.choice(['Win3.11', 'WinNT3.51', 'WinNT4.0', 'Windows NT 5.0', 'Windows NT 5.1', 'Windows NT 5.2', 'Windows NT 6.0', 'Windows NT 6.1', 'Windows NT 6.2', 'Win95', 'Win98', 'Win 9x 4.90', 'WindowsCE'])
    elif platform == 'X11':
        os  = random.choice(['Linux i686', 'Linux x86_64'])
    browser = random.choice(['chrome', 'firefox', 'ie'])
    if browser == 'chrome':
        webkit = str(random.randint(500, 599))
        version = str(random.randint(0, 24)) + '.0' + str(random.randint(0, 1500)) + '.' + str(random.randint(0, 999))
        return 'Mozilla/5.0 (' + os + ') AppleWebKit/' + webkit + '.0 (KHTML, live Gecko) Chrome/' + version + ' Safari/' + webkit
    elif browser == 'firefox':
        year = str(random.randint(2000, 2012))
        month = random.randint(1, 12)
        if month < 10:
            month = '0' + str(month)
        else:
            month = str(month)
        day = random.randint(1, 30)
        if day < 10:
            day = '0' + str(day)
        else:
            day = str(day)
        gecko = year + month + day
        version = random.choice(['1.0', '2.0', '3.0', '4.0', '5.0', '6.0', '7.0', '8.0', '9.0', '10.0', '11.0', '12.0', '13.0', '14.0', '15.0'])
        return 'Mozilla/5.0 (' + os + '; rv:' + version + ') Gecko/' + gecko + ' Firefox/' + version
    elif browser == 'ie':
        version = str(random.randint(1, 10)) + '.0'
        engine = str(random.randint(1, 5)) + '.0'
        option = random.choice([True, False])
        if option == True:
            token = random.choice(['.NET CLR', 'SV1', 'Tablet PC', 'Win64; IA64', 'Win64; x64', 'WOW64']) + '; '
        elif option == False:
            token = ''
        return 'Mozilla/5.0 (compatible; MSIE ' + version + '; ' + os + '; ' + token + 'Trident/' + engine + ')'


_DEFAULT_HEADER = {
    'User-Agent' : _get_user_agent(),
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate'
    }


def _get_cookies(domain=""):
    """Load cookie from default browser and filtering them by domain"""
    if settings.DEFAULT_BROWSER == settings.CHROME:
        logger.debug("Load cookie from chrome.")
        return browsercookie.chrome()  #domain_name=domain)
    if settings.DEFAULT_BROWSER == settings.FIREFOX:
        logger.debug("Load cookie from firefox.")
        return browsercookie.firefox()#domain_name=domain)
    return None

SESSIONS = {}
SESSIONS["localhost"] = requests.Session()
SESSIONS["localhost"].headers = _DEFAULT_HEADER
SESSIONS["localhost"].cookies = _get_cookies()
SESSIONS["localhost"].HTTP_requests = 0

def _check_captcha(soup):
    """Return true if ReCaptcha was found"""
    return soup.find('div', id='gs_captcha_ccl') != None or \
       soup.find('div', class_='g-recaptcha') != None or \
       soup.find('img', id="captcha") != None


def handle_captcha(response):
    """ Captcha handler """
    host = urlparse(response.request.url).hostname
    if "sci-hub" in host:
        
        #and :
        #logger.debug("CAPTCHA was found, skip.")
        #settings.print_message("CAPTCHA was found, skip.")
        #return None
        #try:
        #    with open('html_fails/{}.html'.format(time.time()), 'w', encoding='UTF-8') as f:
        #        f.write(response.text)
        #except KeyboardInterrupt:
        #    raise
        #except:
        #    pass
        logger.debug("Solving captcha.")
        try:
            logger.debug("Get img id.")
            soup = BeautifulSoup(response.text, 'html.parser')
            captcha_img_url = soup.find('img', id="captcha")['src']
            captcha_id = captcha_img_url.split('/')[-1].split('.')[0]
            try:
                if soup.find('img', id="captcha"):
                    href = "http://{}{}".format(host, captcha_img_url)
                    tmp_fname = settings.DIR_CAPTCHA_IMG + 'tmp_' + href.split('/')[-1]
                    logger.debug("Download captcha image.")
                    download_file(href, tmp_fname)
                    if settings.PARAMS.get('sci_hub_download_captcha'):
                        fname = settings.DIR_CAPTCHA_IMG + href.split('/')[-1]
                        logger.debug("Copy file {} -> {}.".format(tmp_fname, fname))
                        copyfile(tmp_fname, settings.DIR_CAPTCHA_IMG + href.split('/')[-1])
                    if not settings.PARAMS.get("sci_hub_show_captcha"):
                        global LAST_CAPTCHA_SOLVE_TIME
                        timespan = int((datetime.now() - LAST_CAPTCHA_SOLVE_TIME).total_seconds())
                        sleep_time = settings.PARAMS["sci_hub_timeout"] - timespan
                        sleep_time = sleep_time if sleep_time > 0 else 0
                        logger.debug("Sleep {} seconds for auto solving captcha. Last solve {}".format(sleep_time, LAST_CAPTCHA_SOLVE_TIME))
                        for sec in range(sleep_time, 0, -1):
                            fstr = "Please wait {} seconds to solve CAPTCHA.  \r".format(sec)
                            settings.print_message(fstr, 3, "")
                            time.sleep(1)
                            if sec == 1: settings.print_message(" " * len(fstr), 3, "\r")
                        LAST_CAPTCHA_SOLVE_TIME = datetime.now()
                        logger.debug("Auto solve captcha...")
                        settings.print_message("Solving CAPTCHA...\r", 3, "")
                        CAPTCHA_STATISTIC["total_attempts"] += 1
                        answer = compaund_model.solve(tmp_fname)
                        settings.print_message("Try download PDF again...", 3)
                    else:
                        logger.debug("Open captcha image (file {}).".format(tmp_fname))
                        img = Image.open(tmp_fname)
                        img.show()
                    logger.debug("Remove file {}.".format(tmp_fname))
                    os.remove(tmp_fname)
            except KeyboardInterrupt:
                raise
            except:
                settings.print_message('Can\'t load captcha image', 2)
                raise Exception("CAPTCHA image unavailable!")
            #settings.print_message(captcha_id)
            logger.debug("Captcha ID {}.".format(captcha_id))
            logger.debug("Send answer.")
            if settings.PARAMS.get("sci_hub_show_captcha"):
                answer = input("Input code from CAPTCHA image: ")
            if answer != '':
                req = get_request(response.request.url, POST=True, data={"id":captcha_id, "answer":answer}, skip_captcha=True, allow_redirects=False)
                SESSIONS["localhost"].cookies = _get_cookies()
                logger.debug("Captcha was solved.")
            else:
                return -1
        except KeyboardInterrupt:
            raise
        except:
            logger.debug("Error solving captcha.")
            logger.warn(traceback.format_exc())
            if settings.PARAMS.get("sci_hub_show_captcha"):
                cline = 'start chrome {1} "{0}" --user-data-dir="%LOCALAPPDATA%/Google/Chrome/User Data"'
                os.popen(cline.format(response.request.url, ""))
                answer = input("Press Enter to try load again. For skip this paper type 'skip' and press Enter.")
                if answer != 'skip': return -1
    else:
    ##
        if settings.PARAMS.get("open_browser_if_captcha"):
            logger.debug("CAPTCHA was found.")
            settings.print_message("CAPTCHA was found.")
            cline = 'start chrome {1} "{0}" --user-data-dir="%LOCALAPPDATA%\\Google\\Chrome\\User Data"'
            os.popen(cline.format(response.request.url, "-proxy-server={0}".format(PROXY_OBJ.current_proxy_ip)))
            if input("Press Enter after entering to continue. Type 'c' and press Enter to change proxy and continue.") == "c": 
                PROXY_OBJ.get_proxy()
                logger.debug("Change proxy to #{} (total {}): {}".format(
                                                PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
                settings.print_message("Change proxy to #{} (total {}): {}".format(
                                                PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
                
            ip = PROXY_OBJ.current_proxy_ip
            if SESSIONS.get(ip) is None:
                logger.debug("Create new session for proxy {}".format(ip))
                SESSIONS[ip] = create_new_session()
    ##
        else:
            if SESSIONS.get(PROXY_OBJ.current_proxy_ip) is not None:
                SESSIONS[PROXY_OBJ.current_proxy_ip].HTTP_requests = 0
            PROXY_OBJ.get_proxy()
            ip = PROXY_OBJ.current_proxy_ip
            if SESSIONS.get(ip) is None:
                logger.debug("Create new session for proxy {}".format(ip))
                SESSIONS[ip] = create_new_session()
            logger.debug("CAPTCHA was found. Change proxy to #{} (total {}): {}".format(
                                                PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
            settings.print_message("CAPTCHA was found. Change proxy to #{} (total {}): {}".format(
                                                PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip))
    return 0


def get_request(url, stream=False, return_resp=False, POST=False, att_file=None, for_download=False, skip_captcha=False, data=None, allow_redirects=True, timeout=settings.DEFAULT_TIMEOUT):
    """Send get request [, catch errors, try again]* & return data"""
    global REQUEST_STATISTIC
    host = urlparse(url).hostname
    bad_requests_counter = 0
    # var for control count handled capthas, this help avoid inf cycle
    capthas_handled = 0
    MAX_CAPTCHAS_HANDLED = PROXY_OBJ.proxies_count
    use_proxy = not (POST and not host.endswith(scihub.SCIHUB_HOST_NAME) or for_download)
    while bad_requests_counter < settings.PARAMS["http_contiguous_requests"]:
        resp = None
        try:
            ip = "localhost"
            proxy = None
            if use_proxy:
                proxy = PROXY_OBJ.current_proxy
                ip = PROXY_OBJ.current_proxy_ip
                if SESSIONS.get(ip) is None:
                    logger.debug("Create new session for proxy {}".format(ip))
                    SESSIONS[ip] = create_new_session()
                logger.debug("Use proxy #{} (total {}): {}. Successfull HTTP requests: {}".format(PROXY_OBJ.current_proxy_num, PROXY_OBJ.proxies_count, ip, SESSIONS[ip].HTTP_requests))
            if POST:
                resp = SESSIONS[ip].post(url=url, proxies=proxy, files=att_file, stream=stream, timeout=timeout, verify=False, data=data, allow_redirects=allow_redirects)
            else:
                resp = SESSIONS[ip].get(url=url, proxies=proxy, files=att_file, stream=stream, timeout=timeout, verify=False, data=data, allow_redirects=allow_redirects)
            REQUEST_STATISTIC['count_requests'] += 1
            if resp.headers.get('Content-Type') and 'text/html' in resp.headers['Content-Type']:
                if _check_captcha(BeautifulSoup(resp.text, 'html.parser')):  # maybe captcha
                    if not skip_captcha and capthas_handled < MAX_CAPTCHAS_HANDLED \
                    and (host.endswith(scihub.SCIHUB_HOST_NAME) \
                        and (not settings.PARAMS["sci_hub_show_captcha"] and capthas_handled < settings.PARAMS["sci_hub_capcha_autosolve"] \
                             or settings.PARAMS["sci_hub_show_captcha"])
                    or not host.endswith(scihub.SCIHUB_HOST_NAME)):
                        # handle captcha
                        if host.endswith(scihub.SCIHUB_HOST_NAME):
                            if capthas_handled == 0:
                                CAPTCHA_STATISTIC["total"] += 1
                                logger.debug("New autosolve. Cur statistic: {}".format(json.dumps(CAPTCHA_STATISTIC)))
                            if capthas_handled == 1: CAPTCHA_STATISTIC["solved_by_several_attempts"] += 1
                            if settings.PARAMS.get("sci_hub_show_captcha"): CAPTCHA_STATISTIC["total_attempts"] += 1
                        if handle_captcha(resp) != 0: return None
                    else:
                        if host.endswith(scihub.SCIHUB_HOST_NAME) and capthas_handled >= settings.PARAMS["sci_hub_capcha_autosolve"]:
                            CAPTCHA_STATISTIC["not_solved"] += 1
                        return None
                    capthas_handled += 1
                    continue
            if resp.status_code == 404:
                logger.debug("Http error 404: Page '{}' not found".format(url))
                #settings.print_message("Http error 404: Page '{}' not found".format(url))
                # +1 bad requests
                REQUEST_STATISTIC['failed_requests'].append(url)
                if ip: SESSIONS[ip].HTTP_requests = 0
                process_many_bad_status_code(host, use_proxy)
                return None

            if resp.status_code != 200:
                bad_requests_counter += 1
                dict_bad_status_code[resp.status_code] += 1
                if ip: SESSIONS[ip].HTTP_requests = 0
                #PROXY_OBJ.set_next_proxy(host)
                logger.debug("HTTP ERROR: Status code {}".format(resp.status_code))
                process_many_bad_status_code(host, use_proxy)
                continue

            if resp.status_code == 200:
                # +1 good requests
                if ip: SESSIONS[ip].HTTP_requests += 1
                if stream or return_resp:
                    return resp
                else:
                    return resp.text  # OK
        except KeyboardInterrupt:
            raise
        except Exception as error:
            dict_bad_status_code[-1] += 1
            logger.warn(traceback.format_exc())
            bad_requests_counter += 1
            process_many_bad_status_code(host, use_proxy)
            continue
    settings.print_message("Failed {} times get requests from '{}'".format(settings.PARAMS["http_contiguous_requests"], url))
    if check_internet_connection() > 0:
        """ If there was a disconnection from the Internet, then try again to connection the host """
        return get_request(url, stream, return_resp, POST, att_file, for_download, skip_captcha, data, allow_redirects)
    # +1 bad requests
    REQUEST_STATISTIC['failed_requests'].append(url)
    SESSIONS["localhost"].cookies = _get_cookies()
    # save html for bad request
    try:
        with open('html_fails\{}.html'.format(time.time()), 'w', encoding='UTF-8') as f:
            f.write(resp.text)
    except KeyboardInterrupt:
        raise
    except:
        pass
    return None


def _get_name_max_try_to_host(url):
    """   """
    dict_host_to_name = \
        {
            'scholar.google.com': 'google',
            scihub.SCIHUB_HOST_NAME: 'sci_hub'
        }
    host = urlparse(url).hostname
    host = PROXY_OBJ.update_host_name_for_resources(host)
    if dict_host_to_name.get(host) is None: return None
    name = dict_host_to_name[host]
    name_field_in_ctl_dict = name + '_captcha_retry_by_proxy_count'
    return name_field_in_ctl_dict

def get_soup(url, post=False, data=None):
    """Return the BeautifulSoup for a page"""
    try:
        request = get_request(url, POST=post, data=data)
        if request == None:
            logger.debug("Request is empty, don't create soup.")
            return None
        soup = BeautifulSoup(request, 'html.parser')
        return soup
    except Exception as error:
        raise
    return None


def get_text_data(url, ignore_errors = False, repeat_until_captcha = False):
    """Return the data in text format"""
    try:
        data = get_request(url)
        return data
    except Exception as error:
        raise
    return None


def get_json_data(url):
    """Send get request to URL and get data in JSON format"""
    tmp_accept = SESSIONS["localhost"].headers["Accept"]
    SESSIONS["localhost"].headers.update({"Accept" : "application/json"})
    json_data = None
    try:
        resp = get_request(url)
        if resp == None:
            logger.debug("Json is empty.")
            return None
        logger.debug("Parse host answer from json.")
        json_data = json.loads(resp)
    except Exception as error:
        raise
    SESSIONS["localhost"].headers.update({"Accept" : tmp_accept})
    return json_data


def download_file(url, output_filename):
    """Download file from url"""
    logger.warn("Download file (url='%s') and save (filename='%s')" % (url, output_filename))
    response = get_request(url, stream=True, for_download=True)
    if response == None: return False
    content_length = 0
    if response.headers.get('content-type') is None:
        return False
    if 'content-length' in response.headers:
        content_length = int(response.headers['content-length'])
        logger.debug('Content-length={}'.format(content_length))
    else:
        if not ('application/pdf' in response.headers['content-type']) and not 'refresh' in response.headers:
            logger.debug('Server do not give PDF.')
            return False

    if 'refresh' in response.headers:
        logger.debug('Try get PDF from {}.'.format(response.headers['refresh'].split('url=')[1]))
        return download_file(response.headers['refresh'].split('url=')[1], output_filename)

    if content_length == 0 and 'application/pdf' in response.headers['content-type']:
        logger.debug('Downloading the entire file.')
        response = get_request(url, return_resp=True, for_download=True)

    downloaded_size = 0
    chunk_size = 65536

    with open(output_filename, 'bw') as outfile:
        download = False
        if content_length > 0:
            logger.debug('Create file {0}, start download.'.format(output_filename))
            for chunk in response.iter_content(chunk_size):
                download = True
                outfile.write(chunk)
                downloaded_size += len(chunk)
            logger.debug('End download file {0}.'.format(output_filename))
        else:
            logger.debug('Save file {0}.'.format(output_filename))
            outfile.write(response.content)
    return download

def check_pdf(filename):
    pages = None
    try:
        logger.debug('Check PDF "{}" on valid.'.format(filename))
        if not os.path.exists(filename): 
            logger.debug('PDF file "{}" is not exists.'.format(filename))
            return pages
        with open(filename, "rb") as pdf:
            pdf = PyPDF2.PdfFileReader(pdf)
            pages = pdf.numPages
    except PyPDF2.utils.PdfReadError:
        logger.debug('Invalid PDF file "{}".'.format(filename))
        os.remove(filename)
        return pages
    else:
        logger.debug('PDF file "{}" is valid.'.format(filename))
        return pages


def is_doi(DOI):
    """Return true if DOI corresponds to the standard"""
    doiRegex = '(10[.][0-9]{4,}(?:[.][0-9]+)*/(?:(?![%"#? ])\\S)+)'
    logger.debug("Check DOI '%s'." % DOI)
    res = len(re.match(doiRegex, DOI).group()) == len(DOI)
    logger.debug("DOI '%s' is %s" % (DOI, "correct" if res else "not correct"))
    return res


def rename_file(old_name, new_name):
    """ Check exists file new_name and if not exists file
        old_name rename to new_name else rename file 
        old_name to new_name(N + 1). N is count of file versions.
    """
    logger.debug("Rename file '{}' -> '{}'.".format(old_name, new_name))
    fname, ext = os.path.splitext(new_name)
    tmp = fname.split("_")
    version = 1
    if len(tmp) > 1:
        str_version = tmp[::-1][0]
        if str_version.isnumeric():
            fname = tmp[:-1][0]
            version = int(str_version) + 1
    file_name = new_name
    while os.path.exists(file_name):
        file_name = "{0}_{1}{2}".format(fname, version, ext)
        version += 1
    os.rename(old_name, file_name)
    return file_name

def delfile(file_name):
    """ Delete file 'filename' """
    logger.debug("Check exists file '{}'.".format(file_name))
    if os.path.exists(file_name):
        logger.debug("Delete file '{}'.".format(file_name))
        os.remove(file_name)
    else:
        logger.debug("File '{}' not exists.".format(file_name))


def check_internet_connection():
    """ Check internet connection and handle disconnection
        return Exception if not access to internet,
               or number of attempts to connection
    """
    logger.debug("Check internet connection.")
    resp = None
    connection_attempts = settings.DEFAULT_CONN_ATTEMPTS if not settings.PARAMS.get("connection_attempts") \
        else settings.PARAMS.get("connection_attempts")
    for attempt in range(connection_attempts + 1):
        try:
            if attempt > 0: 
                msg = "Connection attempt #{} of {}...".format(attempt, connection_attempts)
                logger.debug(msg)
                settings.print_message(msg)
            resp = requests.get(CHECK_CONN_URL)
            logger.debug("There is internet access.")
            return attempt
        except:
            pass
        if not resp or resp.status_code != 200:
            if attempt == 0: 
                msg = "No access to the Internet."
                settings.print_message(msg)
                logger.info(msg)
            if attempt < connection_attempts:
                timeout = settings.DEFAULT_DISCONNECTION_TIMEOUT if not settings.PARAMS.get("disconnection_timeout") \
                            else settings.PARAMS.get("disconnection_timeout")
                logger.debug("Reconnection after {} seconds.".format(timeout))
                for sec in range(timeout, 0, -1):
                    fstr = "Reconnection after {} seconds...  \r".format(sec)
                    settings.print_message(fstr, end="")
                    time.sleep(1)
                    if sec == 1: settings.print_message(" " * len(fstr), 3, "\r")
    msg = "Not access to the Internet, check the connection and try again."
    logger.error(msg)
    settings.print_message(msg)
    raise Exception(msg)