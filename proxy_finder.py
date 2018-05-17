# python proxy_finder.py -q "163.121.187.100:8080" -c 1 -o proxies.txt

import argparse
from datetime import datetime
import random
import re
import time
import traceback
import browsercookie
import requests
from bs4 import BeautifulSoup


cfromat = "[{0}] {1}{2}"
def print_message(message, level=0):
    level_indent = " " * level
    print(cfromat.format(datetime.now(), level_indent, message))

# Programm version
__VERSION__ = "0.1.0"
# Header
_header = "Proxy-finder (v{0}, {1})".format(__VERSION__, datetime.now().strftime("%B %d %Y, %H:%M:%S"))

def _get_user_agent():
    """Generate new UA for header"""
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

def _get_cookies():
    """Load cookie from default browser and filtering them by domain"""
    return browsercookie.chrome()

_DEFAULT_HEADER = {
    'User-Agent' : _get_user_agent(),
    'Accept': 'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate'
    }

SESSION = requests.Session()
SESSION.headers = _DEFAULT_HEADER
SESSION.cookies = _get_cookies()

SEARCH_GOOGLE_TMPL_HREF = 'https://www.google.ru/search?q="{}"'
GOOGLE_TMPL_HREF = 'https://www.google.ru/{}'

DEFAULT_ATEEMPTS_COUNT = 5
DEFAULT_QUERY = '163.121.187.181:8080'

def get_request(url):
    return SESSION.get(url)

def ProxyExtracter(href):
    try:
        resp = get_request(href)
        text = resp.text
        proxies = re.findall(
            r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)[:|\s| ]+[1-9][0-9]+",
            text)
        return set(proxies)
    except Exception as e:
        print_message(traceback.format_exc())
        return set()

        
def get_all_proxy(q, max_page):
    resp = get_request(SEARCH_GOOGLE_TMPL_HREF.format(q))
    open('fail.html', 'w', encoding='UTF-8').write(resp.text)
    google_soup = BeautifulSoup(resp.text, 'html.parser')
    page_counter = 0
    while True:
        print_message('Current page: {}'.format(page_counter+1))
        for h3 in google_soup.find_all('h3', 'r'):
            site_url = h3.a['href']
            if site_url.startswith('/url'):
                site_url = re.findall('q=([^&]*)&', site_url)[0]
            print_message('Go to {}'.format(site_url))
            for proxy in ProxyExtracter(site_url):
                yield proxy
        page_counter += 1
        if page_counter == max_page:
            break
        else:
            url_next_page = google_soup.find_all('a', 'pn')
            if len(url_next_page) == 2 or (len(url_next_page) == 1 and page_counter == 1):
                url_next_page = url_next_page[-1]['href']
                resp = get_request(GOOGLE_TMPL_HREF.format(url_next_page))
                google_soup = BeautifulSoup(resp.text, 'html.parser')

def save_to_file(proxies, fn=''):
    with open(fn, 'w') as f_out:
        f_out.write("\n".join(proxies))
    return 0

# Command line parser
parser = argparse.ArgumentParser()
parser.add_argument("-q", "--query", action="store", dest="QUERY", help="Query for search proxies in Google", type=str)
parser.add_argument("-o", "--output", action="store", dest="OUTPUT_PROXIES_FILE_NAME", help="File with extracted proxy servers", type=str)
parser.add_argument("-c", "--count", action="store", dest="ATTEMPTS_COUNT", help="Number of page", type=int)
command_args = parser.parse_args()


OUTPUT_FILE = command_args.OUTPUT_PROXIES_FILE_NAME
if OUTPUT_FILE == None:
    OUTPUT_FILE = 'proxies_extracted.txt'
ATTEMPTS_COUNT = DEFAULT_ATEEMPTS_COUNT if command_args.ATTEMPTS_COUNT == None else command_args.ATTEMPTS_COUNT
QUERY = DEFAULT_QUERY if command_args.QUERY == None else command_args.QUERY



if __name__ == '__main__':
    start_time = time.time()
    print_message("Start finding")
    proxies = get_all_proxy(QUERY, ATTEMPTS_COUNT)
    proxies = set([proxy for proxy in proxies])
    len_list_proxies = len(proxies)
    save_to_file(proxies, fn=OUTPUT_FILE)
    end_time = datetime.now()
    print_message('Finish list: {} proxies.'.format(len_list_proxies))
    print_message("Run began on {0}".format(start_time))
    print_message("Run ended on {0}".format(end_time))
    print_message("Elapsed time was: {0}".format(time.time() - start_time))