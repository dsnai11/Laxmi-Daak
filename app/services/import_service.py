import bcrypt
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, PatternFill
from io import BytesIO

# ─────────────────────────────────────────
# Branch Import
# ─────────────────────────────────────────

def import_branches_from_excel(file_path):
    """Import branches from Excel file. Returns dict with success/failed/errors.
    
    Columns expected (row 1 = header):
        branch_code | name | city | state | address | phone | pincode | email
    
    Auto-creates a branch login user:
        Login ID  = branch_code (lowercase)
        Password  = pincode  (if provided, else 'Branch@123')
    """
    from app import db
    from app.models.branch import Branch
    from app.models.user import User

    results = {'success': 0, 'failed': 0, 'errors': [], 'credentials': []}

    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
    except Exception as e:
        results['errors'].append(f'Could not open file: {str(e)}')
        return results

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue

        try:
            from app.utils import normalize_state_name
            branch_code = str(row[0]).strip().upper()  if row[0] else ''
            name        = str(row[1]).strip()          if row[1] else ''
            city        = str(row[2]).strip()          if row[2] else ''
            state       = normalize_state_name(str(row[3]).strip() if row[3] else '')
            address     = str(row[4]).strip()          if row[4] else ''
            phone       = str(row[5]).strip()          if row[5] else ''
            pincode     = str(row[6]).strip()          if row[6] else ''
            email       = str(row[7]).strip()          if row[7] else ''

            if not branch_code or not name:
                results['failed'] += 1
                results['errors'].append(f'Row {row_idx}: branch_code and name are required')
                continue

            import re
            
            clean_name = re.sub(r'[^A-Za-z0-9]', '', name)
            branch_username = clean_name.capitalize()
            default_password = f"{branch_username}@{pincode}" if pincode else f"{branch_username}@123"

            # Upsert branch
            existing = Branch.query.filter_by(branch_code=branch_code).first()
            if existing:
                existing.name    = name
                existing.city    = city
                existing.state   = state
                existing.address = address
                existing.phone   = phone
                existing.email   = email
                if pincode:
                    existing.pincode = pincode
                branch_obj = existing
            else:
                branch_obj = Branch(
                    branch_code=branch_code, name=name, city=city,
                    state=state, address=address, phone=phone,
                    pincode=pincode, email=email
                )
                db.session.add(branch_obj)

            db.session.flush()  # get branch_obj.id

            # Upsert branch login user
            branch_user = User.query.filter_by(username=branch_username).first()
            if branch_user:
                branch_user.name      = name
                branch_user.branch_id = branch_obj.id
                if pincode:
                    branch_user.set_password(default_password)
            else:
                branch_user = User(
                    username=branch_username,
                    name=name,
                    email=email,
                    role='manager',
                    branch_id=branch_obj.id,
                    is_active=True
                )
                branch_user.set_password(default_password)
                db.session.add(branch_user)

            db.session.commit()
            results['success'] += 1
            results['credentials'].append({
                'branch': name,
                'login_id': branch_username,
                'password': default_password
            })

        except Exception as e:
            db.session.rollback()
            results['failed'] += 1
            results['errors'].append(f'Row {row_idx}: {str(e)}')

    return results


# ─────────────────────────────────────────
# Employee Import
# ─────────────────────────────────────────

def import_employees_from_excel(file_path):
    """Import employees from Excel file.
    
    Columns expected (row 1 = header):
        name | username (Login ID) | password | role | branch_code | email | phone | pincode
    
    Notes:
        - If 'pincode' column is filled, it OVERRIDES the 'password' column.
        - role must be 'manager' or 'employee' (defaults to 'employee')
    """
    from app import db
    from app.models.user import User
    from app.models.branch import Branch

    results = {'success': 0, 'failed': 0, 'errors': []}

    try:
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
    except Exception as e:
        results['errors'].append(f'Could not open file: {str(e)}')
        return results

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue

        try:
            name        = str(row[0]).strip()                    if row[0] else ''
            username    = str(row[1]).strip()                    if row[1] else ''
            password    = str(row[2]).strip()                    if row[2] else ''
            role        = str(row[3]).strip().lower()            if row[3] else 'employee'
            branch_code = str(row[4]).strip().upper()           if row[4] else ''
            email       = str(row[5]).strip()                    if row[5] else ''
            phone       = str(row[6]).strip()                    if row[6] else ''
            pincode     = str(row[7]).strip()                    if len(row) > 7 and row[7] else ''

            # Pincode overrides password if provided
            if pincode:
                password = pincode

            if not name or not username or not password:
                results['failed'] += 1
                results['errors'].append(f'Row {row_idx}: name, username and password (or pincode) are required')
                continue

            if role not in ['manager', 'employee']:
                role = 'employee'

            branch = Branch.query.filter_by(branch_code=branch_code).first() if branch_code else None

            existing = User.query.filter_by(username=username).first()
            if existing:
                existing.name  = name
                existing.role  = role
                existing.email = email
                existing.phone = phone
                if branch:
                    existing.branch_id   = branch.id
                    existing.branch_name = branch.name
                    existing.branch_code = branch.branch_code
                existing.set_password(password)
            else:
                user = User(
                    name=name, username=username, role=role,
                    email=email, phone=phone,
                    branch_id=branch.id if branch else None,
                    branch_name=branch.name if branch else '',
                    branch_code=branch.branch_code if branch else ''
                )
                user.set_password(password)
                db.session.add(user)

            db.session.commit()
            results['success'] += 1

        except Exception as e:
            db.session.rollback()
            results['failed'] += 1
            results['errors'].append(f'Row {row_idx}: {str(e)}')

    return results


