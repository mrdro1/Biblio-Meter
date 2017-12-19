# -*- coding: utf-8 -*-
import sys
import traceback
import logging
import os
import queue
import json
from datetime import datetime
import random
#
import settings
import dbutils
import utils
import paper
import author
import scholar
import researchgate
import scihub

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

def get_papers_by_key_words():
    """This function searches for articles according to the given parameters and downloads the information about them and authors into database"""
    logger.debug("Search papers from google.scholar.")
    settings.print_message("Search papers from google.scholar.")
    paper_generator, about_res_count = scholar.search_pubs_query_with_control_params(settings.PARAMS)
    if paper_generator is None:
        logger.debug("Soup from google.scholar is None. End command get_papers_by_key_words")
        return (0, 0, 0)
    logger.debug(about_res_count)
    settings.print_message("Google: Found {0} papers.".format(about_res_count))
    number_of_papers_compared = int(settings.PARAMS["max_researchgate_papers"])
    if number_of_papers_compared <= 0: utils.skip_RG_stage_for_all()
    new_papers = 0
    new_auth = 0
    max_papers_count = int(settings.PARAMS["max_google_papers"])
    commit_iterations = int(settings.PARAMS["commit_iterations"])
    papers_counter = 0
    if max_papers_count > 0:
        for paper_info in paper_generator:
            rg_query_page_cache = None
            # Loop for different versions of paper
            paper_versions = len(paper_info["different_information"])
            if paper_versions == 0: settings.print_message("Not found information about paper #%i, skipped." % paper_versions, 1)
            for paper_version_counter, paper_addition_information in enumerate(paper_info["different_information"]):
                papers_counter += 1
                if not utils.RG_stage_is_skipped_for_all(): utils.skip_RG_stage_reset()
                # if papers_counter > max_papers_count: break;
                if not "year" in paper_addition_information or not "author" in paper_addition_information: 
                    logger.debug("Skip paper #%i, empty year or authors fields." % papers_counter)
                    continue
                logger.debug("Process content of EndNote file #%i\n%s\n%s" % (papers_counter, json.dumps(paper_info["general_information"]), json.dumps(paper_addition_information)) )
                # Create new paper entity
                newpaper = paper.Paper()
                # Fill data from google scholar
                newpaper.get_info_from_sch(paper_info["general_information"], paper_addition_information, paper_version_counter + 1)
                if paper_versions > 1: 
                    if rg_query_page_cache == None:
                        if not utils.RG_stage_is_skipped(): 
                            settings.print_message("Search papers from researchgate.", 1)
                            rg_query_page_cache = newpaper.get_rg_first_search_page()
                        else:
                            settings.print_message("Skip researchgate stage.", 1)
                            logger.debug("Skip researchgate stage.")
                    settings.print_message("Handle paper version #%i (total %i)" % (paper_version_counter + 1, paper_versions), 1)
                # Fill data from researchgate
                if not utils.RG_stage_is_skipped():
                    settings.print_message("Researchgate:", 2)
                    settings.print_message("Filling in information about the paper%s." % (" version" if paper_versions > 1 else ""), 3)
                    if newpaper.get_data_from_rg(rg_query_page_cache, number_of_papers_compared) == True:
                        settings.print_message("This paper%s was identified and filled." % (" version" if paper_versions > 1 else ""), 3)
                    else:
                        settings.print_message("This paper%s not found." % (" version" if paper_versions > 1 else ""), 3)
                logger.debug("Check exists paper and if not then insert into DB.")
                if newpaper.in_database(): 
                    settings.print_message("This paper%s already exists, id = %i." % ((" version" if paper_versions > 1 else ""), newpaper.db_id), 1)
                    continue
                new_papers += 1
                # insert paper into DB
                newpaper.add_to_database()
                settings.print_message("Adding a paper%s to the database" % (" version" if paper_versions > 1 else ""), 1)

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

                # Commit transaction each commit_iterations iterations
                if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
            # if papers_counter >= max_papers_count: break;
    logger.debug("End processing. Changes in DB: %i." % (new_auth + new_papers))
    settings.print_message("End processing. Changes in DB: %i." % (new_auth + new_papers))
    return (new_papers, new_auth, papers_counter)

def update_authors():
    pass

def get_papers_of_authors():
    pass

