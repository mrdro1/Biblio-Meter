# -*- coding: utf-8 -*-
import collections
import itertools
from random import shuffle
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
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver import ChromeOptions
#
import browsercookie #

from bs4 import BeautifulSoup
import shutil
import progressbar as pb
import PyPDF2
#
import settings
import dbutils
import scihub


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
REQUEST_STATISTIC = {'count_requests': 0, 'failed_requests':list()}
# dict for save count response with same status code != 200
dict_bad_status_code = collections.defaultdict(lambda: 0)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


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
        self.MAX_REQUESTS = 0
        self.MAX_REQUESTS_FOR_RELOAD_PROXIES = 250
        self.reqests_counter = 1
        self.list_host_names = ['scholar.google.com', scihub.SCIHUB_HOST_NAME, 'otherhost']
        self.file_name = settings.PROXY_FILE
        self.dict_gens_proxy = {host_name: self.load_proxies() for host_name in self.list_host_names}
        self.proxy_request_count = {host_name: 0 for host_name in self.list_host_names}
        # initialize current proxies for each host name
        self.proxy = dict()
        self.bad_proxies = list()
        [self.set_next_proxy(host_name) for host_name in self.list_host_names]  # set self.proxy

    def load_proxies(self):
        """ load proxies from txt file to generator"""
        logger.debug("Load proxies list from '{0}'".format(self.file_name))
        with open(self.file_name, 'r') as f:
            proxies_list = f.readlines()
            self.proxies_count = len(proxies_list)
            shuffle(proxies_list)
            proxies_list = itertools.cycle(proxies_list)
        return ({"https": proxy.strip()} for proxy in proxies_list)

    def set_next_proxy(self, host_name):
        """ change current proxy for specific host name """
        host_name = self.update_host_name_for_resources(host_name)
        if not host_name in self.list_host_names:
            host_name = "otherhost"
        self.proxy[host_name] = next(self.dict_gens_proxy[host_name])
        while self.proxy[host_name] in self.bad_proxies:
            self.proxy[host_name] = next(self.dict_gens_proxy[host_name])
        self.proxy_request_count[host_name] = 0
        logger.debug("Change proxy to {0} for {1}".format(self.proxy[host_name], host_name))
        return 0

    def get_cur_proxy(self, host_name):
        """ get current proxy for specific host name """
        logger.debug("Get current proxy for {0}.".format(host_name))
        host_name = self.update_host_name_for_resources(host_name)
        if not host_name in self.list_host_names:
            host_name = "otherhost"
        logger.debug("Proxy: {0}".format(self.proxy[host_name]))
        if self.proxy_request_count[host_name] >= self.MAX_REQUESTS:
            self.set_next_proxy(host_name)
        else:
            self.proxy_request_count[host_name] += 1
        return self.proxy[host_name]

    def get_cur_proxy_without_changing(self, host_name):
        """ get current proxy for specific host name without changing it """
        logger.debug("Get current proxy for {0}.".format(host_name))
        host_name = self.update_host_name_for_resources(host_name)
        if not host_name in self.list_host_names:
            host_name = "otherhost"
        logger.debug("Proxy: {0}".format(self.proxy[host_name]))
        return self.proxy[host_name]

    def update_host_name_for_resources(self, host_name):
        """  """
        if host_name.startswith('scholar'):
            host_name = 'scholar.google.com'
        if host_name.endswith(scihub.SCIHUB_HOST_NAME):
            host_name = scihub.SCIHUB_HOST_NAME
        return host_name

# init proxy
_PROXY_OBJ = ProxyManager()


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
                ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy_without_changing(host).values()][0]
                if SESSIONS.get(ip) is not None:
                    SESSIONS[ip].HTTP_requests = 0
                ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy(host).values()][0]
                if SESSIONS.get(ip) is None:
                    logger.debug("Create new session for proxy {}".format(ip))
                    SESSIONS[ip] = create_new_session()
                number = [i for i, proxy_ in enumerate(SESSIONS.keys()) if proxy_ == ip][0]
                logger.debug("HTTP ERROR {}. Change proxy to #{} (total {}): {}".format(code_with_biggest_value, 
                                                                                         number + 1, _PROXY_OBJ.proxies_count, ip))
                settings.print_message("HTTP ERROR {}. Change proxy to #{} (total {}): {}".format(code_with_biggest_value, 
                                                                                                  number + 1, _PROXY_OBJ.proxies_count, ip))
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

