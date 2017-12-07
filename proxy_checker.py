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
	"https://scholar.google.ru/",
	"https://www.researchgate.net/search?q=test",
	"https://sci-hub.bz/"
	]

DEFAULT_ATEEMPTS_COUNT = 2
LOCK = multiprocessing.Lock()
RESULTS = list()

# CONSOLE LOG
cfromat = "[{0}] {1}{2}"
def print_message(message, level=0):
	level_indent = " " * level
	print(cfromat.format(datetime.now(), level_indent, message))
#

# Programm version
__VERSION__ = "0.1.5"

# Header
_header = "Proxy-checker (v{0}, {1})".format(__VERSION__, datetime.now().strftime("%B %d %Y, %H:%M:%S"))

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


def check(proxy, total_good, total_bad, lock):
	try:
		for url in TEST_URLS:
			for i in range(ATTEMPTS_COUNT):
				if get_request(url, {"https":proxy}) == False:
					lock.acquire()
					total_bad.value += 1
					lock.release()
					print_message("{0:23} {1:8} {2:5} Didn't pass the {3} test on the url '{4}'".format(proxy, "SKIPPED", total_bad.value, i + 1, url))
					return
		lock.acquire()
		total_good.value += 1
		print_message("{0:23} {1:8} {2:5} Proxy pass all tests".format(proxy, "ADDED", total_good.value))
		with open(OUTPUT_FILE, "a") as file:
			file.write("{0}\n".format(proxy))
		lock.release()
		return True
	except Exception as error:
		print_message(traceback.format_exc())	   
		return False

def results_collectors(result):
	RESULTS.append(result)

def main():
	print_message(_header)
	threads = 20
	pool = multiprocessing.Pool(threads, init_worker)
	m = multiprocessing.Manager()
	lock = m.Lock()
	total_good = m.Value('i', 0)
	total_bad = m.Value('i', 0)
	print_message("Parameters:")
	print_message("Input file: '{0}'".format(INPUT_FILE), 2)
	print_message("Output file: '{0}'".format(OUTPUT_FILE), 2)
	print_message("Number of attempts: {0}".format(ATTEMPTS_COUNT), 2)
	with open(OUTPUT_FILE, "w") as Fo:
		pass
	with open(INPUT_FILE, "r") as Fi:
		start_time = datetime.now()
		print_message("Start checking")
		print_message("{0:23} {1:8} {2:6} {3}".format("PROXY", "STATUS", "TOTAL", "COMMENT")) # HEADER
		proxies = list(Fi.readlines())
		for proxy in proxies:
			pool.apply_async(check, args=(proxy.strip(), total_good, total_bad, lock), callback=results_collectors)
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