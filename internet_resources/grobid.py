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

GROBID_SERVER = 'http://cloud.science-miner.com/grobid/api/'
GROBID_PROCESSED_HEADER_COMMAND = 'processHeaderDocument'
GROBID_PROCESSED_REFERENCES_COMMAND = 'processReferences'
GROBID_PROCESSED_FULL_TEXT_COMMAND = 'processFulltextDocument'

class GrobidError(Exception): pass

class ConnectionError(Exception): pass


def get_data_from_grobid(command, pdf_file):
    """ Send post request to grobid and returned data """
    return utils.get_request("{}{}".format(GROBID_SERVER, command), POST=True, att_file={'input': pdf_file}, timeout=30, data={"timeout":300})


def processHeaderDocument(pdf_file_name):
    settings.print_message("Send to grobid service.", 2)
    data = get_data_from_grobid(GROBID_PROCESSED_HEADER_COMMAND, open(pdf_file_name, 'rb'))
    settings.print_message("Check data.", 2)
    logger.debug("Check data.")
    if not data: 
        logger.debug("Server returned empty response (File processing failed), skip.")
        return None
    settings.print_message("Processing TEI data.", 2)
    logger.debug("Convert tei to dictionary.")
    dictData = tei2dict.tei_to_dict(data)
    logger.debug("Convert completed: {}".format(json.dumps(dictData)))
    authors = set(dictData["authors"]) if dictData["authors"] else []
    msg = "RESULT: has title:{:^3}has date:{:^3}has DOI:{:^3}has abstract:{:^3}authors:{:^4}has start page:{:^3}has end page:{:^3}has publisher:{:^3}".format(
        dictData["title"] != None,
        dictData["pubdate"] != None,
        dictData["DOI"] != None,
        dictData["abstract"] != None,
        len(authors),
        dictData["start_page"] != None,
        dictData["end_page"] != None,
        dictData["publisher"] != None
        )
    dictData["abstract_ru"] = None
    logger.debug(msg)
    return dictData


def processReferencesDocument(pdf_file_name):
    settings.print_message("Send to grobid service..", 2)
    data = get_data_from_grobid(GROBID_PROCESSED_REFERENCES_COMMAND, open(pdf_file_name, 'rb'))
    settings.print_message("Check data", 2)
    logger.debug("Check data")
    if not data: 
        logger.debug("Server returned empty response (File processing failed), skip.")
        return None
    settings.print_message("Processing TEI data", 2)
    logger.debug("Convert tei to dictionary")
    dictData = tei2dict.tei_to_dict(data)
    logger.debug("Convert completed: {}".format(json.dumps(dictData)))
    if not dictData["references"]:
        logger.debug("References are not available, skip")
        return None
    return dictData["references"]
