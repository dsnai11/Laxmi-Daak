from datetime import datetime, timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def ist_today_start():
    """Start of today in India (IST), as the naive UTC datetime the database stores.

    All timestamps are saved in UTC. Counting "today" from UTC midnight (05:30 IST) put a
    parcel delivered early in the Indian morning into yesterday.
    """
    now_ist = datetime.utcnow() + IST_OFFSET
    return now_ist.replace(hour=0, minute=0, second=0, microsecond=0) - IST_OFFSET


def normalize_state_name(state_str):
    """Normalize state abbreviations and spelling variations to clean, full names."""
    if not state_str:
        return 'Default'
        
    val = state_str.strip().lower()
    if val in ['default', '']:
        return 'Default'
        
    mapping = {
        'rj': 'Rajasthan',
        'rajasthan': 'Rajasthan',
        'gj': 'Gujarat',
        'gujarat': 'Gujarat',
        'mp': 'Madhya Pradesh',
        'madhya pradesh': 'Madhya Pradesh',
        'up': 'Uttar Pradesh',
        'uttar pradesh': 'Uttar Pradesh',
        'mh': 'Maharastra',
        'maharashtra': 'Maharastra',
        'maharastra': 'Maharastra',
        'cg': 'Chhatisgarh',
        'chhatisgarh': 'Chhatisgarh',
        'chhattisgarh': 'Chhatisgarh'
    }
    return mapping.get(val, state_str.strip())
