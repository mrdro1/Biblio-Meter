# -*- coding: utf-8 -*-
from codecs import getdecoder
import re
import time
import random
import sys
import traceback
import logging
import requests
import json
#
from endnoteparser import EndNote_parsing  # bibtexparser
import settings
import utils


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

_HOST = 'https://scholar.google.com'
_DOMAIN = 'google.com'
_CITATIONAUTH = '/citations?user={}&hl=en'
_PUBADVANCEDSEARCH = '/scholar?start={11}&q={0}&as_epq={1}&as_oq={2}&as_eq={3}&as_occt={4}&as_sauthors={5}&as_publication={6}&as_ylo={7}&as_yhi={8}&btnG=&hl=en&as_sdt={9}%2C5&as_vis={10}'
_SCHOLARCLUSTER = '/scholar?cluster={0}&hl=en&as_sdt=1,5&as_vis=1'
_FULLURL = r'{0}{1}'
_SITIES_SEARCH_URL = "/scholar?start={1}&hl=en&cites={0}&as_vis={2}&as_sdt={3}&as_ylo={4}&as_yhi={5}"
_AUTHOR_PAPERS_PAGE = _CITATIONAUTH + "&cstart={}&pagesize=100"
_CITATIONAUTHRE = r'user=([\w-]*)'


def get_pdfs_link_from_cluster(cluster_id):
    logger.debug("Process papers from cluster %s." % (cluster_id))
    url = _FULLURL.format(_HOST, _SCHOLARCLUSTER.format(cluster_id))
    logger.debug("Get cluster page URL='{0}'.".format(url))
    pdf_links = list()

    # Loop on pages
    MAX_PAGES = 15
    links_count = 0
    for page in range(1, MAX_PAGES + 1):
        result = True
        soup = None
        while result and soup is None:
            soup = utils.get_soup(url)
            if soup is None:
                result = None
                # while result is None:
                #    result = input('Do not load cluster page on scholar. Try again? [Y/N/A]').lower()
                #    if result == "y": result = True
                #    elif result == "n": result = False
        if soup is None:
            logger.debug(
                "Soup for cluster page URL='{0}' is None.".format(url))
            return None
        # This list contains links to EndNote and cited by count for each paper
        # in cluster
        logger.debug("Find PDF links on page #{}.".format(page))
        pdf_links.extend([
            _get_url_pdf(paper_block)
            # gs_ggs gs_fl
            for paper_block in soup.find_all('div', class_='gs_r gs_or gs_scl')
            if _get_url_pdf(paper_block)
        ])
        logger.debug(
            "Found {} links on page #{}.".format(
                len(pdf_links) -
                links_count,
                page))
        links_count = len(pdf_links)
        # NEXT button on html page
        if soup.find(class_='gs_ico gs_ico_nav_next'):
            url = _FULLURL.format(
                _HOST, soup.find(
                    class_='gs_ico gs_ico_nav_next').parent['href'].strip())
            logger.debug("Load next page in resulting query selection.")
            #soup = utils.get_soup(_FULLURL.format(_HOST, url))
        else:
            break
    logger.debug(
        "Found {} links to PDFs in cluster {}.".format(
            links_count, cluster_id))
    logger.debug("URLS: {}".format("\n".join(pdf_links)))
    if links_count == 0:
        return None
    return tuple(pdf_links)


def get_paper_from_cluster(cluster_id, paper_number=1, print_level=-1, max_endnote=False):
    logger.debug("Process papers from cluster {}.".format(cluster_id))
    url = _FULLURL.format(_HOST, _SCHOLARCLUSTER.format(cluster_id))
    logger.debug("Get cluster page URL='{0}'.".format(url))
    # Loop on pages
    MAX_PAGES = 15
    best_paper = None
    for page in range(1, MAX_PAGES + 1):
        result = True
        soup = None
        while result and soup is None:
            soup = utils.get_soup(url)
            if soup is None:
                result = None
        if soup is None:
            logger.debug(
                "Soup for cluster page URL='{0}' is None.".format(url))
            return None
        paper_blocks = soup.find_all('div', 'gs_r')
        logger.debug(
            "Found papers {} on page #{} in cluster {}".format(
                len(paper_blocks), page, cluster_id))

        for counter, paper in enumerate(paper_blocks):
            if counter + 1 < paper_number:
                continue
            logger.debug("Process paper #{} on page #{}".format(counter + 1, page))
            if max_endnote:
                paper_info = _get_info_from_resulting_selection(
                    paper, print_level=-1)
                logger.debug(
                    "G paper\n{}\nBest paper\n{}".format(
                        json.dumps(paper_info),
                        json.dumps(best_paper)))
                if not paper_info["different_information"]["EndNote"]:
                    continue
                if not best_paper or len(best_paper["different_information"]["EndNote"]) < len(
                        paper_info["different_information"]["EndNote"]):
                    best_paper = paper_info
            else:
                best_paper = _get_info_from_resulting_selection(
                    paper, print_level=print_level)
        if best_paper: break
    return best_paper


