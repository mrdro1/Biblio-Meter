# -*- coding: utf-8 -*-
from codecs import getdecoder
import re, time, random
import sys, traceback, logging
import requests
#
from endnoteparser import EndNote_parsing # bibtexparser
import settings
import utils


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

_HOST = 'https://scholar.google.com'
_DOMAIN = 'google.com'
_AUTHSEARCH = '/citations?view_op=search_authors&hl=en&mauthors={0}'
_CITATIONAUTH = '/citations?user={0}&hl=en'
_CITATIONPUB = '/citations?view_op=view_citation&citation_for_view={0}'
_KEYWORDSEARCH = '/citations?view_op=search_authors&hl=en&mauthors=label:{0}'
_PUBSEARCH = '/scholar?q={0}'
_PUBADVANCEDSEARCH = '/scholar?as_q={0}&as_epq={1}&as_oq={2}&as_eq={3}&as_occt={4}&as_sauthors={5}&as_publication={6}&as_ylo={7}&as_yhi={8}&btnG=&hl=en&as_sdt={9}%2C5&as_vis={10}'
_SCHOLARPUB = '/scholar?oi=bibs&hl=en&cites={0}'
_SCHOLARCLUSTER = '/scholar?cluster={0}&hl=en&as_sdt=1,5&as_vis=1'
_FULLURL = r'{0}{1}'

_CITATIONAUTHRE = r'user=([\w-]*)'
_CITATIONPUBRE = r'citation_for_view=([\w-]*:[\w-]*)'
_SCHOLARCITERE = r'gs_ocit\(event,\'([\w-]*)\''
_SCHOLARPUBRE = r'cites=([\w-]*)'
_SCHOLARCLUSTERRE = r'cluster=[0-9]*'


