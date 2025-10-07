from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Enum
from sqlalchemy.orm import declarative_base, relationship
import datetime
import uuid
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMIN = "admin"
    INTERN = "intern"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.INTERN)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationship to sessions
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

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
    username = Column(String, ForeignKey("users.username"), nullable=False)
    session_token = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    # Relationship to user
    user = relationship("User", back_populates="sessions")

    def is_valid(self) -> bool:
        # instance attribute comparison (returns a plain Python bool)
        return bool(self.expires_at and self.expires_at > datetime.datetime.utcnow())

    @staticmethod
    def generate_token():
        return str(uuid.uuid4())