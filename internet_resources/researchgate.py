# -*- coding: utf-8 -*-
import requests
import sys, traceback, logging, time
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
_PUBSEARCH = r'publicbrowse.SearchItemsList.html?query[0]={0}&type=publications&page={1}'
_SEARCHBYDOI = r'search?q={0}'
_FULLURL = r'{0}{1}'
_WORDUNION = "%252B"
_BLOCKUNION = "%252C"
_PUBLICATIONPAGE = r'publication/{0}'
_REFINFO = r'publicliterature.PublicationResourceTabBox.html?publicationUid={0}&showLiteratureReviewInfo=1'
_PUBREFERENCESDATA = r'publicliterature.PublicPublicationReferenceList.html?publicationUid={0}&initialDisplayLimit={1}'
_PUBCITEDSDATA = r'publicliterature.PublicationCitationList.html?publicationUid={0}&initialDisplayLimit={1}'
_PUBRISDATA = r"publicliterature.PublicationHeaderDownloadCitation.downloadCitation.html?publicationUid={0}&fileType=RIS&citationAndAbstract=true"
_AUTHORSLISTDATA = r"publicliterature.PublicationAuthorList.loadMore.html?publicationUid={0}&offset={1}&count={2}"
_AUTHORDATA = r"publicprofile.ProfileHighlightsStats.html?accountId={0}"
_RGIDRE = r"\/[0-9]+_"


def paper_search_by_DOI(DOI):
    url = _FULLURL.format(_HOST, _SEARCHBYDOI.format(DOI))
    logger.debug("Get paper by DOI {0} from '{1}'.".format(DOI, url))
    resp = utils.get_request(url, True)
    if  resp != None and resp.request.url != url:
        return get_rg_paper_id_from_url(resp.request.url)
    return None


def get_info_about_ref_and_citations(rg_paper_id):
    url = _FULLURL.format(_HOST, _REFINFO.format(rg_paper_id))
    logger.debug("Get info about references and cities for paper RGID='{0}'.".format(rg_paper_id))
    try:
        dict_req_result = utils.get_json_data(url)
    except:
        raise
    if dict_req_result == None: 
        logger.debug("Data is empty.")
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return {
                'citationsCount' : dict_req_result['result']['data']['citationsCount'], 
                'referencesCount' : dict_req_result['result']['data']['referencesCount']
               }
    logger.debug("Data is not correct.")
    return None


def get_query_json(params):
    """Return resulting json"""
    #   DEBUG messages
    logger.debug("Proceed stop word list for title '%s'." % params["title"])
    logger.debug("Title without stop words: '%s'" % stopwords.delete_stopwords(params["title"], " "))
    logger.debug("Title with logical conditions: '%s'" % stopwords.delete_stopwords(params["title"], " and "))
    #
    url = _PUBSEARCH.format(requests.utils.quote(stopwords.delete_stopwords(params["title"], " and ")), 1)
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, url))
    json_query_result = utils.get_json_data(_FULLURL.format(_HOST, url))
    return json_query_result


def identification_and_fill_paper(params, query_json = None, delay=0):
    """Search papers on researchgate and fill the data about it"""
    paper_info_url = None
    try:
        paper_info_url = _ident_and_fill_paper(
            get_query_json(params) if query_json == None else query_json, params)
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    return paper_info_url


def get_rg_paper_id_from_url(url):
    res = None
    try:
        res = re.findall(_RGIDRE, url)[0].strip("/_")
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    return res


def fill_paper(src_info, rg_paper_id):
    info = src_info
    logger.debug("Translate abstract.")
    if "abstract" in info:
        try:
            info["abstract_ru"] = translate(info["abstract"], 'ru')
        except Exception as error:
            #logger.warn(traceback.format_exc())
            raise
    logger.debug("Get references.")
    info["rg_id"] = rg_paper_id

    len_ref_info = get_info_about_ref_and_citations(rg_paper_id)
    if len_ref_info != None:
        info["references_count"] = len_ref_info["referencesCount"]
    return info


