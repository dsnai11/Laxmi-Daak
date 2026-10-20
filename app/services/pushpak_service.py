import requests
import json
import os
from datetime import datetime
from flask import current_app


def _get_base_url():
    """Get Pushpak API base URL from config."""
    return current_app.config.get('PUSHPAK_API_BASE_URL', 'https://www.pushpakcourier.net/v3').rstrip('/')


def _get_scbf_id():
    """Get Pushpak sCBF_ID (Client Business ID) from config."""
    return current_app.config.get('PUSHPAK_SCBF_ID', '')


def _get_auth():
    """Get HTTP Basic Auth tuple if credentials are configured."""
    user = current_app.config.get('PUSHPAK_API_USER') or os.environ.get('PUSHPAK_API_USER', '')
    pwd = current_app.config.get('PUSHPAK_API_PASS') or os.environ.get('PUSHPAK_API_PASS', '')
    if user and pwd:
        return (user, pwd)
    return None


def _determine_doc_type(description):
    """Determine Doc_type from item description. D=Document, P=Parcel."""
    if not description:
        return 'P'
    desc_lower = description.lower()
    if 'document' in desc_lower or 'file' in desc_lower or 'letter' in desc_lower or 'stationery' in desc_lower:
        return 'D'
    return 'P'


def pushpak_booking_request(parcel):
    """Book a delivery with Pushpak Courier API.
    
    POST /deliverybookingrequest
    
    Args:
        parcel: Parcel SQLAlchemy model instance
    
    Returns:
        dict: {'success': bool, 'doc_no': str, 'message': str, 'raw_response': dict}
    """
    base_url = _get_base_url()
    scbf_id = _get_scbf_id()
    
    if not scbf_id:
        return {'success': False, 'doc_no': '', 'message': 'Pushpak sCBF_ID not configured. Please set PUSHPAK_SCBF_ID in environment variables.', 'raw_response': {}}
    
    # Convert weight from kg to the expected format
    weight_kg = parcel.weight if parcel.weight else 0.0
    
    payload = {
        'sCBF_ID': scbf_id,
        'Doc_No': parcel.tracking_number,
        'Ref_No': parcel.tracking_number,
        'Recipient_Name': (parcel.receiver_name or '')[:80],
        'Rec_Address': (parcel.receiver_address or '')[:100],
        'Rec_Contact': (parcel.receiver_phone or '')[:10],
        'Rec_Mobile': (parcel.receiver_phone or '')[:10],
        'Ref_No1': '',
        'Qty': 1,
        'Weight': str(weight_kg),
        'Doc_type': _determine_doc_type(parcel.description),
        'Sender_Name': (parcel.sender_name or '')[:80],
        'S_Address': (parcel.sender_address or '')[:100],
        'S_Mobile': (parcel.sender_phone or '')[:10],
        'Rate': str(parcel.billing_amount or 0),
        'category': 'N',  # N=Normal, default
    }
    
    # Set category based on priority
    if parcel.priority and parcel.priority.lower() in ('urgent', 'express'):
        payload['category'] = 'P'  # Premium
    
    try:
        auth = _get_auth()
        response = requests.post(
            f'{base_url}/deliverybookingrequest',
            json=payload,
            auth=auth,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        # Extract Doc_No from response
        doc_no = ''
        if isinstance(data, dict):
            doc_no = data.get('Doc_No', data.get('doc_no', data.get('DocNo', '')))
        
        return {
            'success': True,
            'doc_no': str(doc_no) if doc_no else parcel.tracking_number,
            'message': 'Booking request sent to Pushpak successfully.',
            'raw_response': data
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'doc_no': '', 'message': 'Pushpak API timeout. Please try again.', 'raw_response': {}}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'doc_no': '', 'message': 'Cannot connect to Pushpak API. Please check your internet connection.', 'raw_response': {}}
    except requests.exceptions.HTTPError as e:
        return {'success': False, 'doc_no': '', 'message': f'Pushpak API error: {e.response.status_code} - {e.response.text[:200]}', 'raw_response': {}}
    except Exception as e:
        return {'success': False, 'doc_no': '', 'message': f'Pushpak booking error: {str(e)}', 'raw_response': {}}


