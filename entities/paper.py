# -*- coding: utf-8 -*-
import endnoteparser
import utils
import sys, traceback, logging
#
import scholar
import researchgate
import settings
import dbutils


logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

class Paper(object):
    """Represents an article. Contains obligatory fields: title, year of writing, authors. Supports the addition of data from different sources."""
    def __init__(self):
        self.title = None
        self.year = None
        self.authors = None
        self.EndNoteURL = None
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
        self.rg_type = None
        self.references = None
        self.references_count = None
        self.db_id = None
        self.rg_paper_id = None
        self.cluster = None
        self.EndNote = None
        self.paper_version = None

    def get_info_from_sch(self, general_information, additional_information, paper_version = 1):
        # General
        if "title" in general_information: self.title = general_information["title"]
        if "year" in general_information: self.year = general_information["year"]
        if "cluster" in general_information: self.cluster = general_information["cluster"]
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

    #
    def get_rg_first_search_page(self):
        return researchgate.get_query_json(
                {
                    "title":self.title, 
                    "authors_count":len(self.authors), 
                    "year":self.year, 
                    "type":self.g_type.split()[0].lower()
                }
            )


    def get_data_from_rg(self, query_soup = None, number_of_papers_compared = 30):
        if number_of_papers_compared == 0: return False
        logger.debug("Identify paper (or its version) on researchgate")
        search_params = {
                "title":self.title.lower(), 
                "authors_count":len(self.authors), 
                "year":self.year, 
                "spage":self.start_page,
                "epage":self.end_page,
                "max_researchgate_papers":number_of_papers_compared,
                "EndNote":self.EndNote,
                "paper_version":self.paper_version
            }
        rg_info = researchgate.identification_and_fill_paper(search_params, query_soup)
        if rg_info == None:
            logger.debug("This paper (or its version) is not identified") 
            return False
        logger.debug("Save info about paper (or its version)")
        if "doi" in rg_info: self.DOI = rg_info["doi"] 
        if "abstract" in rg_info: self.abstract = rg_info["abstract"] 
        if "abstract_ru" in rg_info: self.abstract_ru = rg_info["abstract_ru"] 
        if "rg_id" in rg_info: self.rg_paper_id = rg_info["rg_id"] 
        if "references_count" in rg_info: self.references_count = rg_info["references_count"] 
        if "rg_type" in rg_info: self.rg_type = rg_info["rg_type"] 
        if "references" in rg_info: self.references = rg_info["references"] 
        if "start_page" in rg_info and self.start_page == None: self.start_page = rg_info["start_page"]
        if "end_page" in rg_info and self.end_page == None: self.end_page = rg_info["end_page"]
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
                "rg_id":self.rg_paper_id,                
                "references_count":self.references_count,
                "rg_type":self.rg_type,
                "EndNote":self.EndNote,
                "authors":len(self.authors)
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
                "rg_id":self.rg_paper_id,
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
                "rg_id":self.rg_paper_id,
                "references_count":self.references_count,
                "rg_type":self.rg_type,
                "EndNote":self.EndNote,
                "authors":len(self.authors),
                "id":self.db_id
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
                "rg_id":self.rg_paper_id,
                "start_page":self.start_page,
                "end_page":self.end_page
            }
        self.db_id = dbutils.get_paper_ID(param)
        return self.db_id != None