def _get_url_pdf(databox):
    """ Функция поиска ссылки на pdf статьи"""
    link_to_pdf = None
    pdf = databox.find('div', class_='gs_or_ggsm')
    if pdf:
        pdf = pdf.a
        if pdf.text.startswith('[PDF]'):
            link_to_pdf = pdf['href']
    return link_to_pdf


def get_pdf(url, filename):
    """Load pdf for paper with DOI and save to file filename"""
    settings.print_message("PDF-file found in google scholar.", 2)
    if url is None:
        return None
    try:
        settings.print_message("Download pdf...", 2)
        utils.download_file(url, filename)
        return utils.check_pdf(filename)
    except KeyboardInterrupt:
        raise
    except BaseException:
        logger.warn(traceback.format_exc())
        # return False
        raise
    return 0


def _get_info_from_resulting_selection(
        paper_soup, skip_endnote=False, print_level=0):
    """retrieving data about an article in the resulting selection"""
    # Full info about paper include general and addition information
    # MAYBE no one addition information, because this paper in cluster
    # and for each paper from cluster contains additional info
    full_info = dict()
    general_information = dict()
    databox = paper_soup.find('div', class_='gs_ri')
    title = databox.find('h3', class_='gs_rt')
    if title.find('span', class_='gs_ct'):  # A citation
        title.span.extract()
    elif title.find('span', class_='gs_ctc'):  # A book or PDF
        title.span.extract()
    general_information['title'] = title.text.strip()
    if title.find('a'):
        general_information['url'] = title.find('a')['href'].strip()

    paperinfo = databox.find('div', class_='gs_a')
    author_list = list()
    author_ref_list = paperinfo('a')
    ref_index = 0
    ref_list_len = len(author_ref_list)
    for auth_shortname in paperinfo.text.split("-")[0].split(","):
        GID = ""
        auth_shortname = auth_shortname.strip(" …\xa0")
        if ref_list_len > ref_index and auth_shortname == author_ref_list[ref_index].text:
            GID = re.findall(_CITATIONAUTHRE,
                             author_ref_list[ref_index]['href'].strip())[0]
            ref_index += 1
        author_list.append({"shortname": auth_shortname, "gid": GID})
    general_information['author'] = author_list
    year = re.findall("[0-9]{4}", paperinfo.text)

    if len(year) != 0:
        general_information['year'] = int(year[0])

    # Save general info
    full_info["general_information"] = general_information
    if print_level >= 0:
        settings.print_message(
            "Title: '{}'{}".format(
                general_information['title'],
                ", " + str(
                    year[0]) if len(year) != 0 else ""),
            print_level + 1)
    # Get addition information (maybe paper in cluster then analysis cluster
    # and get additional info for each unique paper in cluster)
    footer_links = databox.find('div', class_='gs_fl').find_all('a')
    #settings.print_message("Get additional information.", 3)

    count_sim_papers = 0
    different_information = dict()
    for link in footer_links:
        if 'versions' in link.text or 'версии статьи' in link.text:
            count_sim_papers = int(re.findall(r'\d+', link.text.strip())[0])
            logger.debug("In cluster %i papers." % count_sim_papers)
            general_information["cluster"] = int(
                re.findall(r'\d+', link['href'].strip())[0])
            different_information["versions"] = int(
                re.findall(r'\d+', link.text.strip())[0])
            break

    # check: have paper link to pdf
    # and take this link if exists
    link_to_pdf = _get_url_pdf(paper_soup)
    full_info['link_to_pdf'] = link_to_pdf

    is_end_note = False
    for link in footer_links:
        if 'endnote' in link.text.strip().lower():
            is_end_note = True
            if not skip_endnote:
                end_note = get_info_from_EndNote(link['href'].strip(), True)
                if end_note is not None:
                    different_information.update(end_note)
                else:
                    full_info["different_information"] = None
                    return full_info
            different_information["url_scholarbib"] = link['href'].strip()
        if 'Cited by' in link.text or 'Цитируется' in link.text:
            #utils.get_soup(_HOST + link['href'].strip())
            different_information["citedby"] = int(
                re.findall(r'\d+', link.text)[0])
            if not general_information.get("cluster"):
                general_information["cluster"] = int(
                    re.findall(r'\d+', link['href'].strip())[0])
    if not is_end_note:
        settings.print_message('Error getting EndNote files. '
                               'Please change the display settings Google Scholar in English '
                               '(https://scholar.google.com/).')
        logger.debug(
            'End work programme because did not find link to EndNote file.')
        input('Press enter to continue')

        #raise Exception('Did not find EndNote.')
    full_info["different_information"] = different_information
    return full_info


