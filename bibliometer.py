# -*- coding: utf-8 -*-
import sys
import traceback
import logging
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import queue
import json
from datetime import datetime
import random
import time
from math import inf
#
import settings
import dbutils
import utils
import paper
import author
import scholar
import scihub
import grobid
from translator import translate

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def get_papers_by_key_words():
    logger.debug("Search papers from google.scholar.")
    settings.print_message("Search papers from google.scholar.")
    paper_generator, about_res_count = scholar.search_pubs_query_with_control_params(settings.PARAMS)
    
    if paper_generator is None:
        logger.debug("Soup from google.scholar is None. End command get_papers_by_key_words")
        return (0, 0, 0, 0, 0, 0, 0, 0, 0)

    logger.debug(about_res_count)
    settings.print_message("Google: Found {0} papers.".format(about_res_count))
    new_papers = 0
    new_auth = 0
    max_papers_count = int(settings.PARAMS["google_max_papers"])
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    papers_counter = 0
    pdf_url_counter = 0
    pdf_cluster_counter = 0
    pdf_scihub_counter = 0
    pdf_unavailable_counter = 0
    if max_papers_count > 0:
        for paper_info in paper_generator:
            max_papers_count -= 1
            # Loop for different versions of paper
            if not paper_info["different_information"]: settings.print_message(
                "Not found information about paper #%i, skipped." % papers_counter, 1)
            paper_addition_information = paper_info["different_information"]
            papers_counter += 1
            # if papers_counter > max_papers_count: break;
            #if not "author" in paper_addition_information: #or not "year" in paper_addition_information:
            #    logger.debug("Skip paper #%i, empty authors fields." % papers_counter)#year or 
            #    continue
            logger.debug("Process content of EndNote file #%i\n%s\n%s" % (
            papers_counter, json.dumps(paper_info["general_information"]), json.dumps(paper_addition_information)))
            # Create new paper entity
            newpaper = paper.Paper()
            # Fill data from google scholar
            newpaper.get_info_from_sch(paper_info["general_information"], paper_addition_information,
                                        1, paper_info['link_to_pdf'])
            if newpaper.in_database():
                settings.print_message("This paper already exists, id = {}.".format(newpaper.db_id), 1)
            else:
                new_papers += 1
                newpaper.add_to_database()
                settings.print_message("Adding a paper to the database", 1)

                # Get and insert in database info about author
                settings.print_message("Authors:", 2)
                for author_info in newpaper.authors:
                    # Create new author entity
                    newauthor = author.Author()
                    newauthor.get_base_info_from_sch(author_info)

                    settings.print_message("Handle author '%s'." % (newauthor.shortname if newauthor.name == None else newauthor.name), 4)
                    logger.debug("Check exists author and if not then insert into DB.")
                    if not newauthor.in_database():
                        newauthor.get_info_from_sch()
                        # Insert new author into DB
                        settings.print_message("Adding author to the database", 4)
                        newauthor.save_to_database()
                        new_auth += 1
                    else:
                        settings.print_message("This author already exists, id = %i." % newauthor.db_id, 4)
                    # Insert into DB reference
                    dbutils.add_author_paper_edge(newauthor.db_id, newpaper.db_id)

            if settings.PARAMS["google_get_files"]:
                tmp = download_pdf(
                    paper_info['general_information']['url'],
                    paper_info['link_to_pdf'],
                    paper_info['general_information'].get("cluster"),
                    None, newpaper.db_id)
                download_pdf_url, download_pdf_cluster, download_pdf_scihub = tmp
                pdf_url_counter += 1 if download_pdf_url else 0
                pdf_cluster_counter += 1 if download_pdf_cluster else 0
                pdf_scihub_counter += 1 if download_pdf_scihub else 0
                pdf_unavailable_counter += 1 if \
                    not download_pdf_url and \
                    not download_pdf_cluster and \
                    not download_pdf_scihub else 0
            # Commit transaction each commit_iterations iterations
            if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
            # if papers_counter >= max_papers_count: break;
    return (about_res_count, new_papers, new_auth, papers_counter, new_auth + new_papers, 
            pdf_url_counter, pdf_cluster_counter, pdf_scihub_counter, pdf_unavailable_counter)

