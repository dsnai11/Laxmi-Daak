import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from flask import current_app
import threading
import time
from datetime import date

import email.utils
import logging

# Configure dedicated email logger
logger = logging.getLogger('email_service')
logger.setLevel(logging.INFO)

def send_email_sync(to_email, subject, html_body, sender_email=None, app_config=None):
    """Synchronous SMTP email delivery with full RFC compliance and error handling."""
    if not to_email or not to_email.strip():
        print("[EMAIL] Skipping email send: recipient email is empty.")
        return False

    to_email = to_email.strip()
    config = app_config or (current_app.config if current_app else {})
    
    mail_server = config.get('MAIL_SERVER')
    mail_port = int(config.get('MAIL_PORT', 587))
    mail_user = config.get('MAIL_USERNAME')
    mail_pass = config.get('MAIL_PASSWORD')
    default_sender = config.get('MAIL_DEFAULT_SENDER', mail_user)

    if not mail_server or not mail_user:
        print(f"[EMAIL ERROR] MAIL_SERVER or MAIL_USERNAME is not configured in environment.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = default_sender
        msg['To'] = to_email
        msg['Date'] = email.utils.formatdate(localtime=True)
        sender_domain = 'lifc.in'
        if default_sender and '@' in default_sender:
            sender_domain = default_sender.split('@')[1]
        msg['Message-ID'] = email.utils.make_msgid(domain=sender_domain)
        if sender_email:
            msg['Reply-To'] = sender_email.strip()

        part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(part)

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        if config.get('MAIL_USE_SSL', False) or mail_port == 465:
            server = smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=20)
            server.ehlo()
        else:
            server = smtplib.SMTP(mail_server, mail_port, timeout=20)
            server.ehlo()
            if config.get('MAIL_USE_TLS', True):
                server.starttls(context=context)
                server.ehlo()

        server.login(mail_user, mail_pass)
        server.sendmail(default_sender, [to_email], msg.as_string(unixfrom=False))
        server.quit()
        print(f"[EMAIL SUCCESS] Mail delivered to {to_email} | Subject: '{subject}'")
        return True
    except Exception as e:
        import traceback
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")
        traceback.print_exc()
        return False

from concurrent.futures import ThreadPoolExecutor

email_executor = ThreadPoolExecutor(max_workers=5)

def send_email(to_email, subject, html_body, sender_email=None, async_send=True):
    """Sends email asynchronously using a persistent ThreadPoolExecutor or synchronously."""
    if not to_email:
        return True

    if async_send and current_app:
        app_config = dict(current_app.config)
        email_executor.submit(send_email_sync, to_email, subject, html_body, sender_email, app_config)
        return True
    else:
        return send_email_sync(to_email, subject, html_body, sender_email)

def send_dispatch_notification(receiver_email, receiver_name, tracking_number, sender_name, company_name, base_url, sender_email=None):
    subject = f"Your file is on the way - {tracking_number}"
    body = f"""
    <html>
      <body>
        <h2>Hello {receiver_name},</h2>
        <p>A file has been dispatched to you by {sender_name} via {company_name}.</p>
        <p>Your tracking number is: <strong>{tracking_number}</strong></p>
        <p>You can track your file here: <a href="{base_url}/track/{tracking_number}">Track File</a></p>
        <br>
        <p>Thank you,</p>
        <p>{company_name}</p>
      </body>
    </html>
    """
    return send_email(receiver_email, subject, body, sender_email=sender_email)

def get_dispatch_receiver_email_data(receiver_email, receiver_name, tracking_number, sender_name, sender_branch, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id=None):
    """Builds email data dictionary for receiver notification."""
    if not receiver_email or not receiver_email.strip():
        return None
        
    courier_display = None
    is_courier = (transfer_mode and 'courier' in transfer_mode.lower()) or courier_partner or courier_id
    if is_courier:
        if courier_partner and courier_id:
            courier_display = f"{courier_partner} / {courier_id}"
        else:
            courier_display = courier_partner or courier_id or "Standard"
            
    subject = f"Parcel Dispatched to You - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#0d1b2a" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; font-weight:bold; color:#ffffff; font-family:Arial, sans-serif;">Incoming Parcel Notification</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#94a3b8; font-family:Arial, sans-serif;">{company_name}</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello <strong>{receiver_name}</strong>,</p>
              <p>A new parcel has been successfully dispatched to your branch (<strong>{receiver_branch}</strong>) from <strong>{sender_branch}</strong>.</p>
              
              <!-- Data Table Box -->
              <table width="100%" border="0" cellspacing="0" cellpadding="12" bgcolor="#f8fafc" style="margin: 20px 0; border-left: 4px solid #4f8ef7; border-radius:4px;">
                <tr>
                  <td>
                    <table width="100%" border="0" cellspacing="0" cellpadding="4" style="font-size:14px; font-family:Arial, sans-serif;">
                      <tr>
                        <td width="35%" style="color:#64748b; font-weight:bold;">Tracking Number:</td>
                        <td width="65%" style="color:#0f172a; font-weight:bold;">{tracking_number}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">From Branch:</td>
                        <td style="color:#0f172a;">{sender_branch}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Destination Branch:</td>
                        <td style="color:#0f172a;">{receiver_branch}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Transfer Mode:</td>
                        <td style="color:#0f172a;">{transfer_mode}</td>
                      </tr>
                      {"<tr><td style='color:#64748b; font-weight:bold;'>Courier / Docket No:</td><td style='color:#0f172a;'>" + str(courier_display) + "</td></tr>" if courier_display else ""}
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Button CTA -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 25px 0;">
                <tr>
                  <td align="center">
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" bgcolor="#4f8ef7" style="border-radius:6px;">
                          <a href="{base_url}/track/{tracking_number}" target="_blank" style="font-size:14px; font-family:Arial, sans-serif; color:#ffffff; text-decoration:none; padding:12px 24px; display:inline-block; font-weight:bold; border-radius:6px;">Track Live Parcel Status</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;">
              <p style="margin:0; font-size:12px; color:#94a3b8; text-align:center;">This is an automated notification from {company_name}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return {'to_email': receiver_email.strip(), 'subject': subject, 'body': body}

