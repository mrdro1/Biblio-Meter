# -*- coding: utf-8 -*-
import requests
import sys
import traceback
import logging
import time
from mtranslate import translate
import json
import re
import RISparser
import random
from urllib.parse import urlparse
#
import utils
import settings
import stopwords

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

_HOST = r"https://www.researchgate.net/"
_PUBSEARCH = r'search/publications?q={0}&page={1}'
_FULLURL = r'{0}{1}'
_WORDUNION = "%252B"
_BLOCKUNION = "%252C"
_PUBLICATIONPAGE = r'publication/{0}'
_PUBREFERENCESDATA = r'publicliterature.PublicPublicationReferenceList.html?publicationUid={0}&initialDisplayLimit=1000&loadMoreCount=1000'
_PUBRISDATA = r"publicliterature.PublicationHeaderDownloadCitation.downloadCitation.html?publicationUid={0}&fileType=RIS&citationAndAbstract=true"
_AUTHORSLISTDATA = r"publicliterature.PublicationAuthorList.loadMore.html?publicationUid={0}&offset={1}&count={2}"
_AUTHORDATA = r"publicprofile.ProfileHighlightsStats.html?accountId={0}"
_RGIDRE = r"\/[0-9]+_"

# init proxy
_PROXY_OBJ = utils.ProxyManager()


def error_handler(error, response, url):
    """Handle exception"""
    if response is not None:
        if response.status_code == 429:
            answ = input("Skip researchgate stage for this paper? [y/n/a]:")
            if answ == 'n':
                _PROXY_OBJ.set_next_proxy()  # change current proxy in HTTP_PARAMS
                return 1, _PROXY_OBJ.get_cur_proxy()
            elif answ == 'y':
                utils.RG_stage_is_skipped()
                return 3, None
            elif answ == 'a':
                utils.skip_RG_stage_for_all()
                return 3, None
    return 4, None


utils.add_exception_handler_if_not_exists(
    urlparse(_HOST).hostname, error_handler)


def get_query_soup(params):
    """Return resulting soup"""
    #   DEBUG messages
    logger.debug("Proceed stop word list for title '%s'." % params["title"])
    logger.debug(
        "Title without stop words: '%s'" %
        stopwords.delete_stopwords(
            params["title"], " "))
    logger.debug(
        "Title with logical conditions: '%s'" %
        stopwords.delete_stopwords(
            params["title"], " and "))
    #
    url = _PUBSEARCH.format(
        requests.utils.quote(
            stopwords.delete_stopwords(
                params["title"], " and ")), 1)
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, url))
    soup = utils.get_soup(
        _FULLURL.format(
            _HOST,
            url),
        _PROXY_OBJ.get_cur_proxy())
    return soup


def identification_and_fill_paper(params, query_soup=None, delay=0):
    """Search papers on researchgate and fill the data about it"""
    paper_info_url = None
    try:
        # Delay about Delay seconds for hide 429 error.
        timeout = random.uniform(0, delay)
        logger.debug("Sleep {0} seconds.".format(timeout))
        time.sleep(timeout)
        paper_info_url = _ident_and_fill_paper(
            get_query_soup(params) if query_soup is None else query_soup, params)
    except Exception as error:
        logger.warn(traceback.format_exc())
    return paper_info_url


def get_rg_paper_id_from_url(url):
    res = None
    try:
        res = re.findall(_RGIDRE, url)[0].strip("/_")
    except Exception as error:
        logger.warn(traceback.format_exc())
    return res