def get_PDFs():
    """This function loads pdf articles from the RG and Sci-hub selected from the query from the database"""
    # statistic for pdf sources
    RG_PDF, SCI_PDF = 0, 0
    #
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    # Get columns from query
    columns = dict()
    for N, column in enumerate(dbutils.get_columns_names("papers")): 
        columns[column.lower()] = N
    logger.debug("Create folder 'PDF_{0}' if not exists.".format(settings._DB_FILE))
    pdf_path = "%s\\%s\\" % (settings.DB_PATH, "PDF_{0}".format(settings._DB_FILE))
    if not os.path.exists(pdf_path): os.mkdir(pdf_path)
    new_files_counter = 0
    unavailable_files_counter = 0
    for paper_index, paper in enumerate(papers):
        settings.print_message("Handle paper #{0} - {1}.".format(paper_index + 1, paper[columns['title']]))
        rg_paper_id = paper[columns["rg_id"]]
        DOI = paper[columns["doi"]]
        id = paper[columns["id"]]
        if (rg_paper_id is None) and (DOI is None):
            settings.print_message('DOI and ResearchGate ID empty, skip the paper.')
            logger.debug("DOI and ResearchGate ID empty, skip the paper.")
            continue
        logger.debug("File name generation.")
        pdf_file_name = "{0}{1}.pdf".format(pdf_path, id)
        counter = 1
        while os.path.exists(pdf_file_name): 
            pdf_file_name = "{0}{1}_{2}.pdf".format(pdf_path, id, counter)
            counter += 1
        logger.debug("PDF file name=%s." % pdf_file_name)
        if rg_paper_id != None:
            settings.print_message("Getting PDF-file in ResearchGate by ID: {0}.".format(rg_paper_id), 2)
            logger.debug("Getting PDF-file in ResearchGate by ID: {0}.".format(rg_paper_id))
            try:
                if researchgate.get_pdf(rg_paper_id, pdf_file_name):
                    new_files_counter += 1
                    RG_PDF += 1
                    settings.print_message("Complete!", 2)
                    dbutils.update_pdf_transaction(id)
                    continue
            except:
                logger.debug("Failed get_pdf from Researchgate for paper #{0}.".format(paper_index + 1))
                settings.print_message("failed load PDF on researchgate.", 2)
                continue
            settings.print_message("PDF unavailable on researchgate.", 2)
        else:
            settings.print_message("PDF-file not exists in ResearchGate.", 2)
        '''if rg_paper_id == None:
            logger.debug("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(paper_index + 1))
            settings.print_message("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(paper_index + 1), 2)
            rg_paper_id = researchgate.paper_search_by_DOI(DOI)
            if rg_paper_id == None:
                logger.debug("Paper #{0} not found on Researchgate.".format(paper_index + 1))
                settings.print_message("Paper #{0} not found on Researchgate.".format(paper_index + 1), 2)'''

        if DOI != None:
            settings.print_message("Getting PDF-file in Sci-Hub by DOI : {0}.".format(DOI), 2)
            logger.debug("Getting PDF-file in ResearchGate by ID: {0}.".format(rg_paper_id))
            #settings.print_message("Trying to take pdf from sci-hub. DOI={0}".format(DOI), 2)
            try:
                if not scihub.get_pdf(DOI, pdf_file_name):
                    settings.print_message("PDF unavailable on sci-hub. DOI={0}".format(DOI), 2)
                    unavailable_files_counter += 1
                else:
                    new_files_counter += 1
                    SCI_PDF += 1
                    settings.print_message("Complete!", 2)
                    dbutils.update_pdf_transaction(id)
            except:
                unavailable_files_counter += 1
                logger.debug("Failed get_pdf from sci-hub for paper #{0}. DOI={0}".format(paper_index + 1, DOI))
                settings.print_message("failed load PDF on sci-hub. DOI={0}".format(DOI), 2)
                continue
        else:
            logger.debug("Failed get_pdf for paper #{0}.".format(paper_index + 1))
            settings.print_message("Failed get_pdf for paper #{0}.".format(paper_index + 1), 2)
            continue

    settings.print_message("Proceed papers: {0}.".format(unavailable_files_counter + new_files_counter))
    settings.print_message("PDF from ResearchGate: {0}.".format(RG_PDF))
    settings.print_message("PDF from Sci-Hub: {0}.".format(SCI_PDF))
    result = (True, new_files_counter, unavailable_files_counter, unavailable_files_counter + new_files_counter)
    return result


