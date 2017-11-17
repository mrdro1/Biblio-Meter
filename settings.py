# -*- coding: utf-8 -*-
import argparse
import collections
import os, logging, re, traceback, sys
import json
from datetime import datetime
#
_main_dir = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_main_dir, 'utils\\'))
sys.path.insert(0, os.path.join(_main_dir, 'entities\\'))
sys.path.insert(0, os.path.join(_main_dir, 'internet_resources\\'))
#
from dbutils import set_program_transaction, close_program_transaction, connect, close_connection

# Default browser
CHROME = 0
FIREFOX = 1
DEFAULT_BROWSER = CHROME

# encoding
OS_ENCODING = "utf-8"
OUTPUT_ENCODING = "utf-16"

# system settings
 #.decode(OS_ENCODING)
_DEFAULT_DB_FILE = "default.db"
_DB_FILE = os.path.join(_main_dir, _DEFAULT_DB_FILE)
_DEFAULT_LOGBOOK = "logbook.log"
_LOGBOOK_NAME = os.path.join(_main_dir, _DEFAULT_LOGBOOK)
_CONTROL_FILE = ""
_SUCCESSFUL_START_FLAG = False
_DEFAULT_PROXY_FILE = os.path.join(_main_dir, 'default\\proxies.txt')
PROXY_FILE = _DEFAULT_PROXY_FILE

INFORMATION_MODE = 1
TRANSACTION_MODE = 0
MODE = TRANSACTION_MODE
INFO_FILE = None

LOG_LEVEL = logging.DEBUG

RESULT = "SUCCESS"

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
    "max_google_papers",
    "google_clusters_handling",
    "google_captcha_retry_by_proxy_count",
    "researchgate_captcha_retry_by_proxy_count",
    "sci_hub_captcha_retry_by_proxy_count"
    ]
CONTROL_DEFAULT_VALUES = collections.defaultdict(lambda: str())
CONTROL_DEFAULT_VALUES["google_captcha_retry_by_proxy_count"] = 4
CONTROL_DEFAULT_VALUES["sci_hub_captcha_retry_by_proxy_count"] = 4
CONTROL_DEFAULT_VALUES["researchgate_captcha_retry_by_proxy_count"] = 4
'''temp_dict = {
    "query": '',
    "date_from": '',
    "date_to",
    "authored",
    "published",
    "exact_phrase",
    "one_of_words",
    "not_contained_words",
    "words_in_body",
    "patents",
    "citations",
    "max_google_papers",
    "google_captcha_retry_by_proxy_count": 4,
    "researchgate_captcha_retry_by_proxy_count": 4,
    "sci_hub_captcha_retry_by_proxy_count": 4
}'''


def CloseObjects():
    if _SUCCESSFUL_START_FLAG:
        # Register successfuly finish curent session
        close_program_transaction(RESULT)
    # Close db conn
    close_connection()
    # Close logbook file
    logger.info("Close logbook")
    _LOG_F_HANDLER.close()

# logging

# CONSOLE LOG
cfromat = "[{0}] {1}"
def print_message(message):
    print(cfromat.format(datetime.now(), message))
#
print_message("Initializing.")

# Logging handlers
class InMemoryHandler(logging.Handler):
    def emit(self, record):
        #print(self.format(record))
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

logger.info("Logger initialized")

# Command line parser
logger.info("Initializing argument parser, version: %s" % argparse.__version__)
_parser = argparse.ArgumentParser()
_parser.add_argument("-d", "--db", "--database", action="store", dest="DB_FILE_NAME", help="Database file", type=str)
_parser.add_argument("-l", "--log", "--logfile", action="store", dest="LOG_FILE_NAME", help="Logbook file", type=str)
_parser.add_argument("-c", "--control", "--controlfile", action="store", dest="CONTROL_FILE_NAME", help="Control file", type=str)
_parser.add_argument("-p", "--proxies", "--proxiesfile", action="store", dest="PROXIES_FILE", help="File with proxies", type=str)
_group = _parser.add_mutually_exclusive_group()
_group.add_argument("-t", action="store_false", dest="TransactionMode", help="Transaction mode")
_group.add_argument("-i", action="store_true", dest="InformationMode", help="Information mode")

logger.debug("Parse arguments.")

try:
    _command_args = _parser.parse_args()
    _DB_FILE = _DEFAULT_DB_FILE if _command_args.DB_FILE_NAME == None else _command_args.DB_FILE_NAME
    _LOGBOOK_NAME = _DEFAULT_LOGBOOK if _command_args.LOG_FILE_NAME == None else _command_args.LOG_FILE_NAME
    _CONTROL_FILE = "" if _command_args.CONTROL_FILE_NAME == None else _command_args.CONTROL_FILE_NAME
    MODE = INFORMATION_MODE if _command_args.InformationMode else TRANSACTION_MODE
    PROXY_FILE = _DEFAULT_PROXY_FILE if _command_args.PROXIES_FILE == None else _command_args.PROXIES_FILE
except:
    exit()

logger.info("Initializing logbook.")

# Add file handler
_LOG_F_HANDLER = logging.FileHandler(_LOGBOOK_NAME, encoding = OUTPUT_ENCODING)
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

# Database
try:
    connect(_DB_FILE)
except:
    logger.error(traceback.format_exc())
    CloseObjects()
    exit()
else:
    logger.info("DB connection initialized.")
if MODE == INFORMATION_MODE:
    INFO_FILE = InfoFile("{0}.{1}".format(os.path.splitext(_DB_FILE)[0], 'txt'))

DB_PATH = _main_dir
if os.path.split(_DB_FILE)[0] != "":
    DB_PATH = os.path.split(_DB_FILE)[0]

# Control file
logger.info("Parsing the control file.")
PARAMS = None
try:
    with open(_CONTROL_FILE) as data_file:    
        PARAMS = json.load(data_file)
    if not "command" in PARAMS:
        raise Exception()
    # check all params, if null then set default
    PARAMS = {key: PARAMS.setdefault(key, CONTROL_DEFAULT_VALUES[key]) for key in CONTROL_KEYS}
    #print(PARAMS)
except:
    print_message("Invalid file control. Check the syntax.")
    logger.error("Invalid file control. Check the syntax.")
    logger.error(traceback.print_exc())
    CloseObjects()
    exit()
else:
    logger.info("Parsing was successful.")
print_message("Parameters:")
for key in PARAMS.keys():
    print_message("  {0} = '{1}'".format(key, PARAMS[key]))
print_message("  File with proxies = '{0}'".format(PROXY_FILE))
_SUCCESSFUL_START_FLAG = True

# Register current session
set_program_transaction(PARAMS['command'], str(PARAMS))

# Register close-function
import atexit
atexit.register(CloseObjects)