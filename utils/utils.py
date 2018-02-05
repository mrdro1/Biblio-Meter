# -*- coding: utf-8 -*-
import collections
import datetime
import itertools
import pickle
from random import shuffle
import time
import re
#
import sys, traceback, logging
import browsercookie #
import random
import requests
from requests.exceptions import ProxyError, ConnectTimeout, SSLError, ReadTimeout
from bs4 import BeautifulSoup
import webbrowser
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import progressbar as pb
import json
import os
from urllib.parse import urlparse
#
import CONST
import settings
import utils
from torrequests import TorRequest

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
REQUEST_STATISTIC = {'count_requests': 0, 'failed_requests':list()}
# dict for save count response with same status code != 200
dict_bad_status_code = collections.defaultdict(lambda: 0)




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
        self.MAX_REQUESTS = 1
        self.list_host_names = ['www.researchgate.net', 'scholar.google.com', CONST.SCIHUB_HOST_NAME, 'otherhost']
        self.file_name = settings.PROXY_FILE
        self.dict_gens_proxy = {host_name: self.load_proxies() for host_name in self.list_host_names}
        self.proxy_request_count = {host_name: 0 for host_name in self.list_host_names}
        # initialize current proxies for each host name
        self.proxy = dict()
        [self.set_next_proxy(host_name) for host_name in self.list_host_names]  # set self.proxy

    def load_proxies(self):
        """ load proxies from txt file to generator"""
        logger.debug("Load proxies list from '{0}'".format(self.file_name))
        with open(self.file_name, 'r') as f:
            proxies_list = f.readlines()
            shuffle(proxies_list)
            proxies_list = itertools.cycle(proxies_list)
        return ({"https": proxy.strip()} for proxy in proxies_list)

    def set_next_proxy(self, host_name):
        """ change current proxy for specific host name """
        host_name = self.update_host_name_for_resources(host_name)
        if not host_name in self.list_host_names:
            host_name = "otherhost"
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
        if host_name.endswith(CONST.SCIHUB_HOST_NAME):
            host_name = CONST.SCIHUB_HOST_NAME
        return host_name


# init proxy
_PROXY_OBJ = ProxyManager()


# Region for work with good cookies
DONT_TOUCH_KEYS_IN_COOKIES = ['SSID', 'SID', 'HSID']
def del_gs_cookies():
    """ Function del google scholar cookies """
    logger.debug("Start delete cookies for google.com and google scholar")
    if SESSION.cookies._cookies.get('.scholar.google.com'):
        del SESSION.cookies._cookies['.scholar.google.com']
        logger.debug("Delete cookies for google scholar")
    if SESSION.cookies._cookies.get('.google.com'):
        google_cookies_keys = list(SESSION.cookies._cookies['.google.com']['/'].keys())
        for key in google_cookies_keys:
            if key not in DONT_TOUCH_KEYS_IN_COOKIES:
                del SESSION.cookies._cookies['.google.com']['/'][key]
        logger.debug("Delete cookies for google.com")
    return SESSION.cookies

def is_many_bad_status_code():
    """ Function for check count response with same status code.
        If count for some status is big (parameter in control file),
        than reload cookies."""
    function_answer = False
    # status by count appearance and select status with biggest value
    if dict_bad_status_code:
        list_status = dict_bad_status_code.items()
        code_with_biggest_value, biggest_appearance_count = sorted(list_status, key=lambda x: x[1])[-1]
        if biggest_appearance_count > int(settings.PARAMS['limit_resp_for_one_code']):
            logger.debug("Status code {0} has {1} appearance. Cookies will reload.".format(code_with_biggest_value,
                                                                                           biggest_appearance_count))
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
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate'
    }


def _get_cookies(domain=""):
    """Load cookie from default browser and filtering them by domain"""
    if settings.DEFAULT_BROWSER == settings.CHROME:
        logger.debug("Load cookie from chrome.")
        return browsercookie.chrome()#domain_name=domain)
    if settings.DEFAULT_BROWSER == settings.FIREFOX:
        logger.debug("Load cookie from firefox.")
        return browsercookie.firefox()#domain_name=domain)
    return None

SESSION = requests.Session()
SESSION.headers = _DEFAULT_HEADER
SESSION.cookies = _get_cookies()


