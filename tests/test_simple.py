import os
import unittest

from overrides import override
from truflation.data.connector import ConnectorCsv,\
    ConnectorSql, ConnectorRest
import truflation.data.task
import truflation.data.validator
import truflation.data.metadata
from truflation.data.pipeline import Pipeline

import examples.csv_example.my_pipeline_details

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
cache = truflation.data.connector.Cache()
os.environ['CONNECTOR'] = f'sqlite:///{SCRIPT_DIR}/database.db'

class ReadTask(truflation.data.task.Task):
    def __init__(self,
                 database_: str,
                 filename_: str,
                 table_: str):
        super().__init__(
            ConnectorCsv(
                path_root=SCRIPT_DIR
            ),
            ConnectorSql(
                database_
            )
        )
        self.filename = filename_
        self.table = table_

    @override
    def run(self, *args, **kwargs):
        self.writer.drop_table(self.table, True)
        b = self.reader.read_all(self.filename)
        self.writer.write_all(b, table=self.table)

class WriteTask(truflation.data.task.Task):
    def __init__(self,
                 database_: str,
                 filename_: str,
                 table_: str):
        super().__init__(
            ConnectorSql(
                database_
            ),
            ConnectorCsv(
                path_root=SCRIPT_DIR
            )
        )
        self.filename = filename_
        self.table = table_

    @override
    def run(self, *args, **kwargs):
        b = self.reader.read_all(self.table)
        self.writer.write_all(b, key=self.filename)

class TestSimple(unittest.TestCase):
    def test_simple(self):
        connector = truflation.data.connector.Connector()
        task = truflation.data.task.Task()

    def test_read_csv(self):
        task = ReadTask(
            f'sqlite:///{SCRIPT_DIR}/database.db',
            'eggs.csv',
            'demo'
        )
        task.run()

    def test_write_csv(self):
        task = WriteTask(
            f'sqlite:///{SCRIPT_DIR}/database.db',
            'eggs.out.csv',
            'demo'
        )
        task.run()

    def test_cache(self):
        r = truflation.data.connector.ConnectorCache('key1')

    def test_playwrite(self):
        r = ConnectorRest(
            'http://ergast.com/api',
            playwrite=True
        )
        b = r.read_all('f1/2004/1/results.json')

class TestMetadataWrite(unittest.TestCase):
    def test_metadata_write(self):
        metadata = truflation.data.metadata.Metadata(
            f'sqlite:///{SCRIPT_DIR}/database.db',
        )

        metadata.write_all('table', {
            'foo': "3434",
            'bar': 232,
            'pow': 1.55
        })
        metadata.write_all('table2', {
            'foo': "3434",
            'bar': 234,
            'pow': 1.55
        })

class TestMetadataRead(unittest.TestCase):
    def test_metadata_read(self):
        metadata = truflation.data.metadata.Metadata(
            f'sqlite:///{SCRIPT_DIR}/database.db',
        )
        obj = metadata.read_all('table')
        self.assertEqual(obj['foo'], "3434")

class TestMetadataRead(unittest.TestCase):
    def test_metadata_read(self):
        metadata = truflation.data.metadata.Metadata(
            f'sqlite:///{SCRIPT_DIR}/database.db',
        )
        obj = metadata.read_by_key('bar')
        self.assertEqual(obj['table2'], 234)

class TestExample(unittest.TestCase):
    def test_example(self):
        pipeline_details = \
            examples.csv_example.my_pipeline_details.get_details()
        my_pipeline = Pipeline(pipeline_details)
        my_pipeline.ingest()

if __name__ == '__main__':
    unittest.main()
