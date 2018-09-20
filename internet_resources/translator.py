# -*- coding: utf-8 -*-
import sys
import re
import traceback
import logging
#
import settings
import utils

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

GOOGLE_TRANSLATE_URL = r"http://translate.google.com/m?hl={}&sl={}&q={}"


def translate(to_translate, to_language="auto", from_language="auto"):
    """ Returns the translation using google translate """
    soup = utils.get_soup(
        GOOGLE_TRANSLATE_URL.format(
            to_language,
            from_language,
            to_translate))
    result = None
    try:
        result = soup.find(class_='t0').string
    except BaseException:
        logger.debug("Tanslate error.")
        logger.error(traceback.format_exc())
    return result
