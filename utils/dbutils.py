# -*- coding: utf-8 -*-
import sys, traceback, logging
import datetime
import sqlite3
import re
import json

_LOG_LEVEL = logging.DEBUG

logger = logging.getLogger(__name__)
logger.setLevel(_LOG_LEVEL)

DB_CONNECTION = None
DB_CHROME_CONNECTION = None

_CURRENT_PROGRAM_TRANSACTION_ID = -1

def set_Loglevel(Loglevel):
    logger.setLevel(LOG_LEVEL)

def create_tables_if_not_exists():
    create_tables_sql = ['''
        create table if not exists transactions
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         from_date datetime not null,
         to_date datetime not null,
         command varchar(10000)  not null,
         parameters varchar(10000) not null,
         result varchar(10000) not null,
         description text
        );''',
        '''
        create table if not exists authors
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         name varchar(1000),
         shortname varchar(1000),
         google_id varchar(1000),
         google_h_index varchar(1000),
         google_i10_index varchar(1000),
         google_citations integer,
         notes varchar(1000),
         r_transaction integer not null,
         foreign key (r_transaction) references transactions(id)
        );
        ''',
        '''
        create table if not exists papers
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         title varchar(1000) not null,
         year integer,
         publisher varchar(1000),
         DOI varchar(1000),
         abstract varchar(10000),
         abstract_ru varchar(10000),
         references_count integer,
         google_type varchar(1000),
         google_url varchar(1000),
         google_cluster_id varchar(1000),
         google_file_url varchar(1000),
         google_cited_by_count integer,
         google_versions integer,
         pages integer,
         start_page integer,
         end_page integer,
         authors integer,
         endnote text,
         source_pdf varchar(1000),
         notes varchar(1000),
         score integer,
         ignore boolean not null,
         r_transaction integer not null,
         r_file_transaction integer,
         foreign key (r_transaction) references transactions(id)
        );
        ''',
        '''
        create table if not exists grobid_papers
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         title varchar(1000) not null,
         year integer,
         DOI varchar(1000),
         google_cluster_id varchar(1000),
         r_paper INTEGER,
         endnote TEXT,
         r_transaction integer not null,
         foreign key (r_paper) references papers(id),
         foreign key (r_transaction) references transactions(id)
        );
        ''',
        '''
        create table if not exists author_paper
        (r_author integer not null,
         r_paper integer not null,
         r_transaction integer not null,
         foreign key (r_transaction) references transactions(id),
         foreign key (r_author) references authors(id),
         foreign key (r_paper) references papers(id)
        );
        ''',
        '''
        create table if not exists paper_paper
        (r_paper1 integer not null,
         r_paper2 integer not null,
         type varchar(100) check (type in ('citied','related')),
         r_transaction integer not null,
         foreign key (r_transaction) references transactions(id),
         foreign key (r_paper2) references papers(id),
         foreign key (r_paper2) references papers(id)
        );
        ''']
    cur = DB_CONNECTION.cursor()
    for sql_op in create_tables_sql:
        cur.execute(sql_op)


def get_columns_names(tablename):
    logger.debug("Get columns names from table %s." % tablename)
    cur = DB_CONNECTION.cursor()
    cur.execute("SELECT * FROM {}".format(tablename))
    return [cn[0] for cn in cur.description]


def get_author_ID(params):
    logger.debug("Get author id %s." % json.dumps(params))
    res = execute_sql("""
        SELECT id 
        FROM authors 
        WHERE google_id = :google_id OR name = :name OR shortname = :shortname
        """, **params)
    id = None
    if res != []: id = res[0][0]
    logger.debug("Author id = {0}.".format(id))
    return id


def get_pdf_download_transaction(params):
    logger.debug("Get pdf download transaction %s." % json.dumps(params))
    res = execute_sql("""
        select r_file_transaction from papers
        where id = :id
        """, **params)
    tr = None
    if res != []: tr = res[0][0]
    logger.debug("r_file_transaction = {0}.".format(tr))
    return tr