# ─────────────────────────────────────────
# Template Generators
# ─────────────────────────────────────────

_HEADER_FONT  = Font(bold=True, color='FFFFFF', size=11)
_HEADER_FILL  = PatternFill('solid', fgColor='1E293B')   # dark slate
_PIN_FILL     = PatternFill('solid', fgColor='065F46')   # dark green — pincode highlight
_SAMPLE_FONT  = Font(color='6B7280', italic=True, size=10)
_SAMPLE_FILL  = PatternFill('solid', fgColor='F1F5F9')
_CENTER       = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _style_header(ws, headers, highlight_col=None):
    """Apply header styling to first row."""
    for i, cell in enumerate(ws[1], start=1):
        cell.font      = _HEADER_FONT
        cell.fill      = _PIN_FILL if highlight_col and i == highlight_col else _HEADER_FILL
        cell.alignment = _CENTER
        ws.column_dimensions[cell.column_letter].width = 20


def generate_branch_template():
    """Branch import template with pincode column.
    
    Columns: branch_code | name | city | state | address | phone | pincode | email
    Pincode column (col 7) is highlighted in green as it becomes the Login Password.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Branches'
    ws.row_dimensions[1].height = 28

    headers = [
        'branch_code *',
        'name *',
        'city *',
        'state *',
        'address',
        'phone',
        '🔑 pincode (= Login Password)',
        'email'
    ]
    ws.append(headers)
    _style_header(ws, headers, highlight_col=7)

    # Sample row
    sample = ['JPS001', 'Jaipur Branch', 'Jaipur', 'Rajasthan',
              'Station Road, Jaipur', '9876543210', '302001', 'jaipur@company.com']
    ws.append(sample)
    for cell in ws[2]:
        cell.font      = _SAMPLE_FONT
        cell.fill      = _SAMPLE_FILL
        cell.alignment = _CENTER

    # Note row
    ws.append([])
    ws.append(['ℹ️  NOTE:',
               'Login ID = Alphanumeric Title Case of Name. Password = LoginID@pincode value. '
               'If pincode left blank, default password = LoginID@123'])
    ws['A4'].font = Font(bold=True, color='1D4ED8')
    ws['B4'].font = Font(italic=True, color='1D4ED8')

    ws.column_dimensions['A'].width = 18
    ws.column_dimensions['B'].width = 22
    ws.column_dimensions['G'].width = 30
    return wb


def generate_employee_template():
    """Employee import template with optional pincode column.
    
    Columns: name | username | password | role | branch_code | email | phone | pincode
    If pincode is filled it OVERRIDES the password column.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Employees'
    ws.row_dimensions[1].height = 28

    headers = [
        'name *',
        'username (Login ID) *',
        'password',
        'role (manager/employee)',
        'branch_code',
        'email',
        'phone',
        '🔑 pincode (overrides password)'
    ]
    ws.append(headers)
    _style_header(ws, headers, highlight_col=8)

    # Sample row
    sample = ['Ram Sharma', 'ram.sharma', 'Ram@123', 'employee',
              'JPS001', 'ram@company.com', '9876500001', '']
    ws.append(sample)
    for cell in ws[2]:
        cell.font      = _SAMPLE_FONT
        cell.fill      = _SAMPLE_FILL
        cell.alignment = _CENTER

    ws.append([])
    ws.append(['ℹ️  NOTE:',
               'If pincode is filled, it will be used as password (overrides the password column). '
               'Role must be "manager" or "employee".'])
    ws['A4'].font = Font(bold=True, color='1D4ED8')
    ws['B4'].font = Font(italic=True, color='1D4ED8')

    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 24
    ws.column_dimensions['C'].width = 16
    ws.column_dimensions['D'].width = 22
    ws.column_dimensions['H'].width = 30
    return wb