def _ident_and_fill_paper(json_query_result, params):
    """ Return paper info """
    if json_query_result == None:
        logger.debug("This paper not found in researchgate.")
        return None
    pagenum = 1
    papers_count = 0
    qtext = requests.utils.quote(stopwords.delete_stopwords(params["title"], " and "))
    while True:
        logger.debug("Find papers on page #%i (max_researchgate_papers=%i)" % (pagenum, params["max_researchgate_papers"]))
        if len(json_query_result['result']['data']['items']) == 0:
                logger.debug("This paper not found in researchgate.")
                return None
        logger.debug("Parse html and get info about papers.")
        papers_box = json_query_result['result']['data']['items']
        logger.debug("On resulting page #%i found %i papers." % (pagenum, len(papers_box)))
        on_page_paper_count = 0
        for papers_item in papers_box:
            if papers_count > params["max_researchgate_papers"]:
                logger.debug("This paper not found in researchgate.")
                return None
            try:
                #on_page_paper_count += 1
                papers_count += 1
                # Get info about paper
                year = int(papers_item['data']['publicationDate'].split(' ')[3]) 
                title = papers_item['data']['title']
                paper_type = papers_item['data']['publicationType']
                logger.debug("Process paper #%i (title='%s'; year=%i; type='%s')" % (papers_count, title, year, paper_type))
                logger.debug("Title and year check.")

                # First compare
                if params["year"] != year:
                    logger.debug("Year of paper #%i does not coincide with the year of the required paper, skipped." % (on_page_paper_count))
                elif params["title"] != title.lower():
                    logger.debug("Title of paper #%i does not coincide with the title of the required paper, skipped." % (on_page_paper_count))
                # Second compare
                else:
                    logger.debug("The title and year of the paper coincided, identification of information from the RIS.")
                    paper_url =  _FULLURL.format(_HOST, papers_item['data']['publicationUrl'])
                    logger.debug("Process RIS for paper #%i." % on_page_paper_count)
                    rg_paper_id = get_rg_paper_id_from_url(paper_url)
                    info = get_info_from_RIS(rg_paper_id)
                    if info == None:
                        logger.debug("Could not load RIS file for paper #%i, skipped." % (on_page_paper_count))
                    elif params["authors_count"] != len(info['authors']):
                        logger.debug("Count of author of paper #%i does not coincide with the count of author of the required paper, skipped." % (on_page_paper_count))
                    elif 'start_page' in info and params["spage"] != None and str(params["spage"]) != info['start_page']:
                        logger.debug("Start page of paper #%i does not coincide with the start page of the required paper, skipped." % (on_page_paper_count))
                    elif 'end_page' in info and params["epage"] != None and str(params["epage"]) != info['end_page']:
                        logger.debug("End page of paper #%i does not coincide with the end page of the required paper, skipped." % (on_page_paper_count))
                    else:
                        logger.debug("Paper #%i was identified with EndNote file #%i." % (on_page_paper_count, params["paper_version"]))
                        logger.debug("EndNote file #%i:\n%s" % (params["paper_version"], params["EndNote"]))
                        info = fill_paper(info, rg_paper_id)
                        info["rg_type"] = paper_type
                        return info
            except Exception as error:
                #logger.warn(traceback.format_exc())
                raise
        if len(papers_box) >= 10:
            pagenum += 1
            logger.debug("Load next page in resulting query selection.")
            qtext = requests.utils.quote(stopwords.delete_stopwords(params["title"], " and "))
            #   DEBUG messages
            url = _PUBSEARCH.format(qtext, pagenum)
            logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, url))
            json_query_result = utils.get_json_data(_FULLURL.format(_HOST, url))
        else:
            logger.debug("This paper not found in researchgate.")
            return None


def get_paper_info_from_html(PaperURL):
    """Fill the data about paper"""
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, PaperURL))
    soup = utils.get_soup(PaperURL)
    res = dict()
    logger.debug("Parse paper string and get information.")
    details_soup = soup.find('div', class_ = 'public-publication-details-top')
    res["type"] = details_soup.find('strong', class_='publication-meta-type').text.strip().lower().rstrip(':')
    res["title"]   = details_soup.find('h1', class_='publication-title').text.strip()
    res["abstract"] = details_soup.find('div', class_='publication-abstract').find_all('div')[1].text.strip()
    meta_sec = details_soup.find('div', class_='publication-meta-secondary').text.split()
    if meta_sec[0] == "DOI:":
        res["doi"] = meta_sec[1]
    logger.debug("Translate abstract.")
    try:
        res["abstract_ru"] = translate(res["abstract"], 'ru')
    except Exception as error:
        #logger.warn(traceback.format_exc())
        raise
    logger.debug("Get references count.")
    rg_paper_id = soup.find('meta', property="rg:id")['content'][3:]
    res["rg_id"] = rg_paper_id
    ref_dict = get_referring_papers(rg_paper_id)
    if ref_dict != None and len(ref_dict) > 0:
        #res["references"] = ref_dict
        res["references_count"] = len(ref_dict)
        logger.debug("References count: %i." % res["references_count"])
    return res


