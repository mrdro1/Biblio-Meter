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


def get_pdf_url(QUESTION):
    """Get link to a PDF if this available"""
    logger.debug("Get page from sci-hub for paper with question {0}.".format(QUESTION))
    url = _FULLURL.format(_HOST, QUESTION)
    soup = utils.get_soup(url, post=True, data={"request":QUESTION, "sci-hub-plugin-check":None})
    if not soup: return None
    captcha = soup.find('img', id="captcha")
    save_btn = soup.find('div', id='save')
    if not save_btn:
        buttons = soup.find('div', id='buttons')
        if buttons:
            save_btn = [i for i in buttons.find_all("a") if "хранить" in i.text]
            if save_btn: save_btn = save_btn[0]
    else:
        save_btn = save_btn.find("a")
    user_answer = None
    if captcha != None:
        utils.handle_captcha(url)
        return get_pdf_url(QUESTION)
    '''if save_btn == None or user_answer != None:
        logger.debug("PDF for this paper is unavailable.")
        return None'''


    if user_answer != None:
        logger.debug("PDF for this paper is unavailable.")
        return None
    if save_btn == None:
        return url


    PDF_url = save_btn["onclick"].split("href='")[1][:-1]
    if PDF_url.startswith("//"):
        PDF_url = PDF_url.replace("//", "https://")
    logger.debug("URL for PDF: {0}.".format(PDF_url))
    return PDF_url


def get_pdf(QUESTION, filename):
    """Load pdf for paper with QUESTION and save to file filename"""
    if not QUESTION: return None
    url = get_pdf_url(QUESTION)
    if url == None: return None
    try:
        settings.print_message("Download pdf from Sci-Hub by '{}'".format(QUESTION), 2)
        utils.download_file(url, filename) 
        return utils.check_pdf(filename)
    except KeyboardInterrupt:
        raise
    except:
        logger.warn(traceback.format_exc())
        #return False
        raise
    return 0