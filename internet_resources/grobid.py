# -*- coding: utf-8 -*-
import os
import requests
import codecs
import logging
from datetime import datetime
import time
import json
#
from mtranslate import translate
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
    return utils.get_request("{}{}".format(GROBID_SERVER, command), POST=True, att_file={'input': pdf_file})


def processHeaderDocument(pdf_file_name):
#try:
    settings.print_message("Send to grobid service.", 2)
    data = get_data_from_grobid(GROBID_PROCESSED_HEADER_COMMAND, open(pdf_file_name, 'rb'))
    settings.print_message("Check data.", 2)
    logger.debug("Check data.")
    if not data: raise Exception("Empty data.")
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
    #settings.print_message(msg, 2)
    logger.debug(msg)
    return dictData
#except:
#    settings.print_message(traceback.format_exc())
#    logger.error(traceback.format_exc())


def processReferencesDocument(pdf_file_name):
#try:
    settings.print_message("Send to grobid service..", 2)
    data = get_data_from_grobid(GROBID_PROCESSED_REFERENCES_COMMAND, open(pdf_file_name, 'rb'))
    settings.print_message("Check data", 2)
    logger.debug("Check data")
    if not data: raise Exception("Empty data")
    settings.print_message("Processing TEI data", 2)
    logger.debug("Convert tei to dictionary")
    dictData = tei2dict.tei_to_dict(data)
    logger.debug("Convert completed: {}".format(json.dumps(dictData)))
    if not dictData["references"]:
        #settings.print_message("References are not available, skip", 2)
        logger.debug("References are not available, skip")
        return None
    return dictData["references"]
    #for i, reference in enumerate(dictData["references"]):
    #    try:
    #        if not reference["ref_title"] and not reference["journal_pubnote"]["journal_title"]:
    #            settings.print_message("Ref #{} (total {}) has not title, skip".format(i, len(dictData["references"])), 2)
    #            logger.debug("Ref #{} (total {}) has not title, skip".format(i, len(dictData["references"])))
    #            continue
    #        authors = set(reference["authors"]) if reference["authors"] else []
    #        count_publications_on_scholar = 0 #utils.get_count_from_scholar(reference["ref_title"].strip() if reference["ref_title"] else 
    #                   #reference["journal_pubnote"]["journal_title"].strip() if "journal_title" in reference["journal_pubnote"] else "", settings.USING_TOR_BROWSER)
    #        msg = "Ref #{} (total {}): has title:{:^3}has date:{:^3}Has DOI:{:^3}authors:{:^4}has start page:{:^3}has end page:{:^3}has publisher:{:^3}publications on scholar:{}".format(
    #            i,
    #            len(dictData["references"]),
    #            reference["ref_title"] != None or reference["journal_pubnote"]["journal_title"] != None,
    #            reference["journal_pubnote"]["year"] != None,
    #            reference["journal_pubnote"]["doi"] != None,
    #            len(authors),
    #            reference["journal_pubnote"]["start_page"] != None,
    #            reference["journal_pubnote"]["end_page"] != None,
    #            reference["journal_pubnote"]["journal_title"] != None,
    #            count_publications_on_scholar
    #            )
    #        settings.print_message(msg, 2)
    #        logger.debug(msg)
    #        row = list()
    #        row.append(os.path.split(pdf)[1])
    #        row.append(reference["ref_title"] if reference["ref_title"] else 
    #                   reference["journal_pubnote"]["journal_title"] if reference["journal_pubnote"]["journal_title"] else "")
    #        row.append(reference["journal_pubnote"]["year"] if reference["journal_pubnote"]["year"] else "")
    #        row.append(reference["journal_pubnote"]["doi"] if reference["journal_pubnote"]["doi"] else "")
    #        row.append(reference["journal_pubnote"]["start_page"] if reference["journal_pubnote"]["start_page"] else "")
    #        row.append(reference["journal_pubnote"]["end_page"] if reference["journal_pubnote"]["end_page"] else "")
    #        row.append(count_publications_on_scholar)
    #        for author in authors: row.append(author)
    #        logger.debug("Write in file {}".format(json.dumps(row)))
    #        wr.writerow(row)
    #    except:
    #        settings.print_message(traceback.format_exc())
    #        logger.error(traceback.format_exc())
#except:
#    settings.print_message(traceback.format_exc())
#    logger.error(traceback.format_exc())