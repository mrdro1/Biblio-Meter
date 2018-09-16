# -*- coding: utf-8 -*-
import sys
import traceback
import requests
import os
import random
import hashlib
from datetime import datetime
import time
import multiprocessing
from threading import Lock
import signal
from bs4 import BeautifulSoup
#
import argparse


TEST_URL = "https://scholar.google.ru/scholar?hl=ru&as_sdt=0%2C5&q={}&btnG="
QUESTIONS = [
    "Cross entropy",
    "Computer vision",
    "CNN",
    "Neural networks",
    "Regression",
    "Clusterisation",
    "Classification",
    "Time siries"]
DEFAULT_PROCESSES = 50
DEFAULT_ATEEMPTS_COUNT = 2
DEFAULT_REFILTERING_COUNT = 1
DEFAULT_TIMEOUT = 1000
LOCK = multiprocessing.Lock()
RESULTS = list()
CURRENT_GOOD_PROXIES = set()
good_proxies = dict()

# CONSOLE LOG
cfromat = "[{0}] {1}{2}"


def print_message(message, level=0):
    level_indent = " " * level
    print(cfromat.format(datetime.now(), level_indent, message))
#


# Programm version
__VERSION__ = "1.0.2"

# Header
_header = "Proxy-checker (v{0}, {1})".format(__VERSION__,
                                             datetime.now().strftime("%B %d %Y, %H:%M:%S"))

# Command line parser
parser = argparse.ArgumentParser()
parser.add_argument(
    "-i",
    "--input",
    action="store",
    dest="INPUT_PROXIES_FILE_NAME",
    help="Input file with proxies",
    type=str)
parser.add_argument(
    "-o",
    "--output",
    action="store",
    dest="OUTPUT_PROXIES_FILE_NAME",
    help="File with good proxy servers",
    type=str)
parser.add_argument(
    "-c",
    "--count",
    action="store",
    dest="ATTEMPTS_COUNT",
    help="Number of attempts",
    type=int)
parser.add_argument(
    "-r",
    "--refiltering",
    action="store",
    dest="REFILTERING_COUNT",
    help="Number of refiltering iterations",
    type=int)
parser.add_argument(
    "-t",
    "--timeout",
    action="store",
    dest="TIMEOUT",
    help="Timeout in miliseconds",
    type=int)
parser.add_argument(
    "-g",
    "--gooclerecaptcha",
    action="store_true",
    dest="CHECK_CAPTCHA",
    help="Check ReCaptcha on GOOGLE")
parser.add_argument(
    "-k",
    "--k_errors",
    action="store",
    dest="COUNT_CHANCE",
    help="",
    type=int)
parser.add_argument(
    "-p",
    "--process",
    action="store",
    dest="PROCESS_COUNT",
    help="Count of process for checking proxies",
    type=int)


command_args = parser.parse_args()
if command_args.INPUT_PROXIES_FILE_NAME is None:
    print_message(
        "USAGE: python %s -i <input file name> [-o <output file name>] [-c <number of attempts>] [-r <number of refiltering>] [-t <timeout in miliseconds>] [-g <check captcha>]" %
        __file__)
    exit()
INPUT_FILE = command_args.INPUT_PROXIES_FILE_NAME
OUTPUT_FILE = command_args.OUTPUT_PROXIES_FILE_NAME
if OUTPUT_FILE is None:
    input_directory = os.path.dirname(INPUT_FILE)
    full_file_name = os.path.basename(INPUT_FILE)
    file_name, file_ext = os.path.splitext(full_file_name)
    OUTPUT_FILE = os.path.join(
        input_directory, "{0}_good{1}".format(
            file_name, file_ext))
ATTEMPTS_COUNT = DEFAULT_ATEEMPTS_COUNT if command_args.ATTEMPTS_COUNT is None else command_args.ATTEMPTS_COUNT
REFILTERING_COUNT = DEFAULT_REFILTERING_COUNT if command_args.REFILTERING_COUNT is None else command_args.REFILTERING_COUNT
TIMEOUT = DEFAULT_TIMEOUT if command_args.TIMEOUT is None else command_args.TIMEOUT
CHECK_CAPTCHA = command_args.CHECK_CAPTCHA
COUNT_CHANCE = REFILTERING_COUNT if command_args.COUNT_CHANCE is None else command_args.COUNT_CHANCE
THREADS = DEFAULT_PROCESSES if command_args.PROCESS_COUNT is None else command_args.PROCESS_COUNT