def get_info_from_EndNote(file_url, return_source=False):
    """Populate the Publication with information from its profile"""
    result = True
    EndNode_file = None
    while result and EndNode_file is None:
        EndNode_file = utils.get_text_data(file_url)
        if EndNode_file is None:
            result = None
            # while result is None:
            #    result = input('Do not load EndNote file from scholar. Try again? [Y/N]').lower()
            #    if result == "y": result = True
            #    elif result == "n": result = False
    if EndNode_file is None:
        logger.debug("Download empty EndNote file.")
        return None
    EndNode_file = EndNode_file.replace("\r", "")
    logger.debug("EndNote file:\n%s" % EndNode_file)
    EndNote_info = EndNote_parsing(EndNode_file)
    if not EndNote_info:
        return None
    if "pages" in EndNote_info:
        try:
            pages = EndNote_info["pages"].split("-")
            if len(pages) == 2:
                start_page = pages[0].strip()
                end_page = pages[1].strip()
                re_st_page = re.search("[0-9]+", start_page)
                re_end_page = re.search("[0-9]+", end_page)
                if re_st_page:
                    EndNote_info["start_page"] = int(re_st_page.group(0))
                if re_end_page:
                    EndNote_info["end_page"] = int(re_end_page.group(0))
                if re_st_page and re_end_page:
                    EndNote_info["pages"] = abs(
                        EndNote_info["end_page"] - EndNote_info["start_page"] + 1)
            else:
                re_st_page = re.search("[0-9]+", EndNote_info["pages"])
                EndNote_info["pages"] = int(re_st_page.group(0))
        except Exception as error:
            logger.warn("Can't eval count of pages for paper.")
            try:
                EndNote_info["pages"] = int(EndNote_info["pages"])
            except BaseException:
                EndNote_info["pages"] = None
    if return_source:
        EndNote_info.update({"EndNote": EndNode_file})
    return EndNote_info


def _search_scholar_soup(soup, max_papers_count, total_papers,
                         start_paper, skip_endnote=False, print_level=0):
    """Generator that returns pub information dictionaries from the search page"""
    page_num = 1
    counter = 0
    while True:
        paper_blocks = soup.find_all('div', 'gs_r')
        page_total = len(paper_blocks)
        logger.debug(
            "Find papers on page #{0} (google_max_papers = {1})".format(
                page_num, max_papers_count))
        logger.debug("Total %i papers on page." % (page_total))
        for page_counter, paper in enumerate(paper_blocks):
            if counter >= max_papers_count:
                break
            counter += 1
            if print_level >= 0:
                settings.print_message(
                    "Process paper #{} (total {})".format(
                        counter, total_papers), print_level)
            logger.debug(
                "Process paper #{} (total {})".format(
                    counter, total_papers))
            logger.debug(
                "Parse html and get info about paper #{0} on searching page (total {1} on page)".format(
                    page_counter + 1, page_total))
            yield _get_info_from_resulting_selection(paper, skip_endnote, print_level)
        if soup.find(
                class_='gs_ico gs_ico_nav_next') and counter < max_papers_count:
            url = soup.find(
                class_='gs_ico gs_ico_nav_next').parent['href'].strip()
            result = True
            soup = None
            logger.debug("Load next page in resulting query selection.")
            while result and soup is None:
                soup = utils.get_soup(_FULLURL.format(_HOST, url))
                if soup is None:
                    result = None
                #    while result is None:
                #        result = input('Do not load new page on scholar. Try again? [Y/N]').lower()
                #        if result == "y": result = True
                #        elif result == "n": result = False
            if soup is None:
                logger.debug(
                    "Soup from google.scholar is None. Break from paper generator loop.")
                break
            page_num += 1
        else:
            break


def get_about_count_results(soup):
    """Shows the approximate number of pages as a result"""
    title = soup.find('div', {'id': 'gs_ab_md'})
    if title:
        title = title.find('div', {'class': 'gs_ab_mdw'})
        if title:
            count_papers = title.text
            try:
                if count_papers:
                    count_papers = re.search(
                        "[0-9]+ resu",
                        count_papers.replace(
                            ',',
                            '')).group(0).split()[0]
                else:
                    count_papers = 1
                int(count_papers)
            except BaseException:
                count_papers = title.text.split(' ')[0].replace(',', '')
    else:
        count_papers = 1
    return int(count_papers)


