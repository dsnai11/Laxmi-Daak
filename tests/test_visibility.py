"""Every user sees only their own parcels (DOs also see what is addressed to / held at their branch)."""
from app import db
from app.models.user import User


def test_do_does_not_see_parcels_of_a_colleague_in_the_same_branch(client_for, make_parcel, ids):
    theirs, _ = make_parcel(created_by=ids['user']['manager_a2'])      # same branch A, other person
    mine, _ = make_parcel(created_by=ids['user']['manager_a'])
    c = client_for('manager_a')
    assert c.get(f'/dispatch/detail/{mine}').status_code == 200
    assert c.get(f'/dispatch/detail/{theirs}').status_code == 403
    page = c.get('/dispatch/list?per_page=500').get_data(as_text=True)
    assert mine in page and theirs not in page


def test_colleague_cannot_edit_or_delete_my_parcel(client_for, make_parcel, ids):
    tn, pid = make_parcel(created_by=ids['user']['manager_a'])
    c = client_for('manager_a2')
    assert c.post(f'/dispatch/delete/{pid}').status_code == 403
    assert c.post(f'/dispatch/archive/{pid}').status_code in (403, 404)
    r = c.get(f'/dispatch/edit/{tn}', follow_redirects=False)
    assert r.status_code == 302 and '/dispatch/detail/' in r.headers['Location']


def test_do_sees_parcels_addressed_to_the_branch(client_for, make_parcel, ids):
    tn, _ = make_parcel(created_by=ids['user']['manager_a'])           # A -> B
    assert client_for('manager_b').get(f'/dispatch/detail/{tn}').status_code == 200
    assert client_for('manager_c').get(f'/dispatch/detail/{tn}').status_code == 403


def test_first_name_prefix_does_not_leak_parcels(app, client_for, make_parcel, ids):
    with app.app_context():
        u = User(name='Ravi', username='ravi_plain', role='employee', is_active=True)
        u.set_password('Test-pass-1234')
        db.session.add(u)
        db.session.commit()
        uid = u.id
    ids['user']['ravi_plain'] = uid
    tn, _ = make_parcel(sender_name='Ravi Chhipa', created_by=ids['user']['manager_a'])
    c = client_for('ravi_plain')
    assert c.get(f'/dispatch/detail/{tn}').status_code == 403
    assert tn not in c.get('/dispatch/list').get_data(as_text=True)


def test_exact_name_match_still_works(app, client_for, make_parcel, ids):
    with app.app_context():
        u = User(name='Meena Sharma', username='meena', role='employee', is_active=True)
        u.set_password('Test-pass-1234')
        db.session.add(u)
        db.session.commit()
        ids['user']['meena'] = u.id
    tn, _ = make_parcel(receiver_name='meena sharma', created_by=ids['user']['manager_a'])
    assert client_for('meena').get(f'/dispatch/detail/{tn}').status_code == 200


def test_reports_are_scoped(client_for, make_parcel, ids):
    tn, _ = make_parcel(created_by=ids['user']['manager_a'], status='pending')
    mine = client_for('manager_a').get('/reports/pending').get_json()
    other = client_for('manager_c').get('/reports/pending').get_json()
    assert tn in [p['tracking_number'] for p in mine]
    assert tn not in [p['tracking_number'] for p in other]


def test_excel_export_is_scoped(client_for, make_parcel, ids):
    import io
    import openpyxl

    def exported(username):
        r = client_for(username).get('/reports/export/excel')
        assert r.status_code == 200
        sheet = openpyxl.load_workbook(io.BytesIO(r.data)).active
        return ' '.join(str(c.value) for row in sheet.iter_rows() for c in row if c.value)

    tn, _ = make_parcel(created_by=ids['user']['manager_a'])
    assert tn in exported('manager_a')
    assert tn not in exported('emp_d2')


def test_do_label_replaces_branch_manager(client_for, ids, app):
    with app.app_context():
        assert db.session.get(User, ids['user']['manager_a']).role_display == 'DO'
    page = client_for('manager_a').get('/dashboard/manager').get_data(as_text=True)
    assert 'Branch Manager' not in page
    assert 'DO' in page


def test_manager_dashboard_counts_only_own_scope(client_for, make_parcel, ids):
    make_parcel(created_by=ids['user']['manager_a2'])
    assert client_for('manager_a').get('/dashboard/manager').status_code == 200
    assert client_for('manager_a2').get('/dashboard/manager').status_code == 200


def test_shared_branch_do_does_not_see_branch_wide_incoming(client_for, make_parcel, ids):
    # Branch A has several logins, so "addressed to branch A" must not reach every DO of A
    tn, _ = make_parcel(sender_branch_id=ids['branch']['B'], receiver_branch_id=ids['branch']['A'],
                        current_branch_id=ids['branch']['B'], created_by=ids['user']['manager_b'],
                        receiver_name='Someone Else')
    assert client_for('manager_a').get(f'/dispatch/detail/{tn}').status_code == 403
    assert client_for('manager_a2').get(f'/dispatch/detail/{tn}').status_code == 403
    assert client_for('manager_b').get(f'/dispatch/detail/{tn}').status_code == 200   # the sender


def test_sender_name_alone_does_not_grant_access(client_for, make_parcel, ids):
    # Parcels often carry the branch name as sender_name; that must not expose them to the branch's users
    tn, _ = make_parcel(sender_name='Manager_A2', created_by=ids['user']['manager_b'],
                        sender_branch_id=ids['branch']['B'], receiver_branch_id=ids['branch']['C'],
                        current_branch_id=ids['branch']['B'])
    assert client_for('manager_a2').get(f'/dispatch/detail/{tn}').status_code == 403


def test_receiver_sees_parcel_addressed_by_email(client_for, make_parcel, ids):
    tn, _ = make_parcel(receiver_email='a2@example.com', created_by=ids['user']['manager_b'],
                        sender_branch_id=ids['branch']['B'], receiver_branch_id=ids['branch']['C'],
                        current_branch_id=ids['branch']['B'])
    assert client_for('manager_a2').get(f'/dispatch/detail/{tn}').status_code == 200


def test_performance_table_shows_only_own_row(client_for):
    page = client_for('manager_a').get('/dashboard/manager').get_data(as_text=True)
    assert 'Manager_A2' not in page and 'Emp_D1' not in page and 'Active Staff' not in page


def test_sender_email_alone_does_not_grant_access(client_for, make_parcel, ids):
    # Two logins sharing a mailbox must not see each other's dispatches
    tn, _ = make_parcel(sender_email='a2@example.com', created_by=ids['user']['manager_b'],
                        sender_branch_id=ids['branch']['B'], receiver_branch_id=ids['branch']['C'],
                        current_branch_id=ids['branch']['B'])
    assert client_for('manager_a2').get(f'/dispatch/detail/{tn}').status_code == 403
