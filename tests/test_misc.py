from datetime import date, timedelta

from app.models.parcel import Parcel
from app.models.user import User


def test_overdue_ignores_finished_parcels():
    past = date.today() - timedelta(days=3)
    for status, expected in [('pending', True), ('in_transit', True), ('delivered', False),
                             ('delivered_pending', False), ('closed', False), ('returned', False)]:
        assert Parcel(status=status, due_date=past).is_overdue is expected, status
    assert Parcel(status='pending', due_date=date.today() + timedelta(days=1)).is_overdue is False


def test_passwords_are_hashed_and_never_stored_in_plain_text(app):
    with app.app_context():
        u = User(name='T', username='pw_user')
        u.set_password('Sup3r-secret-pass')
        assert u.password_plain is None
        assert u.check_password('Sup3r-secret-pass') and not u.check_password('nope')


def test_short_new_password_rejected(client_for):
    r = client_for('manager_a').post('/profile', data={
        'name': 'Manager A', 'new_password': 'abc123', 'confirm_password': 'abc123'},
        follow_redirects=True)
    assert b'at least 8 characters' in r.data


def test_healthz_reports_ok_without_login(app):
    r = app.test_client().get('/healthz')
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'ok' and 'commit' in body


def test_security_headers_present(app):
    r = app.test_client().get('/login')
    assert r.headers['X-Content-Type-Options'] == 'nosniff'
    assert r.headers['X-Frame-Options'] == 'SAMEORIGIN'