def download_pdf(google_url, google_pdf_url, google_cluster_id, DOI, paper_id):
    # Download pdf for paper (first paper if use google cluster)
    download_pdf_url = False
    download_pdf_cluster = False
    download_pdf_scihub = False
    success_download = False
    fn_tmp_pdf = '{0}tmp_{1}.pdf'.format(settings.PDF_CATALOG, paper_id)
    fn_pdf = '{0}{1}.pdf'.format(settings.PDF_CATALOG, paper_id)
    # load pdf from gs
    if google_pdf_url:
        settings.print_message("Try get pdf from Google Scholar.", 1)
        settings.print_message(
            "Getting PDF-file from Google Scholar by url : {0}.".format(google_pdf_url), 2)
        logger.debug("Getting PDF-file from Google Scholar by url : {0}.".format(google_pdf_url))
        try:
            if scholar.get_pdf(google_pdf_url, fn_tmp_pdf):
                settings.print_message("Complete!", 2)
                dbutils.update_pdf_transaction(paper_id, "Google Scholar")
                utils.rename_file(fn_tmp_pdf, fn_pdf)
                download_pdf_url = True
                success_download = True
        except KeyboardInterrupt:
            raise
        except:
            #settings.print_message(traceback.format_exc())
            utils.REQUEST_STATISTIC['failed_requests'].append(google_pdf_url)
            logger.debug("Failed get pdf from Google Scholar URL={0}".format(google_pdf_url))
            settings.print_message("failed load PDF from Google Scholar.", 2)
    # load pdf from google scholar cluster by paper url if does not exist 
    if not success_download and google_cluster_id and settings.PARAMS["google_cluster_files"]:
        settings.print_message("Try get pdf from Google Scholar cluster {}.".format(google_cluster_id), 1)
        cluster_pdfs_links = scholar.get_pdfs_link_from_cluster(google_cluster_id)
        if cluster_pdfs_links is not None:
            for google_pdf_url in cluster_pdfs_links:
                settings.print_message(
                    "Getting PDF-file from cluster Google Scholar by url: {0}.".format(google_pdf_url), 2)
                logger.debug("Getting PDF-file from cluster Google Scholar by url: {0}.".format(google_pdf_url))
                try:
                    if scholar.get_pdf(google_pdf_url, fn_tmp_pdf,):
                        settings.print_message("Complete!", 2)
                        dbutils.update_pdf_transaction(paper_id, "Google Scholar Cluster")
                        utils.rename_file(fn_tmp_pdf, fn_pdf)
                        download_pdf_cluster = True
                        success_download = True
                        break
                except KeyboardInterrupt:
                    raise
                except:
                    utils.REQUEST_STATISTIC['failed_requests'].append(google_pdf_url)
                    logger.debug("Failed get pdf from Google Scholar cluster URL={0}".format(google_pdf_url))
                    settings.print_message("failed load PDF from Google Scholar cluster.", 2)
        else:
            logger.debug("Failed get pdf from Google Scholar cluster. Cluster hasn't links to PDFs.")
            settings.print_message("failed load PDF from Google Scholar cluster. Cluster hasn't links to PDFs.", 2)
    # load pdf from scihub by paper url if does not exist
    if (google_url or DOI) and not success_download and settings.PARAMS["sci_hub_files"]:
        settings.print_message("Try get pdf by paper url on sci-hub.", 1)
        settings.print_message("Getting PDF-file from Sci-Hub.", 2)
        logger.debug("Getting PDF-file on Sci-Hub.")
        try:
            if not scihub.get_pdf(DOI, fn_tmp_pdf) and \
            not scihub.get_pdf(google_url, fn_tmp_pdf):
                settings.print_message("PDF unavailable on sci-hub.", 2)
            else:
                settings.print_message("Complete!", 2)
                dbutils.update_pdf_transaction(paper_id, "Sci-hub")
                utils.rename_file(fn_tmp_pdf, fn_pdf)
                success_download = True
                download_pdf_scihub = True
        except KeyboardInterrupt:
            raise
        except:
            utils.REQUEST_STATISTIC['failed_requests'].append(google_url)
            logger.debug("Failed get pdf from sci-hub URL={0}".format(google_url))
            settings.print_message("failed load PDF from sci-hub URL={0}".format(google_url), 2)
            #continue
    if not success_download:
        settings.print_message("Downolad PDF unavaliable.", 1)
        utils.delfile(fn_tmp_pdf)
    return (download_pdf_url, download_pdf_cluster, download_pdf_scihub)