def get_paper_ID(params):
    logger.debug("Get paper id %s." % json.dumps(params))
    res = execute_sql("""
        select id from papers
        where (
              title = :title
              and authors = :auth_count
              and (google_type = :google_type or google_type is null or :google_type is null)
              and (year = :year or year is null or :year is null)
              and (pages = :pages or pages is null or :pages is null)
              --and (start_page = :start_page or start_page is null or :start_page is null)
              --and (end_page = :end_page or end_page is null or :end_page is null)
              )
              or
              (DOI = :DOI)
        """, **params)
    id = None
    if res != []: id = res[0][0]
    logger.debug("Paper id = {0}.".format(id))
    return id


def get_grobid_paper_ID(params):
    logger.debug("Get paper from grobid id %s." % json.dumps(params))
    res = execute_sql("""
        select id from grobid_papers
        where (
              title = :title
              and (year = :year or year is null or :year is null)
              )
              or
              (doi = :doi)
        """, **params)
    id = None
    if res != []: id = res[0][0]
    logger.debug("Paper id = {0}.".format(id))
    return id


def check_exists_paper_paper_edge(params):
    logger.debug("Check exists paper-paper edge for %s." % json.dumps(params))
    res = execute_sql("""
        SELECT count(*)
        FROM paper_paper
        WHERE r_paper1 = :IDpaper1 and r_paper2 = :IDpaper2 and type = :type
        """, **params)[0][0]
    return res != 0


def set_program_transaction(Command, Params):
    def ADD_Transaction():
        global _CURRENT_PROGRAM_TRANSACTION_ID
        _CURRENT_PROGRAM_TRANSACTION_ID = execute_sql("""
            INSERT INTO transactions(
                from_date,
                to_date,
                command,
                parameters,
                result) VALUES (
                :from_date,
                :to_date,
                :command,
                :parameters,
                \"USER STOPPED\"
                )
            """, **{"from_date":datetime.datetime.now(), "to_date":datetime.datetime.now(), "command":Command, "parameters":Params})
    Transactional(ADD_Transaction)
    

def close_program_transaction(result, description):
    def UPDATE_Transaction():
        execute_sql("""
            UPDATE transactions 
            SET to_date = :to_date, result = :result, description = :description WHERE ID = :ID
            """, **{"to_date":datetime.datetime.now(), "result":result, "ID":_CURRENT_PROGRAM_TRANSACTION_ID, "description":description})
    Transactional(UPDATE_Transaction)


def add_new_paper(params):
    logger.debug("Add new paper (title='%s')" % params["title"])
    params.update({"ignore":False, "r_transaction":_CURRENT_PROGRAM_TRANSACTION_ID})
    keys = [key for key in params.keys() if key != "id"]
    return execute_sql("""
        INSERT INTO papers({}) VALUES(:{})
        """.format(", ".join(keys), ", :".join(keys)), **params)

def add_new_grobid_paper(params):
    logger.debug("Add new paper from grobid (title='%s')" % params["title"])
    params.update({"r_transaction":_CURRENT_PROGRAM_TRANSACTION_ID})
    keys = [key for key in params.keys() if key != "id"]
    return execute_sql("""
        INSERT INTO grobid_papers({}) VALUES(:{})
        """.format(", ".join(keys), ", :".join(keys)), **params)

def add_new_author(params):
    logger.debug("Add new author (GID = %s, Name = %s, Shortname = %s)" % (params["google_id"], params["name"], params["shortname"]))
    params.update({"transaction":_CURRENT_PROGRAM_TRANSACTION_ID})
    return execute_sql("""
        INSERT INTO authors(
            name,
            shortname,
            google_id,
            google_h_index,
            google_i10_index,
            google_citations,
            r_transaction
            ) VALUES (
            :name,
            :shortname,
            :google_id,
            :google_h_index,
            :google_i10_index,
            :google_citations,
            :transaction
            )""", **params)


def add_author_paper_edge(IDAuthor, IDPaper):
    execute_sql("""
    INSERT INTO author_paper 
    VALUES(?, ?, ?)
    """, *(IDAuthor, IDPaper, _CURRENT_PROGRAM_TRANSACTION_ID))


