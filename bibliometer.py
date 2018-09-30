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
import crossref
from translator import translate

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


def add_authors(paper_db_id, authors, print_level=2):
    """ Add authors for paper """
    # Get and insert in database info about author
    new_authors_count = 0
    settings.print_message("Authors:", print_level)
    for author_info in authors:
        # Create new author entity
        newauthor = author.Author()
        newauthor.get_base_info_from_sch(author_info)
        settings.print_message(
            "Process author '%s'." %
            (newauthor.shortname if newauthor.name is None else newauthor.name),
            print_level +
            2)
        logger.debug("Check exists author and if not then insert into DB.")
        if not newauthor.in_database():
            newauthor.get_info_from_sch()
            # Insert new author into DB
            #settings.print_message("Add author to the database", print_level + 2)
            newauthor.save_to_database()
            new_authors_count += 1
        else:
            settings.print_message(
                "This author already exists, id = %i." %
                newauthor.db_id, print_level + 2)
        # Insert into DB reference
        dbutils.add_author_paper_edge(newauthor.db_id, paper_db_id)
    return new_authors_count


def get_papers_by_key_words():
    logger.debug("Search papers from google.scholar.")
    settings.print_message("Search papers from google.scholar.")
    paper_generator, about_res_count = scholar.search_pubs_query_with_control_params(
        settings.PARAMS, skip_endnote=True)

    if paper_generator is None:
        logger.debug(
            "Soup from google.scholar is None. End command get_papers_by_key_words")
        return (0, 0, 0, 0, 0, 0, 0, 0)

    logger.debug(about_res_count)
    settings.print_message("Google: Found {0} papers.".format(about_res_count))
    new_papers = 0
    new_auth = 0
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    papers_counter = 0
    pdf_url_counter = 0
    pdf_cluster_counter = 0
    pdf_scihub_counter = 0
    pdf_unavailable_counter = 0
    for paper_info in paper_generator:
        # Loop for different versions of paper
        if not paper_info["different_information"]:
            settings.print_message(
                "Not found information about paper #%i, skip." %
                papers_counter, 1)
            continue
        papers_counter += 1
        google_cluster_id = paper_info["general_information"].get("cluster")
        if google_cluster_id:
            db_id = dbutils.check_exists_paper_with_cluster_id(
                str(google_cluster_id))
            if db_id:
                settings.print_message(
                    "This paper already exists, id = {}.".format(db_id), 1)
                continue
        EndNote = scholar.get_info_from_EndNote(
            paper_info["different_information"]["url_scholarbib"], True)
        if not EndNote:
            settings.print_message(
                "Not found information about paper #%i, skip." %
                papers_counter, 1)
            continue
        paper_info["different_information"].update(EndNote)
        logger.debug("Process content of EndNote file #%i\n%s\n%s" % (
            papers_counter, json.dumps(paper_info["general_information"]), json.dumps(paper_info["different_information"])))
        # Create new paper entity
        newpaper = paper.Paper()
        # Fill data from google scholar
        newpaper.get_info_from_sch(paper_info["general_information"],
                                   paper_info["different_information"], 1, paper_info['link_to_pdf'])
        if newpaper.in_database():
            settings.print_message(
                "This paper already exists, id = {}.".format(
                    newpaper.db_id), 1)
            continue
        new_papers += 1
        newpaper.add_to_database()
        new_auth += add_authors(newpaper.db_id, newpaper.authors, 1)
        tmp = download_pdf(
            newpaper.title,
            newpaper.paper_URL,
            newpaper.PDF_URL,
            newpaper.cluster,
            None, newpaper.db_id)
        download_pdf_url, download_pdf_cluster, download_pdf_scihub, try_download = tmp
        if try_download:
            pdf_url_counter += 1 if download_pdf_url else 0
            pdf_cluster_counter += 1 if download_pdf_cluster else 0
            pdf_scihub_counter += 1 if download_pdf_scihub else 0
            pdf_unavailable_counter += 1 if \
                not download_pdf_url and \
                not download_pdf_cluster and \
                not download_pdf_scihub else 0
        # Commit transaction each commit_iterations iterations
        if papers_counter % commit_iterations == 0:
            dbutils.commit(papers_counter)
    return (about_res_count, new_papers, new_auth, papers_counter,
            pdf_url_counter, pdf_cluster_counter, pdf_scihub_counter, pdf_unavailable_counter)