def _check_captcha(soup):
    """Return true if ReCaptcha was found"""
    if settings.PARAMS.get('download_scihub_captcha'):
        try:
            if soup.find('img', id="captcha"):
                href = 'http://dacemirror.sci-hub.tw' + soup.find('img', id="captcha")['src']
                if not os.path.exists('captcha//'):
                    os.mkdir('captcha//')
                download_file(href, 'captcha//' + href.split('/')[-1])
        except:
            settings.print_message('Can\'t load captcha image', 2)
    return soup.find('div', id='gs_captcha_ccl') != None or \
       soup.find('div', class_='g-recaptcha') != None or \
       soup.find('img', id="captcha") != None

def handle_captcha(response):
    """ Captcha handler """
    host = urlparse(response.request.url).hostname
    if "sci-hub" in host:
        try:
            with open('html_fails//{}.html'.format(time.time()), 'w', encoding='UTF-8') as f:
                f.write(response.text)
        except:
            pass
        cline = 'start chrome {1} "{0}" --user-data-dir="%LOCALAPPDATA%\\Google\\Chrome\\User Data"'
        os.popen(cline.format(response.request.url, ""))
        input("Press Enter after entering to continue")
        logger.debug("Waiting for cookies to be updated.")
        #settings.print_message("Waiting for cookies to be updated.")
        SESSIONS["localhost"].cookies = _get_cookies()
    else:
        ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy_without_changing(host).values()][0]
        if SESSIONS.get(ip) is not None:
            SESSIONS[ip].HTTP_requests = 0
        ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy("scholar").values()][0]
        if SESSIONS.get(ip) is None:
            logger.debug("Create new session for proxy {}".format(ip))
            SESSIONS[ip] = create_new_session()
        number = [i for i, proxy_ in enumerate(SESSIONS.keys()) if proxy_ == ip][0]
        logger.debug("CAPTCHA was found. Change proxy to #{} (total {}): {}".format(number + 1, _PROXY_OBJ.proxies_count, ip)) #len(SESSIONS.values())
        settings.print_message("CAPTCHA was found. Change proxy to #{} (total {}): {}".format(number + 1, _PROXY_OBJ.proxies_count, ip)) #len(SESSIONS.values())
    return 0


