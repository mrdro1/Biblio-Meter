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
         result varchar(10000) not null
        );''',
        '''
        create table if not exists authors
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         name varchar(1000),
         shortname varchar(1000),
         --rg_profile_id varchar(1000),
         --rg_author_uid varchar(1000),
         --rg_workplace varchar(1000),
         --rg_score varchar(1000),
         --rg_reads integer,
         --rg_citations integer,
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
        create table if not exists authors_skills
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         skill varchar(1000) not null,
         r_author integer not null,
         r_transaction integer not null,
         foreign key (r_author) references authors(id),
         foreign key (r_transaction) references transactions(id)
        );
        ''',
        '''
        create table if not exists authors_topics
        (id INTEGER PRIMARY KEY AUTOINCREMENT not null,
         topic varchar(1000) not null,
         r_author integer not null,
         r_transaction integer not null,
         foreign key (r_author) references authors(id),
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
         rg_id varchar(1000),
         references_count integer,
         g_type varchar(1000),
         google_url varchar(1000),
         google_file_url varchar(1000),
         rg_type varchar(1000),
         pages integer,
         start_page integer,
         end_page integer,
         authors integer,
         g_endnote text,
         rg_ris text,
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


def get_paper_ID(params):
    logger.debug("Get paper id %s." % json.dumps(params))
    res = execute_sql("""
        select id from papers
        where (
              title = :title
              and authors = :auth_count
              and (g_type = :g_type or g_type is null or :g_type is null)
              and (year = :year or year is null or :year is null)
              and (pages = :pages or pages is null or :pages is null)
              --and (start_page = :start_page or start_page is null or :start_page is null)
              --and (end_page = :end_page or end_page is null or :end_page is null)
              )
              or
              (DOI = :DOI)
              or
              (rg_id = :rg_id)
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
    

def close_program_transaction(Result):
    def UPDATE_Transaction():
        execute_sql("""
            UPDATE transactions 
            SET to_date = :to_date, result = :result WHERE ID = :ID
            """, **{"to_date":datetime.datetime.now(), "result":Result, "ID":_CURRENT_PROGRAM_TRANSACTION_ID})
    Transactional(UPDATE_Transaction)


def add_new_paper(params):
    logger.debug("Add new paper (title='%s')" % params["title"])
    params.update({"ignore":False, "transaction":_CURRENT_PROGRAM_TRANSACTION_ID})
    return execute_sql("""
        INSERT INTO papers(
            title, year, publisher, start_page, end_page, pages, g_type,
            DOI, abstract, abstract_ru, rg_id, references_count, rg_type,
            g_endnote, rg_ris, authors, r_transaction, ignore,
            google_url, google_file_url
        ) VALUES(
            :title, :year, :publisher, :start_page, :end_page, :pages, :g_type,
            :DOI, :abstract, :abstract_ru, :rg_id, :references_count, :rg_type,
            :EndNote, :RIS, :authors, :transaction, :ignore, :google_url,
            :google_file_url
        )
        """, **params)


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
    if update_addition_info:
        execute_sql("""
            UPDATE papers 
            SET DOI=:DOI,
                abstract=:abstract,
                abstract_ru=:abstract_ru                
            WHERE id = :id
            """, **params)
    else:
        execute_sql("""
            UPDATE papers 
            SET title=:title,
                year=:year,
                publisher=:publisher,
                start_page=:start_page,
                end_page=:end_page,
                pages=:pages,
                g_type=:g_type,
                DOI=:DOI,
                abstract=:abstract,
                abstract_ru=:abstract_ru,
                rg_id=:rg_id,
                references_count=:references_count,
                rg_type=:rg_type,
                g_endnote=:EndNote,
                rg_ris=:RIS,
                authors=:authors,
                google_url=:google_url,
                google_file_url=:google_file_url
            WHERE id = :id
            """, **params)


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


def delete_cookie_from_chrome_db():
    logger.debug("Delete cookie from scholar cookie database")
    sql = """
        DELETE FROM cookies 
        WHERE
           --(
           --   host_key LIKE "%accounts%" 
           --OR host_key LIKE "%google%"
           --) 
           --AND 
            name not in ('SSID', 'SID', 'HSID', 'GSP')
          """
    logger.debug("Execute sql: \n{}".format(sql))
    cur = DB_CHROME_CONNECTION.cursor()
    cur.execute(sql)
    try:
        DB_CHROME_CONNECTION.commit()
    except sqlite3.OperationalError:
        return -2
    return 0