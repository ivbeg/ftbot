from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from os import path

currentDir = path.abspath(path.dirname(__file__))

Base = declarative_base()
engine = create_engine('sqlite:///' + currentDir + '/db.db', echo=True)

class PostImg(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    flickr_id = Column(String)
    owner = Column(String)
    posted = Column(Integer, server_default='0')
    
    def make_posted(self):
        self.posted = '1'

    def __init__(self, flickr_id, owner):
        self.flickr_id = flickr_id
        self.owner = owner

if __name__ == '__main__':
    Base.metadata.create_all(engine)