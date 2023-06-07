"""
Connector
"""

import os
import json
from typing import Optional, Iterator, Any, List
from pathlib import Path
import pandas
import gspread as gs
import requests
from playwright.sync_api import sync_playwright

import sqlalchemy
from sqlalchemy.sql import text
from sqlalchemy import create_engine, Table, MetaData

class Connector:
    """
    Base class for Import
    """

    def __init__(self, *args, **kwargs):
        pass

    def authenticate(self, token: str):
        pass

    def read_all(
            self,
            *args,
            **kwargs
    ) -> Any:
        """
        Read Source file and parse through parser

        return: DataPandas, the data, of which a dataframe can be accessed via x.df
        """

        data = None
        while True:
            b = self.read_chunk(b)
            if b is None:
                break
            data = b
        return data

    def read_chunk(
            self,
            outputb,
            *args,
            **kwargs
    ) -> Any:
        return None

    def write_all(
            self,
            data,
            *args, **kwargs
    ) -> None:
        for i in self.write_chunk(
                data
        ):
            pass

    def write_chunk(
            self,
            data,
            *args, **kwargs
    ) -> Iterator[Any]:
        raise NotImplementedError

class ConnectorCache(Connector):
    def __init__(self, cache, default_key = None):
        super().__init__()
        self.default_key = default_key
        self.cache = cache

    def read_all(self, *args, **kwargs):
        key = kwargs.get('key', self.default_key)
        return self.cache.get(key) if key is not None else None

    def write_all(self, value, *args, **kwargs):
        key = kwargs.get('key', self.default_key)
        self.cache.set(key, value)

class Cache:
    def __init__(self):
        self.cache_data = {}

    def set(self, key, value):
        self.cache_data[key] = value

    def get(self, key):
        return self.cache_data[key]

    def connector(self, default_key = None):
        return ConnectorCache(self, default_key)


class ConnectorCsv(Connector):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.path_root = kwargs.get('path_root', os.getcwd())
        Path(self.path_root).mkdir(parents=True, exist_ok=True)

    def read_all(
            self, *args, **kwargs
    ) -> Any:
        return pandas.read_csv(os.path.join(self.path_root, args[0]))

    def write_all(
            self,
            data,
            *args, **kwargs) -> None:
        filename = kwargs.get('key', None)
        if filename is None and len(args) > 0:
            filename = args[0]
        filename = os.path.join(self.path_root, filename)
        data.to_csv(filename)

class ConnectorJson(Connector):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.path_root = kwargs.get('path_root', os.getcwd())
        Path(self.path_root).mkdir(parents=True, exist_ok=True)

    def read_all(
            self, *args, **kwargs
    ) -> Any:
        filename = kwargs.get('key', None)
        if filename is None and len(args) > 0:
            filename = args[0]
        with open(os.path.join(self.path_root, filename)) as fileh:
            obj = json.load(fileh)
        return obj

    def write_all(
            self,
            data,
            *args, **kwargs) -> None:
        filename = kwargs.get('key', None)
        if filename is None and len(args) > 0:
            filename = args[0]
        if isinstance(filename, str):
            filename = os.path.join(self.path_root, filename)
            with open(filename, 'w') as fileh:
                fileh.write(json.dumps(data, default=str))
        else:
            if isinstance(data, str):
                print(data, file=filename)
            else:
                filename.write(json.dumps(data, default=str))

class ConnectorSql(Connector):
    def __init__(self, engine):
        super().__init__()
        self.engine = create_engine(engine)

    def read_all(
            self,
            *args, **kwargs) -> Any:
        try:
            df = pandas.read_sql(args[0], self.engine)
            return df
        except Exception as e:
            return None

    def write_all(
            self,
            data,
            *args,
            **kwargs
    ) -> None:
        table = kwargs.pop('key', kwargs.pop('table', None))
        if table is None and len(args) > 0:
            table = args[0]
        with self.engine.connect() as conn:
            data.to_sql(
                table,
                conn,
                **kwargs
            )

    def write_chunk(
            self,
            data,
            *args, **kwargs
    ) -> Iterator[Any]:
        self.write_all(data, *args, **kwargs)
        yield None

    def execute(self, statement_list: List[str], **line):
        with self.engine.connect() as conn:
            for statement in statement_list:
                conn.execute(text(statement), **line)

    def drop_table(
            self,
            table_name: str,
            ignore_fail: bool = True
    ):
        try:
            tbl = Table(
                table_name, MetaData(),
                autoload_with=self.engine
            )
        except sqlalchemy.exc.NoSuchTableError:
            if ignore_fail:
                return
            raise
        tbl.drop(self.engine, checkfirst=False)

    def create_table(
            self,
            table_name: str,
            columns,
            **params):
        metadata = MetaData()
        print(columns)
        Table(table_name, metadata, *columns)
        metadata.create_all(self.engine, **params)

class ConnectorRest(Connector):
    def __init__(self, base_, **kwargs):
        super().__init__()
        self.base = base_
        self.playwright = kwargs.get('playwright', False)

    def read_all(
            self,
            *args, **kwargs) -> Any:
        if type(args[0]) is dict:
            url = self.base.format(**args[0])
        else:
            url = self.base.format(**kwargs)
        if len(args) > 0 and type(args[0]) is not dict:
            url = os.path.join(url, args[0])
        if self.playwright:
            with sync_playwright() as p:
                browser_type = p.firefox
                browser = browser_type.launch()
                page = browser.new_page()
                response = page.goto(
                    url
                )
                return self.process_json(response.json())

        response = requests.get(os.path.join(
            url
        ))
        return self.process_json(response.json())

    @staticmethod
    def process_json(json_obj):
        return json_obj

class ConnectorGoogleSheets(Connector):
    def read_all(self, *args, **kwargs) -> Any:
        sheets = args[0].split(":", 1)
        url = f'https://docs.google.com/spreadsheets/d/{sheets[0]}/export'
        if len(args) > 1:
            kwargs['sheet_name']=args[1]
        df = pandas.read_excel(url, **kwargs)
        df.columns.values[1] = "value"
        df.rename(columns={'Date':'date'},inplace=True)
        return df

cache_ = Cache()

def connector_factory(url: str) -> Optional[Connector]:
    if url.startswith('cache'):
        return cache_.connector()
    if url.startswith('gsheet'):
        return ConnectorGoogleSheets()
    if url.startswith('csv'):
        l = url.split(':', 1)
        if len(l) > 1:
            return ConnectorCsv(path_root=l[1])
        return ConnectorCsv()
    if url.startswith('json'):
        l = url.split(':', 1)
        if len(l) > 1:
            return ConnectorJson(path_root=l[1])
        return ConnectorJson()
    if url.startswith('playwright+http'):
        l = url.split('+', 1)
        return ConnectorRest(l[1], playwright=True)
    if url.startswith('rest+http'):
        return ConnectorRest(url)
    if url.startswith('sqlite') or \
       url.startswith('postgresql') or \
       url.startswith('mysql') or \
       url.startswith('mariadb') or \
       url.startswith('oracle') or \
       url.startswith('mssql') or \
       url.startswith('sqlalchemy') or \
       url.startswith('gsheets') or \
       url.startswith('pybigquery'):
        return ConnectorSql(url)
    return None
