"""The Edit Account form must show the permissions an account really has."""
from app import db
from app.models.user import PERMISSION_KEYS, User


def test_default_manager_shows_new_dispatch_as_allowed(app, ids):
    with app.app_context():
        u = db.session.get(User, ids['user']['manager_a'])
        u.permissions = '{}'                       # never edited: defaults apply
        db.session.commit()
        assert u.has_permission('can_new_dispatch')
        assert 'can_new_dispatch' in u.effective_permissions_string().split(',')
        assert set(u.effective_permissions_string().split(',')) == set(PERMISSION_KEYS)


def test_department_user_default_has_no_dispatch_but_other_defaults(app, ids):
    with app.app_context():
        u = db.session.get(User, ids['user']['emp_d1'])
        u.permissions = '{}'
        db.session.commit()
        keys = u.effective_permissions_string().split(',')
        assert 'can_new_dispatch' not in keys and 'can_bulk_dispatch' not in keys
        assert 'can_scan' in keys and 'can_view_parcels' in keys


def test_explicitly_switched_off_permission_stays_off(app, ids):
    with app.app_context():
        u = db.session.get(User, ids['user']['manager_b'])
        u.set_permissions({'can_new_dispatch': False})
        db.session.commit()
        try:
            keys = u.effective_permissions_string().split(',')
            assert 'can_new_dispatch' not in keys and 'can_scan' in keys
        finally:
            u.set_permissions({})
            db.session.commit()


def test_saving_edit_form_for_default_account_keeps_new_dispatch(app, client_for, ids):
    """Open Edit, change only the phone number, save: New Dispatch must still be on."""
    with app.app_context():
        u = db.session.get(User, ids['user']['manager_c'])
        u.permissions = '{}'
        db.session.commit()
        perms = u.effective_permissions_string().split(',')
    admin = client_for('admin')
    page = admin.get('/admin/accounts').get_data(as_text=True)
    # the modal is pre-filled from this exact string, so the browser submits these checkboxes
    assert "'" + ','.join(perms) + "'" in page
    form = {'name': 'Manager C', 'username': 'manager_c', 'role': 'manager', 'phone': '9999999999'}
    form.update({k: 'on' for k in perms})
    assert admin.post(f"/admin/accounts/edit/{ids['user']['manager_c']}", data=form).status_code == 200
    with app.app_context():
        assert db.session.get(User, ids['user']['manager_c']).has_permission('can_new_dispatch')
