"""Pytest fixtures for isolated in-memory or file-backed database and FastAPI TestClient."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.services.demo_service import DemoService
from app.schemas.session import DemoSessionCreate

# Use dedicated test SQLite database
TEST_DB_URL = "sqlite:///./test_fintech_sandbox.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_fintech_sandbox.db"):
        try:
            os.remove("./test_fintech_sandbox.db")
        except Exception:
            pass


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    yield session
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def demo_session(db_session):
    """Creates a fresh Scenario A demo session with seeded data and tokens."""
    req = DemoSessionCreate(scenario="scenario_a", display_name="Test Session")
    return DemoService.create_session(db_session, req)


@pytest.fixture
def user_headers(demo_session):
    return {"Authorization": f"Bearer {demo_session.credentials.user_token}"}


@pytest.fixture
def agent_headers(demo_session):
    return {"Authorization": f"Bearer {demo_session.credentials.agent_token}"}


@pytest.fixture
def demo_control_headers(demo_session):
    return {"Authorization": f"Bearer {demo_session.credentials.demo_control_token}"}
