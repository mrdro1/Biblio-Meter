# -*- coding: utf-8 -*-
import requests
import logging
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import traceback
#
import settings
import utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

CROSSREF_HOST_NAME = "search.crossref.org"


def title_to_vector(title):
    """
    1. We save only letters and whitespace from title
    2. We split title by whitespace, than delete all words
        with len(word) <= 4
    3. We join result into string
    """
    filtered_title = ''.join(
        filter(
            lambda x: str.isalpha(x) or str.isspace(x),
            title))
    result_vector = ''.join(
        filter(
            lambda x: len(x) >= 4,
            filtered_title.split()))
    return result_vector


def get_DOI_by_title(title):
    """ Get DOI from crossref.org by article title """
    regular = re.compile('\(.*\)')

    vector_title = title_to_vector(title.lower())

    query_title = '%2B' + '+%2B'.join(title.split())
    url = f'https://{CROSSREF_HOST_NAME}/?q={query_title}'
    logger.debug(f"Send query {query_title} to crossref.org.")
    try:
        soup = utils.get_soup(url)
        if not soup:
            return None
        logger.debug("Parse HTML-page with search results.")
        hrefs = [
            x for x in soup.find_all(
                'a',
                class_='cite-link',
                href=True) if x['href'] != '#']
        slice_size = 5 if len(hrefs) >= 5 else len(hrefs)

        result_count = int(
            soup.find(
                'h6',
                class_='number').text.split('of')[1].strip().split(' ')[0].replace(
                ',',
                ''))
        logger.debug(f"Results count: {result_count}.")
        if result_count > settings.PARAMS["crossref_max_papers"]:
            logger.debug("Many results: {} > {}.".format(result_count, settings.PARAMS["crossref_max_papers"]))
            return None

        articles_are_equal = False
        for href in hrefs[:slice_size]:
            scrap_doi = regular.search(href['href'])[0].strip(
                '()').split('\', \'')[0].strip('\' ')
            scrap_title = regular.search(href['href'])[0].strip(
                '()').split('\', \'')[1].strip('\' ')
            logger.debug(f"'{scrap_title}', DOI: {scrap_doi}.")
            if title_to_vector(scrap_title.lower()) == vector_title:
                return scrap_doi.split(r'doi.org/')[-1].strip()
    except Exception as ex:
        logger.error(traceback.print_exc())
    return None
