"""Who may see, change or delete a parcel."""


def test_login_page_loads(app):
    assert app.test_client().get('/login').status_code == 200


def test_anonymous_is_sent_to_login(app, make_parcel):
    tn, _ = make_parcel()
    r = app.test_client().get(f'/dispatch/detail/{tn}')
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_detail_visible_to_sender_and_receiver_branch(client_for, make_parcel):
    tn, _ = make_parcel()
    assert client_for('manager_a').get(f'/dispatch/detail/{tn}').status_code == 200
    assert client_for('manager_b').get(f'/dispatch/detail/{tn}').status_code == 200


def test_detail_forbidden_for_unrelated_branch(client_for, make_parcel):
    tn, _ = make_parcel()
    c = client_for('manager_c')
    assert c.get(f'/dispatch/detail/{tn}').status_code == 403
    assert c.get(f'/dispatch/print-label/{tn}').status_code == 403
    assert c.get(f'/dispatch/success/{tn}').status_code == 403


def test_department_user_sees_department_parcels_only(client_for, make_parcel, ids):
    own = make_parcel(sender_department_id=ids['dept']['1'],
                      created_by=ids['user']['emp_d1_colleague'])[0]
    other = make_parcel(sender_department_id=ids['dept']['2'],
                        created_by=ids['user']['emp_d2'])[0]
    c = client_for('emp_d1')
    assert c.get(f'/dispatch/detail/{own}').status_code == 200
    assert c.get(f'/dispatch/detail/{other}').status_code == 403


def test_delete_requires_ownership(client_for, make_parcel):
    _, pid = make_parcel()
    assert client_for('manager_c').post(f'/dispatch/delete/{pid}').status_code == 403
    assert client_for('manager_b').post(f'/dispatch/delete/{pid}').status_code == 403
    assert client_for('manager_a').post(f'/dispatch/delete/{pid}').status_code == 200


def test_parcel_search_is_scoped(client_for, make_parcel):
    tn, _ = make_parcel(sender_name='Zebra-Unique')
    hit = client_for('manager_a').get('/api/parcels/search?q=Zebra-Unique').get_json()
    miss = client_for('manager_c').get('/api/parcels/search?q=Zebra-Unique').get_json()
    assert [p['tracking_number'] for p in hit] == [tn]
    assert miss == []


def test_pushpak_booking_requires_ownership(client_for, make_parcel):
    _, pid = make_parcel()
    assert client_for('manager_c').post(f'/api/pushpak/book/{pid}').status_code == 403
    assert client_for('manager_c').post(f'/api/pushpak/pickup/{pid}').status_code == 403


def test_pushpak_tracking_only_for_known_dockets(app):
    r = app.test_client().get('/api/pushpak/track/NO-SUCH-DOCKET')
    assert r.status_code == 404


def test_stats_endpoints_are_admin_or_own_branch(client_for, ids):
    c = client_for('manager_a')
    assert c.get('/api/dashboard/stats').status_code == 403
    assert c.get('/api/dashboard/chart-data').status_code == 403
    assert c.get(f"/api/stats/branch/{ids['branch']['A']}").status_code == 200
    assert c.get(f"/api/stats/branch/{ids['branch']['B']}").status_code == 403