def send_dispatch_receiver_notification(receiver_email, receiver_name, tracking_number, sender_name, sender_branch, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id=None):
    """Sends email strictly to the receiver informing that a parcel is dispatched to them."""
    data = get_dispatch_receiver_email_data(receiver_email, receiver_name, tracking_number, sender_name, sender_branch, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id)
    if not data:
        return False
    return send_email(data['to_email'], data['subject'], data['body'])

def get_dispatch_sender_email_data(sender_email, sender_name, tracking_number, receiver_name, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id=None):
    """Builds email data dictionary for sender confirmation."""
    if not sender_email or not sender_email.strip():
        return None
        
    courier_display = None
    is_courier = (transfer_mode and 'courier' in transfer_mode.lower()) or courier_partner or courier_id
    if is_courier:
        if courier_partner and courier_id:
            courier_display = f"{courier_partner} / {courier_id}"
        else:
            courier_display = courier_partner or courier_id or "Standard"
            
    subject = f"Parcel Dispatch Confirmation - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#0d1b2a" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; font-weight:bold; color:#ffffff; font-family:Arial, sans-serif;">Dispatch Successful</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#94a3b8; font-family:Arial, sans-serif;">{company_name}</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello <strong>{sender_name}</strong>,</p>
              <p>Your parcel has been successfully registered and dispatched to <strong>{receiver_name}</strong> (Branch: <strong>{receiver_branch}</strong>).</p>
              
              <!-- Data Table Box -->
              <table width="100%" border="0" cellspacing="0" cellpadding="12" bgcolor="#f8fafc" style="margin: 20px 0; border-left: 4px solid #10b981; border-radius:4px;">
                <tr>
                  <td>
                    <table width="100%" border="0" cellspacing="0" cellpadding="4" style="font-size:14px; font-family:Arial, sans-serif;">
                      <tr>
                        <td width="35%" style="color:#64748b; font-weight:bold;">Tracking Number:</td>
                        <td width="65%" style="color:#0f172a; font-weight:bold;">{tracking_number}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Recipient Name:</td>
                        <td style="color:#0f172a;">{receiver_name}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Destination Branch:</td>
                        <td style="color:#0f172a;">{receiver_branch}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Transfer Mode:</td>
                        <td style="color:#0f172a;">{transfer_mode}</td>
                      </tr>
                      {"<tr><td style='color:#64748b; font-weight:bold;'>Courier / Docket No:</td><td style='color:#0f172a;'>" + str(courier_display) + "</td></tr>" if courier_display else ""}
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Button CTA -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 25px 0;">
                <tr>
                  <td align="center">
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" bgcolor="#10b981" style="border-radius:6px;">
                          <a href="{base_url}/track/{tracking_number}" target="_blank" style="font-size:14px; font-family:Arial, sans-serif; color:#ffffff; text-decoration:none; padding:12px 24px; display:inline-block; font-weight:bold; border-radius:6px;">View Tracking Details</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;">
              <p style="margin:0; font-size:12px; color:#94a3b8; text-align:center;">This is an automated notification from {company_name}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return {'to_email': sender_email.strip(), 'subject': subject, 'body': body}

def send_dispatch_sender_confirmation(sender_email, sender_name, tracking_number, receiver_name, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id=None):
    """Sends email strictly to the sender confirming their parcel dispatch."""
    data = get_dispatch_sender_email_data(sender_email, sender_name, tracking_number, receiver_name, receiver_branch, transfer_mode, courier_partner, company_name, base_url, courier_id)
    if not data:
        return False
    return send_email(data['to_email'], data['subject'], data['body'])