#def _load_cookie_from_dict(data_dict):
#        """ Creates a cookie from the dict """
#        COOKIE_DEFAULT_VALUES = collections.defaultdict(lambda: str())
#        COOKIE_DEFAULT_VALUES = \
#            {
#                "version" : 0,
#                "name" : None,
#                "value" : None,
#                "port" : 0,
#                "port_specified" : False,
#                "domain" : None,
#                "domain_specified" : False,
#                "domain_initial_dot" : False,
#                "path" : '/',
#                "path_specified" : True,
#                "secure" : False,
#                "expires" : None,
#                "discard" : False,
#                "comment" : None,
#                "comment_url" : None,
#                "rest" : {},
#                "rfc2109" : False
#            }
#        cookie_params = dict( [(str(t[0]), t[1]) for t in data_dict.items() if t[0] in list(COOKIE_DEFAULT_VALUES)])
#        for key in COOKIE_DEFAULT_VALUES.keys():
#            cookie_params.setdefault(key, COOKIE_DEFAULT_VALUES[key])
#        if "httpOnly" in data_dict:
#            cookie_params["rest"] = {"HttpOnly":data_dict["httpOnly"]}
#        return requests.cookies.cookielib.Cookie(**cookie_params)


#def cl2cj(cookies_list):
#    """ Convert list with cookies in dictionary to cookie jar """
#    cj = requests.cookies.cookielib.CookieJar()
#    for x in cookies_list:
#         cj.set_cookie(_load_cookie_from_dict(x))
#    return cj


#def _update_cookie_jar(cjar, cookie_list):
#    """ Insert or update cookies in cookie jar """
#    cj = cl2cj(cookie_list)
#    res_cj = requests.cookies.cookielib.CookieJar()
#    for old_cookie in cjar:
#        if [cookie for cookie in cj 
#            if old_cookie.name == cookie.name 
#            and old_cookie.domain == cookie.domain] == []:
#                res_cj.set_cookie(old_cookie)
#    _ = [res_cj.set_cookie(new_cookie) for new_cookie in cj]
#    return res_cj

def _check_captcha(soup):
    """Return true if ReCaptcha was found"""
    return soup.find('div', id='gs_captcha_ccl') != None or \
       soup.find('div', class_='g-recaptcha') != None or \
       soup.find('img', id="captcha") != None


def handle_captcha(response):
    """ Captcha handler """
    host = urlparse(response.request.url).hostname
    settings.print_message("CAPTCHA was found. To continue, you need to enter the captcha in your browser.")
    cline = 'start chrome -proxy-server={1} "{0}" --user-data-dir="%LOCALAPPDATA%\\Google\\Chrome\\User Data"'
    os.popen(cline.format(response.request.url, 
        [ip_port for ip_port in _PROXY_OBJ.get_cur_proxy_without_changing(host).values()][0]))
    input("Press Enter after entering to continue")
    logger.debug("Waiting for cookies to be updated.")
    settings.print_message("Waiting for cookies to be updated.")
    SESSION.cookies = _get_cookies()
    return 0


def get_request(url, stream=False):
    """Send get request [, catch errors, try again]* & return data"""
    global REQUEST_STATISTIC
    host = urlparse(url).hostname
    count_try_for_captcha = 0
    bad_requests_counter = 0
    # var for control count handled capthas, this help avoid inf cycle
    capthas_handled = 0
    MAX_CAPTCHAS_HANDLED = 1

    while(True):
        resp = None
        if bad_requests_counter >= settings.PARAMS["http_contiguous_requests"]:
            settings.print_message("Failed {} times get requests from '{}'".format(settings.PARAMS["http_contiguous_requests"], url))
            # +1 bad requests
            REQUEST_STATISTIC['failed_requests'].append(url)
            REQUEST_STATISTIC['count_requests'] += 1
            return None
        try:
            if settings.using_TOR:
<<<<<<< HEAD
                with TorRequest(tor_app=r"Tor\tor.exe") as tr:
                    resp = tr.get(url=url, cookies=browsercookie.chrome(), timeout=settings.DEFAULT_TIMEOUT)
            elif host.endswith(CONST.SCIHUB_HOST_NAME):
                resp = SESSION.get(url, stream=stream)
=======
                with TorRequest(tor_app=r"..\Tor\tor.exe") as tr:
                    resp = tr.get(url=url, cookies=SESSION.cookies, timeout=settings.DEFAULT_TIMEOUT)
                    SESSION.cookies = resp.cookies