def pushpak_pickup_request(parcel):
    """Request a pickup from Pushpak Courier API.
    
    POST /pickuprequest
    
    Args:
        parcel: Parcel SQLAlchemy model instance
    
    Returns:
        dict: {'success': bool, 'message': str, 'raw_response': dict}
    """
    base_url = _get_base_url()
    scbf_id = _get_scbf_id()
    
    if not scbf_id:
        return {'success': False, 'message': 'Pushpak sCBF_ID not configured.', 'raw_response': {}}
    
    weight_kg = parcel.weight if parcel.weight else 0.0
    
    payload = {
        'sCBF_ID': scbf_id,
        'Doc_No': parcel.tracking_number,
        'Ref_No': parcel.tracking_number,
        'Recipient_Name': (parcel.receiver_name or '')[:80],
        'Rec_Address': (parcel.receiver_address or '')[:100],
        'Rec_Contact': (parcel.receiver_phone or '')[:10],
        'Rec_Mobile': (parcel.receiver_phone or '')[:10],
        'Qty': 1,
        'Weight': str(weight_kg),
        'Doc_type': _determine_doc_type(parcel.description),
        'Sender_Name': (parcel.sender_name or '')[:80],
        'S_Address': (parcel.sender_address or '')[:100],
        'S_Mobile': (parcel.sender_phone or '')[:10],
        'Rate': str(parcel.billing_amount or 0),
        'category': 'N',
        'Valuation': str(parcel.billing_amount or 0),
    }
    
    if parcel.priority and parcel.priority.lower() in ('urgent', 'express'):
        payload['category'] = 'P'
    
    try:
        auth = _get_auth()
        response = requests.post(
            f'{base_url}/pickuprequest',
            json=payload,
            auth=auth,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            'success': True,
            'message': 'Pickup request sent to Pushpak successfully.',
            'raw_response': data
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Pushpak API timeout.', 'raw_response': {}}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'message': 'Cannot connect to Pushpak API.', 'raw_response': {}}
    except requests.exceptions.HTTPError as e:
        return {'success': False, 'message': f'Pushpak API error: {e.response.status_code}', 'raw_response': {}}
    except Exception as e:
        return {'success': False, 'message': f'Pushpak pickup error: {str(e)}', 'raw_response': {}}


def pushpak_track_delivery(tracking_id):
    """Track a delivery via Pushpak Courier API.
    
    GET /trackdelivery/{trackid}
    
    Args:
        tracking_id: Pushpak docket/tracking number (courier_id)
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'category': str,
            'sender': dict,
            'recipient': dict,
            'transit_history': list,  # [{type, type_label, location, date, time, remarks}, ...]
            'pod_data': dict,  # {filename, rs_filename, delivered_to, relation, date}
            'raw_response': dict
        }
    """
    base_url = _get_base_url()
    
    if not tracking_id:
        return {'success': False, 'message': 'No tracking ID provided.', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}
    
    # IMR_Type mapping for transit events
    IMR_TYPE_LABELS = {
        '1': 'Received',
        '2': 'Dispatched',
        '3': 'Allotted',
        '4': 'Return',
        '5': 'Delivered'
    }
    
    IMR_TYPE_ICONS = {
        '1': '📦',
        '2': '🚚',
        '3': '📍',
        '4': '↩️',
        '5': '✅'
    }
    
    try:
        auth = _get_auth()
        response = requests.get(
            f'{base_url}/trackdelivery/{tracking_id}',
            auth=auth,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return {'success': False, 'message': 'No tracking data found for this ID.', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}
        
        # Pushpak API response format: {"code": 0, "error": false, "message": "...", "data": {...}}
        # Extract inner data dict if present
        if isinstance(data, dict) and 'data' in data and isinstance(data['data'], dict):
            raw_top = data
            tracking_data = data['data']
            # Check top-level error first
            if raw_top.get('error') or raw_top.get('code') == 1:
                err_msg = raw_top.get('message') or 'Consignment not found on Pushpak'
                return {
                    'success': False,
                    'message': err_msg,
                    'transit_history': [],
                    'pod_data': {},
                    'raw_response': raw_top
                }
        else:
            # Handle both single object and array responses (legacy fallback)
            tracking_data = data[0] if isinstance(data, list) else data
        
        # Check for error from Pushpak API response (e.g. {"code": 1, "error": true, "message": "Consignment not found"})
        if isinstance(tracking_data, dict) and (tracking_data.get('error') or tracking_data.get('code') == 1):
            err_msg = tracking_data.get('message') or 'Consignment not found on Pushpak'
            return {
                'success': False,
                'message': err_msg,
                'transit_history': [],
                'pod_data': {},
                'raw_response': tracking_data
            }
        
        # Parse transit history from TRAN_DATA
        # Real API field names: IMR_Type, TDate, UCBFFull_Name (full branch name), CBF_Name (current branch),
        #                        UCBF_Name (destination city), Remark
        transit_history = []
        tran_data = tracking_data.get('TRAN_DATA', [])
        if isinstance(tran_data, list):
            for event in tran_data:
                imr_type = str(event.get('IMR_Type', ''))
                # Location: prefer UCBFFull_Name (full branch), fallback to CBF_Name, then Location field
                location = (event.get('UCBFFull_Name') or event.get('CBF_Name') or
                            event.get('UCBF_Name') or event.get('Location') or event.get('location') or '')
                # Date & Time: TDate contains "YYYY-MM-DD HH:MM:SS"
                tdate_raw = event.get('TDate') or event.get('Date') or event.get('date') or ''
                if tdate_raw and ' ' in tdate_raw:
                    date_part, time_part = tdate_raw.split(' ', 1)
                else:
                    date_part = tdate_raw
                    time_part = event.get('Time') or event.get('time') or ''
                # Remarks
                remark = event.get('Remark') or event.get('Remarks') or event.get('remarks') or ''
                transit_history.append({
                    'type': imr_type,
                    'type_label': IMR_TYPE_LABELS.get(imr_type, 'Unknown'),
                    'type_icon': IMR_TYPE_ICONS.get(imr_type, '📋'),
                    'location': location,
                    'date': date_part,
                    'time': time_part,
                    'remarks': remark,
                })
        
        # Parse POD data
        pod_data = {}
        pod_list = tracking_data.get('POD_DATA', [])
        if isinstance(pod_list, list) and len(pod_list) > 0:
            pod = pod_list[0] if isinstance(pod_list[0], dict) else {}
            pod_data = {
                'filename': pod.get('POD_FileName', ''),
                'rs_filename': pod.get('RS_FileName', ''),
                'delivered_to': pod.get('Delivered_To', pod.get('delivered_to', '')),
                'relation': pod.get('Relation', pod.get('relation', '')),
                'date': pod.get('Date', pod.get('date', '')),
            }
        elif isinstance(pod_list, dict):
            pod_data = {
                'filename': pod_list.get('POD_FileName', ''),
                'rs_filename': pod_list.get('RS_FileName', ''),
                'delivered_to': pod_list.get('Delivered_To', ''),
                'relation': pod_list.get('Relation', ''),
                'date': pod_list.get('Date', ''),
            }
        
        result = {
            'success': True,
            'message': 'Tracking data fetched successfully.',
            'category': tracking_data.get('Category', ''),
            'sender': {
                'name': tracking_data.get('Sender_Name', tracking_data.get('sender_name', '')),
                'address': tracking_data.get('Sender_Address', tracking_data.get('S_Address', tracking_data.get('s_address', ''))),
                'mobile': tracking_data.get('Sender_Mobile', tracking_data.get('S_Mobile', tracking_data.get('s_mobile', ''))),
            },
            'recipient': {
                'name': tracking_data.get('Recipient_Name', tracking_data.get('recipient_name', '')),
                'address': tracking_data.get('Rec_Address', tracking_data.get('rec_address', '')),
                'mobile': tracking_data.get('Rec_Mobile', tracking_data.get('rec_mobile', '')),
            },
            'transit_history': transit_history,
            'pod_data': pod_data,
            'raw_response': tracking_data
        }
        
        return result
        
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Pushpak tracking API timeout.', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'message': 'Cannot connect to Pushpak API.', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}
    except requests.exceptions.HTTPError as e:
        return {'success': False, 'message': f'Pushpak tracking error: {e.response.status_code}', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}
    except Exception as e:
        return {'success': False, 'message': f'Pushpak tracking error: {str(e)}', 'transit_history': [], 'pod_data': {}, 'raw_response': {}}


def pushpak_search_pincode(pincode):
    """Search pin code via Pushpak Courier API.
    
    GET /search_pincode/{pincode}
    
    Args:
        pincode: 6-digit Indian pin code string
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': list/dict, 'raw_response': ...}
    """
    base_url = _get_base_url()
    
    if not pincode or len(str(pincode).strip()) != 6:
        return {'success': False, 'message': 'Invalid pincode. Must be 6 digits.', 'data': [], 'raw_response': {}}
    
    try:
        auth = _get_auth()
        response = requests.get(
            f'{base_url}/search_pincode/{pincode}',
            auth=auth,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            'success': True,
            'message': 'Pincode data fetched.',
            'data': data if isinstance(data, list) else [data] if data else [],
            'raw_response': data
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Pushpak pincode API timeout.', 'data': [], 'raw_response': {}}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'message': 'Cannot connect to Pushpak API.', 'data': [], 'raw_response': {}}
    except Exception as e:
        return {'success': False, 'message': f'Pincode search error: {str(e)}', 'data': [], 'raw_response': {}}