def update_authors():
    pass


def get_papers_of_authors():
    pass


def get_PDFs():
    """This function loads pdf articles from the RG and Sci-hub selected from the query from the database"""
    # statistic for pdf sources
    pdf_url_counter = 0
    pdf_cluster_counter = 0
    pdf_scihub_counter = 0
    pdf_unavailable_counter = 0
    #
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    # get conditions and create standart query
    col_names = "id, doi, google_url, google_file_url, google_cluster_id, title"
    PAPERS_SQL = "SELECT {} FROM papers {}".format(col_names, PAPERS_SQL[PAPERS_SQL.lower().find("where"):])
    papers = dbutils.execute_sql(PAPERS_SQL)
    total = len(papers)
    settings.print_message("{0} papers selected.".format(total))
    logger.debug("{0} papers selected.".format(total))
    # Get columns from query
    columns = dict([(word, i) for i, word in enumerate(col_names.split(', '))])
    #for N, column in enumerate(dbutils.get_columns_names("papers")):
    #    columns[column.lower()] = N
    for paper_index, newpaper in enumerate(papers):
        settings.print_message("Process paper #{} (total {}) - {}.".format(paper_index + 1, total, newpaper[columns['title']]))
        id = newpaper[columns["id"]]
        DOI = newpaper[columns["doi"]]
        google_URL = newpaper[columns["google_url"]]
        pdf_google_URL = newpaper[columns["google_file_url"]]
        pdf_google_cluster_URL = newpaper[columns["google_cluster_id"]]
        if (google_URL is None) and (pdf_google_URL is None) and (pdf_google_cluster_URL is None) and (DOI is None):
            settings.print_message('DOI and URLs is empty, skip this paper.')
            logger.debug("DOI and URLs is empty, skip this paper.")
            continue
        tmp = download_pdf(
            google_URL,
            pdf_google_URL,
            pdf_google_cluster_URL,
            DOI, 
            id)
        download_pdf_url, download_pdf_cluster, download_pdf_scihub = tmp
        pdf_url_counter += 1 if download_pdf_url else 0
        pdf_cluster_counter += 1 if download_pdf_cluster else 0
        pdf_scihub_counter += 1 if download_pdf_scihub else 0
        pdf_unavailable_counter += 1 if \
            not download_pdf_url and \
            not download_pdf_cluster and \
            not download_pdf_scihub else 0
    new_files_count = pdf_scihub_counter + pdf_cluster_counter + pdf_url_counter
    settings.print_message("Proceed papers: {}.".format(len(papers)))
    settings.print_message("PDF from Google: {}.".format(pdf_url_counter))
    settings.print_message("PDF from Google Cluster: {}.".format(pdf_cluster_counter))
    settings.print_message("PDF from Sci-Hub: {}.".format(pdf_scihub_counter))
    settings.print_message("Unavailable PDFs: {}.".format(pdf_unavailable_counter))
    result = (True, new_files_count, pdf_unavailable_counter, pdf_unavailable_counter + new_files_count)
    return result

def select_papers_for_citation_graph(tree_queue):
    """ This function selects articles from the database and checks the SQL. """
    #logger.debug("Select papers from database.")
    #settings.print_message("Select papers from database.")
    #PAPERS_SQL = settings.PARAMS["papers"]
    #papers = dbutils.execute_sql(PAPERS_SQL)
    #settings.print_message("{0} papers selected.".format(len(papers)))
    ## Get columns from query
    #columns = dict()
    #for N, column in enumerate(dbutils.get_columns_names("papers")):
    #    columns[column.lower()] = N
    #for db_paper in papers:
    #    # The tree is in the queue in which the tuples are stored.
    #    # Each tuple is (id of paper in the database, id of the paper on the researchgate, the level of the tree)
    #    tree_queue.put((db_paper[columns["id"]], db_paper[columns["rg_id"]], db_paper[columns["doi"]], 1))
    return 0

