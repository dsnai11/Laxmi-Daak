"""A user without the New Dispatch permission must not be offered the button (it led to 'Forbidden')."""
from app import db
from app.models.user import User


def _set_perms(app, ids, username, perms):
    with app.app_context():
        u = db.session.get(User, ids['user'][username])
        u.set_permissions(perms)
        db.session.commit()


def test_button_hidden_and_friendly_page_when_permission_is_off(app, client_for, ids):
    _set_perms(app, ids, 'manager_c', {'can_new_dispatch': False})
    try:
        c = client_for('manager_c')
        assert 'href="/dispatch/new"' not in c.get('/dispatch/list').get_data(as_text=True)
        assert 'href="/dispatch/new"' not in c.get('/dashboard/manager').get_data(as_text=True)
        r = c.get('/dispatch/new')
        assert r.status_code == 403
        assert "don't have permission" in r.get_data(as_text=True)      # friendly page, not bare "Forbidden"
    finally:
        _set_perms(app, ids, 'manager_c', {})


def test_button_shown_and_page_opens_when_permission_is_on(client_for):
    c = client_for('manager_c')
    assert 'href="/dispatch/new"' in c.get('/dispatch/list').get_data(as_text=True)
    assert 'href="/dispatch/new"' in c.get('/dashboard/manager').get_data(as_text=True)
    assert c.get('/dispatch/new').status_code == 200


def test_admin_always_sees_button(client_for):
    assert 'href="/dispatch/new"' in client_for('admin').get('/dispatch/list').get_data(as_text=True)


def test_api_forbidden_stays_plain_for_scripts(client_for):
    r = client_for('manager_a').get('/api/dashboard/stats')
    assert r.status_code == 403