def _ident_and_fill_paper(soup, params):
    """Return paper info"""
    pagenum = 1
    papers_count = 0
    qtext = requests.utils.quote(
        stopwords.delete_stopwords(
            params["title"], " and "))
    # DEBUG messages
    #logger.debug("Proceed stop word list for title '%s'" % params["title"])
    #logger.debug("Title without stop words: '%s'" % stopwords.delete_stopwords(params["title"], " "))
    #logger.debug("Title with logical conditions: '%s'" % stopwords.delete_stopwords(params["title"], " and "))
    ##
    while True:
        logger.debug(
            "Find papers on page #%i (max_researchgate_papers=%i)" %
            (pagenum, params["max_researchgate_papers"]))
        if soup.find('div', class_='search-noresults-headline') is not None:
            logger.debug("This paper not found in researchgate.")
            return None
        logger.debug("Parse html and get info about papers.")
        papers_box = soup.find_all('div', 'publication-item')
        logger.debug(
            "On resulting page #%i found %i papers." %
            (pagenum, len(papers_box)))
        on_page_paper_count = 0
        for papers_item in papers_box:
            if papers_count > params["max_researchgate_papers"]:
                logger.debug("This paper not found in researchgate.")
                return None
            try:
                on_page_paper_count += 1
                papers_count += 1
                # Get info about paper
                authors = len(papers_item.find_all("span", itemprop="name"))
                year = int(
                    papers_item.find(
                        'div',
                        class_='publication-metadata').find('span').text.split()[1])
                title = papers_item.find(
                    "a", class_="publication-title").text.strip().lower()
                type = papers_item.find(
                    'div', class_='publication-type').text.strip().lower()
                logger.debug(
                    "Process paper #%i (title='%s'; year=%i; auth_count=%i; type='%s')" %
                    (papers_count, title, year, authors, type))
                logger.debug("Title and year check.")
                # First compare
                if params["year"] != year:
                    logger.debug(
                        "Year of paper #%i does not coincide with the year of the required paper, skipped." %
                        (on_page_paper_count))
                elif params["title"] != title:
                    logger.debug(
                        "Title of paper #%i does not coincide with the title of the required paper, skipped." %
                        (on_page_paper_count))
                # Second compare
                else:
                    logger.debug(
                        "The title and year of the paper coincided, identification of information from the RIS.")
                    timeout = random.uniform(0, 3)
                    logger.debug("Sleep {0} seconds.".format(timeout))
                    time.sleep(timeout)
                    paper_url = _FULLURL.format(
                        _HOST, papers_item.find(
                            "a", class_="publication-title")["href"])
                    logger.debug(
                        "Process RIS for paper #%i." %
                        on_page_paper_count)
                    rg_paper_id = get_rg_paper_id_from_url(paper_url)
                    info = get_info_from_RIS(rg_paper_id)
                    if params["authors_count"] != len(info['authors']):
                        logger.debug(
                            "Count of author of paper #%i does not coincide with the count of author of the required paper, skipped." %
                            (on_page_paper_count))
                    elif 'start_page' in info and params["spage"] is not None and str(params["spage"]) != info['start_page']:
                        logger.debug(
                            "Start page of paper #%i does not coincide with the start page of the required paper, skipped." %
                            (on_page_paper_count))
                    elif 'end_page' in info and params["epage"] is not None and str(params["epage"]) != info['end_page']:
                        logger.debug(
                            "End page of paper #%i does not coincide with the end page of the required paper, skipped." %
                            (on_page_paper_count))
                    else:
                        logger.debug(
                            "Paper #%i was identified with EndNote file #%i." %
                            (on_page_paper_count, params["paper_version"]))
                        logger.debug(
                            "EndNote file #%i:\n%s" %
                            (params["paper_version"], params["EndNote"]))
                        logger.debug("RIS file:\n%s" % info["RIS"])
                        paper_url = _FULLURL.format(
                            _HOST, papers_item.find(
                                "a", class_="publication-title")["href"])
                        type = papers_item.find(
                            'div', class_='publication-type').text.strip().lower()
                        info = get_paper_info_from_dataRIS(info, rg_paper_id)
                        info.update({
                            "rg_type": type,
                            "url": paper_url,
                        })
                        # Get authors
                        #logger.debug("Get authors list")
                        #auth_list = get_authors(info["rg_id"])
                        # Get author info
                        # for author in auth_list:
                        #    if author["accountId"] != None:
                        #        logger.debug("Get more info for author with rg_account_id={0}".format(author["accountId"]))
                        #        author_info = get_auth_info(author["accountId"])
                        #        author.update(author_info)
                        #info.update({"authors" : auth_list})
                        return info
            except Exception as error:
                logger.warn(traceback.format_exc())
        if len(papers_box) >= 10:
            pagenum += 1
            logger.debug("Load next page in resulting query selection.")
            # Delay about Delay seconds for hide 429 error.
            timeout = random.uniform(1, 2)
            logger.debug("Sleep {0} seconds.".format(timeout))
            time.sleep(timeout)
            qtext = requests.utils.quote(
                stopwords.delete_stopwords(
                    params["title"], " and "))
            #   DEBUG messages
            logger.debug(
                "Proceed stop word list for title '%s'." %
                params["title"])
            logger.debug(
                "Title without stop words: '%s'." %
                stopwords.delete_stopwords(
                    params["title"], " "))
            logger.debug(
                "Title with logical conditions: '%s'." %
                stopwords.delete_stopwords(
                    params["title"], " and "))
            #
            url = _PUBSEARCH.format(qtext, pagenum)
            soup = utils.get_soup(
                _FULLURL.format(
                    _HOST,
                    url),
                _PROXY_OBJ.get_cur_proxy())
        else:
            logger.debug("This paper not found in researchgate.")
            return None