def create_and_fill_paper_for_citation_graph(parent_paper_db_id, rg_new_paper_id, edge_type):
    """ This function creates a new instance of the paper and fills it with information. """
    new_authors_count = 0
    new_papers_count = 0
    # Create new paper entity
    newpaper = paper.Paper()
    ## fill new paper
    #settings.print_message("Filling in information about the paper.", 4)
    #logger.debug("Filling in information about the paper.")
    #if not newpaper.get_data_from_rg_id(rg_new_paper_id):
    #    logger.debug("Failed to get information about the paper, skipped.")
    #    return None, new_papers_count, new_authors_count
    #logger.debug("Check exists paper and if not then insert into DB.")
    #if newpaper.in_database():
    #    settings.print_message("This paper already exists, id = {0}.".format(newpaper.db_id), 4)
    #else:
    #    # Add new paper in DB
    #    settings.print_message("Adding a paper to the database", 4)
    #    newpaper.add_to_database()
    #    new_papers_count += 1
    #    # Get and insert in database info about author
    #    settings.print_message("Authors:", 4)
    #    for author_info in newpaper.authors:
    #        # Create new author entity
    #        newauthor = author.Author()
    #        newauthor.get_base_info_from_sch({"name":author_info})
    #        settings.print_message("Handle author '%s'." % (newauthor.shortname if newauthor.name == None else newauthor.name), 6)
    #        logger.debug("Check exists author and if not then insert into DB.")
    #        if not newauthor.in_database():
    #            # Insert new author into DB
    #            settings.print_message("Adding author to the database", 6)
    #            newauthor.save_to_database()
    #            new_authors_count += 1
    #        else:
    #            settings.print_message("This author already exists, id = %i." % newauthor.db_id, 6)
    #        # Insert into DB reference
    #        dbutils.add_author_paper_edge(newauthor.db_id, newpaper.db_id)
    ## Add reference in DB
    #edge_params = \
    #{
    #    "IDpaper1" : parent_paper_db_id,
    #    "IDpaper2" : newpaper.db_id,
    #    "type" : edge_type
    #}
    #logger.debug("Check exists edge and if not then insert into DB.")
    #if not dbutils.check_exists_paper_paper_edge(edge_params):
    #    logger.debug("Add edge ({0}, {1}, {2}) in DB.".format(parent_paper_db_id, newpaper.db_id, edge_type))
    #    #settings.print_message("Add edge ({0}, {1}, {2}) in DB.".format(parent_paper_db_id, newpaper.db_id, edge_type), 4)
    #    dbutils.add_paper_paper_edge(parent_paper_db_id, newpaper.db_id, edge_type)
    #else:
    #    #settings.print_message("This edge ({0}, {1}, {2}) already exists.".format(parent_paper_db_id, newpaper.db_id, edge_type), 4)
    #    logger.debug("This edge ({0}, {1}, {2}) already exists.".format(parent_paper_db_id, newpaper.db_id, edge_type))
    return newpaper, new_papers_count, new_authors_count

def get_references():
    """This function loads links to articles for papers selected from the database"""
    #MAX_TREE_LEVEL = int(settings.PARAMS["max_tree_level"])
    #commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    #tree_queue = queue.Queue()
    #select_papers_for_citation_graph(tree_queue)
    #papers_counter = 0
    #new_papers_count = 0
    #new_authors_count = 0
    #filled_papers = 0
    #papers_without_list = 0
    #getinfo_fails = 0
    #while not tree_queue.empty():
    #    papers_counter += 1
    #    parent_paper_db_id, parent_paper_rg_id, parent_paper_DOI, tree_level = tree_queue.get()
    #    logger.debug("Process paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
    #    settings.print_message("Process paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
    #    if parent_paper_rg_id == None:
    #        logger.debug("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter))
    #        settings.print_message("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter), 2)
    #        parent_paper_rg_id = researchgate.paper_search_by_DOI(parent_paper_DOI)
    #        if parent_paper_rg_id == None:
    #            logger.debug("Paper #{0} not found on Researchgate, skip.".format(papers_counter))
    #            settings.print_message("Paper #{0} not found on Researchgate, skip.".format(papers_counter), 2)
    #            papers_without_list += 1
    #            continue
    #    settings.print_message("Get paper references. RGID={0}.".format(parent_paper_rg_id), 2)
    #    ref_papers_list = researchgate.get_referring_papers(parent_paper_rg_id)
    #    total_ref = 0
    #    if ref_papers_list != None and len(ref_papers_list) != 0:
    #        total_ref = len(ref_papers_list)
    #    else:
    #        logger.debug("Paper #{0} hasn't cited list, skip.".format(papers_counter))
    #        settings.print_message("Paper #{0} hasn't references list, skip.".format(papers_counter), 2)
    #        papers_without_list += 1
    #        continue
    #    for new_paper_counter, ref_paper in enumerate(ref_papers_list):
    #        if ref_paper["publication"] == None: # It's citation
    #            settings.print_message("Paper #{0} is citation, skip.".format(new_paper_counter + 1), 2)
    #            logger.debug("Paper #{0} is citation, skipped.".format(new_paper_counter + 1))
    #            continue
    #        settings.print_message("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref), 2)
    #        logger.debug("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref))
    #        filled_papers += 1
    #        newpaper, _new_papers_count, _new_authors_count = create_and_fill_paper_for_citation_graph(parent_paper_db_id,
    #            researchgate.get_rg_paper_id_from_url(ref_paper["publication"]["url"]), "citied")
    #        if newpaper == None:
    #            settings.print_message("Failed to get information about the paper #{0}, skipped.".format(new_paper_counter + 1), 2)
    #            getinfo_fails += 1
    #            continue
    #        new_papers_count += _new_papers_count
    #        new_authors_count += _new_authors_count
    #        # Add new paper in queue
    #        if tree_level < MAX_TREE_LEVEL:
    #            logger.debug("Add this paper (db_id={0}, rg_id={1}) in tree levels queue.".format(newpaper.db_id, newpaper.rg_paper_id))
    #            tree_queue.put((newpaper.db_id, newpaper.rg_paper_id, newpaper.DOI, tree_level + 1))
    #        else:
    #            pass
    #        # Commit transaction each commit_iterations iterations
    #        if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    #return (papers_counter, papers_without_list, new_papers_count, getinfo_fails, new_authors_count)
    pass