def download_pdf(title, google_url, google_pdf_url,
                 google_cluster_id, DOI, paper_id):
    # Download pdf for paper (first paper if use google cluster)
    download_pdf_url = False
    download_pdf_cluster = False
    download_pdf_scihub = False
    try_download = False
    success_download = False
    fn_tmp_pdf = '{0}tmp_{1}.pdf'.format(settings.PDF_CATALOG, paper_id)
    fn_pdf = '{0}{1}.pdf'.format(settings.PDF_CATALOG, paper_id)
    # load pdf from gs
    if settings.PARAMS["google_get_files"]:
        if google_pdf_url:
            settings.print_message("Try get pdf from Google Scholar.", 1)
            settings.print_message(
                "Getting PDF-file from Google Scholar by url : {0}.".format(google_pdf_url), 2)
            logger.debug(
                "Getting PDF-file from Google Scholar by url : {0}.".format(google_pdf_url))
            try:
                try_download = True
                num_pages = scholar.get_pdf(google_pdf_url, fn_tmp_pdf)
                if num_pages:
                    settings.print_message("Complete!", 2)
                    dbutils.update_pdf_transaction(
                        paper_id, num_pages, "Google Scholar")
                    utils.rename_file(fn_tmp_pdf, fn_pdf)
                    download_pdf_url = True
                    success_download = True
            except KeyboardInterrupt:
                raise
            except BaseException:
                # settings.print_message(traceback.format_exc())
                utils.REQUEST_STATISTIC['failed_requests'].append(
                    google_pdf_url)
                logger.debug(
                    "Failed get pdf from Google Scholar URL={0}".format(google_pdf_url))
                settings.print_message(
                    "failed load PDF from Google Scholar.", 2)
        # load pdf from google scholar cluster by paper url if does not exist
        if not success_download and google_cluster_id and settings.PARAMS[
                "google_cluster_files"]:
            settings.print_message(
                "Try get pdf from Google Scholar cluster {}.".format(google_cluster_id), 1)
            cluster_pdfs_links = scholar.get_pdfs_link_from_cluster(
                google_cluster_id)
            if cluster_pdfs_links is not None:
                cluster_pdfs_links = [
                    url for url in cluster_pdfs_links if google_pdf_url != url]
                for google_pdf_url in cluster_pdfs_links:
                    settings.print_message(
                        "Getting PDF-file from cluster Google Scholar by url: {0}.".format(google_pdf_url), 2)
                    logger.debug(
                        "Getting PDF-file from cluster Google Scholar by url: {0}.".format(google_pdf_url))
                    try:
                        try_download = True
                        num_pages = scholar.get_pdf(google_pdf_url, fn_tmp_pdf)
                        if num_pages:
                            settings.print_message("Complete!", 2)
                            dbutils.update_pdf_transaction(
                                paper_id, num_pages, "Google Scholar Cluster")
                            utils.rename_file(fn_tmp_pdf, fn_pdf)
                            download_pdf_cluster = True
                            success_download = True
                            break
                    except KeyboardInterrupt:
                        raise
                    except BaseException:
                        utils.REQUEST_STATISTIC['failed_requests'].append(
                            google_pdf_url)
                        logger.debug(
                            "Failed get pdf from Google Scholar cluster URL={0}".format(google_pdf_url))
                        settings.print_message(
                            "failed load PDF from Google Scholar cluster.", 2)
            else:
                logger.debug(
                    "Failed get pdf from Google Scholar cluster. Cluster hasn't links to PDFs.")
                settings.print_message(
                    "failed load PDF from Google Scholar cluster. Cluster hasn't links to PDFs.", 2)
    # load pdf from scihub by paper url if does not exist
    if (google_url or DOI or settings.PARAMS["sci_hub_title_search"]
            ) and not success_download and settings.PARAMS["sci_hub_files"]:
        settings.print_message("Try get pdf by paper url on sci-hub.", 1)
        settings.print_message("Getting PDF-file from Sci-Hub.", 2)
        logger.debug("Getting PDF-file on Sci-Hub.")
        try:
            try_download = True
            if DOI:
                num_pages = scihub.get_pdf(DOI, fn_tmp_pdf)
            else:
                num_pages = scihub.get_pdf(google_url, fn_tmp_pdf)
                if not num_pages and settings.PARAMS["sci_hub_title_search"]:
                    num_pages = scihub.get_pdf(title, fn_tmp_pdf)
            if num_pages:
                settings.print_message("Complete!", 2)
                dbutils.update_pdf_transaction(paper_id, num_pages, "Sci-hub")
                utils.rename_file(fn_tmp_pdf, fn_pdf)
                success_download = True
                download_pdf_scihub = True
            else:
                settings.print_message("PDF unavailable on sci-hub.", 2)
        except KeyboardInterrupt:
            raise
        except BaseException:
            utils.REQUEST_STATISTIC['failed_requests'].append(google_url)
            logger.debug(
                "Failed get pdf from sci-hub URL={0}".format(google_url))
            settings.print_message(
                "failed load PDF from sci-hub URL={0}".format(google_url), 2)
            # continue
    if not success_download and try_download:
        settings.print_message("Downolad PDF unavailable.", 1)
        utils.delfile(fn_tmp_pdf)
    return (download_pdf_url, download_pdf_cluster,
            download_pdf_scihub, try_download)


def select_papers(col_names, grobid_paper=False):
    """ select papers from DB """
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    # get conditions and create standart query
    PAPERS_SQL = "SELECT {} FROM {} {}".format(col_names,
                                               "grobid_papers" if grobid_paper else "papers", PAPERS_SQL[PAPERS_SQL.lower().find("where"):])
    papers = dbutils.execute_sql(PAPERS_SQL)
    total_papers = len(papers)
    settings.print_message("{0} papers selected.".format(total_papers))
    logger.debug("{0} papers selected.".format(total_papers))
    # Get columns from query
    columns = dict([(word, i) for i, word in enumerate(col_names.split(', '))])
    return (papers, columns, total_papers)


