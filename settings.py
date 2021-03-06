# -*- coding: utf-8 -*-
import argparse
import collections
import os
import logging
import re
import traceback
import sys
import json
from datetime import datetime
import re
import subprocess
from math import inf
#
MAIN_DIR = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(MAIN_DIR, 'utils/'))
sys.path.insert(0, os.path.join(MAIN_DIR, 'model/'))
sys.path.insert(0, os.path.join(MAIN_DIR, 'captcha/'))
sys.path.insert(0, os.path.join(MAIN_DIR, 'entities/'))
sys.path.insert(0, os.path.join(MAIN_DIR, 'internet_resources/'))
#
from dbutils import set_program_transaction, close_program_transaction, connect, \
    close_connection


def build_version_string():
    """ This function read current version from version.txt and format version string """
    # MAJOR version when you make incompatible API changes
    __MAJOR_VERSION__ = str()
    # MINOR version when you add functionality in a backwards-compatible manner
    __MINOR_VERSION__ = str()
    # PATCH version when you make backwards-compatible bug fixes
    __PATCH_VERSION__ = str()
    with open('version.txt', 'r') as version_file:
        lines = version_file.readlines()
        for line in lines:
            if line.startswith('__MAJOR_VERSION__'):
                __MAJOR_VERSION__ = re.findall('\d+', line)[0]
            if line.startswith('__MINOR_VERSION__'):
                __MINOR_VERSION__ = re.findall('\d+', line)[0]
            if line.startswith('__PATCH_VERSION__'):
                __PATCH_VERSION__ = re.findall('\d+', line)[0]
    _header = "BiblioMeter (v{0}.{1}.{2}) {3}".format(__MAJOR_VERSION__, __MINOR_VERSION__, __PATCH_VERSION__,
                                                      datetime.now().strftime("%B %d %Y, %H:%M:%S"))
    return _header


# Program version
_header = build_version_string()

# Path to web driver
PATH_TO_WEB_DRIVER = 'chromedriver.exe'

# Default browser
CHROME = 0
FIREFOX = 1
DEFAULT_BROWSER = CHROME

# encoding
OS_ENCODING = "utf-8"
OUTPUT_ENCODING = "utf-16"

# system settings
_DB_FILE = None
_LOGBOOK_NAME = None
_CONTROL_FILE = None
PROXY_FILE = None
_SUCCESSFUL_START_FLAG = False

DIR_CAPTCHA_IMG = r"captcha/"
if not os.path.exists(DIR_CAPTCHA_IMG):
    os.mkdir(DIR_CAPTCHA_IMG)
if not os.path.exists(DIR_CAPTCHA_IMG + "tmp/"):
    os.mkdir(DIR_CAPTCHA_IMG + "tmp/")
if not os.path.exists(DIR_CAPTCHA_IMG + "symbols/"):
    os.mkdir(DIR_CAPTCHA_IMG + "symbols/")

MIN_PROXIES_COUNT = 20
DEFAULT_TIMEOUT = 10
DEFAULT_CONN_ATTEMPTS = 5
DEFAULT_DISCONNECTION_TIMEOUT = 15
DEFAULT_REQUESTS_TIMEOUT = 1.0
LOG_LEVEL = logging.DEBUG

RESULT = "SUCCESS"
DESCR_TRANSACTION = None

CONTROL_KEYS = [
    "command",
    "query",
    "date_from",
    "date_to",
    "authored",
    "published",
    "exact_phrase",
    "one_of_words",
    "not_contained_words",
    "words_in_body",
    "patents",
    "citations",
    "papers",
    "connection_attempts",
    "disconnection_timeout",
    "max_tree_level",
    "max_cited_papers",
    "commit_iterations",
    "http_contiguous_requests",
    "limit_resp_for_one_code",
    "start_paper",
    "google_max_papers",
    "google_get_files",
    "google_cluster_files",
    "google_max_papers_for_identification",
    "sci_hub_files",
    "sci_hub_download_captcha",
    "sci_hub_show_captcha",
    "sci_hub_timeout",
    "sci_hub_capcha_autosolve",
    "sci_hub_title_search",
    "max_references_per_paper",
    "open_browser_if_captcha",
    "google_get_files_through_proxy",
    "crossref_max_papers",
    "authors",
    "google_count_endnotes_for_best",
]

CONTROL_DEFAULT_VALUES = collections.defaultdict(lambda: str())
CONTROL_DEFAULT_VALUES = \
    {

    }


def CloseObjects():
    if _SUCCESSFUL_START_FLAG:
        # Register successfuly finish curent session
        close_program_transaction(RESULT, DESCR_TRANSACTION)
    # Close db conn
    close_connection()
    # Close logbook file
    logger.info("Close logbook")
    _LOG_F_HANDLER.close()

# logging


# CONSOLE LOG
cfromat = "[{time}] {spaсe_level}{msg}"


def print_message(message, level=0, end=None):
    level_indent = " " * level
    try:
        print(
            cfromat.format(
                time=datetime.now(),
                spaсe_level=level_indent,
                msg=message),
            end=end)
    except BaseException:
        logger.error(
            "Message can not be displayed because the encoding is not supported.")
        logger.error(traceback.print_exc())
        print(
            cfromat.format(
                time=datetime.now(),
                spaсe_level=level_indent,
                msg="Message can not be displayed because the encoding is not supported."))
#

# Logging handlers


class InMemoryHandler(logging.Handler):
    def emit(self, record):
        # print(self.format(record))
        IN_MEMORY_LOG.append(self.format(record))