def get_info_from_RIS(rg_paper_id):
    """Get RIS file for paper with rg_paper_id"""
    logger.debug("Downloading RIS data about paper. RGID={0}.".format(rg_paper_id))
    data = utils.get_text_data(_FULLURL.format(_HOST, _PUBRISDATA.format(rg_paper_id))).replace("\r", "")
    logger.debug("RIS file:\n%s" % data)
    logger.debug("Parse RIS data.")
    res = None
    try:
        if data == None:
            logger.debug("RIS data is empty.")
            return res
        datalines = data.split("\n")
        RISgenerator = RISparser.read(datalines)
        res = next(RISgenerator)
        if "doi" in res and not utils.is_doi(res["doi"]): res.pop("doi")
        res["RIS"] = data
    except:
        #logger.warn(traceback.format_exc())
        raise
    return res


def get_referring_papers(rg_paper_id):
    """ Get references dict for paper with rg_paper_id """
    logger.debug("Downloading the list of referring articles.")
    info = get_info_about_ref_and_citations(rg_paper_id)
    if info == None: return None
    ref_url = _PUBREFERENCESDATA.format(rg_paper_id, info["referencesCount"])
    url = _FULLURL.format(_HOST, ref_url)
    try:
        dict_req_result = utils.get_json_data(url)
    except:
        raise
    if dict_req_result == None: 
        logger.debug("Data is empty.")
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return dict_req_result['result']['state']['rigel']['store']['publication:id:PB:{0}'.format(rg_paper_id)]['outgoingCitations']['__pagination__'][0]['list']
    logger.debug("Data is not correct.")
    return None


def get_citations_papers(rg_paper_id):
    """Get cited dict for paper with rg_paper_id"""
    logger.debug("Downloading the list of cited articles.")
    info = get_info_about_ref_and_citations(rg_paper_id)
    if info == None: return None
    ref_url = _PUBCITEDSDATA.format(rg_paper_id, info["citationsCount"])
    url = _FULLURL.format(_HOST, ref_url)
    try:
        dict_req_result = utils.get_json_data(url)
    except:
        raise
    if dict_req_result == None: 
        logger.debug("Data is empty.")
        return None
    success = dict_req_result['success']
    logger.debug("Status=%s." % success)
    if success:
        logger.debug("Data is correct and parse is successfuly.")
        return dict_req_result["result"]["state"]["rigel"]["store"]["publication:id:PB:{0}".format(rg_paper_id)]["incomingCitingPublicationsWithContext"]["__pagination__"][0]["list"]
    logger.debug("Data is not correct.")
    return None


def get_authors(rg_paper_id):
    """Get authors for paper with rg_paper_id"""
    logger.debug("Get authors for paper.")
    ref_url = _AUTHORSLISTDATA.format(rg_paper_id, 0, 100)
    url = _FULLURL.format(_HOST, ref_url)
    try:
        dict_req_result = utils.get_json_data(url)
    except:
        #logger.warn(traceback.format_exc())
        #return None
        raise
    if dict_req_result == None: 
        logger.debug("Data is empty.")
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
        dict_req_result = utils.get_json_data(url)
    except:
        #logger.warn(traceback.format_exc())
        #return None
        raise
    if dict_req_result == None: 
        logger.debug("Data is empty.")
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
    logger.debug("Get page from researchgate for paper with RGID={0}.".format(rg_paper_id))
    ref_url = _PUBLICATIONPAGE.format(rg_paper_id)
    url = _FULLURL.format(_HOST, ref_url)
    soup = utils.get_soup(url)
    logger.debug("Parse paper string and get information.")
    details_soup = soup.find('div', class_ = 'publication-resources-summary--action-container')
    load_button = [ i for i in details_soup.find_all("a") if "publication-header-full-text" in i.attrs['class'] ]
    if load_button == []:
        logger.debug("PDF for this paper is anavailable.")
        return None
    PDF_url = _FULLURL.format(_HOST, load_button[0]["href"].strip())
    logger.debug("URL for PDF: {0}.".format(PDF_url))
    return PDF_url


def get_pdf(rg_paper_id, filename):
    """Load pdf for paper with rg_paper_id and save to file filename"""
    settings.print_message("PDF-file exists in ResearchGate.", 2)
    url = get_pdf_url(rg_paper_id)
    if url == None: return False
    try:
        settings.print_message("Download pdf...", 2)
        return utils.download_file(url, filename)
    except:
        raise
    return True


