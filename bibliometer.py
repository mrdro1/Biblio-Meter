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
    logger.debug(about_res_count)
    settings.print_message("Google: Found {0} papers.".format(about_res_count))
    number_of_papers_compared = int(settings.PARAMS["max_researchgate_papers"]) if "max_researchgate_papers" in settings.PARAMS else 30
    if number_of_papers_compared <= 0: utils.skip_RG_stage_for_all()
    new_papers = 0
    new_auth = 0
    max_papers_count = int(settings.PARAMS["max_google_papers"]) if "max_google_papers" in settings.PARAMS else 1000000
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else 1000000
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
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    # Get columns from query
    columns = dict()
    for N, column in enumerate(dbutils.get_sql_columns(PAPERS_SQL)): columns[column.lower()] = N

    # Check query
    def error_msg(param_name):
       logger.error("Column '{0}' not found in query".format(param_name)) 
       settings.print_message("ERROR: Column '{0}' not found in query.".format(param_name))
       settings.print_message("From the database should be selected column '{0}'.".format(param_name))
    result = (False, 0, 0, 0)
    if not "rg_id" in columns:
       error_msg("rg_id")
       return result
    if not "doi" in columns:
       error_msg("DOI")
       return result
    if not "id" in columns:
       error_msg("id")
       return result
    
    logger.debug("Create folder 'PDF' if not exists.")
    pdf_path = "%s\\%s\\" % (settings.DB_PATH, "PDF")
    if not os.path.exists(pdf_path): os.mkdir(pdf_path)
    new_files_counter = 0
    unavailable_files_counter = 0
    for paper_index, paper in enumerate(papers):
        settings.print_message("Handle paper #{0}.".format(paper_index + 1))
        rg_paper_id = paper[columns["rg_id"]]
        DOI = paper[columns["doi"]]
        id = paper[columns["id"]]
        settings.print_message("Trying to take pdf from researchgate. RGID={0}.".format(rg_paper_id), 2)
        logger.debug("File name generation.")
        pdf_file_name = "{0}{1}.pdf".format(pdf_path, id)
        counter = 1
        while os.path.exists(pdf_file_name): 
            pdf_file_name = "{0}{1}_{2}.pdf".format(pdf_path, id, counter)
            counter += 1
        logger.debug("PDF file name=%s." % pdf_file_name)
        if researchgate.get_pdf(rg_paper_id, pdf_file_name): 
            new_files_counter += 1
            continue
        settings.print_message("PDF unavailable on researchgate.".format(DOI), 2)
        settings.print_message("Trying to take pdf from sci-hub. DOI={0}".format(DOI), 2)
        if not scihub.get_pdf(DOI, pdf_file_name): 
            settings.print_message("PDF unavailable on sci-hub.".format(DOI), 2)
            unavailable_files_counter += 1
        else: 
            new_files_counter += 1
    result = (True, new_files_counter, unavailable_files_counter, unavailable_files_counter + new_files_counter)
    return result