def search_pubs_query_with_control_params(
        params, skip_endnote=False, print_level=0):
    """Advanced search by scholar query and return a generator of Publication objects"""
    one_of_words = params['one_of_words'] if 'one_of_words' in params else ''
    not_contained_words = params['not_contained_words'] if 'not_contained_words' in params else ''
    start_paper = params['start_paper'] if 'start_paper' in params else 1
    max_iter = int(params["google_max_papers"]) \
        if "google_max_papers" in params else float("inf") if "google_max_papers" in params else float("inf")
    url = _PUBADVANCEDSEARCH.format(
        requests.utils.quote(params['query'] if 'query' in params else ''),
        requests.utils.quote(
            params['exact_phrase'] if 'exact_phrase' in params else ''),
        requests.utils.quote(
            one_of_words if one_of_words is str else '+'.join(one_of_words)),
        requests.utils.quote(
            not_contained_words if not_contained_words is str else '+'.join(not_contained_words)),
        'any' if (params['words_in_body']
                  if 'words_in_body' in params else True) else 'title',
        requests.utils.quote(
            params['authored'] if 'authored' in params else ''),
        requests.utils.quote(
            params['published'] if 'published' in params else ''),
        params['date_from'] if 'date_from' in params else '',
        params['date_to'] if 'date_to' in params else '',
        '0' if (params['patents'] if 'patents' in params else True) else '1',
        '0' if (params['citations']
                if 'citations' in params else True) else '1',
        start_paper if start_paper > 1 else ''
    )
    return search_pubs_custom_url(
        url, max_iter, start_paper, skip_endnote, print_level)


def search_cities(cluster_id, params, skip_endnote=False, print_level=0):
    """ Search sities for paper """
    start_paper = params['start_paper'] if 'start_paper' in params else 1
    url = _SITIES_SEARCH_URL.format(
        requests.utils.quote(cluster_id),
        start_paper if start_paper > 1 else '',
        '0' if (params['citations']
                if 'citations' in params else True) else '1',
        '0' if (params['patents'] if 'patents' in params else True) else '1',
        params['date_from'] if 'date_from' in params else '',
        params['date_to'] if 'date_to' in params else ''
    )
    max_iter = int(params["google_max_papers"]) \
        if "google_max_papers" in params else float("inf") if "google_max_papers" in params else float("inf")
    return search_pubs_custom_url(
        url, max_iter, start_paper, skip_endnote, print_level)


def search_pubs_custom_url(url, max_iter, start_paper,
                           skip_endnote=False, print_level=0):
    """Search by custom URL and return a generator of Publication objects
    URL should be of the form '/scholar?q=...'"""
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, url))
    soup = utils.get_soup(_FULLURL.format(_HOST, url))
    if soup is None:
        logger.debug(
            "Soup for generator publication page URL='{0}' is None.".format(url))
        return None, None
    about = get_about_count_results(soup)
    return (_search_scholar_soup(soup, max_iter, about,
                                 start_paper, skip_endnote, print_level), about)


def get_info_from_author_page(author_id):
    """Populate the Author with information from their profile"""
    PAGESIZE = 100
    url = '{0}&pagesize={1}'.format(_CITATIONAUTH.format(author_id), PAGESIZE)
    soup = utils.get_soup(_FULLURL.format(_HOST, url))
    if soup is None:
        logger.debug("Soup for author page URL='{0}' is None.".format(url))
        return None
    # Sitations, h-index, i10-index
    res = dict()
    index = soup.find_all('td', class_='gsc_rsb_std')
    res["citations"] = index[0].text
    res["hindex"] = int(index[2].text)
    res["i10index"] = int(index[4].text)
    return res


def get_author_papers_cluster_id(author_google_id):
    papers_cluster_ids = set()
    MAX_PAGES = 5
    for page in range(1, MAX_PAGES + 1):
        try:
            logger.debug("Get author page #{} with papers from indexes [{}:{}].".format(
                page, (page - 1) * 100 + 1, page * 100 + 1))
            url = _FULLURL.format(_HOST, _AUTHOR_PAPERS_PAGE
                        .format(author_google_id, (page - 1) * 100 + 1))
            soup = utils.get_soup(url)
            if soup is None:
                logger.debug("Soup for author page URL='{0}' is None.".format(url))
                return None
            page_papers_counter = soup.find('span', id='gsc_a_nn')
            logger.debug("Papers counter on page: {}".format(
                "not found. It's last page." 
                if not page_papers_counter 
                else page_papers_counter.text))
            for paper_info in soup.find_all("a", "gsc_a_ac gs_ibl"):
                href = paper_info["href"]
                if href:
                    id = re.findall(r'\d+', href.strip())
                    if id: papers_cluster_ids.add(id[0])
            if not page_papers_counter or int(
                page_papers_counter.text.split("–")[1]) < page * 100 + 1:
                break
        except KeyboardInterrupt:
            raise
        except BaseException:
            logger.warn(traceback.format_exc())
        logger.debug("Found paprs with cluster id: {}".format(len(papers_cluster_ids)))
    return papers_cluster_ids