# -*- coding: utf-8 -*-
import requests
import sys, traceback, logging, time
import re
import random
from urllib.parse import urlparse
#
import utils
import settings

_HOST = r"http://sci-hub.cc/"
_FULLURL = r"{0}{1}"

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def error_handler(error, response, url):
    """Check captcha, maybe it is the cause of the error"""
    if isinstance(error, utils.TypeError):
        soup = utils.get_soup(url)
        captcha = soup.find('img', id="captcha")
        if captcha != None and utils.handle_captcha(url) == "y": 
            return 3, True
    return 3, False
utils.add_exception_handler_if_not_exists(urlparse(_HOST).hostname, error_handler)

def get_pdf_url(DOI):
    """Get link to a PDF if this available"""
    logger.debug("Get page from sci-hub for paper with DOI={0}.".format(DOI))
    url = _FULLURL.format(_HOST, DOI)
    soup = utils.get_soup(url)
    captcha = soup.find('img', id="captcha")
    save_btn = soup.find('div', id = 'save')
    user_answer = None
    if captcha != None:
        user_answer = utils.handle_captcha(url)
        if user_answer == "y": return get_pdf_url(DOI)
    if save_btn == None or user_answer != None: 
        logger.debug("PDF for this paper is anavailable.")
        return None
    PDF_url = save_btn.find("a")["onclick"].split("href='")[1].strip("'")
    logger.debug("URL for PDF: {0}.".format(PDF_url))
    return PDF_url


def get_pdf(DOI, filename):
    """Load pdf for paper with DOI and save to file filename"""
    url = get_pdf_url(DOI)
    if url == None: return False
    try:
        settings.print_message("\tDownload pdf...")
        return utils.download_file(url, filename)
    except:
        logger.warn(traceback.format_exc())
        return False
    return True