def get_cities():
    """This function loads articles that reference selected papers from the database"""
    #MAX_TREE_LEVEL = int(settings.PARAMS["max_tree_level"])
    #MAX_CITED_PAPERS = int(settings.PARAMS["max_cited_papers"])
    #commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    #tree_queue = queue.Queue()
    #select_papers_for_citation_graph(tree_queue)
    #papers_counter = 0
    #new_papers_count = 0
    #new_authors_count = 0
    #filled_papers = 0
    #papers_without_list = 0
    #getinfo_fails = 0
    #while not tree_queue.empty():
    #    papers_counter += 1
    #    parent_paper_db_id, parent_paper_rg_id, parent_paper_DOI, tree_level = tree_queue.get()
    #    logger.debug("Process paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
    #    settings.print_message("Process paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
    #    if parent_paper_rg_id == None:
    #        logger.debug("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter))
    #        settings.print_message("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter), 2)
    #        parent_paper_rg_id = researchgate.paper_search_by_DOI(parent_paper_DOI)
    #        if parent_paper_rg_id == None:
    #            logger.debug("Paper #{0} not found on Researchgate, skip.".format(papers_counter))
    #            settings.print_message("Paper #{0} not found on Researchgate, skip.".format(papers_counter), 2)
    #            papers_without_list += 1
    #            continue
    #    settings.print_message("Get paper citations. RGID={0}.".format(parent_paper_rg_id), 2)
    #    cited_papers_list = researchgate.get_citations_papers(parent_paper_rg_id)
    #    total_ref = 0
    #    if cited_papers_list != None:
    #        total_ref = len(cited_papers_list)
    #    else:
    #        logger.debug("Paper #{0} hasn't cited list, skipped.".format(papers_counter))
    #        settings.print_message("Paper #{0} hasn't cited list, skip.".format(papers_counter), 2)
    #        papers_without_list += 1
    #        continue
    #    for new_paper_counter, ref_paper in enumerate(cited_papers_list):
    #        if ref_paper["publication"] == None: # It's citation
    #            settings.print_message("Paper #{0} is not article, skip.".format(new_paper_counter + 1), 2)
    #            logger.debug("Paper #{0} is not article, skip.".format(new_paper_counter + 1))
    #            continue
    #        settings.print_message("Handle new paper #{0} from citations (total {1}).".format(new_paper_counter + 1, total_ref), 2)
    #        logger.debug("Handle new paper #{0} from citations (total {1}).".format(new_paper_counter + 1, total_ref))
    #        filled_papers += 1
    #        newpaper, _new_papers_count, _new_authors_count = create_and_fill_paper_for_citation_graph(parent_paper_db_id,
    #            researchgate.get_rg_paper_id_from_url(ref_paper["publication"]["url"]), "citied")
    #        if newpaper == None:
    #            settings.print_message("Failed to get information about the paper #{0}, skipped.".format(new_paper_counter + 1), 2)
    #            getinfo_fails += 1
    #            continue
    #        new_papers_count += _new_papers_count
    #        new_authors_count += _new_authors_count
    #        # Add new paper in queue
    #        if tree_level < MAX_TREE_LEVEL:
    #            logger.debug("Add this paper (db_id={0}, rg_id={1}) in tree levels queue.".format(newpaper.db_id, newpaper.rg_paper_id))
    #            tree_queue.put((newpaper.db_id, newpaper.rg_paper_id, newpaper.DOI, tree_level + 1))
    #        else:
    #            pass
    #        # Commit transaction each commit_iterations iterations
    #        if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    #        if  new_paper_counter >= MAX_CITED_PAPERS - 1: break
    #return (papers_counter, papers_without_list, new_papers_count, getinfo_fails, new_authors_count)
    pass