_LOG_HANDLER = InMemoryHandler()
_LOG_FORMAT = "[%(asctime)s %(levelname)s %(name)s] %(message)s"
_LOG_COPY_FORMAT = "%(message)s"
_LOG_HANDLER.setFormatter(logging.Formatter(_LOG_FORMAT))

IN_MEMORY_LOG = []

main_logger = logging.getLogger("")

main_logger.addHandler(_LOG_HANDLER)
main_logger.setLevel(LOG_LEVEL)

logger = logging.getLogger(__name__)

print_message(_header)
logger.info(_header)

# Command line parser
logger.info("Initializing argument parser, version: %s" % argparse.__version__)
_parser = argparse.ArgumentParser()
requiredNamed = _parser.add_argument_group('Required arguments')
requiredNamed.add_argument(
    "-d",
    "--database",
    action="store",
    dest="DB_FILE_NAME",
    help="Database file",
    type=str,
    required=True)
requiredNamed.add_argument(
    "-l",
    "--log",
    action="store",
    dest="LOG_FILE_NAME",
    help="Logbook file",
    type=str,
    required=True)
requiredNamed.add_argument(
    "-c",
    "--control",
    action="store",
    dest="CONTROL_FILE_NAME",
    help="Control file",
    type=str,
    required=True)
requiredNamed.add_argument(
    "-p",
    "--proxies",
    action="store",
    dest="PROXIES_FILE",
    help="File with proxies",
    type=str,
    required=True)
#_group = _parser.add_mutually_exclusive_group()
#_group.add_argument("-t", action="store_false", dest="TransactionMode", help="Transaction mode")
#_group.add_argument("-i", action="store_true", dest="InformationMode", help="Information mode")

logger.debug("Parse arguments.")

_command_args = _parser.parse_args()
_DB_FILE = _command_args.DB_FILE_NAME
_LOGBOOK_NAME = _command_args.LOG_FILE_NAME
_CONTROL_FILE = _command_args.CONTROL_FILE_NAME
PROXY_FILE = _command_args.PROXIES_FILE
#MODE = INFORMATION_MODE if _command_args.InformationMode else TRANSACTION_MODE

logger.info("Initializing logbook.")

# Add file handler
_LOG_F_HANDLER = logging.FileHandler(_LOGBOOK_NAME, encoding=OUTPUT_ENCODING)
_LOG_F_HANDLER.setLevel(LOG_LEVEL)
_LOG_F_FORMATTER = logging.Formatter(_LOG_COPY_FORMAT)
_LOG_F_HANDLER.setFormatter(_LOG_F_FORMATTER)

logger.debug("Copy startlog in logbook.")
main_logger.removeHandler(_LOG_HANDLER)
main_logger.addHandler(_LOG_F_HANDLER)
for record in IN_MEMORY_LOG:
    logger.info(record)

_LOG_F_FORMATTER = logging.Formatter(_LOG_FORMAT)
_LOG_F_HANDLER.setFormatter(_LOG_F_FORMATTER)

# Control file
logger.info("Parsing the control file.")
PARAMS = None
try:
    with open(_CONTROL_FILE) as data_file:
        PARAMS = json.load(data_file)
    for key in PARAMS.keys():
        if not key in CONTROL_KEYS:
            raise Exception("Unknown parameter: {0}".format(key))
    # check all params, if null then set default
    for key in CONTROL_DEFAULT_VALUES.keys():
        PARAMS.setdefault(key, CONTROL_DEFAULT_VALUES[key])
    if not [key for key in PARAMS.keys() if key.lower() == "command"]:
        raise Exception("Command is empty!")
except BaseException:
    print_message("Invalid file control. Check the syntax.")
    logger.error("Invalid file control. Check the syntax.")
    logger.error(traceback.print_exc())
    CloseObjects()
    exit()
else:
    logger.info("Parsing was successful.")
print_message("Parameters:")
logger.debug("Parameters:")
for key in PARAMS.keys():
    param_str = "  {0} = '{1}'".format(key, PARAMS[key])
    print_message(param_str)
    logger.debug(param_str)

# Database
try:
    if PARAMS["command"] != "getPapersByKeyWords" and not os.path.isfile(
            _DB_FILE):
        raise Exception("Database '{}' not found.".format(_DB_FILE))
    connect(_DB_FILE)
except BaseException:
    print_message(
        "Database '{}' is invalid, for more information see log.".format(_DB_FILE))
    logger.error(traceback.format_exc())
    CloseObjects()
    exit()
else:
    logger.info("DB connection initialized.")
# if MODE == INFORMATION_MODE:
#    INFO_FILE = InfoFile("{0}.{1}".format(os.path.splitext(_DB_FILE)[0], 'txt'))

DB_PATH = MAIN_DIR
if os.path.split(_DB_FILE)[0] != "":
    DB_PATH = os.path.split(_DB_FILE)[0]

# DEFINE PDF CATALOG AND CREATE IF NOT EXISTS
logger.debug("Check catalog for PDFs.")
PDF_CATALOG = os.path.splitext(os.path.split(_DB_FILE)[-1])[0] + "_PDF/"
try:
    if not os.path.exists(PDF_CATALOG):
        logger.debug("Create folder {}.".format(PDF_CATALOG))
        os.mkdir(PDF_CATALOG)
except BaseException:
    logger.error(traceback.format_exc())
    CloseObjects()
    exit()

_SUCCESSFUL_START_FLAG = True
# Register current session
set_program_transaction(PARAMS['command'], str(PARAMS))

# Register close-function
import atexit
atexit.register(CloseObjects)