def _cluster_handler(cluster_id, papers_count):
    logger.debug("Handle %i papers from cluster %s." % (papers_count, cluster_id))
    url = _FULLURL.format(_HOST, _SCHOLARCLUSTER.format(cluster_id))
    logger.debug("Get cluster page URL='{0}'.".format(url))
    soup = utils.get_soup(url)
    #utils.soup2file(soup, "D:\A.html")
    # This dictionary contains info about unique papers
    EndNote_list = list()
    file_counter = 0
    merged_counter = 0
    
    # return true if EndNote_1 equal EndNote_2
    is_EndNote_equal = lambda EndNote_1, EndNote_2: \
                EndNote_1["title"].lower() == EndNote_2["title"].lower() and \
                ( 
                    not "year" in EndNote_1 or not "year" in EndNote_2 \
                    or EndNote_1["year"] == EndNote_2["year"]
                ) \
                and len(EndNote_1["author"]) == len(EndNote_1["author"]) \
                and EndNote_1["type"] == EndNote_2["type"] and \
                (
                    not "pages" in EndNote_1 or not "pages" in EndNote_2 \
                    or EndNote_1["pages"] == EndNote_2["pages"]
                )

    # return list of similar papers (maybe empty)
    intersect_papers = lambda EndNote_data, EndNote_list: \
        [i for i in EndNote_list if is_EndNote_equal(EndNote_data, i)]

    # Loop on pages
    while True:
        if soup is None:
            logger.debug("Soup for cluster page URL='{0}' is None.".format(url))
            return None
        # This list contains links to EndNote and cited by count for each paper in cluster
        logger.debug("Find EndNote links for each paper in cluster.")
        footer_links = [
            {
                "EndNote" if "EndNote" in link.text else "citedby" 
                :
                link["href"].strip() if "EndNote" in link.text else int(re.findall(r'\d+', link.text)[0])
                for link in paper_block.find("div", class_="gs_fl").find_all('a')
                if "EndNote" in link.text or "Cited" in link.text or "Цитируется" in link.text
            }
            for paper_block in soup.find_all('div', class_='gs_ri')
        ]
        logger.debug("Extract unique papers in cluster and load data from EndNote.")
        for links in footer_links:
            if links != {}:
                file_counter += 1
                logger.debug("EndNote file #%i (total %i)" % (file_counter, papers_count)) 
                if links.get("EndNote"):
                    paper_EndNote_data = get_info_from_EndNote(links["EndNote"], True)
                else:
                    settings.print_message('Error getting EndNote files. '
                                           'Please change the display settings Google Scholar in English '
                                           '(https://scholar.google.com/).')
                    logger.debug('End work programme because did not find link to EndNote file.')
                    raise Exception('Did not find EndNote.')
                if paper_EndNote_data == None:
                    logger.debug("Skip EndNote file #%i, could not upload file." % file_counter)
                    continue
                if not "year" in paper_EndNote_data or not "author" in paper_EndNote_data: 
                    logger.debug("Skip EndNote file #%i, empty year or authors fields." % file_counter)
                else:
                    similar_papers = intersect_papers(paper_EndNote_data, EndNote_list)
                    if similar_papers == []:
                        merged_counter += 1
                        logger.debug("EndNote file #%i miss all EndNote files in merged array." % file_counter)
                        logger.debug("Add EndNote file #%i in merged array." % file_counter)
                        paper_EndNote_data.update( 
                            {
                            "url_scholarbib" : links["EndNote"],
                            "citedby" : links["citedby"] if "citedby" in links else None
                            }
                        )
                        EndNote_list.append(paper_EndNote_data)
                    else:
                        similar_file = similar_papers[0]
                        similar_file_index = EndNote_list.index(similar_file)
                        if len(similar_file) < len(paper_EndNote_data):
                            logger.debug("EndNote file #{0} like #{1} EndNote file in merged array and has more fields, replace.".format(
                                file_counter, similar_file_index + 1))
                            EndNote_list[similar_file_index] = paper_EndNote_data
                        else:
                            logger.debug("EndNote file #{0} like #{1} EndNote file in merged array, skipped.".format(
                                file_counter, similar_file_index + 1))
        # NEXT button on html page
        if soup.find(class_='gs_ico gs_ico_nav_next'):
            url = soup.find(class_='gs_ico gs_ico_nav_next').parent['href'].strip()
            logger.debug("Load next page in resulting query selection.")
            soup = utils.get_soup(_FULLURL.format(_HOST, url))
        else:
            break
    if merged_counter == 0:
        logger.debug("All %i EndNote files in the cluster are not informative. No merged files." % file_counter)
    else:
        logger.debug("All {0} EndNote files merged in {1} (i.e. distinct versions in cluster: {1}):".format(file_counter, merged_counter))
        for counter, data in enumerate(EndNote_list): logger.debug("Merged EndNote file #%i:\n%s" % (counter + 1, data["EndNote"]))
    return tuple(EndNote_list)

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
    settings.print_message("PDF-file found in Sci-Hub.", 2)
    if url == None: return False
    try:
        settings.print_message("Download pdf...", 2)
        return utils.download_file(url, filename)
    except:
        #logger.warn(traceback.format_exc())
        #return False
        raise
    return True

