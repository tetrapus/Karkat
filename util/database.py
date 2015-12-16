from typing import Optional

from contextlib import contextmanager
from contextlib import _GeneratorContextManager as Context

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.schema import MetaData


class Database(object):
    def __init__(self, uri: str) -> None:
        self.engine = create_engine(uri)
        self.Session = sessionmaker(bind=self.engine)
    
    def create_all(self,  metadata: MetaData) -> None:
        metadata.create_all(self.engine)

    @contextmanager
    def transaction(self) -> Context:
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    __call__ = transaction