def select_authors(col_names):
    """ select authors from DB """
    logger.debug("Select authors from database.")
    settings.print_message("Select authors from database.")
    AUTHORS_SQL = settings.PARAMS["authors"]
    # get conditions and create standart query
    AUTHORS_SQL = "SELECT {} FROM {} {}".format(col_names,
                                               "authors", AUTHORS_SQL[AUTHORS_SQL.lower().find("where"):])
    authors = dbutils.execute_sql(AUTHORS_SQL)
    total_authors = len(authors)
    settings.print_message("{0} authors selected.".format(total_authors))
    logger.debug("{0} authors selected.".format(total_authors))
    # Get columns from query
    columns = dict([(word, i) for i, word in enumerate(col_names.split(', '))])
    return (authors, columns, total_authors)


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
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    papers, columns, total = select_papers(
        "id, doi, google_url, google_file_url, google_cluster_id, title")
    for paper_index, newpaper in enumerate(papers):
        settings.print_message("Process paper #{} (total {}) - {}.".format(
            paper_index + 1, total, newpaper[columns['title']]))
        id = newpaper[columns["id"]]
        title = newpaper[columns["title"]]
        DOI = newpaper[columns["doi"]]
        google_URL = newpaper[columns["google_url"]]
        pdf_google_URL = newpaper[columns["google_file_url"]]
        pdf_google_cluster_URL = newpaper[columns["google_cluster_id"]]
        if (google_URL is None) and (pdf_google_URL is None) and (
                pdf_google_cluster_URL is None) and (DOI is None):
            settings.print_message('DOI and URLs is empty, skip this paper.')
            logger.debug("DOI and URLs is empty, skip this paper.")
            continue
        tmp = download_pdf(
            title,
            google_URL,
            pdf_google_URL,
            pdf_google_cluster_URL,
            DOI,
            id)
        download_pdf_url, download_pdf_cluster, download_pdf_scihub, try_download = tmp
        if try_download:
            pdf_url_counter += 1 if download_pdf_url else 0
            pdf_cluster_counter += 1 if download_pdf_cluster else 0
            pdf_scihub_counter += 1 if download_pdf_scihub else 0
            pdf_unavailable_counter += 1 if \
                not download_pdf_url and \
                not download_pdf_cluster and \
                not download_pdf_scihub else 0
        if paper_index % commit_iterations == 0:
            dbutils.commit(paper_index)
    new_files_count = pdf_scihub_counter + pdf_cluster_counter + pdf_url_counter
    result = (
        True,
        new_files_count,
        pdf_unavailable_counter,
        pdf_unavailable_counter +
        new_files_count)
    return result


def add_adge_to_sitation_graph(
        parent_paper_db_id, child_paper_db_id, serial_number):
    """ Add new adge to citation graph. """
    # Add reference in DB
    edge_params = \
        {
            "IDpaper1": parent_paper_db_id,
            "IDpaper2": child_paper_db_id,
        }
    logger.debug("Check exists edge and if not then insert into DB.")
    if not dbutils.check_exists_paper_paper_edge(edge_params):
        logger.debug(
            "Add edge ({0}, {1}) in DB.".format(
                parent_paper_db_id,
                child_paper_db_id))
        dbutils.add_paper_paper_edge(
            parent_paper_db_id,
            child_paper_db_id,
            serial_number)
    else:
        logger.debug(
            "This edge ({0}, {1}) already exists.".format(
                parent_paper_db_id,
                child_paper_db_id))