def _get_info_from_resulting_selection(paper_soup, handling_cluster = False):
    """retrieving data about an article in the resulting selection"""
    # Full info about paper include general and addition information
    # MAYBE no one addition information, because this paper in cluster
    # and for each paper from cluster contains additional info
    settings.print_message("Google scholar:", 2)
    settings.print_message("Get general information.", 3)
    full_info = dict()
    general_information = dict()
    databox = paper_soup.find('div', class_='gs_ri')
    title = databox.find('h3', class_='gs_rt')
    if title.find('span', class_='gs_ct'): # A citation
        title.span.extract()
    elif title.find('span', class_='gs_ctc'): # A book or PDF
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
            GID = re.findall(_CITATIONAUTHRE, author_ref_list[ref_index]['href'].strip())[0]
            ref_index += 1
        author_list.append({ "shortname" : auth_shortname, "gid" : GID})
    general_information['author'] = author_list
    year = re.findall("[0-9]{4}", paperinfo.text)

    if len(year) != 0: general_information['year'] = int(year[0])
    
    # Save general info
    full_info["general_information"] = general_information
    settings.print_message("Title: '%s'" % general_information['title'], 3)
    # Get addition information (maybe paper in cluster then analysis cluster and get additional info for each unique paper in cluster)
    footer_links = databox.find('div', class_='gs_fl').find_all('a')
    settings.print_message("Get additional information.", 3)
    # CLUSTER HANDLER
    if handling_cluster:
        for link in footer_links:
            if 'versions' in link.text or 'версии статьи' in link.text:
                count_sim_papers = int(re.findall(r'\d+', link.text.strip())[0])
                logger.debug("In cluster %i papers." % count_sim_papers)
                settings.print_message("In cluster %i similar papers." % count_sim_papers, 3)
                settings.print_message("Cluster handling...", 3)
                general_information["cluster"] = int(re.findall(r'\d+', link['href'].strip())[0])
                different_information = _cluster_handler(general_information["cluster"], count_sim_papers)
                if different_information == None: break
                full_info["different_information"] = different_information
                settings.print_message("Versions in cluster: %i." % len(different_information), 3)
                return full_info



    # check: have paper link to pdf
    # and take this link if exists
    link_to_pdf = _get_url_pdf(paper_soup)
    full_info['link_to_pdf'] = link_to_pdf


    # Paper not in cluster => get addition info for it
    if handling_cluster:
        settings.print_message("Cluster link not exists.", 3)
    else:
        settings.print_message("Don't touch cluster info.", 3)
    different_information = list()
    different_information.append(dict())
    is_end_note = False
    for link in footer_links:
        if 'EndNote' in link.text:
            is_end_note = True
            end_note = get_info_from_EndNote(link['href'].strip(), True)
            if end_note != None:
                different_information[0].update(end_note)
            different_information[0]["url_scholarbib"] = link['href'].strip()
        if 'Cited by' in link.text or 'Цитируется' in link.text:
            different_information[0]["citedby"] = int(re.findall(r'\d+', link.text)[0])
    if not is_end_note:
        settings.print_message('Error getting EndNote files. '
                               'Please change the display settings Google Scholar in English '
                               '(https://scholar.google.com/).')
        logger.debug('End work programme because did not find link to EndNote file.')
        raise Exception('Did not find EndNote.')
    full_info["different_information"] = tuple(different_information)
    return full_info


def get_info_from_EndNote(file_url, return_source = False):
    """Populate the Publication with information from its profile"""
    EndNode_file = utils.get_text_data(file_url)
    if EndNode_file == None:
        logger.debug("Upload empty EndNote file.")
        return None
    EndNode_file = EndNode_file.replace("\r", "")
    logger.debug("EndNote file:\n%s" % EndNode_file)
    EndNote_info = EndNote_parsing(EndNode_file)      
    if "pages" in EndNote_info:
        try:
            pages = EndNote_info["pages"].split("-")
            if len(pages) == 2:
                start_page = pages[0].strip()
                end_page = pages[1].strip()
                re_st_page = re.search("[0-9]+$", start_page)
                re_end_page = re.search("^[0-9]+", end_page)
                if re_st_page: EndNote_info["start_page"] = int(re_st_page.group())
                if re_end_page: EndNote_info["end_page"] = int(re_end_page.group())
                if re_st_page and re_end_page: EndNote_info["volume"] = EndNote_info["end_page"] - EndNote_info["start_page"] + 1
        except Exception as error:
            logger.warn("Can't eval count of pages for paper.")
    if return_source: EndNote_info.update({ "EndNote" : EndNode_file })
    return EndNote_info


