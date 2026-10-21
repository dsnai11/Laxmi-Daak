"""Shared fixtures: one throw-away app on an in-memory SQLite database.

The real database, .env and SMTP settings are never used by the tests.
"""
import itertools
from unittest import mock

import pytest

from app import create_app, db
from app.config import Config


class TestConfig(Config):
    __test__ = False  # not a pytest test class
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SECRET_KEY = 'test-only-key'
    MAIL_SERVER = ''
    MAIL_USERNAME = ''
    MAIL_PASSWORD = ''
    PUSHPAK_API_USER = ''
    PUSHPAK_API_PASS = ''


@pytest.fixture(scope='session')
def app():
    # No background e-mail threads during tests
    with mock.patch('app.services.email_service.start_overdue_checker'), \
         mock.patch('app.services.email_service.start_missing_fields_checker'):
        flask_app = create_app(TestConfig)
    with flask_app.app_context():
        _seed()
    return flask_app


_counter = itertools.count(1)


def _seed():
    from app.models.branch import Branch
    from app.models.department import Department
    from app.models.user import User

    branches = {}
    for code in ('A', 'B', 'C'):
        b = Branch(branch_code=code, name=f'Branch {code}', city=code, state='Rajasthan')
        db.session.add(b)
        branches[code] = b
    depts = {n: Department(name=f'Dept {n}') for n in ('1', '2')}
    db.session.add_all(depts.values())
    db.session.flush()

    def user(username, role, branch=None, dept=None, email=''):
        u = User(name=username.title(), username=username, role=role, email=email,
                 branch_id=branches[branch].id if branch else None,
                 department_id=depts[dept].id if dept else None,
                 is_active=True)
        u.set_password('Test-pass-1234')
        db.session.add(u)
        return u

    user('manager_a', 'manager', 'A', email='a@example.com')
    user('manager_b', 'manager', 'B', email='b@example.com')
    user('manager_c', 'manager', 'C', email='c@example.com')
    user('emp_d1', 'employee', 'A', '1', email='d1@example.com')
    user('emp_d1_colleague', 'employee', 'A', '1', email='d1b@example.com')
    user('emp_d2', 'employee', 'A', '2', email='d2@example.com')
    db.session.commit()


@pytest.fixture()
def ids(app):
    """Primary keys of the seeded rows, looked up by name."""
    from app.models.branch import Branch
    from app.models.department import Department
    from app.models.user import User
    with app.app_context():
        return {
            'user': {u.username: u.id for u in User.query.all()},
            'branch': {b.branch_code: b.id for b in Branch.query.all()},
            'dept': {d.name.split()[-1]: d.id for d in Department.query.all()},
        }


@pytest.fixture()
def client_for(app, ids):
    """client_for('manager_a') -> a test client already logged in as that user."""
    def make(username):
        c = app.test_client()
        with c.session_transaction() as s:
            s['_user_id'] = str(ids['user'][username])
            s['_fresh'] = True
        return c
    return make


@pytest.fixture()
def make_parcel(app, ids):
    """Create a parcel from branch A to branch B (override anything via kwargs)."""
    from app.models.parcel import Parcel

    def make(**kw):
        n = next(_counter)
        data = dict(
            tracking_number=f'CRR-TEST-{n:05d}',
            sender_name='Sender', receiver_name='Receiver',
            sender_branch_id=ids['branch']['A'],
            receiver_branch_id=ids['branch']['B'],
            current_branch_id=ids['branch']['A'],
            created_by=ids['user']['manager_a'],
            status='pending',
        )
        data.update(kw)
        with app.app_context():
            p = Parcel(**data)
            db.session.add(p)
            db.session.commit()
            return p.tracking_number, p.id
    return make
