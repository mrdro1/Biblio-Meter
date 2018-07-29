# -*- coding: utf-8 -*-
import sys, traceback, logging
#
from utils import DoubleDict
from settings import LOG_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

_TYPECODE = "%0"
_AUTHCODE = "%A"

PARAMS = DoubleDict({
         _TYPECODE : "Type",
         "%A" : "Author",
         "%B" : "SecondaryTitle", # of a book or conference name
         "%C" : "PublishedPlace",
         "%D" : "Year",
         "%E" : "Editor",
         "%F" : "Label",
         "%G" : "Language",
         "%H" : "TranslatedAuthor",
         "%I" : "Publisher",
         "%J" : "Journal",
         "%K" : "Keywords",
         "%L" : "CallNumber",
         "%M" : "AccessionNumber",
         "%N" : "NumberORISsue",
         "%O" : "AlternateTitle",
         "%P" : "Pages",
         "%Q" : "TranslatedTitle",
         "%R" : "DOI", # digital object identifier
         "%S" : "TertiaryTitle",
         "%T" : "Title",
         "%" : "URL",
         "%V" : "Volume",
         "%W" : "DatabaseProvider",
         "%X" : "Abstract",
         "%Y" : "TertiaryAuthorOrTranslator",
         "%Z" : "Notes",
         "%1" : "Custom1",
         "%2" : "Custom2",
         "%3" : "Custom1",
         "%4" : "Custom4",
         "%6" : "NumberOfVolumes",
         "%7" : "Edition",
         "%8" : "Date",
         "%9" : "TypeOfWork",
         "%?" : "SubsidiaryAuthor",
         "%@" : "ISBN/ISSN", # ISBN or ISSN number
         "%!" : "ShortTitle",
         "%#" : "Custom5",
         "%$" : "Custom6",
         "%]" : "Custom7",
         "%&" : "Section",
         "%(" : "OriginalPublication",
         "%)" : "ReprintEdition",
         "%*" : "ReviewedItem",
         "%+" : "AuthorAddress",
         "%^" : "Caption",
         "%>" : "FileAttachments",
         "%<" : "ResearchNotes",
         "%[" : "AccessDate",
         "%=" : "Custom8",
         "%~" : "NameOfDatabase",
       })

_TYPE = [
        "Generic",
        "Government Document",
        "Aggregated Database",
        "Ancient Text",
        "Artwork",
        "Audiovisual Material",
        "Bill",
        "uBlog",
        "Book",
        "Book Section",
        "Case",
        "Catalog",
        "Chart or Table",
        "Classical Work",
        "Computer Program",
        "Conference Paper",
        "Conference Proceedings",
        "Dictionary",
        "Edited Book",
        "Electronic Article",
        "Electronic Book",
        "Encyclopedia",
        "Equation",
        "Figure",
        "Film or Broadcast",
        "Grant",
        "Hearing",
        "Journal Article",
        "Legal Rule or Regulation",
        "Magazine Article",
        "Manuscript",
        "Map",
        "Music",
        "Newspaper Article",
        "Online Database",
        "Online Multimedia",
        "Pamphlet",
        "Patent",
        "Personal Communication",
        "Report",
        "Serial Publication",
        "Standard",
        "Statute",
        "Thesis",
        "Unpublished Work",
        "Web Page",
        "Unused 1",
        "Unused 2",
        "Unused 3"
    ]

def EndNote_parsing(SourceText, DecodeIdentifiers = True):
    """Parse text in EndNote format.
        SourceText : ustr - text in EndNote format.
        DecodeIdentifiers : Bool - Indicates whether the decode identifiers will take place.
    """
    def trueCode(code):
        if DecodeIdentifiers:
            return PARAMS[code].lower()
        return code

    resultDict = dict()
    logger.debug("Parsing EndNode text.")
    for line in SourceText.strip().split("\n"):
        cmd_line = line.strip("\t\r")
        # check that line from EN have length bigger than minimum ("%O A")
        if len(cmd_line) < 4:
            logger.debug("Invalid length: len == %i < 4." % len(cmd_line))
            return None
        code = cmd_line[:2]
        value = cmd_line[3:]
        # check code name
        if not code in PARAMS:
            logger.debug("Unknown code: %s." % code)
            return None
        # procces on type paper: valid name type
        if code == _TYPECODE and not value in _TYPE:
            logger.debug("Unknown type: %s." % value)
            return None
        # if code == _AUTHCODE: value = " ".join(value.split(', ')[::-1])

        # procces code with many value, for example: authors
        # if current code exists in result dict, than convert value to list and append current value
        if trueCode(code) in resultDict:
        # code is yet in result dict, but value is not list
            if not isinstance(resultDict[trueCode(code)], list):
                logger.debug("Parameter '%s' has more one value. Union this parameter in list." % code)
                resultDict[trueCode(code)] = list(resultDict[trueCode(code)])
            resultDict[trueCode(code)].append(value)
        # code is not in result dict, just add pair key-value to result dict
        else:
            if code == _AUTHCODE: value = list([value])
            resultDict[trueCode(code)] = value
    logger.debug("Successful EndNode text parsing.")
    return resultDict