def get_info_from_PDFs():
    """ This function get info from PDFs by GROBID """
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    papers_counter = 0
    bad_papers = 0
    bad_pdfs = 0
    unavailable_files_counter = 0
    nonempty_abstract = 0
    #
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    # get conditions and create standart query
    PAPERS_SQL = "SELECT id FROM papers " + PAPERS_SQL[PAPERS_SQL.lower().find("where"):]
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    logger.debug("{0} papers selected.".format(len(papers)))
    for paper_index, paper_info in enumerate(papers):
        settings.print_message("Process paper #{0} (total {1}).".format(paper_index + 1, len(papers)))
        id = paper_info[0]
        file_name = "{0}{1}.pdf".format(settings.PDF_CATALOG, id)
        if not os.path.exists(file_name):
            settings.print_message('PDF "{}" not found, skip this paper.'.format(file_name), 2)
            logger.debug('PDF "{}" not found, skip this paper.'.format(file_name))
            bad_pdfs += 1
            continue
        cur_paper = paper.Paper()
        cur_paper.db_id = id
        if not cur_paper.get_data_from_grobid(file_name):
            settings.print_message('Process PFD "{}" is failed, skip.'.format(file_name), 2)
            logger.debug('Process PFD "{}" is failed, skip.'.format(file_name))
            bad_papers += 1
            continue
        papers_counter += 1
        #translated_abstract += 1 if cur_paper.abstract and cur_paper.abstract_ru else 0
        nonempty_abstract +=  1 if cur_paper.abstract else 0
        settings.print_message('Success processed PFD "{}".'.format(file_name), 2)
        logger.debug('Success processed PFD "{}".'.format(file_name))
        if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    return (papers_counter, bad_pdfs, bad_papers, len(papers), nonempty_abstract)


def translate_abstracts():
    """ Get papers with abstract and translate this. """
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    papers_counter = 0
    bad_abstracts = 0
    translated_abstract = 0
    #
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    # get conditions and create standart query
    col_names = "id, abstract"
    PAPERS_SQL = "SELECT {} FROM papers {}".format(col_names, PAPERS_SQL[PAPERS_SQL.lower().find("where"):])
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    logger.debug("{0} papers selected.".format(len(papers)))
    # Get columns from query
    columns = dict([(word, i) for i, word in enumerate(col_names.split(', '))])
    #for N, column in enumerate(dbutils.get_columns_names("papers")):
    #    columns[column.lower()] = N
    for paper_index, paper_info in enumerate(papers):
        settings.print_message("Process paper #{0} (total {1}).".format(paper_index + 1, len(papers)))
        id = paper_info[columns["id"]]
        abstract = paper_info[columns["abstract"]]
        if not abstract:
            msg = "Paper (id: {}) hasn't abstract, skip.".format(paper_index + 1, id)
            settings.print_message(msg, 2)
            logger.debug(msg)
            bad_abstracts += 1
            continue
        msg = "Translate abstract..."
        logger.debug(msg)
        settings.print_message(msg, 2)
        abstract_ru = translate(abstract, to_language='ru')
        if abstract_ru:
            dbutils.update_paper({"id":id, "abstract_ru":abstract_ru,}, True)
            msg = "Successful translated."
            logger.debug(msg)
            settings.print_message(msg, 2)
            translated_abstract += 1
        else:
            msg = "Translated abstract is failed."
            logger.debug(msg)
            settings.print_message(msg, 2)
            bad_abstracts += 1
            continue
        papers_counter += 1
        if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    return (papers_counter, len(papers), bad_abstracts, translated_abstract)