def send_bulk_dispatch_emails_background(email_items, app_config):
    """
    Sends bulk dispatch emails in a dedicated background daemon thread using a persistent,
    reused SMTP connection with retry. Does not block the HTTP request, does not leak
    memory, and delivers hundreds of notifications smoothly in seconds.
    """
    if not email_items or not app_config:
        return

    def _worker():
        mail_server = app_config.get('MAIL_SERVER')
        mail_port = int(app_config.get('MAIL_PORT', 587))
        mail_user = app_config.get('MAIL_USERNAME')
        mail_pass = app_config.get('MAIL_PASSWORD')
        default_sender = app_config.get('MAIL_DEFAULT_SENDER', mail_user)
        use_ssl = app_config.get('MAIL_USE_SSL', False) or mail_port == 465
        use_tls = app_config.get('MAIL_USE_TLS', True)

        if not mail_server or not mail_user:
            print("[BULK EMAIL] SMTP configuration missing, skipping bulk send.")
            return

        print(f"[BULK EMAIL] Starting background delivery of {len(email_items)} emails...")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        def _connect():
            try:
                if use_ssl:
                    s = smtplib.SMTP_SSL(mail_server, mail_port, context=context, timeout=20)
                    s.ehlo()
                else:
                    s = smtplib.SMTP(mail_server, mail_port, timeout=20)
                    s.ehlo()
                    if use_tls:
                        s.starttls(context=context)
                        s.ehlo()
                s.login(mail_user, mail_pass)
                return s
            except Exception as e:
                print(f"[BULK EMAIL ERROR] SMTP connect error: {e}")
                return None

        server = _connect()
        sent_count = 0

        for item in email_items:
            to_email = item.get('to_email')
            if not to_email or '@' not in to_email:
                continue

            subject = item.get('subject', 'Parcel Notification')
            html_body = item.get('body', '')
            reply_to = item.get('reply_to')

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = default_sender
            msg['To'] = to_email.strip()
            msg['Date'] = email.utils.formatdate(localtime=True)
            sender_domain = 'lifc.in'
            if default_sender and '@' in default_sender:
                sender_domain = default_sender.split('@')[1]
            msg['Message-ID'] = email.utils.make_msgid(domain=sender_domain)
            if reply_to:
                msg['Reply-To'] = reply_to.strip()
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            # Send with retry on dropped connection
            for attempt in range(2):
                if server is None:
                    server = _connect()
                if server is None:
                    break
                try:
                    server.sendmail(default_sender, [to_email.strip()], msg.as_string(unixfrom=False))
                    sent_count += 1
                    break
                except Exception as e:
                    print(f"[BULK EMAIL] Connection dropped on {to_email}, reconnecting: {e}")
                    try:
                        server.quit()
                    except Exception:
                        pass
                    server = None
                    time.sleep(1)

        if server:
            try:
                server.quit()
            except Exception:
                pass
        print(f"[BULK EMAIL COMPLETE] Delivered {sent_count}/{len(email_items)} emails successfully.")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

def send_arrival_notification(receiver_email, receiver_name, tracking_number, branch_name, company_name, base_url):
    subject = f"Parcel Arrived at Branch - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; border:1px solid #e2e8f0;">
          <tr>
            <td bgcolor="#0d1b2a" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; color:#ffffff;">Parcel Arrived at Branch</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#94a3b8;">{company_name}</p>
            </td>
          </tr>
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello <strong>{receiver_name}</strong>,</p>
              <p>Your parcel (Tracking: <strong>{tracking_number}</strong>) has arrived at our <strong>{branch_name}</strong> branch.</p>
              <p>It will be out for delivery soon.</p>
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 20px 0;">
                <tr>
                  <td align="center">
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" bgcolor="#4f8ef7" style="border-radius:6px;">
                          <a href="{base_url}/track/{tracking_number}" target="_blank" style="font-size:14px; font-family:Arial, sans-serif; color:#ffffff; text-decoration:none; padding:12px 24px; display:inline-block; font-weight:bold; border-radius:6px;">Track Parcel</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;">
              <p style="margin:0; font-size:12px; color:#94a3b8; text-align:center;">This is an automated notification from {company_name}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return send_email(receiver_email, subject, body)

