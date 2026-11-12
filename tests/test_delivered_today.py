"""The "Delivered Today" card and the list it opens must agree."""
import re
from datetime import datetime, timedelta

from app import db
from app.models.parcel import Parcel
from app.utils import ist_today_start


def _deliver(app, pid, when):
    with app.app_context():
        p = db.session.get(Parcel, pid)
        p.status = 'delivered'
        p.delivered_at = when
        p.is_archived = True            # delivery archives the parcel automatically
        db.session.commit()


def _card_count(page):
    m = re.search(r'Delivered Today</h3>\s*<p[^>]*>(\d+)</p>', page)
    return int(m.group(1)) if m else None


def test_ist_day_starts_at_0530_utc(monkeypatch):
    import app.utils as utils

    class Fixed(datetime):
        @classmethod
        def utcnow(cls):
            return cls(2026, 11, 12, 3, 0, 0)       # 08:30 IST on 12 Nov

    monkeypatch.setattr(utils, 'datetime', Fixed)
    assert utils.ist_today_start() == datetime(2026, 11, 11, 18, 30, 0)   # 12 Nov 00:00 IST


def test_admin_card_count_matches_the_list_it_opens(app, client_for, make_parcel):
    admin = client_for('admin')
    before = _card_count(admin.get('/dashboard/admin').get_data(as_text=True))
    ids_today = [make_parcel()[1] for _ in range(3)]
    for pid in ids_today:
        _deliver(app, pid, datetime.utcnow())
    old, old_id = make_parcel()
    _deliver(app, old_id, ist_today_start() - timedelta(hours=1))          # delivered yesterday

    page = admin.get('/dashboard/admin').get_data(as_text=True)
    assert _card_count(page) == before + 3
    assert "filter=delivered_today" in page                                  # the card links to the right list

    listing = admin.get('/dispatch/list?filter=delivered_today').get_data(as_text=True)
    shown = set(re.findall(r'CRR-TEST-\d+', listing))                         # each parcel appears several times
    assert len(shown) == before + 3                                          # list rows == card count
    assert old not in listing


def test_delivered_status_filter_shows_archived_delivered_parcels(app, client_for, make_parcel):
    tn, pid = make_parcel()
    _deliver(app, pid, datetime.utcnow() - timedelta(days=5))
    admin = client_for('admin')
    assert tn in admin.get('/dispatch/list?status=delivered').get_data(as_text=True)
    assert tn not in admin.get('/dispatch/list').get_data(as_text=True)     # default list still hides archived


def test_do_card_and_list_only_count_their_own_scope(app, client_for, make_parcel, ids):
    mine, mine_id = make_parcel(created_by=ids['user']['manager_c'], sender_branch_id=ids['branch']['C'],
                                receiver_branch_id=ids['branch']['B'], current_branch_id=ids['branch']['C'])
    other, other_id = make_parcel(created_by=ids['user']['manager_a'])       # A -> B, nothing to do with C
    _deliver(app, mine_id, datetime.utcnow())
    _deliver(app, other_id, datetime.utcnow())
    c = client_for('manager_c')
    listing = c.get('/dispatch/list?filter=delivered_today').get_data(as_text=True)
    assert mine in listing and other not in listing
