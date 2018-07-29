# -*- coding: utf-8 -*-
import utils
import sys, traceback, logging
import re
#
import scholar
import settings
import dbutils
import grobid
from endnoteparser import PARAMS as EndNote_params

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

class Paper(object):
    """Represents an article. Contains obligatory fields: title, year of writing, authors. Supports the addition of data from different sources."""
    def __init__(self):
        self.title = None
        self.year = None
        self.authors = None
        self.citedby = None
        self.google_type = None
        self.pages = None
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
        self.grobid_db_id = None
        self.cluster = None
        self.EndNote = None
        self.paper_version = None
        self.paper_URL = None
        self.PDF_URL = None
        self.versions = None
        self.downloaded = False

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
        if "versions" in additional_information: self.versions = additional_information["versions"]
        if "url_scholarbib" in additional_information: self.EndNoteURL = additional_information["url_scholarbib"]
        if "year" in additional_information: self.year = int(additional_information["year"])
        if "type" in additional_information: self.google_type = additional_information["type"]
        if "publisher" in additional_information: self.publisher = additional_information["publisher"]
        if "secondarytitle" in additional_information: self.secondaryTitle = additional_information["secondarytitle"]
        if "pages" in additional_information: self.pages = additional_information["pages"]

        if "start_page" in additional_information \
            and "end_page" in additional_information:
            self.start_page = additional_information["start_page"]
            self.end_page = additional_information["end_page"]
        
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
        self.year = pdf_info["pubdate"]
        dbutils.update_paper(
            {
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,
                "id":self.db_id,
                "year":self.year
            }, True
            ) 
        return True

    def make_EndNote(self, replace_EndNote=True):
        param_template = "{param} {value}\n"
        EndNote = \
            param_template.format(param=EndNote_params["Type"], value="Generic") +\
            param_template.format(param=EndNote_params["Title"], value=self.title) if self.title else "" +\
            param_template.format(param=EndNote_params["Year"], value=self.year) if self.year else "" +\
            param_template.format(param=EndNote_params["Publisher"], value=self.publisher) if self.publisher else "" +\
            param_template.format(param=EndNote_params["Pages"], 
                                  value="{}-{}".format(self.start_page, self.end_page)) if self.start_page else "" +\
            param_template.format(param=EndNote_params["DOI"], value=self.DOI) if self.DOI else "" +\
            param_template.format(param=EndNote_params["Abstract"], value=self.abstract) if self.abstract else ""
        for author in self.authors:
            EndNote += param_template.format(param=EndNote_params["Author"], value=author)
        if replace_EndNote: self.EndNote = EndNote
        return EndNote

    def add_to_database(self):
        self.db_id = dbutils.add_new_paper(
            {
                "title":self.title,
                "year":self.year,
                "publisher":self.publisher,
                "start_page":self.start_page,
                "end_page":self.end_page,
                "pages":self.pages,
                "google_type":self.google_type,
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,          
                "references_count":self.references_count,
                "endnote":self.EndNote,
                "authors":len(self.authors),
                "google_url":self.paper_URL,
                "google_cluster_id": str(self.cluster) if self.cluster else None,
                "google_file_url":self.PDF_URL,
                "google_cited_by_count":self.citedby,
                "google_versions":self.versions,
            }
            )


    def update_in_database(self):
        if self.db_id == None: self.db_id = get_paper_ID({
                "DOI":self.DOI, 
                "title":self.title, 
                "auth_count":len(self.authors), 
                "google_type":self.google_type, 
                "pages":self.pages, 
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
                "pages":self.pages,
                "google_type":self.google_type,
                "DOI":self.DOI,
                "abstract":self.abstract,
                "abstract_ru":self.abstract_ru,
                "references_count":self.references_count,
                "EndNote":self.EndNote,
                "authors":len(self.authors),
                "id":self.db_id,
                "google_url":self.paper_URL,
                "google_file_url":self.PDF_URL,
                "google_cluster_id":self.cluster
            }
            ) 


    def in_database(self):
        param = {
                "DOI":self.DOI, 
                "title":self.title, 
                "auth_count":len(self.authors), 
                "google_type":self.google_type, 
                "pages":self.pages, 
                "year":self.year, 
                "start_page":self.start_page,
                "end_page":self.end_page
            }
        self.db_id = dbutils.get_paper_ID(param)
        return self.db_id != None


    def is_downloaded(self):
        param = { "id" : self.db_id }
        self.downloaded = dbutils.get_pdf_download_transaction(param) != None
        return self.downloaded


    def in_database_as_grobid_paper(self):
        #param = {
        #        "doi":self.DOI, 
        #        "title":self.title, 
        #        "year":self.year, 
        #    }
        #self.grobid_db_id = dbutils.get_grobid_paper_ID(param)
        #return self.grobid_db_id != None
        return False


    def add_to_database_as_grobid_paper(self, parent_paper_db_id):
        self.grobid_db_id = dbutils.add_new_grobid_paper(
            {
                "title" : self.title,
                "year" : self.year,
                "doi" : self.DOI,     
                "endnote" : self.EndNote,
                "google_cluster_id" : None,
                "r_paper" : parent_paper_db_id
            }
            )