def _get_user_agent():
    """Generate new UA for header"""
    platform = random.choice(['Macintosh', 'Windows', 'X11'])
    if platform == 'Macintosh':
        os = random.choice(['68K', 'PPC'])
    elif platform == 'Windows':
        os = random.choice(['Win3.11',
                            'WinNT3.51',
                            'WinNT4.0',
                            'Windows NT 5.0',
                            'Windows NT 5.1',
                            'Windows NT 5.2',
                            'Windows NT 6.0',
                            'Windows NT 6.1',
                            'Windows NT 6.2',
                            'Win95',
                            'Win98',
                            'Win 9x 4.90',
                            'WindowsCE'])
    elif platform == 'X11':
        os = random.choice(['Linux i686', 'Linux x86_64'])
    browser = random.choice(['chrome', 'firefox', 'ie'])
    if browser == 'chrome':
        webkit = str(random.randint(500, 599))
        version = str(random.randint(0, 24)) + '.0' + \
            str(random.randint(0, 1500)) + '.' + str(random.randint(0, 999))
        return 'Mozilla/5.0 (' + os + ') AppleWebKit/' + webkit + \
            '.0 (KHTML, live Gecko) Chrome/' + version + ' Safari/' + webkit
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
        version = random.choice(['1.0',
                                 '2.0',
                                 '3.0',
                                 '4.0',
                                 '5.0',
                                 '6.0',
                                 '7.0',
                                 '8.0',
                                 '9.0',
                                 '10.0',
                                 '11.0',
                                 '12.0',
                                 '13.0',
                                 '14.0',
                                 '15.0'])
        return 'Mozilla/5.0 (' + os + '; rv:' + version + \
            ') Gecko/' + gecko + ' Firefox/' + version
    elif browser == 'ie':
        version = str(random.randint(1, 10)) + '.0'
        engine = str(random.randint(1, 5)) + '.0'
        option = random.choice([True, False])
        if option == True:
            token = random.choice(
                ['.NET CLR', 'SV1', 'Tablet PC', 'Win64; IA64', 'Win64; x64', 'WOW64']) + '; '
        elif option == False:
            token = ''
        return 'Mozilla/5.0 (compatible; MSIE ' + version + \
            '; ' + os + '; ' + token + 'Trident/' + engine + ')'


def create_new_session():
    session = requests.session()
    session.headers = {
        'User-Agent': _get_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate'
    }
    google_id = hashlib.md5(
        str(random.randint(0, 16**16)).encode()).hexdigest()[: 16]
    cookie = {
        "domain": ".scholar.google.com",
        "expires": time.time() + 60 * 60,
        "name": "GSP",
        "value": 'ID={}:CF=3'.format(google_id),
        "httpOnly": False}
    session.cookies.set(cookie['name'], cookie['value'])
    session.HTTP_requests = 0
    return session


def _check_captcha(soup):
    """Return true if ReCaptcha was found"""
    return soup.find('div', id='gs_captcha_ccl') is not None or \
        soup.find('div', class_='g-recaptcha') is not None or \
        soup.find('img', id="captcha") is not None


def get_request(url, proxy):
    """Send get request & return data"""
    try:
        resp = create_new_session().get(url, proxies=proxy, timeout=TIMEOUT * 0.001)
    except requests.exceptions.Timeout as TMError:
        return 1
    except requests.exceptions.ConnectTimeout as TMError:
        return 1
    except Exception as error:
        return 2
    if resp.status_code != 200:
        return 2
    if CHECK_CAPTCHA \
            and resp.headers.get('Content-Type') \
            and 'text/html' in resp.headers['Content-Type'] \
            and _check_captcha(BeautifulSoup(resp.text, 'html.parser')):
        return 3
    return 0


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def check(proxy, total_good, total_bad, lock):
    try:
        for i in range(ATTEMPTS_COUNT):
            url = TEST_URL.format(random.choice(QUESTIONS))
            res = get_request(url, {"https": proxy})
            if res != 0:
                lock.acquire()
                total_bad.value += 1
                lock.release()
                print_message(
                    "{0:23} {1:8} {2:5} Didn't pass the {3} test on the url '{4}'".format(
                        proxy,
                        "TIMEOUT" if res == 1 else "HTTP ERR" if res == 2 else "CAPTCHA",
                        total_bad.value,
                        i + 1,
                        url))
                return
        lock.acquire()
        total_good.value += 1
        print_message(
            "{0:23} {1:8} {2:5} Proxy pass all tests".format(
                proxy, "ADDED", total_good.value))
        # CURRENT_GOOD_PROXIES.add(proxy)
        lock.release()
        return True, proxy
    except Exception as error:
        print_message(traceback.format_exc())
        return False, None