def get_paper_info_from_html(PaperURL):
    """Fill the data about paper"""
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, PaperURL))
    soup = utils.get_soup(PaperURL, _PROXY_OBJ.get_cur_proxy())
    res = dict()
    logger.debug("Parse paper string and get information.")
    details_soup = soup.find('div', class_='public-publication-details-top')
    res["type"] = details_soup.find(
        'strong', class_='publication-meta-type').text.strip().lower().rstrip(':')
    res["title"] = details_soup.find(
        'h1', class_='publication-title').text.strip()
    res["abstract"] = details_soup.find(
        'div', class_='publication-abstract').find_all('div')[1].text.strip()
    meta_sec = details_soup.find(
        'div', class_='publication-meta-secondary').text.split()
    if meta_sec[0] == "DOI:":
        res["doi"] = meta_sec[1]
    logger.debug("Translate abstract.")
    try:
        res["abstract_ru"] = translate(res["abstract"], 'ru')
    except Exception as error:
        logger.warn(traceback.format_exc())
    logger.debug("Get references count.")
    rg_paper_id = soup.find('meta', property="rg:id")['content'][3:]
    res["rg_id"] = rg_paper_id
    ref_dict = get_referring_papers(rg_paper_id)
    if ref_dict is not None and len(ref_dict) > 0:
        #res["references"] = ref_dict
        res["references_count"] = len(ref_dict)
        logger.debug("References count: %i." % res["references_count"])
    return res


def get_paper_info_from_RIS(rg_paper_id):
    get_paper_info_from_dataRIS(get_info_from_RIS(rg_paper_id), rg_paper_id)


def get_paper_info_from_dataRIS(RIS_data, rg_paper_id):
    res = dict()
    logger.debug("Parse paper string and get information.")
    if RIS_data is None:
        return None
    res.update(RIS_data)
    logger.debug("Translate abstract.")
    try:
        res["abstract_ru"] = translate(res["abstract"], 'ru')
    except Exception as error:
        logger.warn(traceback.format_exc())
    logger.debug("Get references.")
    res["rg_id"] = rg_paper_id
    ref_dict = get_referring_papers(rg_paper_id)
    if len(ref_dict) > 0:
        res["references"] = ref_dict
        res["references_count"] = len(ref_dict)
    return res


