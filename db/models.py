from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
import datetime
import uuid

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
    id = Column(Integer, primary_key=True, index=True)
    ig_ids = Column(String)
    caption = Column(String)
    media_url = Column(String)
    public_id = Column(String)
    media_type = Column(String)
    scheduled_time = Column(DateTime)
    username = Column(String)
    in_progress = Column(Boolean, default=False, nullable=False)

class PostLog(Base):
    __tablename__ = "post_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    ig_ids = Column(Text, nullable=False)
    caption = Column(Text, nullable=False)
    media_type = Column(String, nullable=False)
    results = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    
class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    session_token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    def is_valid(self) -> bool:
        # instance attribute comparison (returns a plain Python bool)
        return bool(self.expires_at and self.expires_at > datetime.datetime.utcnow())

    @staticmethod
    def generate_token():
        return str(uuid.uuid4())