def _search_scholar_soup(soup, handling_cluster, max_papers_count, total_papers):
    """Generator that returns pub information dictionaries from the search page"""
    page_num = 1
    counter = 0
    while True:
        paper_blocks = soup.find_all('div', 'gs_r')
        page_total = len(paper_blocks)
        logger.debug("Find papers on page #{0} (max_google_papers = {1})".format(page_num, max_papers_count))
        logger.debug("Total %i papers on page." % (page_total))
        for page_counter, paper in enumerate(paper_blocks):
            if counter >= max_papers_count: break;
            counter += 1
            settings.print_message("Handle paper #%i (total %i)" % (counter, total_papers))
            logger.debug("Handle paper #%i (total %i)" % (counter, total_papers))
            logger.debug("Parse html and get info about paper #{0} on searching page (total {1} on page)".format(page_counter + 1, page_total))
            yield _get_info_from_resulting_selection(paper, handling_cluster)
        if soup.find(class_='gs_ico gs_ico_nav_next') and counter < max_papers_count:
            url = soup.find(class_='gs_ico gs_ico_nav_next').parent['href'].strip()
            logger.debug("Load next page in resulting query selection.")
            soup = utils.get_soup(_FULLURL.format(_HOST, url))
            if soup is None:
                logger.debug("Soup from google.scholar is None. Break from paper generator loop.")
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
            if count_papers:
                count_papers = count_papers.split(' ')[1].replace(',', '')
            else:
                count_papers = 1
            try:
                int(count_papers)
            except:
                count_papers = title.text.split(' ')[0].replace(',', '')
    else:
        count_papers = 1
    return int(count_papers)

def search_pubs_query_with_control_params(params):
    """Advanced search by scholar query and return a generator of Publication objects"""
    return search_pubs_query_with_params(
        params['query'] if 'query' in params else '',
        params['date_from'] if 'date_from' in params else '',
        params['date_to'] if 'date_to' in params else '',
        params['authored'] if 'authored' in params else '',
        params['published'] if 'published' in params else '',
        params['exact_phrase'] if 'exact_phrase' in params else '',
        params['one_of_words'] if 'one_of_words' in params else '',
        params['not_contained_words'] if 'not_contained_words' in params else '',
        (True if params['words_in_body'] == 'true' else False) if 'words_in_body' in params else True,
        (True if params['patents'] == 'true' else False) if 'patents' in params else True,
        (True if params['citations'] == 'true' else False) if 'citations' in params else True,
        params["google_clusters_handling"].lower() == "true" if "google_clusters_handling" in params else False,
        int(params["max_google_papers"]) if "max_google_papers" in params else float("inf") if "max_google_papers" in params else float("inf")
    )


def search_pubs_query_with_params(
        query, date_from, date_to, authored, published,
        exact_phrase, one_of_words, not_contained_words, words_in_body,
        patents, citations, handling_cluster = False, max_iter = float("inf")
    ):
    """Advanced search by scholar query and return a generator of Publication objects"""
    url = _PUBADVANCEDSEARCH.format(
        requests.utils.quote(query), 
        requests.utils.quote(exact_phrase),
        requests.utils.quote(one_of_words if one_of_words is str else '+'.join(one_of_words)),
        requests.utils.quote(not_contained_words if not_contained_words is str else '+'.join(not_contained_words)),
        'any' if words_in_body else 'title',
        requests.utils.quote(authored),
        requests.utils.quote(published),
        date_from,
        date_to,
        '0' if patents else '1',
        '0' if citations else '1',
    )
    return search_pubs_custom_url(url, handling_cluster, max_iter)


def search_pubs_custom_url(url, handling_cluster, max_iter):
    """Search by custom URL and return a generator of Publication objects
    URL should be of the form '/scholar?q=...'"""
    logger.debug("Load html from '%s'." % _FULLURL.format(_HOST, url))
    soup = utils.get_soup(_FULLURL.format(_HOST, url))
    if soup is None:
        logger.debug("Soup for generator publication page URL='{0}' is None.".format(url))
        return None, None
    about = get_about_count_results(soup)
    return (_search_scholar_soup(soup, handling_cluster, max_iter, about), about)


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