def send_delivery_notification(sender_email, receiver_email, tracking_number, receiver_name, company_name, base_url):
    subject = f"Parcel Delivered Successfully - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family: Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9; padding: 30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background: linear-gradient(135deg, #10b981, #059669); padding: 28px 32px; text-align:center;">
          <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:bold;">&#9989; Parcel Delivered!</h1>
          <p style="margin:6px 0 0; color:rgba(255,255,255,0.85); font-size:14px;">{company_name}</p>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding: 28px 32px;">
          <p style="color:#0f172a; font-size:16px; margin:0 0 16px;">Dear <strong>{receiver_name}</strong>,</p>
          <p style="color:#334155; font-size:14px; line-height:1.6; margin:0 0 20px;">
            Great news! Your parcel has been <strong>successfully delivered</strong>. Below are the delivery details:
          </p>
          <!-- Details Table -->
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0; margin-bottom:24px;">
            <tr style="border-bottom:1px solid #e2e8f0;">
              <td width="40%" style="padding:12px 16px; color:#64748b; font-weight:bold; font-size:13px;">Tracking Number</td>
              <td width="60%" style="padding:12px 16px; color:#0f172a; font-weight:bold; font-size:13px;">{tracking_number}</td>
            </tr>
            <tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:12px 16px; color:#64748b; font-weight:bold; font-size:13px;">Delivered To</td>
              <td style="padding:12px 16px; color:#0f172a; font-size:13px;">{receiver_name}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px; color:#64748b; font-weight:bold; font-size:13px;">Status</td>
              <td style="padding:12px 16px; font-size:13px;"><span style="background:#dcfce7; color:#16a34a; padding:3px 10px; border-radius:12px; font-weight:bold;">Delivered</span></td>
            </tr>
          </table>
          <!-- CTA Button -->
          <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:8px 0 24px;">
            <a href="{base_url}/track/{tracking_number}" target="_blank"
               style="background: linear-gradient(135deg, #10b981, #059669); color:#ffffff; text-decoration:none; padding:13px 28px; border-radius:6px; font-size:14px; font-weight:bold; display:inline-block; box-shadow:0 4px 6px rgba(16,185,129,0.2);">
              View Tracking Details &#8594;
            </a>
          </td></tr></table>
          <p style="color:#64748b; font-size:13px; line-height:1.6;">Thank you for using {company_name}. If you have any questions, please contact us.</p>
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#f8fafc; padding:16px 32px; text-align:center; border-top:1px solid #e2e8f0;">
          <p style="margin:0; color:#94a3b8; font-size:12px;">&copy; {company_name}. This is an automated notification.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    success_receiver = send_email(receiver_email, subject, body) if receiver_email else False
    success_sender = send_email(sender_email, subject, body) if sender_email else False
    return success_receiver or success_sender

def send_failed_notification(sender_email, sender_name, tracking_number, company_name, base_url):
    subject = f"Delivery Attempt Failed - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0; padding:0; background-color:#f1f5f9; font-family: Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9; padding: 30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background: linear-gradient(135deg, #ef4444, #b91c1c); padding: 28px 32px; text-align:center;">
          <h1 style="margin:0; color:#ffffff; font-size:22px; font-weight:bold;">&#10060; Delivery Attempt Failed</h1>
          <p style="margin:6px 0 0; color:rgba(255,255,255,0.85); font-size:14px;">{company_name}</p>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding: 28px 32px;">
          <p style="color:#0f172a; font-size:16px; margin:0 0 16px;">Dear <strong>{sender_name}</strong>,</p>
          <p style="color:#334155; font-size:14px; line-height:1.6; margin:0 0 20px;">
            We attempted to deliver your parcel but the delivery <strong>could not be completed</strong>. 
            Our team will attempt re-delivery or contact you for further instructions.
          </p>
          <!-- Details Table -->
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff5f5; border-radius:8px; border:1px solid #fecaca; margin-bottom:24px;">
            <tr style="border-bottom:1px solid #fecaca;">
              <td width="40%" style="padding:12px 16px; color:#64748b; font-weight:bold; font-size:13px;">Tracking Number</td>
              <td width="60%" style="padding:12px 16px; color:#0f172a; font-weight:bold; font-size:13px;">{tracking_number}</td>
            </tr>
            <tr>
              <td style="padding:12px 16px; color:#64748b; font-weight:bold; font-size:13px;">Status</td>
              <td style="padding:12px 16px; font-size:13px;"><span style="background:#fee2e2; color:#b91c1c; padding:3px 10px; border-radius:12px; font-weight:bold;">Delivery Failed</span></td>
            </tr>
          </table>
          <!-- CTA Button -->
          <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:8px 0 24px;">
            <a href="{base_url}/track/{tracking_number}" target="_blank"
               style="background: linear-gradient(135deg, #ef4444, #b91c1c); color:#ffffff; text-decoration:none; padding:13px 28px; border-radius:6px; font-size:14px; font-weight:bold; display:inline-block; box-shadow:0 4px 6px rgba(239,68,68,0.2);">
              View Tracking Details &#8594;
            </a>
          </td></tr></table>
          <p style="color:#64748b; font-size:13px; line-height:1.6;">Please contact us if you need to reschedule or have any concerns.</p>
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#f8fafc; padding:16px 32px; text-align:center; border-top:1px solid #e2e8f0;">
          <p style="margin:0; color:#94a3b8; font-size:12px;">&copy; {company_name}. This is an automated notification.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return send_email(sender_email, subject, body)