>>>>>>> 113132a78f53c4a21352742e96e4da51958b7717
            else:
                proxy = _PROXY_OBJ.get_cur_proxy(host)
                resp = SESSION.get(url, proxies=proxy, stream=stream, timeout=5)
            #handle_captcha(resp)
            if 'text/html' in resp.headers['Content-Type']:
                if _check_captcha(BeautifulSoup(resp.text, 'html.parser')):  # maybe captcha
                    count_try_for_captcha += 1
                    if count_try_for_captcha <= settings.PARAMS[_get_name_max_try_to_host(url)]:
                        _PROXY_OBJ.set_next_proxy(host)
                        continue
                    else:
                        if capthas_handled<MAX_CAPTCHAS_HANDLED:
                            handle_captcha(resp)
                        else:
                            return None
                        capthas_handled += 1
                        continue
            if resp.status_code != 200:
                bad_requests_counter += 1
                dict_bad_status_code[resp.status_code] += 1
                _PROXY_OBJ.set_next_proxy(host)
                # if count resp with same code enough big than reload cookies
                if is_many_bad_status_code():
                    del_gs_cookies()
                continue

            if resp.status_code == 200:
                # +1 good requests
                REQUEST_STATISTIC['count_requests'] += 1
                if stream:
                    return resp
                else:
                    return resp.text  # OK
        #except(ProxyError, ConnectTimeout, SSLError, ReadTimeout):
        #    bad_requests_counter += 1
        #    logger.warn(traceback.format_exc())
        #    _PROXY_OBJ.set_next_proxy(host)
        #    continue
        except Exception as error:
            logger.warn(traceback.format_exc())
            bad_requests_counter += 1
            _PROXY_OBJ.set_next_proxy(host)
            continue
    raise Exception(resp.status_code, resp.reason)


def _get_name_max_try_to_host(url):
    """   """
    dict_host_to_name = \
        {
            'www.researchgate.net': 'researchgate',
            'scholar.google.com': 'google',
            CONST.SCIHUB_HOST_NAME: 'sci_hub'
        }
    host = urlparse(url).hostname
    host = _PROXY_OBJ.update_host_name_for_resources(host)
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
        #logger.warn(traceback.format_exc())
        raise
    return None


def get_text_data(url, ignore_errors = False, repeat_until_captcha = False):
    """Return the data in text format"""
    try:
        data = get_request(url)
        return data
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    return None


def get_json_data(url):
    """Send get request to URL and get data in JSON format"""
    tmp_accept = SESSION.headers["Accept"]
    SESSION.headers.update({"Accept" : "application/json"})
    json_data = None
    try:
        resp = get_request(url)
        if resp == None:
            logger.debug("Json is empty.")
            return None
        logger.debug("Parse host answer from json.")
        json_data = json.loads(resp)
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    SESSION.headers.update({"Accept" : tmp_accept})
    return json_data


def download_file(url, output_filename):
    """Download file from url"""
    logger.warn("Download file (url='%s') and save (filename='%s')" % (url, output_filename))
    response = get_request(url, stream=True)
    if response == None: return False
    content_length = int(response.headers['content-length'])

    downloaded_size = 0
    chunk_size = 65536
 
    with open(output_filename, 'bw') as outfile:
        logger.debug('Create file {0}, start download.'.format(output_filename))
        widgets = [pb.Percentage(), pb.Bar(), pb.ETA()]
        progress = pb.ProgressBar(maxval=content_length,
                                  widgets=widgets).start()
        for chunk in response.iter_content(chunk_size):
            outfile.write(chunk)
            downloaded_size += len(chunk)
            progress.update(downloaded_size)
        logger.debug('End download file {0}.'.format(output_filename))
    #print("")
    return True


def is_doi(DOI):
    """Return true if DOI corresponds to the standard"""
    doiRegex = '(10[.][0-9]{4,}(?:[.][0-9]+)*/(?:(?![%"#? ])\\S)+)'
    logger.debug("Check DOI '%s'." % DOI)
    res = len(re.match(doiRegex, DOI).group()) == len(DOI)
    logger.debug("DOI '%s' is %s" % (DOI, "correct" if res else "not correct"))
    return res

#
_SKIP_RG = False
_SKIP_RG_FOR_ALL = False

def skip_RG_stage(): 
    global _SKIP_RG
    _SKIP_RG = True

def skip_RG_stage_for_all(): 
    global _SKIP_RG, _SKIP_RG_FOR_ALL
    _SKIP_RG = True
    _SKIP_RG_FOR_ALL = True

def skip_RG_stage_reset(): 
    global _SKIP_RG
    _SKIP_RG = False

def skip_RG_stage_for_all_reset(): 
    global _SKIP_RG, _SKIP_RG_FOR_ALL
    _SKIP_RG = False
    _SKIP_RG_FOR_ALL = False

def RG_stage_is_skipped():
    return _SKIP_RG

def RG_stage_is_skipped_for_all():
    return _SKIP_RG_FOR_ALL
#