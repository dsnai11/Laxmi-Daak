"""A parcel that is still in transit must never be hidden from All Parcels by the archive flag."""
from app import db
from app.models.parcel import Parcel, unarchive_active_parcels


def scan(client, tn, action):
    return client.post('/scan/process', json={'tracking_number': tn, 'action': action})


def test_delivered_parcel_moves_to_archive_not_all_parcels(client_for, make_parcel, ids):
    tn, _ = make_parcel()
    assert scan(client_for('manager_b'), tn, 'delivered').status_code == 200
    admin = client_for('admin')
    assert tn not in admin.get('/dispatch/list').get_data(as_text=True)
    assert tn in admin.get('/dispatch/archive').get_data(as_text=True)


def test_rescanning_a_delivered_parcel_brings_it_back_to_all_parcels(client_for, make_parcel, ids):
    tn, _ = make_parcel()
    scan(client_for('manager_b'), tn, 'delivered')                      # delivered + archived
    assert scan(client_for('manager_c'), tn, 'received').status_code == 200   # forwarded onwards
    admin = client_for('admin')
    page = admin.get(f'/dispatch/list?search={tn}').get_data(as_text=True)
    assert tn in page                                                     # visible again
    assert tn not in admin.get('/dispatch/archive').get_data(as_text=True)


def test_startup_repair_unarchives_parcels_that_are_still_active(app, make_parcel):
    tn, pid = make_parcel(status='in_transit')
    done, did = make_parcel(status='delivered')
    with app.app_context():
        for i in (pid, did):
            p = db.session.get(Parcel, i)
            p.is_archived = True
        db.session.commit()
        assert unarchive_active_parcels() >= 1
        assert db.session.get(Parcel, pid).is_archived is False
        assert db.session.get(Parcel, did).is_archived is True           # delivered stays archived
        assert unarchive_active_parcels() == 0                            # idempotent