def print_to_log_http_statistic():
    """ This function print statistic of http requests in log. """
    logger.info('HTTP-requests: {0}({1} failed)'.format(utils.REQUEST_STATISTIC['count_requests'],
                                                            len(utils.REQUEST_STATISTIC['failed_requests'])))
    settings.print_message('HTTP-requests: {0} ({1} failed)'.format(utils.REQUEST_STATISTIC['count_requests'],
                                                            len(utils.REQUEST_STATISTIC['failed_requests'])))
    if len(utils.REQUEST_STATISTIC['failed_requests']) > 0:
        logger.info('List failed HTTP-requests:\n{0}'.format("\n".join(utils.REQUEST_STATISTIC['failed_requests'])))

def dispatch(command):
    result = None
    logger.debug("command %s.", command)
    start_time = datetime.now()
    msg = None
    try:
        for case in utils.Switch(command):
            if case('extractAbstractsFromPDF'):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_info_from_PDFs()
                msg = "Processing was successful.\nSuccess updated: %i.\nBad PDFs: %i." \
                        "\nFailed processing: %i.\nTotal papers: %i\n" \
                        "Non-empty abstracts: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("translateAbstracts"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = translate_abstracts()
                msg = "Processing was successful.\nProcessing papers: %i.\n" \
                            "Total papers: %i.\nNon-translated abstracts: %i\n" \
                            "Translated abstracts: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getPapersByKeyWords"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_papers_by_key_words()
                msg = "Processing was successful.\nFounded papers in Google Scholar by keywords: %i\n" \
                             "Added new papers: %i.\nAdded new authors: %i.\n" \
                             "Processed total papers: %i.\nChanges in DB: %i.\n Downloaded PDFs from URL %i.\n Downloaded PDFs from cluster %i.\n" \
                             " Downloaded PDFs from Sci-Hub %i.\n Unavailable PDFs %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getFiles"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_PDFs()
                msg = "Processing was successful.\nDownloads files: %i.\nUnavailable pdf's: %i.\nProcessed total: %i." % result[1:]
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getReferences"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_references()
                msg = "Processing was successful. Processed total papers: %i. Papers without references: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getCities"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_cities()
                msg = "Processing was successful. Processed total papers: %i. Papers without citations: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case(): # default
                logger.warn("Unknown command: %s" % command)
                settings.print_message("Unknown command: %s" % command)
                msg = "Unknown command '{}'".format(command)
                break
        # Fix database changes
        dbutils.commit()
    except KeyboardInterrupt:
        logger.warn("Caught KeyboardInterrupt, terminating processing")
        settings.print_message("Caught KeyboardInterrupt, terminating processing")
        settings.RESULT = "WARNING"
        msg = "User was terminated processing"
        dbutils.rollback()
    except:
        logger.error(traceback.format_exc())
        settings.print_message("Processing finished with error.")
        settings.print_message("For more details, see the log.")
        settings.RESULT = "ERROR"
        msg = traceback.format_exc()
        dbutils.rollback()
    end_time = datetime.now()
    settings.print_message("Run began on {0}".format(start_time))
    settings.print_message("Run ended on {0}".format(end_time))
    settings.print_message("Elapsed time was: {0}".format(end_time - start_time))
    settings.print_message("Last used proxy-server {} (#{}, total {} proxies)".format(
        utils.PROXY_OBJ.current_proxy_ip, utils.PROXY_OBJ.current_proxy_num, utils.PROXY_OBJ.proxies_count))
    logger.debug("Run began on {0}".format(start_time))
    logger.debug("Run ended on {0}".format(end_time))
    logger.debug("Elapsed time was: {0}".format(end_time - start_time))
    logger.debug("Last used proxy-server {} (#{}, total {} proxies, proxies file scans: {})".format(
        utils.PROXY_OBJ.current_proxy_ip, utils.PROXY_OBJ.current_proxy_num, utils.PROXY_OBJ.proxies_count, utils.PROXY_OBJ.scan_proxy_files_count))
    print_to_log_http_statistic()
    settings.DESCR_TRANSACTION = msg

if __name__ == "__main__":
    dispatch(settings.PARAMS["command"])

