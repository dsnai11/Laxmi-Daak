import qrcode
import os
from flask import current_app

def generate_qr_code(tracking_number, base_url):
    qr_folder = os.path.join(current_app.root_path, 'static', 'qr')
    if not os.path.exists(qr_folder):
        os.makedirs(qr_folder)
        
    qr_path = os.path.join(qr_folder, f'{tracking_number}.png')
    tracking_url = f'{base_url}/track/{tracking_number}'
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(tracking_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1a1a2e", back_color="white")
    img.save(qr_path)
    
    return {
        'qr_path': f'/static/qr/{tracking_number}.png',
        'tracking_url': tracking_url
    }

def qr_exists(tracking_number):
    qr_path = os.path.join(current_app.root_path, 'static', 'qr', f'{tracking_number}.png')
    return os.path.exists(qr_path)

def delete_qr(tracking_number):
    qr_path = os.path.join(current_app.root_path, 'static', 'qr', f'{tracking_number}.png')
    if os.path.exists(qr_path):
        os.remove(qr_path)