def send_overdue_notification(parcel, base_url, company_name):
    subject = f"[OVERDUE ALERT] Parcel {parcel.tracking_number} is past due date"
    body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #fecaca;">
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#7f1d1d" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; font-weight:bold; color:#ffffff; font-family:Arial, sans-serif;">⚠️ Overdue Parcel Alert</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#fca5a5; font-family:Arial, sans-serif;">{company_name}</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello,</p>
              <p>This is an automated notification to inform you that the parcel registered under tracking number <strong>{parcel.tracking_number}</strong> has passed its expected delivery due date and is still pending delivery.</p>
              
              <!-- Data Table Box -->
              <table width="100%" border="0" cellspacing="0" cellpadding="12" bgcolor="#fff5f5" style="margin: 20px 0; border-left: 4px solid #ef4444; border-radius:4px;">
                <tr>
                  <td>
                    <table width="100%" border="0" cellspacing="0" cellpadding="4" style="font-size:14px; font-family:Arial, sans-serif;">
                      <tr>
                        <td width="35%" style="color:#7f1d1d; font-weight:bold;">Tracking Number:</td>
                        <td width="65%" style="color:#0f172a; font-weight:bold;">{parcel.tracking_number}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Sender Name:</td>
                        <td style="color:#0f172a;">{parcel.sender_name}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Receiver Name:</td>
                        <td style="color:#0f172a;">{parcel.receiver_name}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Expected Due Date:</td>
                        <td style="color:#ef4444; font-weight:bold;">{parcel.due_date.strftime('%d %b %Y') if parcel.due_date else 'N/A'}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Current Status:</td>
                        <td style="color:#0f172a;">{parcel.status_label}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
              
              <p>Please click the button below to view the current tracking status and detail logs:</p>
              
              <!-- Button CTA -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 24px 0 10px 0;">
                <tr>
                  <td align="center">
                    <a href="{base_url}/track/{parcel.tracking_number}" target="_blank" style="background: linear-gradient(135deg, #ef4444, #b91c1c); color: #ffffff; text-decoration: none; padding: 12px 30px; border-radius: 6px; font-size: 15px; font-weight: bold; display: inline-block; box-shadow: 0 4px 6px rgba(239,68,68,0.2);">Track Parcel Status</a>
                  </td>
                </tr>
              </table>
              
              <p style="margin-bottom:0; margin-top:20px; font-size:13px; color:#64748b;">If you have any questions or require support, please contact the branch operations manager.</p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td bgcolor="#f8fafc" align="center" style="padding: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b;">
              &copy; {company_name} Operations. All rights reserved.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    success_receiver = True
    if parcel.receiver_email:
        success_receiver = send_email(parcel.receiver_email, subject, body, sender_email=parcel.sender_email)
        
    success_sender = True
    if parcel.sender_email:
        success_sender = send_email(parcel.sender_email, subject, body, sender_email=parcel.sender_email)
        
    return success_receiver or success_sender

def start_overdue_checker(app):
    def run_check():
        with app.app_context():
            # Wait 10 seconds after app startup before checking
            time.sleep(10)
            while True:
                try:
                    from app.models.parcel import Parcel
                    from app import db
                    
                    today = date.today()
                    # Fetch parcels where:
                    # 1. due_date is set and has passed (due_date < today)
                    # 2. status is not 'delivered' and not 'returned'
                    # 3. last_overdue_email_sent is NULL or < today (i.e. haven't received an overdue email today)
                    overdue_parcels = Parcel.query.filter(
                        Parcel.due_date != None,
                        Parcel.due_date < today,
                        ~Parcel.status.in_(['delivered', 'returned']),
                        (Parcel.last_overdue_email_sent == None) | (Parcel.last_overdue_email_sent < today)
                    ).all()
                    
                    if overdue_parcels:
                        print(f"[Overdue Checker] Found {len(overdue_parcels)} overdue parcels to notify today.")
                        for parcel in overdue_parcels:
                            try:
                                success = send_overdue_notification(
                                    parcel=parcel,
                                    base_url=app.config['BASE_URL'],
                                    company_name=app.config['COMPANY_NAME']
                                )
                                if success:
                                    parcel.overdue_email_sent = True
                                    parcel.last_overdue_email_sent = today
                                    db.session.commit()
                                    print(f"[Overdue Checker] Successfully sent daily overdue email for {parcel.tracking_number}")
                            except Exception as e:
                                print(f"[Overdue Checker] Failed to send email for {parcel.tracking_number}: {e}")
                except Exception as e:
                    print(f"[Overdue Checker] Error scanning database: {e}")
                
                # Sleep for 1 hour (3600 seconds) before scanning again
                time.sleep(3600)

    # Run as a daemon thread so it stops when main Flask process stops
    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()

