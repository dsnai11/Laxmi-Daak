"""Admin password reset: new password shown once, never stored in readable form."""
from app import db
from app.models.security_log import SecurityLog
from app.models.user import User


def _login(app, username, password):
    return app.test_client().post('/login', data={'username': username, 'password': password})


def test_admin_reset_generates_password_that_works_once_shown(app, client_for, ids):
    uid = ids['user']['emp_d2']
    r = client_for('admin').post(f'/admin/accounts/reset-password/{uid}')
    body = r.get_json()
    assert r.status_code == 200 and body['success']
    assert len(body['password']) == 10 and body['username'] == 'emp_d2'
    assert r.headers['Cache-Control'] == 'no-store'
    # new password logs in (redirect), the old one does not
    assert _login(app, 'emp_d2', body['password']).status_code == 302
    assert _login(app, 'emp_d2', 'Test-pass-1234').status_code == 200


def test_admin_can_choose_the_password(app, client_for, ids):
    uid = ids['user']['emp_d1_colleague']
    r = client_for('admin').post(f'/admin/accounts/reset-password/{uid}', data={'password': 'Chosen-By-Admin-1'})
    assert r.get_json()['password'] == 'Chosen-By-Admin-1'
    assert _login(app, 'emp_d1_colleague', 'Chosen-By-Admin-1').status_code == 302


def test_short_password_rejected(client_for, ids):
    r = client_for('admin').post(f"/admin/accounts/reset-password/{ids['user']['manager_c']}",
                                 data={'password': 'short'})
    assert r.status_code == 400 and not r.get_json()['success']


def test_only_admin_can_reset(client_for, ids):
    uid = ids['user']['manager_b']
    assert client_for('manager_a').post(f'/admin/accounts/reset-password/{uid}').status_code == 403
    assert client_for('emp_d1').post(f'/admin/accounts/reset-password/{uid}').status_code == 403


def test_unknown_account_is_404(client_for):
    assert client_for('admin').post('/admin/accounts/reset-password/999999').status_code == 404


def test_password_is_never_stored_readably(app, client_for, ids):
    uid = ids['user']['manager_a2']
    secret = client_for('admin').post(f'/admin/accounts/reset-password/{uid}').get_json()['password']
    with app.app_context():
        u = db.session.get(User, uid)
        assert u.password_plain is None
        assert secret.encode() not in bytes(u.password_hash)
        assert u.check_password(secret)


def test_accounts_page_never_shows_a_password(client_for, ids):
    admin = client_for('admin')
    secret = admin.post(f"/admin/accounts/reset-password/{ids['user']['emp_d2']}").get_json()['password']
    page = admin.get('/admin/accounts').get_data(as_text=True)
    assert secret not in page
    assert 'resetAccountPassword(' in page


def test_reset_is_written_to_security_log(app, client_for, ids):
    client_for('admin').post(f"/admin/accounts/reset-password/{ids['user']['manager_c']}")
    with app.app_context():
        assert SecurityLog.query.filter_by(action='password_reset_by_admin').count() >= 1