def get_references():
    """This function loads links to articles for papers selected from the database"""
    logger.debug("Select papers from database.")
    settings.print_message("Select papers from database.")
    PAPERS_SQL = settings.PARAMS["papers"]
    MAX_TREE_LEVEL = int(settings.PARAMS["max_tree_level"])
    papers = dbutils.execute_sql(PAPERS_SQL)
    settings.print_message("{0} papers selected.".format(len(papers)))
    # Get columns from query
    columns = dict()
    for N, column in enumerate(dbutils.get_sql_columns(PAPERS_SQL)): columns[column.lower()] = N
    commit_iterations = int(settings.PARAMS["commit_iterations"]) if "commit_iterations" in settings.PARAMS else 1000000
    # Check query
    def error_msg(param_name):
       logger.error("Column '{0}' not found in query".format(param_name)) 
       settings.print_message("ERROR: Column '{0}' not found in query.".format(param_name))
       settings.print_message("From the database should be selected column '{0}'.".format(param_name))
    result = (False, 0, 0, 0)
    if not "rg_id" in columns:
       error_msg("rg_id")
       return result
    if not "id" in columns:
       error_msg("id")
       return result
    tree_queue = queue.Queue()
    for db_paper in papers:
        tree_queue.put((db_paper[columns["id"]], db_paper[columns["rg_id"]], 1))
    papers_counter = 0
    while not tree_queue.empty():
        papers_counter += 1
        parent_paper_db_id, parent_paper_rg_id, tree_level = tree_queue.get()
        logger.debug("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        settings.print_message("Handle paper #{0}, treelevel #{1}.".format(papers_counter, tree_level))
        settings.print_message("Get paper references. RGID={0}.".format(parent_paper_rg_id), 2)
        ref_papers_list = researchgate.get_referring_papers(parent_paper_rg_id)
        total_ref = 0
        if ref_papers_list != None:
            total_ref = len(ref_papers_list)
        for new_paper_counter, ref_paper in enumerate(ref_papers_list):
            if ref_paper["publication"] == None: # It's citation
                settings.print_message("Paper #{0} is citation, skip.".format(new_paper_counter + 1), 2)
                logger.debug("Paper #{0} is citation, skip.".format(new_paper_counter + 1))
                continue
            settings.print_message("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref), 2)
            logger.debug("Handle new paper #{0} from references (total {1}).".format(new_paper_counter + 1, total_ref))
            # Create new paper entity
            newpaper = paper.Paper()
            # fill new paper
            settings.print_message("Filling in information about the paper.", 4)
            logger.debug("Filling in information about the paper #{0}.".format(new_paper_counter + 1))
            newpaper.get_data_from_rg_id(researchgate.get_rg_paper_id_from_url(ref_paper["publication"]["url"]))
            logger.debug("Check exists paper and if not then insert into DB.")
            if newpaper.in_database(): 
                settings.print_message("This paper already exists, id = {0}.".format(newpaper.db_id), 4)
            else:
                # Add new paper in DB
                settings.print_message("Adding a paper to the database", 4)
                newpaper.add_to_database()
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
                else:
                    settings.print_message("This author already exists, id = %i." % newauthor.db_id, 6)
                # Insert into DB reference
                dbutils.add_author_paper_edge(newauthor.db_id, newpaper.db_id)
            # Add reference in DB
            edge_params = \
            {
                "IDpaper1" : parent_paper_db_id,
                "IDpaper2" : newpaper.db_id,
                "type" : "related"
            }
            logger.debug("Check exists edge and if not then insert into DB.")
            if not dbutils.check_exists_paper_paper_edge(edge_params):
                logger.debug("Add edge ({0}, {1}, 'related') in DB.".format(parent_paper_db_id, newpaper.db_id))
                settings.print_message("Add edge ({0}, {1}, 'related') in DB.".format(parent_paper_db_id, newpaper.db_id), 4)
                dbutils.add_paper_paper_edge(parent_paper_db_id, newpaper.db_id, "related")
            else:
                settings.print_message("This edge ({0}, {1}, 'related') already exists.".format(parent_paper_db_id, newpaper.db_id), 4)
                logger.debug("This edge ({0}, {1}, 'related') already exists.".format(parent_paper_db_id, newpaper.db_id))
            # Add new paper in queue
            if tree_level < MAX_TREE_LEVEL:
                logger.debug("Add this paper (db_id={0}, rg_id={1}) in tree levels queue.".format(newpaper.db_id, newpaper.rg_paper_id))
                tree_queue.put((newpaper.db_id, newpaper.rg_paper_id, tree_level + 1))
            else:
                pass
            # Commit transaction each commit_iterations iterations
            if papers_counter % commit_iterations == 0: dbutils.commit(papers_counter)
    pass

def get_cities():
    pass


def test():
    pass

def dispatch(command):
    result = None
    logger.debug("command %s.", command)
    try:
        for case in utils.switch(command):
            start_time = datetime.now()
            if case("getPapersByKeyWords"): 
                logger.debug("Handling command '%s'." % command)
                settings.print_message("Handling command '%s'." % command)
                result = get_papers_by_key_words() 
                logger.debug("Handling was successful. Added new papers: %i. Added new authors: %i. Processed total papers: %i." % result)
                settings.print_message("Added new papers: %i. Added new authors: %i. Processed total papers: %i." % result)
                break
            if case("updateAuthors"): 
                result = update_authors()
                break
            if case("getPapersOfAuthors"): 
                result = get_papers_of_authors()
                break
            if case("getPDFs"): 
                logger.debug("Handling command '%s'." % command)
                settings.print_message("Handling command '%s'." % command)
                result = get_PDFs()
                settings.print_message("Handling was successful. Downloads files: %i. Not available pdf's: %i. Processed total: %i." % result[1:])
                logger.debug("Handling was successful. Downloads files: %i. Not available pdf's: %i. Processed total: %i." % result[1:])
                break
            if case("getReferences"): 
                result = get_references()
                break
            if case("getCities"): 
                result = get_cities()
                break
            if case("test"): 
                result = test()
                break
            if case(): # default
                logger.warn("Unknown command: %s" % command)
                settings.print_message("Unknown command: %s" % command)
                return
        end_time = datetime.now()
        settings.print_message("Run began on {0}".format(start_time))
        settings.print_message("Run ended on {0}".format(end_time))
        settings.print_message("Elapsed time was: {0}".format(end_time - start_time))
        logger.debug("Run began on {0}".format(start_time))
        logger.debug("Run ended on {0}".format(end_time))
        logger.debug("Elapsed time was: {0}".format(end_time - start_time))
        # Fix database changes
        dbutils.commit()
        return
    except KeyboardInterrupt:
        settings.print_message("Caught KeyboardInterrupt, terminating processing")
        settings.RESULT = "WARNING: User was terminated processing"
    except:
        logger.error(traceback.format_exc())
        settings.print_message("An error has occurred. For more details, see the log.")
        settings.RESULT = "ERROR: {0}".format(traceback.format_exc())
    dbutils.rollback()

def main():  
    dispatch(settings.PARAMS["command"])


if __name__ == "__main__":
    main()

