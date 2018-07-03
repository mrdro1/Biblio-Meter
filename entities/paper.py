# -*- coding: utf-8 -*-
import utils
import sys, traceback, logging
import re
#
import scholar
import settings
import dbutils
import grobid

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

class Paper(object):
    """Represents an article. Contains obligatory fields: title, year of writing, authors. Supports the addition of data from different sources."""
    def __init__(self):
        self.title = None
        self.year = None
        self.authors = None
        self.citedby = None
        self.g_type = None
        self.volume = None
        self.secondaryTitle = None
        self.EndNoteURL = None
        self.start_page = None
        self.end_page = None
        self.publisher = None
        self.abstract = None
        self.abstract_ru = None
        self.DOI = None
        self.references = None
        self.references_count = None
        self.db_id = None
        self.cluster = None
        self.EndNote = None
        self.paper_version = None
        self.paper_URL = None,
        self.PDF_URL = None

    def get_info_from_sch(self, general_information, additional_information, paper_version=1, pdf_url=None):
        # General
        if "title" in general_information: self.title = general_information["title"]
        if "year" in general_information: self.year = general_information["year"]
        if "cluster" in general_information: self.cluster = general_information["cluster"]
        if "url" in general_information: self.paper_URL = general_information["url"]
        self.PDF_URL = pdf_url
        # Addition
        self.paper_version = paper_version
        if "title" in additional_information: self.title = additional_information["title"]
        if "citedby" in additional_information: self.citedby = additional_information["citedby"]
        if "url_scholarbib" in additional_information: self.EndNoteURL = additional_information["url_scholarbib"]
        if "start_page" in additional_information: self.start_page = additional_information["start_page"]
        if "end_page" in additional_information: self.end_page = additional_information["end_page"]
        if "year" in additional_information: self.year = int(additional_information["year"])
        if "type" in additional_information: self.g_type = additional_information["type"]
        if "publisher" in additional_information: self.publisher = additional_information["publisher"]
        if "secondarytitle" in additional_information: self.secondaryTitle = additional_information["secondarytitle"]
        if "volume" in additional_information: self.volume = int(additional_information["volume"])
        if "EndNote" in additional_information: self.EndNote = additional_information["EndNote"]
        # Matching authors from the header and from EndNote, adding information in case of coincidence
        self.authors = list()
        for auth_index, additional_author in enumerate(additional_information["author"]):
            splited_author_name = additional_author.split(", ")
            # if string with name has not ',' (for example: chinese name), than name_initials is empty string
            if len(splited_author_name) == 1:
                sirname = splited_author_name[0]
                name_initials = str()
            else:
                sirname = additional_author.split(", ")[0]
                name_initials = additional_author.split(", ")[1][0]
            intersect_lst = [(index, author) for index, author in enumerate(general_information["author"]) if  not "name" in author and sirname in author["shortname"] and name_initials == author["shortname"][0]] 
            author_dict = {"name" : additional_author}
            if intersect_lst != []: author_dict.update(intersect_lst[0][1])
            self.authors.append(author_dict)
        # Delete unmatched authors
        for auth_index, author in enumerate(self.authors):
            if not "name" in author:
                del self.authors[auth_index]


    def get_data_from_grobid(self, pdf_filename):
        try:
            pdf_info = grobid.processHeaderDocument(pdf_filename)
        except:
            logger.error(traceback.format_exc()) 
            logger.debug("Failed to load paper information") 
            return False
        logger.debug("Save info about paper (or its version)")
        self.DOI = pdf_info["DOI"]
        self.abstract = pdf_info["abstract"]
        self.abstract_ru = pdf_info["abstract_ru"]
        dbutils.update_paper(
            {
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,
                "id":self.db_id
            }, True
            ) 
        return True


    def add_to_database(self):
        self.db_id = dbutils.add_new_paper(
            {
                "title":self.title,
                "year":self.year,
                "publisher":self.publisher,
                "start_page":self.start_page,
                "end_page":self.end_page,
                "pages":self.volume,
                "g_type":self.g_type,
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,          
                "references_count":self.references_count,
                "EndNote":self.EndNote,
                "authors":len(self.authors),
                "google_url":self.paper_URL,
                "google_cluster_url":str(self.cluster),
                "google_file_url":self.PDF_URL,
            }
            )


    def update_in_database(self):
        if self.db_id == None: self.db_id = get_paper_ID({
                "DOI":self.DOI, 
                "title":self.title, 
                "auth_count":len(self.authors), 
                "g_type":self.g_type, 
                "pages":self.volume, 
                "year":self.year, 
                "start_page":self.start_page,
                "end_page":self.end_page
            })
        dbutils.update_paper(
            {
                "title":self.title,
                "year":self.year,
                "publisher":self.publisher,
                "start_page":self.start_page,
                "end_page":self.end_page,
                "pages":self.volume,
                "g_type":self.g_type,
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,
                "references_count":self.references_count,
                "EndNote":self.EndNote,
                "authors":len(self.authors),
                "id":self.db_id,
                "google_url":self.paper_URL,
                "google_file_url":self.PDF_URL,
                "google_cluster_url":self.cluster
            }
            ) 


    def in_database(self):
        param = {
                "DOI":self.DOI, 
                "title":self.title, 
                "auth_count":len(self.authors), 
                "g_type":self.g_type, 
                "pages":self.volume, 
                "year":self.year, 
                "start_page":self.start_page,
                "end_page":self.end_page
            }
        self.db_id = dbutils.get_paper_ID(param)
        return self.db_id != None