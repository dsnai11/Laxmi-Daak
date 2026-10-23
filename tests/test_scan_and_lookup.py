"""Scanner rules and the user lookup used by the dispatch form."""


def scan(client, tn, action):
    return client.post('/scan/process', json={'tracking_number': tn, 'action': action})


def test_unknown_action_rejected(client_for, make_parcel):
    tn, _ = make_parcel()
    assert scan(client_for('manager_a'), tn, 'hacked').status_code == 400


def test_any_branch_can_log_transit_scan(client_for, make_parcel):
    tn, _ = make_parcel()
    r = scan(client_for('manager_c'), tn, 'received')
    assert r.status_code == 200 and r.get_json()['new_status'] == 'in_transit'


def test_closing_actions_need_scope(client_for, make_parcel):
    tn, _ = make_parcel()
    c = client_for('manager_c')
    assert scan(c, tn, 'delivered').status_code == 403
    assert scan(c, tn, 'failed').status_code == 403
    assert scan(c, tn, 'returned').status_code == 403


def test_only_destination_branch_delivers(client_for, make_parcel):
    tn, _ = make_parcel()
    assert scan(client_for('manager_a'), tn, 'delivered').status_code == 400
    ok = scan(client_for('manager_b'), tn, 'delivered')
    assert ok.status_code == 200 and ok.get_json()['new_status'] == 'delivered'


def test_query_workflow_parcels_cannot_be_scanned(client_for, make_parcel):
    tn, _ = make_parcel(status='query_raised')
    assert scan(client_for('manager_a'), tn, 'received').status_code == 400


def test_api_scan_checks_scan_permission(client_for, make_parcel, app, ids):
    from app import db
    from app.models.user import User
    tn, _ = make_parcel(created_by=ids['user']['emp_d1'])
    with app.app_context():
        u = db.session.get(User, ids['user']['emp_d1'])
        u.set_permissions({'can_scan': False})
        db.session.commit()
    try:
        r = client_for('emp_d1').post('/api/scan', json={'tracking_number': tn, 'action': 'received'})
        assert r.status_code == 403
    finally:
        with app.app_context():
            u = db.session.get(User, ids['user']['emp_d1'])
            u.set_permissions({})
            db.session.commit()


def test_scan_lookup_hides_contact_details_from_outsiders(client_for, make_parcel):
    tn, _ = make_parcel(receiver_phone='9999999999', receiver_email='r@example.com',
                        description='secret goods')
    outsider = client_for('manager_c').get(f'/scan/lookup/{tn}').get_json()['parcel']
    insider = client_for('manager_a').get(f'/scan/lookup/{tn}').get_json()['parcel']
    assert outsider['receiver_phone'] == '' and outsider['receiver_email'] == ''
    assert outsider['description'] == ''
    assert insider['receiver_phone'] == '9999999999' and insider['description'] == 'secret goods'


def test_user_lookup_is_exact_match(client_for):
    c = client_for('manager_a')
    assert c.get('/api/users/lookup?email=b@example.com').status_code == 200
    assert c.get('/api/users/lookup?email=%25').status_code == 404
    assert c.get('/api/users/lookup?email=B@EXAMPLE.COM').status_code == 200
