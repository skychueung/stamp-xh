import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.projects import create_project, list_projects
from app.database import Base
from app.models.orm import Project
from app.schemas import ProjectCreate


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


def test_project_crud_scopes_by_owner(db_session):
    first = create_project(db_session, ProjectCreate(name="first"), owner_id="user-a")
    create_project(db_session, ProjectCreate(name="second"), owner_id="user-b")
    owned = list_projects(db_session, owner_id="user-a")
    assert [project.id for project in owned] == [first.id]
    assert db_session.query(Project).count() == 2
