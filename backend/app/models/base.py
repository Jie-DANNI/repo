"""ORM 基类：所有模型继承 Base，表结构须与 db/schema.sql 严格一致。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