def send_password_reset_email(to_email, name, reset_url, company_name):
    """Sends a professional, Outlook-compatible password reset email to a user."""
    if not to_email:
        return False
        
    subject = f"Password Reset Request - {company_name}"
    body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#0d1b2a" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; font-weight:bold; color:#ffffff; font-family:Arial, sans-serif;">Password Reset Request</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#94a3b8; font-family:Arial, sans-serif;">{company_name}</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello <strong>{name}</strong>,</p>
              <p>We received a request to reset your password for your Laxmi India Finance Ltd. account. If you did not make this request, you can safely ignore this email.</p>
              <p>To reset your password, please click the button below. This password reset link is valid for 1 hour.</p>
              
              <!-- Button CTA -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin: 25px 0;">
                <tr>
                  <td align="center">
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" bgcolor="#c21c1c" style="border-radius:6px;">
                          <a href="{reset_url}" target="_blank" style="font-size:14px; font-family:Arial, sans-serif; color:#ffffff; text-decoration:none; padding:12px 24px; display:inline-block; font-weight:bold; border-radius:6px;">Reset Password</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <p style="font-size: 12px; color: #64748b;">If the button doesn't work, copy and paste the following link into your web browser:</p>
              <p style="font-size: 12px; word-break: break-all; color: #4f8ef7;"><a href="{reset_url}" target="_blank" style="color: #4f8ef7; text-decoration: none;">{reset_url}</a></p>

              <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;">
              <p style="margin:0; font-size:12px; color:#94a3b8; text-align:center;">This is an automated notification from {company_name}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return send_email(to_email, subject, body, async_send=True)

def send_parcel_cancellation_notification(to_email, name, tracking_number, sender_name, sender_branch, receiver_name, receiver_branch, cancelled_by, company_name):
    """Sends a parcel cancellation email notification to sender/receiver."""
    if not to_email:
        return False
        
    subject = f"Parcel Cancelled / Removed - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f6f9; font-family:Arial, Helvetica, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" bgcolor="#f4f6f9">
    <tr>
      <td align="center" style="padding: 20px 10px;">
        <table width="600" border="0" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="max-width:600px; width:100%; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#ef4444" align="center" style="padding: 24px; color: #ffffff;">
              <h2 style="margin:0; font-size:22px; font-weight:bold; color:#ffffff; font-family:Arial, sans-serif;">Parcel Cancellation Notice</h2>
              <p style="margin:6px 0 0 0; font-size:13px; color:#fee2e2; font-family:Arial, sans-serif;">{company_name}</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 24px; color: #334155; font-size: 15px; line-height: 1.5;">
              <p style="margin-top:0;">Hello <strong>{name}</strong>,</p>
              <p>Please be informed that the parcel (Tracking Number: <strong>{tracking_number}</strong>) originally dispatched from <strong>{sender_branch}</strong> to <strong>{receiver_branch}</strong> has been <strong>cancelled and removed</strong> from the system by {cancelled_by}.</p>
              <p style="color: #64748b; font-size: 14px;">If this dispatch was sent in error, no further action is required as it has now been officially cancelled.</p>
              
              <!-- Data Table Box -->
              <table width="100%" border="0" cellspacing="0" cellpadding="12" bgcolor="#fef2f2" style="margin: 20px 0; border-left: 4px solid #ef4444; border-radius:4px;">
                <tr>
                  <td>
                    <table width="100%" border="0" cellspacing="0" cellpadding="4" style="font-size:14px; font-family:Arial, sans-serif;">
                      <tr>
                        <td width="35%" style="color:#64748b; font-weight:bold;">Tracking Number:</td>
                        <td width="65%" style="color:#991b1b; font-weight:bold;">{tracking_number}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">From Branch:</td>
                        <td style="color:#0f172a;">{sender_branch}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Destination Branch:</td>
                        <td style="color:#0f172a;">{receiver_branch}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Cancelled By:</td>
                        <td style="color:#0f172a;">{cancelled_by}</td>
                      </tr>
                      <tr>
                        <td style="color:#64748b; font-weight:bold;">Status:</td>
                        <td style="color:#ef4444; font-weight:bold;">CANCELLED / REMOVED</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;">
              <p style="margin:0; font-size:12px; color:#94a3b8; text-align:center;">This is an automated notification from {company_name}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return send_email(to_email, subject, body, async_send=True)


def send_query_raised_notification(sender_email, sender_name, tracking_number, receiver_name, receiver_branch, company_name):
    """Notify the sender that their dispatch query has been raised successfully."""
    if not sender_email or not sender_email.strip():
        return False
    subject = f"Dispatch Query Registered - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
  <div style="background-color: #0d1b2a; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0;">
    <h2 style="margin: 0; color: #ffffff;">Dispatch Request Registered</h2>
    <p style="margin: 5px 0 0 0; opacity: 0.8; color: #ffffff;">{company_name}</p>
  </div>
  <div style="padding: 20px;">
    <p>Hello <strong>{sender_name}</strong>,</p>
    <p>Your dispatch request (Query) has been registered successfully. The Admin department has been notified to pick up the physical courier from your location.</p>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background-color: #f8fafc; border-left: 4px solid #f59e0b;">
      <tr><td style="padding: 8px; font-weight: bold; width: 35%;">Tracking ID:</td><td style="padding: 8px;">{tracking_number}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Recipient Name:</td><td style="padding: 8px;">{receiver_name}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Destination Branch:</td><td style="padding: 8px;">{receiver_branch}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Status:</td><td style="padding: 8px; color: #d97706; font-weight: bold;">PENDING ADMIN PICKUP</td></tr>
    </table>
    <p>We will notify you once the courier has been dispatched by the Admin team.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated notification from {company_name}.</p>
  </div>
