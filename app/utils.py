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