def select_papers_for_citation_graph(tree_queue):
    """ This function selects articles from the database and checks the SQL. """
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    # Get columns from query
    columns = dict()
    for N, column in enumerate(dbutils.get_columns_names("papers")): 
        columns[column.lower()] = N
    for db_paper in papers:
        # The tree is in the queue in which the tuples are stored. 
        # Each tuple is (id of paper in the database, id of the paper on the researchgate, the level of the tree)
        tree_queue.put((db_paper[columns["id"]], db_paper[columns["rg_id"]], db_paper[columns["doi"]], 1))
    return 0


def create_and_fill_paper_for_citation_graph(parent_paper_db_id, rg_new_paper_id, edge_type):
    """ This function creates a new instance of the paper and fills it with information. """
    new_authors_count = 0
    new_papers_count = 0
    # Create new paper entity
    newpaper = paper.Paper()
    # fill new paper
    settings.print_message("Filling in information about the paper.", 4)
    logger.debug("Filling in information about the paper.")
    if not newpaper.get_data_from_rg_id(rg_new_paper_id):
        logger.debug("Failed to get information about the paper, skipped.")
        return None, new_papers_count, new_authors_count
    logger.debug("Check exists paper and if not then insert into DB.")
    if newpaper.in_database(): 
        settings.print_message("This paper already exists, id = {0}.".format(newpaper.db_id), 4)
    else:
        # Add new paper in DB
        settings.print_message("Adding a paper to the database", 4)
        newpaper.add_to_database()
        new_papers_count += 1
        # Get and insert in database info about author
        settings.print_message("Authors:", 4)
        for author_info in newpaper.authors:
            # Create new author entity
            newauthor = author.Author()
            newauthor.get_base_info_from_sch({"name":author_info})
            settings.print_message("Handle author '%s'." % (newauthor.shortname if newauthor.name == None else newauthor.name), 6)
            logger.debug("Check exists author and if not then insert into DB.")
            if not newauthor.in_database():
                # Insert new author into DB
                settings.print_message("Adding author to the database", 6)
                newauthor.save_to_database()
                new_authors_count += 1
            else:
                settings.print_message("This author already exists, id = %i." % newauthor.db_id, 6)
            # Insert into DB reference
            dbutils.add_author_paper_edge(newauthor.db_id, newpaper.db_id)
    # Add reference in DB
    edge_params = \
    {
        "IDpaper1" : parent_paper_db_id,
        "IDpaper2" : newpaper.db_id,
        "type" : edge_type
    }
    logger.debug("Check exists edge and if not then insert into DB.")
    if not dbutils.check_exists_paper_paper_edge(edge_params):
        logger.debug("Add edge ({0}, {1}, {2}) in DB.".format(parent_paper_db_id, newpaper.db_id, edge_type))
        #settings.print_message("Add edge ({0}, {1}, {2}) in DB.".format(parent_paper_db_id, newpaper.db_id, edge_type), 4)
        dbutils.add_paper_paper_edge(parent_paper_db_id, newpaper.db_id, edge_type)
    else:
        #settings.print_message("This edge ({0}, {1}, {2}) already exists.".format(parent_paper_db_id, newpaper.db_id, edge_type), 4)
        logger.debug("This edge ({0}, {1}, {2}) already exists.".format(parent_paper_db_id, newpaper.db_id, edge_type))
    return newpaper, new_papers_count, new_authors_count

