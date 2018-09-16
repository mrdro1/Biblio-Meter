# -*- coding: utf-8 -*-
import sys
import traceback
import logging
#
import scholar
import settings
import dbutils

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


class Author(object):
    """Represent author"""

    def __init__(self):
        self.name = None
        self.shortname = None
        self.citations = None
        self.hindex = None
        self.i10index = None
        self.g_id = None
        self.db_id = None

    def get_base_info_from_sch(self, info_dict):
        if "name" in info_dict:
            self.name = info_dict["name"]
        if "shortname" in info_dict:
            self.shortname = info_dict["shortname"]
        if "gid" in info_dict and info_dict["gid"] != '':
            self.g_id = info_dict["gid"]

    def get_info_from_sch(self):
        """Populate the Author with information from their profile"""
        if self.g_id is None:
            return False
        try:
            info_dict = scholar.get_info_from_author_page(self.g_id)
        except BaseException:
            logger.debug("Failed to load author information")
            return False
        if info_dict is None:
            return False
        if "citations" in info_dict:
            self.citations = info_dict["citations"]
        if "hindex" in info_dict:
            self.hindex = info_dict["hindex"]
        if "i10index" in info_dict:
            self.i10index = info_dict["i10index"]
        return True

    def save_to_database(self):
        self.db_id = dbutils.add_new_author(
            {
                "name": self.name,
                "shortname": self.shortname,
                "google_id": self.g_id,
                "google_h_index": self.hindex,
                "google_i10_index": self.i10index,
                "google_citations": self.citations
            }
        )

    def in_database(self):
        param = {
            "name": self.name,
            "shortname": self.shortname,
            "google_id": self.g_id
        }
        self.db_id = dbutils.get_author_ID(param)
        return self.db_id is not None