def get_references():
    """This function loads links to articles for papers selected from the database"""
    # this paper -> other papers
    # statistic for childs papers
    new_authors_count = 0
    new_papers_count = 0
    new_grobid_papers_count = 0
    total_processed = 0
    total_refereneces_from_all_pdfs = 0
    papers_without_ref = 0
    identified_papers = 0
    many_references = 0
    #
    many_results = 0
    many_versions = 0
    not_found = 0
    #
    methods = [0, 0, 0, 0]
    #
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    papers, columns, total = select_papers("title, id, year")
    for parent_paper_index, parent_paper in enumerate(papers):
        year = parent_paper[columns['year']]
        parent_paper_db_id = parent_paper[columns["id"]]
        title = parent_paper[columns["title"]]
        settings.print_message("Get references for paper #{} (total {}) - {}{}.".format(parent_paper_index + 1,
                                                                                        total, title, ", " + str(year) if year else ""))
        logger.debug(
            "Get references for paper #{} (total {}) - {}.".format(
                parent_paper_index + 1, total, title))
        # Get referensec from PDF
        file_name = "{0}{1}.pdf".format(
            settings.PDF_CATALOG, parent_paper_db_id)
        if not os.path.exists(file_name):
            settings.print_message(
                'PDF "{}" not found, skip this paper.'.format(file_name), 2)
            logger.debug(
                'PDF "{}" not found, skip this paper.'.format(file_name))
            continue
        references = grobid.processReferencesDocument(file_name)
        total_processed += 1
        if not references:
            settings.print_message(
                'References from PFD "{}" is not extracted, skip.'.format(file_name), 2)
            logger.debug(
                'References from PFD "{}" is not extracted, skip.'.format(file_name))
            papers_without_ref += 1
            continue
        total_references = len(references)
        if settings.PARAMS["max_references_per_paper"] < total_references:
            msg = 'References from PFD "{}" is so much (>{}), skip.'.format(
                file_name, settings.PARAMS["max_references_per_paper"])
            settings.print_message(msg, 2)
            logger.debug(msg)
            many_references += 1
            continue
        total_refereneces_from_all_pdfs += total_references
        dbutils.update_paper(
            {
                "references_count": total_references,
                "id": parent_paper_db_id
            }
        )

        for ref_index, reference in enumerate(references):
            settings.print_message(
                "Process paper #{} from references (total {}).".format(
                    ref_index + 1, total_references), 2)
            logger.debug(
                "Process paper #{} from references (total {}).".format(
                    ref_index + 1, total_references))
            logger.debug(
                "Data about reference: {}".format(
                    json.dumps(reference)))
            grobid_paper = paper.Paper()
            grobid_paper.authors = set(
                reference["authors"]) if reference["authors"] else []
            grobid_paper.title = reference["ref_title"] if reference["ref_title"] else \
                reference["journal_pubnote"].get("journal_title")
            grobid_paper.year = reference["journal_pubnote"].get("year")
            grobid_paper.DOI = reference["journal_pubnote"].get("doi")
            grobid_paper.start_page = reference["journal_pubnote"].get(
                "start_page")
            grobid_paper.end_page = reference["journal_pubnote"].get(
                "end_page")
            msg = "Reference paper has not title. Add this reference to DB as grobid paper."
            if reference["ref_title"] or reference["journal_pubnote"]["journal_title"]:
                msg = "Search paper '{}'{} from google.scholar.".format(
                    grobid_paper.title, grobid_paper.year if grobid_paper.year else "")
                logger.debug(msg)
                settings.print_message(msg, 3)

                google_papers = None
                for i in range(4):
                    logger.debug("Search with \"\"." if i <
                                 2 else "Search without \"\".")
                    # 0 -         "" and         year
                    # 1 -         "" and without year
                    # 2 - without "" and         year
                    # 3 - without "" and without year
                    search_params = {
                        "query": ('intitle:"{}"' if i < 2 else 'intitle:{}').format(grobid_paper.title),
                        "date_from": grobid_paper.year if i % 2 == 0 else "",
                        "date_to": grobid_paper.year if i % 2 == 0 else "",
                        "patents": True,
                        "citations": False,
                    }
                    methods[i] += 1
                    paper_generator, about_res_count = scholar.search_pubs_query_with_control_params(
                        search_params, skip_endnote=True, print_level=-1)
                    if not paper_generator:
                        continue
                    if about_res_count > settings.PARAMS["google_max_papers"]:
                        continue
                    google_papers = [paper for paper in paper_generator]
                    if google_papers:
                        break
                logger.debug("Methods STATISTIC: [{}]".format(
                    ", ".join(map(str, methods))))
                # Check search results.
                msg = "Papers not found, indentification unavailable. Add this reference to DB as grobid paper."
                if google_papers:
                    # Check count papers from google search results.
                    if about_res_count <= settings.PARAMS["google_max_papers"]:
                        logger.debug(about_res_count)
                        logger.debug(
                            "Google: Found {0} papers.".format(about_res_count))
                        # Check results on one paper (maybe average versions
                        # about one paper).
                        papers_count = len(
                            {paper["general_information"]["title"].lower() for paper in google_papers})
                        max_ident_papers = settings.PARAMS.get("google_max_papers_for_identification") \
                            if settings.PARAMS.get("google_max_papers_for_identification") else 1
                        if papers_count <= max_ident_papers:
                            best_paper = None
                            for google_paper in google_papers:
                                logger.debug(
                                    "G paper\n{}\nBest paper\n{}".format(
                                        json.dumps(google_paper),
                                        json.dumps(best_paper)))
                                EndNote = scholar.get_info_from_EndNote(
                                    google_paper["different_information"]["url_scholarbib"], True)
                                if not EndNote:
                                    continue
                                google_paper["different_information"].update(
                                    EndNote)
                                if not best_paper or len(best_paper["different_information"]["EndNote"]) < len(
                                        google_paper["different_information"]["EndNote"]):
                                    best_paper = google_paper
                            if best_paper:
                                logger.debug("Process content of EndNote file for paper from references\n{}\n{}".format(json.dumps(best_paper["general_information"]),
                                                                                                                        json.dumps(best_paper["different_information"])))
                                # Fill data from google scholar
                                settings.print_message(
                                    "Paper was identified on google.scholar and processed.".format(
                                        grobid_paper.db_id), 3)
                                grobid_paper.get_info_from_sch(best_paper["general_information"],
                                                               best_paper["different_information"], 1, best_paper['link_to_pdf'])
                                if grobid_paper.in_database():
                                    settings.print_message(
                                        "This paper already exists, id = {}.".format(
                                            grobid_paper.db_id), 3)
                                else:
                                    new_papers_count += 1
                                    if new_papers_count % commit_iterations == 0:
                                        dbutils.commit(new_papers_count)
                                    grobid_paper.add_to_database()
                                    new_authors_count += add_authors(
                                        grobid_paper.db_id, grobid_paper.authors, 4)
                                add_adge_to_sitation_graph(
                                    parent_paper_db_id, grobid_paper.db_id, ref_index + 1)
                                identified_papers += 1
                                # Success identification, process next
                                # reference.
                                continue
                        else:
                            many_versions += 1
                            msg = "Found different papers on scholar, indentification unavailable. Add this reference to DB as grobid paper."
                    else:
                        msg = "Found many papers on scholar, indentification unavailable. Add this reference to DB as grobid paper."
                        many_results += 1
            # Identification unavailable, add grobid paper to DB.
            settings.print_message(msg, 3)
            logger.debug(msg)
            if grobid_paper.in_database_as_grobid_paper():
                settings.print_message(
                    "This grobid paper already exists, id = {}.".format(
                        grobid_paper.grobid_db_id), 3)
            else:
                new_grobid_papers_count += 1
                grobid_paper.make_EndNote()
                grobid_paper.serial_number = ref_index + 1
                grobid_paper.add_to_database_as_grobid_paper(
                    parent_paper_db_id)
        dbutils.update_references_transaction(parent_paper_db_id)
    not_found = new_grobid_papers_count - many_results - many_versions
    logger.debug(
        "STATISTIC ABOUT SEARCH ON GOOGLE:\nNot found papers: {}\nMany results: {}\nMany versions: {}")
    return (total_processed, papers_without_ref, total_refereneces_from_all_pdfs, identified_papers,
            new_papers_count, new_authors_count, new_grobid_papers_count, many_references)