</body>
</html>"""
    return send_email(sender_email, subject, body, async_send=True)


def send_query_pickup_alert_to_admin(admin_email, sender_name, sender_department, sender_branch, tracking_number, company_name):
    """Notify the Admin team that a new dispatch query is pending collection from a department."""
    if not admin_email or not admin_email.strip():
        return False
    subject = f"NEW: Courier Pickup Request - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
  <div style="background-color: #f59e0b; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0;">
    <h2 style="margin: 0; color: #ffffff;">New Courier Pickup Request</h2>
    <p style="margin: 5px 0 0 0; opacity: 0.9; color: #ffffff;">{company_name}</p>
  </div>
  <div style="padding: 20px;">
    <p>Hello Admin Team,</p>
    <p>A new dispatch query has been raised by a department employee and is ready for physical pickup.</p>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background-color: #fffbeb; border-left: 4px solid #f59e0b;">
      <tr><td style="padding: 8px; font-weight: bold; width: 35%;">Tracking ID:</td><td style="padding: 8px; font-weight: bold;">{tracking_number}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Sender Name:</td><td style="padding: 8px;">{sender_name}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Sender Department:</td><td style="padding: 8px;">{sender_department}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Source Location:</td><td style="padding: 8px;">{sender_branch}</td></tr>
    </table>
    <p>Please collect the physical courier from the sender, update the weight/mode details, and confirm the dispatch in the Admin Panel.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated notification from {company_name}.</p>
  </div>
</body>
</html>"""
    return send_email(admin_email, subject, body, async_send=True)


def send_query_delivered_pending_notification(sender_email, sender_name, tracking_number, receiver_name, company_name, base_url):
    """Notify the sender that Admin team marked the parcel as delivered, prompting confirmation."""
    if not sender_email or not sender_email.strip():
        return False
    subject = f"Action Required: Confirm Delivery - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
  <div style="background-color: #10b981; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0;">
    <h2 style="margin: 0; color: #ffffff;">Confirm Delivery Receipt</h2>
    <p style="margin: 5px 0 0 0; opacity: 0.9; color: #ffffff;">{company_name}</p>
  </div>
  <div style="padding: 20px;">
    <p>Hello <strong>{sender_name}</strong>,</p>
    <p>The Admin team has followed up with the recipient and marked the parcel <strong>{tracking_number}</strong> as received by <strong>{receiver_name}</strong>.</p>
    <p>To officially close this query, please log into the dashboard and confirm the delivery receipt.</p>
    
    <div style="text-align: center; margin: 30px 0;">
      <a href="{base_url}/dispatch/queries" target="_blank" style="background-color: #10b981; color: white; padding: 12px 28px; text-decoration: none; font-weight: bold; border-radius: 6px; display: inline-block;">Confirm Delivery & Close Query</a>
    </div>

    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated notification from {company_name}.</p>
  </div>
</body>
</html>"""
    return send_email(sender_email, subject, body, async_send=True)


def send_query_closed_notification(sender_email, receiver_email, tracking_number, receiver_name, company_name):
    """Notify sender and receiver that the query is closed and confirmed."""
    subject = f"Dispatch Closed & Confirmed - {tracking_number}"
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
  <div style="background-color: #0d1b2a; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0;">
    <h2 style="margin: 0; color: #ffffff;">Dispatch Request Closed</h2>
    <p style="margin: 5px 0 0 0; opacity: 0.8; color: #ffffff;">{company_name}</p>
  </div>
  <div style="padding: 20px;">
    <p>Hello,</p>
    <p>The dispatch request for tracking number <strong>{tracking_number}</strong> has been successfully closed and confirmed by the sender.</p>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0; background-color: #f1f5f9; border-left: 4px solid #475569;">
      <tr><td style="padding: 8px; font-weight: bold; width: 35%;">Tracking ID:</td><td style="padding: 8px;">{tracking_number}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Recipient Name:</td><td style="padding: 8px;">{receiver_name}</td></tr>
      <tr><td style="padding: 8px; font-weight: bold;">Status:</td><td style="padding: 8px; color: #16a34a; font-weight: bold;">CLOSED & CONFIRMED</td></tr>
    </table>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated notification from {company_name}.</p>
  </div>
</body>
</html>"""
    if sender_email and sender_email.strip():
        send_email(sender_email, subject, body, async_send=True)
    if receiver_email and receiver_email.strip():
        send_email(receiver_email, subject, body, async_send=True)
    return True


