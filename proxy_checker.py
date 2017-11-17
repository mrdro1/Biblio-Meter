# -*- coding: utf-8 -*-
import sys, traceback
import requests
import os
from datetime import datetime
import time
import multiprocessing
from threading import Lock
import signal
#
import argparse

TEST_URLS = [
    "https://scholar.google.ru/scholar?hl=en&as_sdt=0%2C5&q=test&btnG=",
    "https://www.researchgate.net/search?q=test",
    "http://sci-hub.cc/10.1145/1497185.1497232"
    ]

DEFAULT_ATEEMPTS_COUNT = 2
LOCK = multiprocessing.Lock()
RESULTS = list()

def print_message(message):
    print("[{0}] {1}".format(datetime.now(), message))

# Command line parser
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input", action="store", dest="INPUT_PROXIES_FILE_NAME", help="Input file with proxies", type=str)
parser.add_argument("-o", "--output", action="store", dest="OUTPUT_PROXIES_FILE_NAME", help="File with good proxy servers", type=str)
parser.add_argument("-c", "--count", action="store", dest="ATTEMPTS_COUNT", help="Number of attempts", type=int)

command_args = parser.parse_args()
if command_args.INPUT_PROXIES_FILE_NAME == None:
    print_message("USAGE: python %s -i <input file name> [-o <output file name>] [-c <number of attempts>]" % __file__)
    exit()
INPUT_FILE = command_args.INPUT_PROXIES_FILE_NAME
OUTPUT_FILE = command_args.OUTPUT_PROXIES_FILE_NAME
if OUTPUT_FILE == None:
    input_directory = os.path.dirname(INPUT_FILE)
    full_file_name = os.path.basename(INPUT_FILE) 
    file_name, file_ext = os.path.splitext(full_file_name) 
    OUTPUT_FILE = os.path.join(input_directory, "{0}_good{1}".format(file_name, file_ext))
ATTEMPTS_COUNT = DEFAULT_ATEEMPTS_COUNT if command_args.ATTEMPTS_COUNT == None else command_args.ATTEMPTS_COUNT
total = 0

def get_request(url, proxy):
    """Send get request & return data"""
    try:
        resp = requests.get(url, proxies=proxy, timeout=5)
    except Exception as error:
        return False
    if resp.status_code != 200:
        return False
    return True


def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def check(proxy):
    global total
    try:
        for url in TEST_URLS:
            for i in range(ATTEMPTS_COUNT):
                if get_request(url, {"https":proxy}) == False:
                    print_message("Skip proxy {0}, is bad (didn't pass the {1} test on the url '{2}')".format(proxy, i + 1, url))
                    return
        LOCK.acquire()
        total += 1
        print_message("Add proxy {0} in good proxies (total good {1})".format(proxy, total))
        with open(OUTPUT_FILE, "a") as file:
            file.write("{0}\n".format(proxy))
        LOCK.release()
        return True
    except Exception as error:
        print_message(traceback.format_exc())      
        return False

def results_collectors(result):
    RESULTS.append(result)

def main():
    threads = 8
    pool = multiprocessing.Pool(threads, init_worker)
    lock = multiprocessing.Lock()
    print_message("Parameters:")
    print_message("  Input file: '{0}'".format(INPUT_FILE))
    print_message("  Output file: '{0}'".format(OUTPUT_FILE))
    print_message("  Number of attempts: {0}".format(ATTEMPTS_COUNT))
    with open(OUTPUT_FILE, "w") as Fo:
        pass
    with open(INPUT_FILE, "r") as Fi:
        start_time = datetime.now()
        print_message("Start checking")
        proxies = list(Fi.readlines())
        for proxy in proxies:
            pool.apply_async(check, args=(proxy.strip(), ), callback=results_collectors)
    try:
        while True:
            time.sleep(2)
            if len(RESULTS) == len(proxies):
                break
    except KeyboardInterrupt:
        print_message("Caught KeyboardInterrupt, terminating processing")
        pool.terminate()
        pool.join()
    else:
        pool.close()
        pool.join()

    end_time = datetime.now()
    print_message("Run began on {0}".format(start_time))
    print_message("Run ended on {0}".format(end_time))
    print_message("Elapsed time was: {0}".format(end_time - start_time))

if __name__ == "__main__":
    main()