def get_cities():
    """This function loads articles that reference selected papers from the database"""
    # other papers -> this paper
    # statistic for childs papers
    new_authors_count = 0
    new_papers_count = 0
    total_processed = 0
    #
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    papers, columns, total = select_papers(
        "title, id, google_cluster_id, year")
    for parent_paper_index, parent_paper in enumerate(papers):
        year = parent_paper[columns["year"]]
        parent_paper_db_id = parent_paper[columns["id"]]
        google_cluster_id = parent_paper[columns["google_cluster_id"]]
        title = parent_paper[columns["title"]]
        settings.print_message("Get cities for paper #{} (total {}) - {}{}.".format(parent_paper_index + 1,
                                                                                    total, title, ", " + str(year) if year else ""))
        logger.debug(
            "Get cities for paper #{} (total {}) - {}.".format(parent_paper_index + 1, total, title))
        if (google_cluster_id is None):
            settings.print_message(
                "Google cluster id is empty, skip this paper.")
            logger.debug("Google cluster id is empty, skip this paper.")
            continue
        # Search cities
        logger.debug("Search cities papers from google.scholar...")
        settings.print_message("Search cities papers from google.scholar.", 2)
        paper_generator, about_res_count = scholar.search_cities(
            google_cluster_id, skip_endnote=True, params=settings.PARAMS, print_level=3)

        if paper_generator is None:
            settings.print_message("Cities not found, skip.", 2)
            logger.debug("Soup from google.scholar is empty, skip.")
            continue
        logger.debug(about_res_count)
        logger.debug("Google: Found {0} papers.".format(about_res_count))
        child_processed = False
        for child_paper_index, paper_info in enumerate(paper_generator):
            child_processed = True
            if not paper_info["different_information"]:
                settings.print_message(
                    "Not found information about child paper #{}, skip.".format(
                        child_paper_index + 1), 3)
                continue
            google_cluster_id = paper_info["general_information"].get(
                "cluster")
            if google_cluster_id:
                db_id = dbutils.check_exists_paper_with_cluster_id(
                    str(google_cluster_id))
                if db_id:
                    settings.print_message(
                        "This paper already exists, id = {}.".format(db_id), 3)
                    total_processed += 1
                    # other papers -> this paper
                    add_adge_to_sitation_graph(db_id, parent_paper_db_id, None)
                    continue
            EndNote = scholar.get_info_from_EndNote(
                paper_info["different_information"]["url_scholarbib"], True)
            if not EndNote:
                settings.print_message(
                    "Not found information about paper #%i, skip." %
                    (child_paper_index + 1), 1)
                continue
            paper_info["different_information"].update(EndNote)
            logger.debug("Process content of EndNote file #{} for root paper #{}\n{}\n{}".format(
                child_paper_index + 1, parent_paper_index +
                1, json.dumps(paper_info["general_information"]),
                json.dumps(paper_info["different_information"])))
            # Create new paper entity
            newpaper = paper.Paper()
            # Fill data from google scholar
            newpaper.get_info_from_sch(paper_info["general_information"],
                                       paper_info["different_information"], 1, paper_info['link_to_pdf'])
            if newpaper.in_database():
                settings.print_message(
                    "This paper already exists, id = {}.".format(
                        newpaper.db_id), 3)
            else:
                new_papers_count += 1
                newpaper.add_to_database()
                #settings.print_message("Adding a paper to the database", 3)
                new_authors_count += add_authors(newpaper.db_id,
                                                 newpaper.authors, 4)
            total_processed += 1
            # other papers -> this paper
            add_adge_to_sitation_graph(
                newpaper.db_id, parent_paper_db_id, None)
            if new_papers_count > 0 and new_papers_count % commit_iterations == 0:
                dbutils.commit(new_papers_count)
        if not child_processed:
            settings.print_message("Cities not found, skip.", 2)
            logger.debug("Cities not found, skip.")
        dbutils.update_cities_transaction(parent_paper_db_id)
    return (total, total_processed, new_papers_count, new_authors_count)


def get_info_from_PDFs():
    """ This function get info from PDFs by GROBID """
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    papers_counter = 0
    bad_papers = 0
    bad_pdfs = 0
    unavailable_files_counter = 0
    nonempty_abstract = 0
    #
    papers, columns, total = select_papers("id, year, doi")
    for paper_index, paper_info in enumerate(papers):
        settings.print_message(
            "Process paper #{0} (total {1}).".format(
                paper_index + 1, len(papers)))
        id = paper_info[0]
        year = paper_info[1]
        doi = paper_info[2]
        file_name = "{0}{1}.pdf".format(settings.PDF_CATALOG, id)
        if not os.path.exists(file_name):
            settings.print_message(
                'PDF "{}" not found, skip this paper.'.format(file_name), 2)
            logger.debug(
                'PDF "{}" not found, skip this paper.'.format(file_name))
            bad_pdfs += 1
            continue
        cur_paper = paper.Paper()
        cur_paper.db_id = id
        cur_paper.year = year
        cur_paper.DOI = doi
        if not cur_paper.get_data_from_grobid(file_name):
            settings.print_message(
                'Process PFD "{}" is failed, skip.'.format(file_name), 2)
            logger.debug('Process PFD "{}" is failed, skip.'.format(file_name))
            bad_papers += 1
            continue
        papers_counter += 1
        #translated_abstract += 1 if cur_paper.abstract and cur_paper.abstract_ru else 0
        nonempty_abstract += 1 if cur_paper.abstract else 0
        settings.print_message(
            'Success processed PFD "{}".'.format(file_name), 2)
        logger.debug('Success processed PFD "{}".'.format(file_name))
        if papers_counter % commit_iterations == 0:
            dbutils.commit(papers_counter)
    return (papers_counter, bad_pdfs, bad_papers,
            len(papers), nonempty_abstract)