def get_request(url, stream=False, return_resp=False, POST=False, att_file=None, for_download=False, skip_captcha=False, force_use_proxy=False):
    """Send get request [, catch errors, try again]* & return data"""
    global REQUEST_STATISTIC
    host = urlparse(url).hostname
    bad_requests_counter = 0
    count_try_proxy = 0
    # var for control count handled capthas, this help avoid inf cycle
    capthas_handled = 0
    MAX_CAPTCHAS_HANDLED = _PROXY_OBJ.proxies_count
    use_proxy = not (POST or host.endswith(scihub.SCIHUB_HOST_NAME) or for_download)
    while bad_requests_counter < settings.PARAMS["http_contiguous_requests"]:
        TIMEOUT = 10
        resp = None
        try:
            ip = None
            if POST:
                resp = SESSIONS["localhost"].post(url=url, files=att_file, stream=stream, timeout=TIMEOUT, verify=False)
            elif host.endswith(scihub.SCIHUB_HOST_NAME) or for_download and not force_use_proxy:
                resp = SESSIONS["localhost"].get(url, stream=stream, timeout=TIMEOUT, verify=False)
            else:
                proxy = _PROXY_OBJ.get_cur_proxy_without_changing(host)

                ip = [ip_port for ip_port in proxy.values()][0]
                if SESSIONS.get(ip) is None:
                    logger.debug("Create new session for proxy {}".format(ip))
                    SESSIONS[ip] = create_new_session()

                number = [i for i, proxy_ in enumerate(SESSIONS.keys()) if proxy_ == ip][0]   
                logger.debug("Use proxy #{} (total {}): {}. Successfull HTTP requests: {}".format(number + 1, _PROXY_OBJ.proxies_count, proxy, SESSIONS[ip].HTTP_requests))
                resp = SESSIONS[ip].get(url, proxies=proxy, stream=stream, timeout=TIMEOUT)
            if resp.headers.get('Content-Type') and 'text/html' in resp.headers['Content-Type']:
                if _check_captcha(BeautifulSoup(resp.text, 'html.parser')):  # maybe captcha
                    #count_try_for_captcha += 1
                    #if _get_name_max_try_to_host(url):
                        #if count_try_for_captcha < settings.PARAMS[_get_name_max_try_to_host(url)]:
                        #    settings.print_message("CAPTCHA was found, try get request again. Try count: {} (total{}) Current proxy #{} (total {}): {}.".format(count_try_for_captcha, 
                        #                                        settings.PARAMS[_get_name_max_try_to_host(url)], number + 1, _PROXY_OBJ.proxies_count, ip, SESSIONS[ip].HTTP_requests), 3)
                        #    logger.debug("CAPTCHA was found, try get request again. Try count: {} (total{}) Current proxy #{} (total {}): {}.".format(count_try_for_captcha, 
                        #                                        settings.PARAMS[_get_name_max_try_to_host(url)], number + 1, _PROXY_OBJ.proxies_count, ip, SESSIONS[ip].HTTP_requests))
                        #    continue
                        #else:
                            if host.endswith(scihub.SCIHUB_HOST_NAME) and not settings.PARAMS.get("show_sci_hub_captcha") or force_use_proxy:
                                logger.debug("CAPTCHA was found, skip.")
                                settings.print_message("CAPTCHA was found, skip.")
                                if force_use_proxy:
                                    ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy_without_changing(host).values()][0]
                                    if SESSIONS.get(ip) is not None:
                                        SESSIONS[ip].HTTP_requests = 0
                                    ip = [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy(host).values()][0]
                                    if SESSIONS.get(ip) is None:
                                        logger.debug("Create new session for proxy {}".format(ip))
                                        SESSIONS[ip] = create_new_session()
                                    number = [i for i, proxy_ in enumerate(SESSIONS.keys()) if proxy_ == ip][0]
                                    logger.debug("Change proxy to #{} (total {}): {}".format(number + 1, _PROXY_OBJ.proxies_count, ip))
                                    settings.print_message("Change proxy to #{} (total {}): {}".format(number + 1, _PROXY_OBJ.proxies_count, ip))
                                return None
                            if not skip_captcha and capthas_handled < MAX_CAPTCHAS_HANDLED:
                                bad_proxy = _PROXY_OBJ.get_cur_proxy_without_changing(host)
                                handle_captcha(resp)
                                count_try_for_captcha = 0
                            else:
                                try:
                                    with open('html_fails//{}.html'.format(time.time()), 'w', encoding='UTF-8') as f:
                                        f.write(resp.text)
                                except:
                                    pass
                                return None
                            capthas_handled += 1
                            continue
            if resp.status_code == 404:
                settings.print_message("Http error 404: Page '{}' not found".format(url))
                # +1 bad requests
                REQUEST_STATISTIC['failed_requests'].append(url)
                REQUEST_STATISTIC['count_requests'] += 1
                if ip: SESSIONS[ip].HTTP_requests = 0
                return None
            if resp.status_code != 200:
                bad_requests_counter += 1
                dict_bad_status_code[resp.status_code] += 1
                if ip: SESSIONS[ip].HTTP_requests = 0
                #_PROXY_OBJ.set_next_proxy(host)
                logger.debug("HTTP ERROR: Status code {}".format(resp.status_code))
                process_many_bad_status_code(host, use_proxy)
                continue

            if resp.status_code == 200:
                # +1 good requests
                if ip: SESSIONS[ip].HTTP_requests += 1
                REQUEST_STATISTIC['count_requests'] += 1
                if stream or return_resp:
                    return resp
                else:
                    return resp.text  # OK
        except Exception as error:
            dict_bad_status_code[-1] += 1
            logger.warn(traceback.format_exc())
            bad_requests_counter += 1
            process_many_bad_status_code(host, use_proxy)
            continue
    settings.print_message("Failed {} times get requests from '{}'".format(settings.PARAMS["http_contiguous_requests"], url))
    # +1 bad requests
    REQUEST_STATISTIC['failed_requests'].append(url)
    REQUEST_STATISTIC['count_requests'] += 1
    SESSIONS["localhost"].cookies = _get_cookies()
    # save html for bad request
    try:
        with open('html_fails//{}.html'.format(time.time()), 'w', encoding='UTF-8') as f:
            f.write(resp.text)
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
    host = _PROXY_OBJ.update_host_name_for_resources(host)
    if dict_host_to_name.get(host) is None: return None
    name = dict_host_to_name[host]
    name_field_in_ctl_dict = name + '_captcha_retry_by_proxy_count'
    return name_field_in_ctl_dict

def get_soup(url):
    """Return the BeautifulSoup for a page"""
    try:
        request = get_request(url)
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


def download_file(url, output_filename, force_use_proxy=False):
    """Download file from url"""
    logger.warn("Download file (url='%s') and save (filename='%s')" % (url, output_filename))
    response = get_request(url, stream=True, for_download=True, force_use_proxy=force_use_proxy)
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
        response = get_request(url, return_resp=True, for_download=True, force_use_proxy=force_use_proxy)

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
    try:
        logger.debug('Check PDF "{}" on valid.'.format(filename))
        if not os.path.exists(filename): 
            logger.debug('PDF file "{}" is not exists.'.format(filename))
            return False
        with open(filename, "rb") as pdf:
            PyPDF2.PdfFileReader(pdf)
    except PyPDF2.utils.PdfReadError:
        logger.debug('Invalid PDF file "{}".'.format(filename))
        os.remove(filename)
        return False
    else:
        logger.debug('PDF file "{}" is valid.'.format(filename))
        return True


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