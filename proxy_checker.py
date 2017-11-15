# -*- coding: utf-8 -*-
import sys, traceback
import requests
import os
from datetime import datetime
from multiprocessing.pool import ThreadPool as Pool
#
import argparse

TEST_URLS = [
    "https://scholar.google.ru/scholar?hl=en&as_sdt=0%2C5&q=test&btnG=",
    "https://www.researchgate.net/search?q=test",
    "http://sci-hub.cc/10.1145/1497185.1497232"
    ]

DEFAULT_ATEEMPTS_COUNT = 2

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
    OUTPUT_FILE = os.path.join(input_directory, "%s_good%s" % (file_name, file_ext))
ATTEMPTS_COUNT = DEFAULT_ATEEMPTS_COUNT if command_args.ATTEMPTS_COUNT == None else command_args.ATTEMPTS_COUNT

def get_request(url, proxy):
    """Send get request & return data"""
    try:
        resp = requests.get(url, proxies=proxy, timeout=5)
    except Exception as error:
        return False
    if resp.status_code != 200:
        return False
    return True

print_message("Parameters:")
print_message("  Input file: '%s'" % INPUT_FILE)
print_message("  Output file: '%s'" % OUTPUT_FILE)
print_message("  Number of attempts: %i" % ATTEMPTS_COUNT)
with open(INPUT_FILE, "r") as Fi:
    with open(OUTPUT_FILE, "w") as Fo:
        start_time = datetime.now()
        try:
            pool_size = 6
            pool = Pool(pool_size)


            def check(proxy):
                for url in TEST_URLS:
                    for i in range(ATTEMPTS_COUNT):
                        #print_message("#%i proxy check on %s" % (i, url))
                        if get_request(url, {"https":proxy}) == False:
                            print_message("Skip proxy %s, is bad (didn't pass the %i test on the url '%s')" % (proxy, i + 1, url))
                            return
                Fo.write("%s\n" % proxy)
                print_message("Add proxy %s in good proxies" % proxy)
                    

            print_message("Start checking")
            for proxy in Fi.readlines():
                pool.apply_async(check, (proxy.strip(),))
            pool.close()
            pool.join()
        except Exception as error:
            print_message(traceback.format_exc())      
        end_time = datetime.now()
        print_message("Run began on {0}".format(start_time))
        print_message("Run ended on {0}".format(end_time))
        print_message("Elapsed time was: {0}".format(end_time - start_time))  