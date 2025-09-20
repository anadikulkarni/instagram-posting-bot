from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    accounts = relationship("GroupAccount", back_populates="group", cascade="all, delete")

class GroupAccount(Base):
    __tablename__ = "group_accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    ig_id = Column(String, nullable=False)
    group = relationship("Group", back_populates="accounts")

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ig_ids = Column(Text, nullable=False)
    caption = Column(Text, nullable=False)
    media_url = Column(String, nullable=False)
    public_id = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)

class PostLog(Base):
    __tablename__ = "post_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    ig_ids = Column(Text, nullable=False)
    caption = Column(Text, nullable=False)
    media_type = Column(String, nullable=False)
    results = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)