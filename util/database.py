from typing import Optional

from contextlib import contextmanager
from contextlib import _GeneratorContextManager as Context

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.schema import MetaData


class Database(object):
    def __init__(self, uri: str, cache_limit: Optional[int]=0) -> None:
        self.engine = create_engine(uri)
        self.Session = sessionmaker(bind=self.engine)
        self.cache_limit = cache_limit
        self.cache = []
    
    def create_all(self,  metadata: MetaData) -> None:
        metadata.create_all(self.engine)

    @contextmanager
    def transaction(self) -> Context:
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        if self.cache:
            for i in self.cache:
                session.add(i)
            session.flush()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    __call__ = transaction

    def add(self, obj: object) -> None:
        """ Add an object to the database. """
        self.cache.append(obj)
        if self.cache_limit is not None and len(self.cache) > self.cache_limit:
            with self.transaction():
                # Starting a transaction will flush the cache
                pass

    def flush(self):
        with self.transaction():
            pass