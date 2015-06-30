# -*- coding: utf-8 -*-

__all__ = ['Mapper', 'setup_mapping']

from . import dynamo
from .metadata import MetaData
from .field import *

import kiwi


class Mapper(object):
    def __init__(self, class_, tablename, schema,
                throughput=None, attributes=None,
                indexes=None, global_indexes=None,
                metadata=None):

        self.metadata = metadata or kiwi.metadata
        assert isinstance(self.metadata, MetaData)

        self.class_ = class_
        self.tablename = tablename
        self.schema = schema
        self.throughput = throughput

        self.attributes = attributes
        self.indexes = indexes or {}
        self.global_indexes = global_indexes or {}

        self.metadata.add(self)


    @property
    def table(self):
        if not hasattr(self, '_table'):
            self._table = self._build_table(dynamo.Table)
        return self._table

    def _build_table(self, builder):
        kwargs = {}
        kwargs['throughput'] = self.throughput
        kwargs['connection'] = self.metadata.connection

        if self.indexes:
            kwargs['indexes'] = [idx.map() for idx in self.indexes.values()]
        if self.global_indexes:
            kwargs['global_indexes'] = [idx.map() for idx in self.global_indexes.values()]

        return builder(self.tablename, self.schema, **kwargs)

    def create_table(self):
        self._table = self._build_table(dynamo.Table.create)

    def drop_table(self):
        self.table.delete()


    def get_item(self, *args):
        '''
        not support `consistent`, `attributes` yet
        '''
        assert len(self.schema) == len(args)
        kwargs = dict()
        for key, value in zip(self.schema, args):
            kwargs[key.name] = value
        try:
            return self.table.get_item(**kwargs)
        except dynamo.ItemNotFound: # ItemNotFound
            return None

    def new_item(self, **kwargs):
        return dynamo.Item(self.table, data=kwargs)

def setup_mapping(cls, clsname, dict_):
    _MapperConfig(cls, clsname, dict_)

class _MapperConfig(object):

    def __init__(self, cls_, clsname, dict_):
        self.cls = cls_
        self.clsname = clsname
        self.dict_ = dict(dict_)

        self.metadata = None
        self.tablename = None
        self.throughput = None
        self.attributes = {}
        self.schema = []
        self.indexes = {}
        self.global_indexes = {}

        self._scan_metadata()
        self._scan_tablename()
        self._scan_throughput()
        self._scan_attributes()
        self._scan_indexes()

        self._setup_mapper()

    def _scan_metadata(self):
        self.metadata = getattr(self.cls, '__metadata__', None)

    def _scan_tablename(self):
        self.tablename = getattr(self.cls, '__tablename__', None)

    def _scan_throughput(self):
        self.throughput = getattr(self.cls, '__throughput__', None)

    def _scan_attributes(self):
        cls = self.cls
        attributes = self.attributes
        schema = self.schema
        hashkey = None
        rangekey = None

        for base in cls.__mro__:
            for name, obj in vars(base).items():
                if isinstance(obj, Field):
                    if name in attributes:
                        continue

                    obj.configure(cls, name)
                    attributes[name] = obj

                    if obj.attr_type == dynamo.HashKey:
                        if not hashkey:
                            hashkey = obj.map_key()
                    elif obj.attr_type == dynamo.RangeKey:
                        if not rangekey:
                            rangekey = obj.map_key()

        if not hashkey:
            raise Exception("not hashkey found")
        schema.append(hashkey)
        if rangekey:
            schema.append(rangekey)


    def _scan_indexes(self):
        cls = self.cls
        indexes = self.indexes
        global_indexes = self.global_indexes

        for base in cls.__mro__:
            for name, obj in vars(base).items():
                if isinstance(obj, Index):
                    if name in indexes or name in global_indexes:
                        continue

                    obj.configure(cls, name)

                    if isinstance(obj, LocalIndex):
                        indexes[name] = obj
                    elif isinstance(obj, GlobalIndex):
                        global_indexes[name] = obj
                    else:
                        pass
        #TODO: check indexes for
        #   1. Hash primary key  vs Hask & Range primary key
        #   2. local indexes only for Hask & Range primary ??
        #   3. other


    def _setup_mapper(self):
        cls = self.cls

        mapper = Mapper(cls,
                    self.tablename,
                    schema=self.schema,
                    throughput=self.throughput,
                    attributes=self.attributes,
                    indexes=self.indexes,
                    global_indexes=self.global_indexes,
                    metadata=self.metadata,
                )
        cls.__mapper__ = mapper