def results_collectors(result):
    result = result or (None, None)
    RESULTS.append(result[0])
    if result[1]:
        CURRENT_GOOD_PROXIES.add(result[1])


def main():
    print_message(_header)
    threads = THREADS
    pool = multiprocessing.Pool(threads, init_worker)
    m = multiprocessing.Manager()
    lock = m.Lock()
    total_good = m.Value('i', 0)
    total_bad = m.Value('i', 0)
    print_message("Parameters:")
    print_message("Input file: '{0}'".format(INPUT_FILE), 2)
    print_message("Output file: '{0}'".format(OUTPUT_FILE), 2)
    print_message("Number of attempts: {0}".format(ATTEMPTS_COUNT), 2)
    print_message("Number of refiltering: {0}".format(REFILTERING_COUNT), 2)
    print_message("Processes: {0}".format(THREADS), 2)
    print_message(
        "Number of iter. for good proxy: {0}".format(COUNT_CHANCE), 2)
    start_time = datetime.now()
    with open(INPUT_FILE, "r") as Fi:
        proxies = set(Fi.readlines())
    len_start_list_proxies = len(proxies)
    print_message('Start list: {0} proxies'.format(len_start_list_proxies))
    print_message("Start checking")

    for iter_filtering in range(REFILTERING_COUNT):
        print_message(
            "{0:23} {1:8} {2:6} {3}".format(
                "PROXY",
                "STATUS",
                "TOTAL",
                "COMMENT"))  # HEADER
        for proxy in proxies:
            pool.apply_async(
                check,
                args=(
                    proxy.strip(),
                    total_good,
                    total_bad,
                    lock),
                callback=results_collectors)
        try:
            while True:
                time.sleep(2)
                if len(RESULTS) == len(proxies):
                    break
        except KeyboardInterrupt:
            print_message("Caught KeyboardInterrupt, terminating processing")
            pool.terminate()
            pool.join()
        current_count_proxies = len(CURRENT_GOOD_PROXIES)
        for proxy in CURRENT_GOOD_PROXIES:
            if good_proxies.get(proxy):
                good_proxies[proxy] += 1
            else:
                good_proxies[proxy] = 1
        if iter_filtering != REFILTERING_COUNT - 1:
            # end iteration => reset all global lists, sets, counters
            RESULTS.clear()
            #proxies = CURRENT_GOOD_PROXIES.copy()
            CURRENT_GOOD_PROXIES.clear()
            total_good = m.Value('i', 0)
            total_bad = m.Value('i', 0)
            current_count_proxies = len(proxies)
        if REFILTERING_COUNT > 1:
            print_message('End {0} iteration. Current count good proxies: {1}'.format(iter_filtering + 1,
                                                                                      current_count_proxies))
    # close pool
    if pool:
        pool.close()
        pool.join()
    # save chosen proxies to output file
    # print(good_proxies)
    result_list = [proxy for proxy in good_proxies.keys(
    ) if good_proxies[proxy] >= COUNT_CHANCE]
    with open(OUTPUT_FILE, 'w') as file_output:
        for proxy in result_list:
            file_output.write(proxy + '\n')

    end_time = datetime.now()
    print_message(
        'Start list: {0} proxies, finish list: {1} proxies.'.format(
            len_start_list_proxies,
            len(result_list)))
    print_message("Run began on {0}".format(start_time))
    print_message("Run ended on {0}".format(end_time))
    print_message("Elapsed time was: {0}".format(end_time - start_time))


if __name__ == "__main__":
    main()