def translate_abstracts():
    """ Get papers with abstract and translate this. """
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    papers_counter = 0
    bad_abstracts = 0
    translated_abstract = 0
    #
    papers, columns, total = select_papers("id, abstract")
    for paper_index, paper_info in enumerate(papers):
        settings.print_message(
            "Process paper #{0} (total {1}).".format(
                paper_index + 1, len(papers)))
        id = paper_info[columns["id"]]
        abstract = paper_info[columns["abstract"]]
        if not abstract:
            msg = "Paper (id: {}) hasn't abstract, skip.".format(
                paper_index + 1, id)
            settings.print_message(msg, 2)
            logger.debug(msg)
            bad_abstracts += 1
            continue
        msg = "Translate abstract..."
        logger.debug(msg)
        settings.print_message(msg, 2)
        abstract_ru = translate(abstract, to_language='ru')
        if abstract_ru:
            dbutils.update_paper(
                {"id": id, "abstract_ru": abstract_ru, }, True)
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
        if papers_counter % commit_iterations == 0:
            dbutils.commit(papers_counter)
    return (papers_counter, len(papers), bad_abstracts, translated_abstract)


def get_DOI_by_title():
    """ Get DOI for papers by title (use crossref.org). """
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    papers_counter = 0
    non_empty_DOI = 0
    #
    papers, columns, total = select_papers("id, title")
    for paper_index, paper_info in enumerate(papers):
        id = paper_info[columns["id"]]
        title = paper_info[columns["title"]]
        settings.print_message(
            "Process paper #{0} - '{2}' (total {1}).".format(paper_index + 1, len(papers), title))
        msg = "Get DOI from crossref.org..."
        logger.debug(msg)
        settings.print_message(msg, 2)
        DOI = crossref.get_DOI_by_title(title)
        if DOI:
            dbutils.update_paper({"id": id, "DOI": DOI, }, True)
            msg = "DOI: {}.".format(DOI)
            logger.debug(msg)
            settings.print_message(msg, 2)
            non_empty_DOI += 1
        else:
            msg = "DOI is unavailable."
            logger.debug(msg)
            settings.print_message(msg, 2)
        papers_counter += 1
        if papers_counter % commit_iterations == 0:
            dbutils.commit(papers_counter)
    return (papers_counter, non_empty_DOI, papers_counter - non_empty_DOI)


def process_GROBID_papers():
    """ This function select grobid papers, find this on scholar and create new full paper """
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    bad_papers = 0
    new_papers = 0
    new_authors = 0
    #
    papers, columns, total_db_papers = select_papers(
        "id, title, year, google_cluster_id, serial_number, r_paper", grobid_paper=True)
    for paper_index, paper_info in enumerate(papers):
        grobid_paper_db_id = paper_info[columns["id"]]
        title = paper_info[columns["title"]]
        year = paper_info[columns["year"]]
        google_cluster_id = paper_info[columns["google_cluster_id"]]
        serial_number = paper_info[columns["serial_number"]]
        parent_paper_db_id = paper_info[columns["r_paper"]]

        settings.print_message("Get info about paper #{} (total {}) {}{}.".format(paper_index + 1,
                                                                                  total_db_papers, "- " + title if title else "", ", " + str(year) if year and title else ""))
        if not google_cluster_id:
            msg = "Paper (id: {}) hasn't google_cluster_id, skip.".format(
                grobid_paper_db_id)
            settings.print_message(msg, 2)
            logger.debug(msg)
            bad_papers += 1
            continue

        # Check cluster id in DB. If exists, add adge and all.
        db_id = dbutils.check_exists_paper_with_cluster_id(google_cluster_id)
        if not db_id:
            msg = "Get info from Google cluster (cluster id='{}').".format(
                google_cluster_id)
            logger.debug(msg)
            settings.print_message(msg, 2)

            try:
                paper_info = scholar.get_paper_from_cluster(
                    google_cluster_id, print_level=1)
            except KeyboardInterrupt:
                raise
            except BaseException:
                msg = "Failed get information from cluster, skip."
                settings.print_message(msg, 2)
                logger.debug(msg)
                bad_papers += 1
                continue

            # Loop for different versions of paper
            if not paper_info or not paper_info["different_information"]:
                settings.print_message(
                    "Not found information about paper, skip.", 1)
                continue
            paper_addition_information = paper_info["different_information"]
            logger.debug("Process content of EndNote file #{}\n{}\n{}".format(
                paper_index + 1, json.dumps(paper_info["general_information"]), json.dumps(paper_addition_information)))

            # Create new paper entity
            newpaper = paper.Paper()
            # Fill data from google scholar
            newpaper.get_info_from_sch(paper_info["general_information"],
                                       paper_addition_information, 1, paper_info['link_to_pdf'])
            if newpaper.in_database():
                settings.print_message(
                    "This paper already exists, id = {}.".format(
                        newpaper.db_id), 1)
                dbutils.update_paper({"id": newpaper.db_id, "google_cluster_id": google_cluster_id, })
            else:
                new_papers += 1
                newpaper.add_to_database()
                new_authors += add_authors(newpaper.db_id, newpaper.authors, 2)
            db_id = newpaper.db_id
        else:
            msg = "Paper from cluster (cluster id='{}') already exists.".format(
                google_cluster_id)
            logger.debug(msg)
            settings.print_message(msg, 2)
        settings.print_message("Move grobid paper into main papers table.", 2)
        # Delete from grobid_papers
        logger.debug("Delete paper (grobid paper id={}) from grobid papers.".format(
            grobid_paper_db_id))
        dbutils.delete_paper_from_grobid_papers(grobid_paper_db_id)
        # Add adge in paper_paper
        add_adge_to_sitation_graph(
            parent_paper_db_id,
            db_id,
            serial_number)

        if (paper_index + 1) % commit_iterations == 0:
            dbutils.commit(paper_index + 1)
    return (total_db_papers, total_db_papers -
            bad_papers, new_papers, new_authors)


