"""
Database Connection - 数据库连接管理
"""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session

from .models import Base

# 数据库引擎
_engine = None
_SessionFactory = None
db = None


def get_database_url() -> str:
    """
    获取数据库连接 URL

    支持环境变量配置:
    - DATABASE_URL: 完整的数据库 URL
    - DB_TYPE: 数据库类型 (postgresql/mysql)
    - DB_HOST: 数据库主机
    - DB_PORT: 数据库端口
    - DB_NAME: 数据库名称
    - DB_USER: 数据库用户名
    - DB_PASSWORD: 数据库密码
    """
    # 优先使用完整 URL
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return database_url

    # 从单独的环境变量构建 URL
    db_type = os.environ.get('DB_TYPE', 'postgresql')
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_port = os.environ.get('DB_PORT', '5432')
    db_name = os.environ.get('DB_NAME', 'hierarchical_agents')
    db_user = os.environ.get('DB_USER', 'postgres')
    db_password = os.environ.get('DB_PASSWORD', '')

    if db_type == 'mysql':
        # 使用 pymysql 驱动（更易安装）
        return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    else:
        # 默认 PostgreSQL
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


def init_db(app=None, database_url: str = None):
    """
    初始化数据库

    Args:
        app: Flask 应用实例（可选，用于获取配置）
        database_url: 数据库 URL（可选，优先级高于环境变量）
    """
    global _engine, _SessionFactory, db

    # 确定数据库 URL
    if database_url:
        url = database_url
    elif app and app.config.get('DATABASE_URL'):
        url = app.config['DATABASE_URL']
    else:
        url = get_database_url()

    # 创建引擎
    _engine = create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=os.environ.get('DB_ECHO', 'false').lower() == 'true'
    )

    # 创建会话工厂
    _SessionFactory = sessionmaker(bind=_engine)
    db = scoped_session(_SessionFactory)

    # 创建所有表（如果不存在）
    Base.metadata.create_all(_engine)

    return db


def get_engine():
    """获取数据库引擎"""
    global _engine
    if _engine is None:
        init_db()
    return _engine


def get_db_session() -> Session:
    """
    获取数据库会话（scoped session，适用于 Flask 请求上下文）

    Returns:
        SQLAlchemy Session 实例
    """
    global db, _SessionFactory
    if db is None:
        init_db()
    return db()


def create_new_session() -> Session:
    """
    创建新的独立数据库会话（适用于后台线程）

    每次调用都会创建一个全新的 session，不与其他线程共享。
    调用者负责在使用完后关闭 session。

    Returns:
        新的 SQLAlchemy Session 实例
    """
    global _SessionFactory
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    数据库会话上下文管理器

    Usage:
        with get_db_context() as session:
            session.query(Model).all()
    """
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_db():
    """关闭数据库连接"""
    global db, _engine
    if db:
        db.remove()
    if _engine:
        _engine.dispose()
