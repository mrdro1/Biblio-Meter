# -*- coding: utf-8 -*-
import collections
import itertools
from random import shuffle
#
import sys, traceback, logging
import browser_cookie3 #
import random
import requests
from requests.exceptions import ProxyError, ConnectTimeout, SSLError, ReadTimeout
from bs4 import BeautifulSoup
import webbrowser
import time
import re
import progressbar as pb
import json
from urllib.parse import urlparse
#
import settings
import utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class switch(object):
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
        self.MAX_REQUESTS = 5
        self.list_host_names = ['www.researchgate.net', 'scholar.google.com', 'sci-hub.cc', 'otherhost']
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
        if self.proxy_request_count[host_name] % self.MAX_REQUESTS == self.MAX_REQUESTS - 1:
            self.set_next_proxy(host_name)
        else:
            self.proxy_request_count[host_name] += 1
        return self.proxy[host_name]

    def update_host_name_for_resources(self, host_name):
        """  """
        if host_name.startswith('scholar'):
            host_name = 'scholar.google.com'
        if host_name.endswith('sci-hub.cc'):
            host_name = 'sci-hub.cc'
        return host_name


# init proxy
_PROXY_OBJ = ProxyManager()


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


def _get_cookies(domain):
    """Load cookie from default browser and filtering them by domain"""
    if settings.DEFAULT_BROWSER == settings.CHROME:
        logger.debug("Load cookie from chrome.")
        return browser_cookie3.chrome(domain_name=domain)
    if settings.DEFAULT_BROWSER == settings.FIREFOX:
        logger.debug("Load cookie from firefox.")
        return browser_cookie3.firefox(domain_name=domain)
    return None


_DEFAULT_HEADER = {
    'User-Agent' : _get_user_agent(),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate'
    }


_HTTP_PARAMS = {
    "session" : requests.Session(),
    "header" : _DEFAULT_HEADER,
    "cookies" : _get_cookies("")
}


def _set_http_params(session = None, header = None, cookies = None):
    """Set http params. If parameter none, it will be auto-generated or the default value will be used."""
    global _HTTP_PARAMS
    _HTTP_PARAMS["session"] = session if session != None else requests.Session()
    _HTTP_PARAMS["header"].update(header if header != None else {"User-Agent" : _get_user_agent()})
    _HTTP_PARAMS["cookies"] = cookies if cookies != None else _get_cookies("")


def _check_captcha(soup):
    """Return true if ReCaptcha was found"""
    return soup.find('div', id='gs_captcha_ccl') != None or \
       soup.find('div', class_='g-recaptcha') != None or \
       soup.find('img', id="captcha") != None


def handle_captcha(url):
        # ReCaptcha :(
        res = input("CAPTCHA was found. To continue, you need to enter the captcha in your browser.\nDo you want to open a browser to enter? [y/n]: ")
        if res != 'y' and res != 'n': raise Exception('Error: CAPTCHA was found. To continue, needed to enter the captcha in browser.')
        if res == 'y':
            webbrowser.open(url=url)
            input("Press Enter after entering to continue")
        logger.debug("Waiting for cookies to be updated.")
        settings.print_message("Waiting for cookies to be updated.")
        DELAY_TIME = 2
        max_iter = 5
        _PROXY_OBJ.set_next_proxy(host)
        while max_iter > 0:
            timeout = random.uniform(0, DELAY_TIME)
            logger.debug("Sleep {0} seconds.".format(timeout))
            time.sleep(timeout)
            _set_http_params()
            max_iter -= 1
        return res


def get_request(url, stream=False):
    """Send get request [, catch errors, try again]* & return data"""
    host = urlparse(url).hostname
    count_try_for_captcha = 0
    while(True):
        resp = None
        try:
            proxy = _PROXY_OBJ.get_cur_proxy(host)
            resp = _HTTP_PARAMS["session"].get(url, headers=_HTTP_PARAMS["header"], 
                cookies=_HTTP_PARAMS["cookies"], proxies=proxy, stream=stream, timeout=5)
            if 'text/html' in resp.headers['Content-Type']:
                if _check_captcha(BeautifulSoup(resp.text, 'html.parser')):  # maybe captcha
                    count_try_for_captcha += 1
                    if count_try_for_captcha <= settings.PARAMS[_get_name_max_try_to_host(url)]:
                        _PROXY_OBJ.set_next_proxy(host)
                    else:
                        handle_captcha(url)
                    continue
            if resp.status_code != 200:
                if resp.status_code == 429:
                    raise ProxyError("Error: 429, To many requests.")
                break
            if resp.status_code == 200:
                if stream:
                    return resp
                else:
                    return resp.text  # OK
        except(ProxyError, ConnectTimeout, SSLError, ReadTimeout):
            logger.warn(traceback.format_exc())
            settings.print_message("Connection error (see log for get more informartion), change proxy.")
            _PROXY_OBJ.set_next_proxy(host)
            continue
        except Exception as error:
            #logger.warn(traceback.format_exc())
            #settings.print_message(error)
            raise
    raise Exception(resp.status_code, resp.reason)

def _get_name_max_try_to_host(url):
    """   """
    dict_host_to_name = \
        {
            'www.researchgate.net': 'researchgate',
            'scholar.google.com': 'google',
            'sci-hub.cc': 'sci_hub'
        }
    host = urlparse(url).hostname
    host = _PROXY_OBJ.update_host_name_for_resources(host)
    name = dict_host_to_name[host]
    name_field_in_ctl_dict = name + '_captcha_retry_by_proxy_count'
    return name_field_in_ctl_dict

def get_soup(url):
    """Return the BeautifulSoup for a page"""
    try:
        soup = BeautifulSoup(get_request(url), 'html.parser')
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
    global _HTTP_PARAMS
    tmp_accept = _HTTP_PARAMS["header"]["Accept"]
    _HTTP_PARAMS["header"].update({"Accept" : "application/json"})
    json_data = None
    try:
        resp = get_request(url)
        logger.debug("Parse host answer from json.")
        json_data = json.loads(resp)
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    _HTTP_PARAMS["header"].update({"Accept" : tmp_accept})
    return json_data


def download_file(url, output_filename):
    """Download file from url"""
    logger.warn("Download file (url='%s') and save (filename='%s')" % (url, output_filename))
    response = get_request(url, stream=True)
    content_length = int(response.headers['content-length'])

    downloaded_size = 0
    chunk_size = 65536
 
    with open(output_filename, 'bw') as outfile:
        widgets = [pb.Percentage(), pb.Bar(), pb.ETA()]
        progress = pb.ProgressBar(maxval=content_length,
                                  widgets=widgets).start()
        for chunk in response.iter_content(chunk_size):
            outfile.write(chunk)
            downloaded_size += len(chunk)
            progress.update(downloaded_size)
    print("")
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