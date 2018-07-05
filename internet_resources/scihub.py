# -*- coding: utf-8 -*-
import requests
import sys, traceback, logging, time
import re
import random
from urllib.parse import urlparse
#
import utils
import settings

SCIHUB_HOST_NAME = 'sci-hub.tw'
_HOST = r"http://{0}/".format(SCIHUB_HOST_NAME)
_FULLURL = r"{0}{1}"

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def get_pdf_url(DOI):
    """Get link to a PDF if this available"""
    logger.debug("Get page from sci-hub for paper with DOI={0}.".format(DOI))
    url = _FULLURL.format(_HOST, DOI)
    soup = utils.get_soup(url)
    captcha = soup.find('img', id="captcha")
    save_btn = soup.find('div', id='save')
    user_answer = None
    if captcha != None:
        utils.handle_captcha(url)
        return get_pdf_url(DOI)
    '''if save_btn == None or user_answer != None:
        logger.debug("PDF for this paper is anavailable.")
        return None'''


    if user_answer != None:
        logger.debug("PDF for this paper is anavailable.")
        return None
    if save_btn == None:
        return url


    PDF_url = save_btn.find("a")["onclick"].split("href='")[1].strip("'")
    if PDF_url.startswith("//"):
        PDF_url = PDF_url.replace("//", "https://")
    logger.debug("URL for PDF: {0}.".format(PDF_url))
    return PDF_url


def get_pdf(DOI, filename):
    """Load pdf for paper with DOI and save to file filename"""
    if not DOI: return False
    url = get_pdf_url(DOI)
    if url == None: return False
    try:
        settings.print_message("Download pdf from Sci-Hub by '{}'".format(DOI), 2)
        utils.download_file(url, filename) 
        return utils.check_pdf(filename)
    except:
        logger.warn(traceback.format_exc())
        #return False
        raise
    return True