def get_info_from_RIS(rg_paper_id):
    """Get RIS file for paper with rg_paper_id"""
    logger.debug(
        "Downloading RIS data about paper. RGID={0}.".format(rg_paper_id))
    data = utils.get_json_data(
        _FULLURL.format(
            _HOST,
            _PUBRISDATA.format(rg_paper_id)),
        _PROXY_OBJ.get_cur_proxy()).replace(
            "\r",
        "")
    logger.debug("RIS file:\n%s" % data)
    logger.debug("Parse RIS data.")
    res = None
    try:
        if data is None:
            logger.debug("RIS data is empty.")
            return res
        datalines = data.split("\n")
        RISgenerator = RISparser.read(datalines)
        res = next(RISgenerator)
        if "doi" in res and not utils.is_doi(res["doi"]):
            res.pop("doi")
        res["RIS"] = data
    except BaseException:
        logger.warn(traceback.format_exc())
    return res


def get_referring_papers(rg_paper_id):
    """Get references dict for paper with rg_paper_id"""
    logger.debug("Downloading the list of referring articles.")
    ref_url = _PUBREFERENCESDATA.format(rg_paper_id)
    url = _FULLURL.format(_HOST, ref_url)
    try:
        req_result = utils.get_json_data(url, _PROXY_OBJ.get_cur_proxy())
        logger.debug("Parse host answer from json.")
        dict_req_result = json.loads(req_result)
    except BaseException:
        logger.warn(traceback.format_exc())
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return dict_req_result['result']['state']['publicliteratureReferences']['itemEntities']
    logger.debug("Data is not correct.")
    return None


def get_authors(rg_paper_id):
    """Get authors for paper with rg_paper_id"""
    logger.debug("Get authors for paper.")
    ref_url = _AUTHORSLISTDATA.format(rg_paper_id, 0, 100)
    url = _FULLURL.format(_HOST, ref_url)
    try:
        req_result = utils.get_json_data(url, _PROXY_OBJ.get_cur_proxy())
        logger.debug("Parse host answer from json.")
        dict_req_result = json.loads(req_result)
    except BaseException:
        logger.warn(traceback.format_exc())
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return dict_req_result['result']['loadedItems']
    logger.debug("Data is not correct.")
    return None


def get_auth_info(rg_account_id):
    """Get info about author with account_id"""
    logger.debug("Downloading the auth info.")
    ref_url = _AUTHORDATA.format(rg_account_id)
    url = _FULLURL.format(_HOST, ref_url)
    try:
        req_result = utils.get_json_data(url, _PROXY_OBJ.get_cur_proxy())
        logger.debug("Parse host answer from json.")
        dict_req_result = json.loads(req_result)
    except BaseException:
        logger.warn(traceback.format_exc())
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return dict_req_result['result']['data']
    logger.debug("Data is not correct.")
    return None


def get_pdf_url(rg_paper_id):
    """Get link to a PDF if this available"""
    logger.debug(
        "Get page from researchgate for paper with RGID={0}.".format(rg_paper_id))
    ref_url = _PUBLICATIONPAGE.format(rg_paper_id)
    url = _FULLURL.format(_HOST, ref_url)
    soup = utils.get_soup(url, _PROXY_OBJ.get_cur_proxy())
    logger.debug("Parse paper string and get information.")
    details_soup = soup.find(
        'div', class_='publication-resources-summary--action-container')
    load_button = [i for i in details_soup.find_all(
        "a") if "publication-header-full-text" in i.attrs['class']]
    if load_button == []:
        logger.debug("PDF for this paper is anavailable.")
        return None
    PDF_url = _FULLURL.format(_HOST, load_button[0]["href"].strip())
    logger.debug("URL for PDF: {0}.".format(PDF_url))
    return PDF_url


def get_pdf(rg_paper_id, filename):
    """Load pdf for paper with rg_paper_id and save to file filename"""
    url = get_pdf_url(rg_paper_id)
    if url is None:
        return False
    try:
        settings.print_message("\tDownload pdf...")
        return utils.download_file(url, filename)
    except BaseException:
        logger.warn(traceback.format_exc())
        return False
    return True