def get_references():
    """This function loads links to articles for papers selected from the database"""
    MAX_TREE_LEVEL = int(settings.PARAMS["max_tree_level"])
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else 1000000
    tree_queue = queue.Queue()
    select_papers_for_citation_graph(tree_queue)
    papers_counter = 0
    new_papers_count = 0
    new_authors_count = 0
    filled_papers = 0
    papers_without_list = 0
    getinfo_fails = 0
    while not tree_queue.empty():
        papers_counter += 1
        parent_paper_db_id, parent_paper_rg_id, parent_paper_DOI, tree_level = tree_queue.get()
        logger.debug("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        settings.print_message("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        if parent_paper_rg_id == None:
            logger.debug("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter))
            settings.print_message("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter), 2)
            parent_paper_rg_id = researchgate.paper_search_by_DOI(parent_paper_DOI)
            if parent_paper_rg_id == None:
                logger.debug("Paper #{0} not found on Researchgate, skip.".format(papers_counter))
                settings.print_message("Paper #{0} not found on Researchgate, skip.".format(papers_counter), 2)
                papers_without_list += 1
                continue
        settings.print_message("Get paper references. RGID={0}.".format(parent_paper_rg_id), 2)
        ref_papers_list = researchgate.get_referring_papers(parent_paper_rg_id)
        total_ref = 0
        if ref_papers_list != None and len(ref_papers_list) != 0:
            total_ref = len(ref_papers_list)
        else:
            logger.debug("Paper #{0} hasn't cited list, skip.".format(papers_counter))
            settings.print_message("Paper #{0} hasn't references list, skip.".format(papers_counter), 2)
            papers_without_list += 1
            continue
        for new_paper_counter, ref_paper in enumerate(ref_papers_list):
            if ref_paper["publication"] == None: # It's citation
                settings.print_message("Paper #{0} is citation, skip.".format(new_paper_counter + 1), 2)
                logger.debug("Paper #{0} is citation, skipped.".format(new_paper_counter + 1))
                continue
            settings.print_message("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref), 2)
            logger.debug("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref))
            filled_papers += 1
            newpaper, _new_papers_count, _new_authors_count = create_and_fill_paper_for_citation_graph(parent_paper_db_id, 
                researchgate.get_rg_paper_id_from_url(ref_paper["publication"]["url"]), "citied")
            if newpaper == None:
                settings.print_message("Failed to get information about the paper #{0}, skipped.".format(new_paper_counter + 1), 2)
                getinfo_fails += 1
                continue
            new_papers_count += _new_papers_count
            new_authors_count += _new_authors_count
            # Add new paper in queue
            if tree_level < MAX_TREE_LEVEL:
                logger.debug("Add this paper (db_id={0}, rg_id={1}) in tree levels queue.".format(newpaper.db_id, newpaper.rg_paper_id))
                tree_queue.put((newpaper.db_id, newpaper.rg_paper_id, newpaper.DOI, tree_level + 1))
            else:
                pass
            # Commit transaction each commit_iterations iterations
            if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    return (papers_counter, papers_without_list, new_papers_count, getinfo_fails, new_authors_count)

def get_cities():
    """This function loads articles that reference selected papers from the database"""
    MAX_TREE_LEVEL = int(settings.PARAMS["max_tree_level"])
    MAX_CITED_PAPERS = int(settings.PARAMS["max_cited_papers"])
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else 1000000
    tree_queue = queue.Queue()
    select_papers_for_citation_graph(tree_queue)
    papers_counter = 0
    new_papers_count = 0
    new_authors_count = 0
    filled_papers = 0
    papers_without_list = 0
    getinfo_fails = 0
    while not tree_queue.empty():
        papers_counter += 1
        parent_paper_db_id, parent_paper_rg_id, parent_paper_DOI, tree_level = tree_queue.get()
        logger.debug("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        settings.print_message("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        if parent_paper_rg_id == None:
            logger.debug("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter))
            settings.print_message("Paper #{0} hasn't rg_id, search paper by DOI on Researchgate.".format(papers_counter), 2)
            parent_paper_rg_id = researchgate.paper_search_by_DOI(parent_paper_DOI)
            if parent_paper_rg_id == None:
                logger.debug("Paper #{0} not found on Researchgate, skip.".format(papers_counter))
                settings.print_message("Paper #{0} not found on Researchgate, skip.".format(papers_counter), 2)
                papers_without_list += 1
                continue
        settings.print_message("Get paper citations. RGID={0}.".format(parent_paper_rg_id), 2)
        cited_papers_list = researchgate.get_citations_papers(parent_paper_rg_id)
        total_ref = 0
        if cited_papers_list != None:
            total_ref = len(cited_papers_list)
        else:
            logger.debug("Paper #{0} hasn't cited list, skipped.".format(papers_counter))
            settings.print_message("Paper #{0} hasn't cited list, skip.".format(papers_counter), 2)
            papers_without_list += 1
            continue
        for new_paper_counter, ref_paper in enumerate(cited_papers_list):
            if ref_paper["publication"] == None: # It's citation
                settings.print_message("Paper #{0} is not article, skip.".format(new_paper_counter + 1), 2)
                logger.debug("Paper #{0} is not article, skip.".format(new_paper_counter + 1))
                continue
            settings.print_message("Handle new paper #{0} from citations (total {1}).".format(new_paper_counter + 1, total_ref), 2)
            logger.debug("Handle new paper #{0} from citations (total {1}).".format(new_paper_counter + 1, total_ref))
            filled_papers += 1
            newpaper, _new_papers_count, _new_authors_count = create_and_fill_paper_for_citation_graph(parent_paper_db_id, 
                researchgate.get_rg_paper_id_from_url(ref_paper["publication"]["url"]), "citied")
            if newpaper == None:
                settings.print_message("Failed to get information about the paper #{0}, skipped.".format(new_paper_counter + 1), 2)
                getinfo_fails += 1
                continue
            new_papers_count += _new_papers_count
            new_authors_count += _new_authors_count
            # Add new paper in queue
            if tree_level < MAX_TREE_LEVEL:
                logger.debug("Add this paper (db_id={0}, rg_id={1}) in tree levels queue.".format(newpaper.db_id, newpaper.rg_paper_id))
                tree_queue.put((newpaper.db_id, newpaper.rg_paper_id, newpaper.DOI, tree_level + 1))
            else:
                pass
            # Commit transaction each commit_iterations iterations
            if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
            if  new_paper_counter >= MAX_CITED_PAPERS - 1: break
    return (papers_counter, papers_without_list, new_papers_count, getinfo_fails, new_authors_count)


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
    try:
        for case in utils.Switch(command):
            if case("getPapersByKeyWords"): 
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                # START COMMAND
                result = get_papers_by_key_words()
                logger.debug("Processing was successful. Added new papers: %i. Added new authors: %i. Processed total papers: %i." % result)
                settings.print_message("Processing was successful. Added new papers: %i. Added new authors: %i. Processed total papers: %i." % result)
                break
            if case("updateAuthors"): 
                result = update_authors()
                break
            if case("getPapersOfAuthors"): 
                result = get_papers_of_authors()
                break
            if case("getPDFs"): 
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_PDFs()
                settings.print_message("Processing was successful. Downloads files: %i. Not available pdf's: %i. Processed total: %i." % result[1:])
                logger.debug("Processing was successful. Downloads files: %i. Not available pdf's: %i. Processed total: %i." % result[1:])
                break
            if case("getReferences"): 
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_references()
                logger.debug("Processing was successful. Processed total papers: %i. Papers without references: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result)
                settings.print_message("Processing was successful. Processed total papers: %i. Papers without references: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result)      
                break
            if case("getCities"): 
                logger.debug("Processing command '%s'." % command)
                settings.print_message("Processing command '%s'." % command)
                result = get_cities()
                logger.debug("Processing was successful. Processed total papers: %i. Papers without citations: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result)
                settings.print_message("Processing was successful. Processed total papers: %i. Papers without citations: %i. Added new papers: %i. Fails to get data about paper: %i. Added new authors: %i." % result)       
                break
            if case(): # default
                logger.warn("Unknown command: %s" % command)
                settings.print_message("Unknown command: %s" % command)
                break
        # Fix database changes
        dbutils.commit()
    except KeyboardInterrupt:
        settings.print_message("Caught KeyboardInterrupt, terminating processing")
        settings.RESULT = "WARNING: User was terminated processing"
        dbutils.rollback()
    except:
        logger.error(traceback.format_exc())
        settings.print_message("Processing finished with error.")
        settings.print_message("For more details, see the log.")
        settings.RESULT = "ERROR: {0}".format(traceback.format_exc())
        dbutils.rollback()
    end_time = datetime.now()
    settings.print_message("Run began on {0}".format(start_time))
    settings.print_message("Run ended on {0}".format(end_time))
    settings.print_message("Elapsed time was: {0}".format(end_time - start_time))
    logger.debug("Run began on {0}".format(start_time))
    logger.debug("Run ended on {0}".format(end_time))
    logger.debug("Elapsed time was: {0}".format(end_time - start_time))
    print_to_log_http_statistic()


def main():  
    dispatch(settings.PARAMS["command"])


if __name__ == "__main__":
    main()