def send_missing_fields_alert(sender_email, sender_name, tracking_number, missing_fields, company_name, base_url):
    """Sends a professional email reminder to the sender about missing details in their parcel dispatch."""
    subject = f"Missing Details Alert: Parcel {tracking_number} - Action Required"
    fields_list_html = "".join([f"<li style='margin-bottom: 6px;'><strong>{field}</strong></li>" for field in missing_fields])
    body = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
  <div style="background-color: #ef4444; color: white; padding: 20px; text-align: center; border-radius: 6px 6px 0 0;">
    <h2 style="margin: 0; color: #ffffff;">Missing Parcel Details Alert</h2>
    <p style="margin: 5px 0 0 0; opacity: 0.8; color: #ffffff;">{company_name}</p>
  </div>
  <div style="padding: 20px;">
    <p>Hello {sender_name},</p>
    <p>We noticed that you dispatched a parcel with tracking number <strong>{tracking_number}</strong> approximately 2 hours ago, but some mandatory/important fields were left blank or incomplete.</p>
    <p style="font-weight: bold; color: #ef4444;">Please fill in the following missing details:</p>
    <ul style="padding-left: 20px; color: #374151;">
      {fields_list_html}
    </ul>
    <p>You can update these details by logging into the system, finding your parcel, and clicking the <strong>✏️ Edit Dispatch</strong> button on the parcel detail page.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="{base_url}/dispatch/detail/{tracking_number}" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Update Details Now</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="font-size: 11px; color: #94a3b8; text-align: center;">This is an automated reminder from {company_name}.</p>
  </div>
</body>
</html>"""
    send_email(sender_email, subject, body, async_send=True)
    return True


def start_missing_fields_checker(app):
    """Periodically scans the database for active parcels created 2 hours ago with missing fields, sending alert emails to the sender."""
    def run_check():
        with app.app_context():
            # Wait 20 seconds after app startup
            time.sleep(20)
            while True:
                try:
                    from app.models.parcel import Parcel
                    from app import db
                    from datetime import datetime, timedelta

                    # We check for parcels created/dispatched more than 2 hours ago
                    # and less than 48 hours ago (to avoid notifying for very old parcels)
                    two_hours_ago = datetime.utcnow() - timedelta(hours=2)
                    forty_eight_hours_ago = datetime.utcnow() - timedelta(hours=48)
                    
                    parcels = Parcel.query.filter(
                        Parcel.dispatched_at != None,
                        Parcel.dispatched_at.between(forty_eight_hours_ago, two_hours_ago),
                        (Parcel.missing_fields_email_sent == False) | (Parcel.missing_fields_email_sent == None)
                    ).all()
                    
                    for parcel in parcels:
                        missing_fields = []
                        # Check transfer mode specific fields
                        if parcel.transfer_mode == 'by_bus':
                            if not parcel.bus_number or not parcel.bus_number.strip():
                                missing_fields.append("Bus Number")
                            if not parcel.driver_phone or not parcel.driver_phone.strip():
                                missing_fields.append("Driver Mobile Number")
                        elif parcel.transfer_mode == 'by_courier':
                            if not parcel.courier_partner or not parcel.courier_partner.strip():
                                missing_fields.append("Courier Partner Name")
                            if not parcel.courier_id or not parcel.courier_id.strip():
                                missing_fields.append("Docket/AWB Number")
                        elif parcel.transfer_mode == 'by_hand':
                            if not parcel.hand_carry_name or not parcel.hand_carry_name.strip():
                                missing_fields.append("Hand Carry Person Name")
                            if not parcel.hand_carry_phone or not parcel.hand_carry_phone.strip():
                                missing_fields.append("Hand Carry Person Phone")
                                
                        # Check general details
                        if not parcel.weight or parcel.weight == 0.0:
                            missing_fields.append("Weight (kg)")
                        if not parcel.description or not parcel.description.strip():
                            missing_fields.append("Package Description")
                        if not parcel.receiver_phone or not parcel.receiver_phone.strip():
                            missing_fields.append("Receiver Phone")
                        if not parcel.receiver_email or not parcel.receiver_email.strip():
                            missing_fields.append("Receiver Email")
                        if not parcel.receiver_address or not parcel.receiver_address.strip():
                            missing_fields.append("Receiver Address")
                            
                        # If there are missing fields and we have the sender's email
                        if missing_fields and parcel.sender_email:
                            print(f"[Missing Fields Checker] Parcel {parcel.tracking_number} has missing fields: {missing_fields}. Notifying sender {parcel.sender_email}")
                            try:
                                success = send_missing_fields_alert(
                                    sender_email=parcel.sender_email,
                                    sender_name=parcel.sender_name or "User",
                                    tracking_number=parcel.tracking_number,
                                    missing_fields=missing_fields,
                                    company_name=app.config['COMPANY_NAME'],
                                    base_url=app.config['BASE_URL']
                                )
                                if success:
                                    parcel.missing_fields_email_sent = True
                                    db.session.commit()
                            except Exception as e:
                                print(f"[Missing Fields Checker] Error notifying sender for {parcel.tracking_number}: {e}")
                                
                except Exception as e:
                    print(f"[Missing Fields Checker] Error scanning database: {e}")
                
                # Sleep for 15 minutes before scanning again (900 seconds)
                time.sleep(900)

    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()


