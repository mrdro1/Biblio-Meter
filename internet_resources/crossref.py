# -*- coding: utf-8 -*-
import os
import requests
import codecs
import logging
from datetime import datetime
import time
import json
#
import tei2dict
import settings
import utils
import traceback

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_DOI_by_title(title):
    pass