def add_paper_paper_edge(IDPaper1, IDPaper2, Type):
    execute_sql("""
    INSERT INTO paper_paper
    VALUES(?, ?, ?, ?)
    """, *(IDPaper1, IDPaper2, Type, _CURRENT_PROGRAM_TRANSACTION_ID))

def update_paper(params, update_addition_info=False):
    logger.debug("Update paper id={0}.".format(params["id"]))
    execute_sql("""
        UPDATE papers
        SET {}
        WHERE id=:id
        """.format(", ".join([key + "=:" + key for key in params.keys() if key != "id"])), **params)

def execute_sql(SQL, *args, **options):
    cur = DB_CONNECTION.cursor()
    operator_type = SQL.strip().lower().split(" ")[0]
    if args != () or options != {}:
        logger.debug("Execute sql with params: type={2} sql='{0}'; params={1}".format(SQL, args if args != () else options, operator_type))
        cur.execute(SQL, args if args != () else options)
    else: 
        logger.debug("Execute sql: type={1} sql='{0}'".format(SQL, operator_type))
        cur.execute(SQL)
    # variables for checking len row, this need for logging
    len_row = 0
    if operator_type == "select":
        res = cur.fetchall()
        if res:
            len_row = len(res[0])
    elif operator_type == "insert": res = cur.lastrowid
    else: res = None
    if len_row>3:
        res_for_logging = [row[:3] for row in res]
    else:
        res_for_logging = res
    logger.debug("Query result: {0}".format(json.dumps(res_for_logging)))
    return res


def commit(transaction_name=""):
    """Fixes the transaction changes"""
    logger.debug("Commiting transaction %s." % transaction_name)
    DB_CONNECTION.commit()


def rollback(transaction_name=""):
    """Rolling back the transaction changes"""
    logger.debug("Rolling back transaction %s" % transaction_name)
    DB_CONNECTION.rollback()


def Transactional(func, *args, **kwargs):
    """Executes the transaction. If successful, fixes the changes. In case of failure, it rolls back."""
    result = None
    try:
        logger.debug("Enters transaction proxy for function: %s." % func.__name__)
        result = func(*args, **kwargs)
        commit("for function: %s" % func.__name__)
    except:
        logger.warn(traceback.format_exc())
        rollback("for function: %s" % func.__name__)
    return result


def connect(DBPath):
    global DB_CONNECTION
    logger.info("Initializing connection to sqlite database, version: %i.%i.%i." % sqlite3.version_info)
    DB_CONNECTION = sqlite3.connect(DBPath)
    create_tables_if_not_exists()


def connect_to_cookies_database(DBPath):
    global DB_CHROME_CONNECTION
    logger.info("Initializing connection to sqlite chrome database, version: %i.%i.%i." % sqlite3.version_info)
    DB_CHROME_CONNECTION = sqlite3.connect(DBPath)


def close_connection():
    logger.info("Close database.")
    if DB_CONNECTION: DB_CONNECTION.close()


def close_connection_to_cookies_database():
    logger.info("Close database.")
    if DB_CHROME_CONNECTION: DB_CHROME_CONNECTION.close()


def get_sql_columns(SQL):
    """Function extract parametrs from SQL and return it in source order"""
    SQL_PARAMS_RE = "select [A-Za-z0-9_, ]* from"
    logger.info("Extract columns from SQL: '{0}'.".format(SQL))
    regex_result = re.findall(SQL_PARAMS_RE, SQL)[0]
    params = regex_result[len("select "):len(regex_result) - len(" from")]
    res = [param for param in map(str.strip, params.split(","))]
    logger.info("Extracted columns: {0}".format(str(res)))
    return res


def update_pdf_transaction(paper_id, source):
    logger.debug("Update pdf_transaction for paper id={0}.".format(paper_id))
    execute_sql("""
        UPDATE papers 
        SET r_file_transaction=:r_file_transaction,
            source_pdf=:source_pdf
        WHERE id = :id
        """, **{"r_file_transaction":_CURRENT_PROGRAM_TRANSACTION_ID, "source_pdf":source, "id":paper_id})
    return 0