def get_papers_by_author():
    """ This function get papers of authors. """
    commit_iterations = int(
        settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else inf
    # statistic
    authors_with_empty_papers = 0
    bad_papers = 0
    new_papers = 0
    new_authors = 0
    processed_papers = 0
    #
    authors, columns, total_db_authors = select_authors("id, google_id, name")
    for author_index, author_info in enumerate(authors):
        id = author_info[columns["id"]]
        google_id = author_info[columns["google_id"]]
        name = author_info[columns["name"]]
        msg = "Get papers of the author #{} whith google id={} - {} (total {}).".format(
            author_index + 1, google_id, name, total_db_authors)
        settings.print_message(msg)
        logger.info(msg)
        google_cluster_ids = scholar.get_author_papers_cluster_id(google_id)
        if not google_cluster_ids:
            msg = "Author has empty list of papers, skip."
            logger.debug(msg)
            settings.print_message(msg, 2)
            authors_with_empty_papers += 1
        total_papers = len(google_cluster_ids)
        for paper_index, google_cluster_id in enumerate(google_cluster_ids):
            processed_papers += 1
            msg = "Get info about paper #{} (total {}) with google cluster id={}.".format(
                paper_index + 1, total_papers, google_cluster_id)
            settings.print_message(msg, 2)
            logger.debug(msg)
            # Check cluster id in DB.
            db_id = dbutils.check_exists_paper_with_cluster_id(google_cluster_id)
            if not db_id:
                msg = "Get info from Google cluster (cluster id='{}').".format(
                    google_cluster_id)
                logger.debug(msg)
                settings.print_message(msg, 4)

                try:
                    paper_info = scholar.get_paper_from_cluster(
                        google_cluster_id, print_level=3, max_endnote=True)
                except KeyboardInterrupt:
                    raise
                except BaseException:
                    logger.error(traceback.format_exc())
                    msg = "Failed get information from cluster, skip."
                    settings.print_message(msg, 6)
                    logger.debug(msg)
                    bad_papers += 1
                    continue

                # Loop for different versions of paper
                if not paper_info or not paper_info["different_information"]:
                    settings.print_message(
                        "Not found information about paper, skip.", 6)
                    continue
                paper_addition_information = paper_info["different_information"]
                logger.debug("Process content of EndNote file #{}\n{}\n{}".format(
                    paper_index + 1, json.dumps(paper_info["general_information"]), json.dumps(paper_addition_information)))

                # Create new paper entity
                newpaper = paper.Paper()
                # Fill data from google scholar
                newpaper.get_info_from_sch(paper_info["general_information"],
                                           paper_addition_information, 1, paper_info['link_to_pdf'])
                if newpaper.in_database():
                    settings.print_message(
                        "This paper already exists, id={}.".format(
                            newpaper.db_id), 4)
                    dbutils.update_paper({"id": newpaper.db_id, "google_cluster_id": google_cluster_id, })
                else:
                    new_papers += 1
                    newpaper.add_to_database()
                    new_authors += add_authors(newpaper.db_id, newpaper.authors, 2)
                db_id = newpaper.db_id
            else:
                msg = "This paper already exists, id={}.".format(db_id)
                logger.debug(msg)
                settings.print_message(msg, 4)
            if (paper_index + 1) % commit_iterations == 0:
                dbutils.commit(paper_index + 1)
    return (total_db_authors, authors_with_empty_papers, processed_papers, 
            processed_papers - bad_papers, new_papers, new_authors)


def print_to_log_http_statistic():
    """ This function print statistic of http requests in log. """
    logger.info('HTTP-requests: {0}({1} failed)'.format(utils.REQUEST_STATISTIC['count_requests'],
                                                        len(utils.REQUEST_STATISTIC['failed_requests'])))
    settings.print_message('HTTP-requests: {0} ({1} failed)'.format(utils.REQUEST_STATISTIC['count_requests'],
                                                                    len(utils.REQUEST_STATISTIC['failed_requests'])))
    if len(utils.REQUEST_STATISTIC['failed_requests']) > 0:
        logger.info('List failed HTTP-requests:\n{0}'.format(
            "\n".join(utils.REQUEST_STATISTIC['failed_requests'])))


def print_to_log_captcha_statistic():
    """ This function print statistic of sci-hub CAPTCHA solving in log. """
    if utils.CAPTCHA_STATISTIC["total"] > 0:
        msg = "CAPTCHA solve statistic:\n Total: {}\n Solved: {} ({:.3f}%)\n At once solved: {} ({:.3f}%)\n Several attempts: {:.1f}".format(
            utils.CAPTCHA_STATISTIC["total"],
            utils.CAPTCHA_STATISTIC["total"] -
            utils.CAPTCHA_STATISTIC["not_solved"],
            (utils.CAPTCHA_STATISTIC["total"] - utils.CAPTCHA_STATISTIC["not_solved"]
             ) * 100. / utils.CAPTCHA_STATISTIC["total"],
            utils.CAPTCHA_STATISTIC["total"] -
            utils.CAPTCHA_STATISTIC["solved_by_several_attempts"],
            (utils.CAPTCHA_STATISTIC["total"] - utils.CAPTCHA_STATISTIC["solved_by_several_attempts"]
             ) * 100. / utils.CAPTCHA_STATISTIC["total"],
            utils.CAPTCHA_STATISTIC["total_attempts"] * 1. / utils.CAPTCHA_STATISTIC["total"])
        logger.debug(
            "Cur captcha statistic: {}".format(
                json.dumps(
                    utils.CAPTCHA_STATISTIC)))
        logger.info(msg)
        settings.print_message(msg)


def dispatch(command):
    result = None
    logger.debug("command %s.", command)
    start_time = datetime.now()
    msg = None
    try:
        if utils.PROXY_OBJ.proxies_count < utils.PROXY_OBJ.MIN_PROXIES_COUNT:
            msg = "Too few proxy servers. Requires a count of proxies >= {}".format(
                utils.PROXY_OBJ.MIN_PROXIES_COUNT)
            settings.print_message(msg)
            raise Exception(msg)
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
                    "Processed total papers: %i.\n Downloaded PDFs from URL %i.\n Downloaded PDFs from cluster %i.\n" \
                    " Downloaded PDFs from Sci-Hub %i.\n Unavailable PDFs %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                print_to_log_captcha_statistic()
                break
            if case("getFiles"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_PDFs()
                msg = "Processing was successful.\nDownloads files: %i.\nUnavailable pdf's: %i.\nProcessed total: %i." % result[
                    1:]
                logger.debug(msg)
                settings.print_message(msg)
                print_to_log_captcha_statistic()
                break
            if case("getReferences"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_references()
                msg = "Processing was successful.\nProcessed total papers: %i.\nPapers without references: %i.\nReceived from GROBID reference papers: %i.\nIdentified by Google Scholar reference papers: %i.\nAdded new papers: %i.\nAdded new authors: %i.\nAdded reference papers into grobid_papers table: %i\nSkipped papers with too many references: %i" % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getCities"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_cities()
                msg = "Processing was successful.\nProcessed total papers: %i.\nFounded and processed citing papers: %i.\nAdded new papers: %i.\nAdded new authors: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("processGROBIDpapers"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = process_GROBID_papers()
                msg = "Processing was successful.\nProcessed total grobid papers: %i.\nMoved grobid papers into main papers table: %i.\nAdded new papers: %i.\nAdded new authors: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getDOIbyTitle"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_DOI_by_title()
                msg = "Processing was successful.\nProcessing papers: %i.\n" \
                    "Non-empty DOI: %i\n" \
                    "Unavailable DOI: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case("getPapersByAuthor"):
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_papers_by_author()
                msg = "Processing was successful.\nProcessed authors: %i.\n" \
                    "Authors without google papers: %i.\nTotal processed papers: %i.\n" \
                    "Successful processed papers: %i.\nAdded new papers: %i.\nAdded new authors: %i." % result
                logger.debug(msg)
                settings.print_message(msg)
                break
            if case():  # default
                logger.warn("Unknown command: %s" % command)
                settings.print_message("Unknown command: %s" % command)
                msg = "Unknown command '{}'".format(command)
                break
        # Fix database changes
        dbutils.commit()
    except KeyboardInterrupt:
        logger.warn("Caught KeyboardInterrupt, terminating processing")
        settings.print_message(
            "Caught KeyboardInterrupt, terminating processing")
        settings.RESULT = "WARNING"
        msg = "User was terminated processing"
        dbutils.rollback()
    except BaseException:
        logger.error(traceback.format_exc())
        settings.print_message("Processing finished with error.")
        settings.print_message("For more details, see the log.")
        settings.RESULT = "ERROR"
        msg = traceback.format_exc()
        dbutils.rollback()
    end_time = datetime.now()
    settings.print_message("Run began on {0}".format(start_time))
    settings.print_message("Run ended on {0}".format(end_time))
    settings.print_message(
        "Elapsed time was: {0}".format(
            end_time - start_time))
    logger.debug("Run began on {0}".format(start_time))
    logger.debug("Run ended on {0}".format(end_time))
    logger.debug("Elapsed time was: {0}".format(end_time - start_time))
    if utils.PROXY_OBJ.proxies_count >= utils.PROXY_OBJ.MIN_PROXIES_COUNT:
        settings.print_message("Last used proxy-server {} (#{}, total {} proxies, proxies file scans: {})".format(
            utils.PROXY_OBJ.current_proxy_ip, utils.PROXY_OBJ.current_proxy_num, utils.PROXY_OBJ.proxies_count, utils.PROXY_OBJ.scan_proxy_files_count))
        logger.debug("Last used proxy-server {} (#{}, total {} proxies, proxies file scans: {})".format(
            utils.PROXY_OBJ.current_proxy_ip, utils.PROXY_OBJ.current_proxy_num, utils.PROXY_OBJ.proxies_count, utils.PROXY_OBJ.scan_proxy_files_count))
    print_to_log_http_statistic()
    settings.DESCR_TRANSACTION = msg


if __name__ == "__main__":
    dispatch(settings.PARAMS["command"])
