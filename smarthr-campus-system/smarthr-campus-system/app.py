import os
import json
from fastapi import Response
import qrcode
import pandas as pd
import base64
import uuid
from datetime import datetime
from io import BytesIO
from flask import Flask, abort, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash
from flask_cors import CORS
from werkzeug.utils import secure_filename
import zipfile
import csv
from flask import send_file
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import ssl
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import folium
from folium import plugins
import networkx as nx
import json
import csv
import io
import secrets
from datetime import datetime, timedelta
import traceback
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
import zipfile

app = Flask(__name__)
app.secret_key = 'hr-conclave-2026-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['PROFILE_PHOTOS'] = 'static/profile_photos'  # Make sure this points to the same directory
CORS(app)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)
# Only create one directory since both point to the same location
os.makedirs(app.config['PROFILE_PHOTOS'], exist_ok=True)
os.makedirs('static/profile_photos', exist_ok=True)
# Email Configuration
EMAIL_CONFIG = {
    'SMTP_SERVER': 'smtp.gmail.com',
    'SMTP_PORT': 587,
    'EMAIL_USER': 'placements@sphoorthyengg.ac.in',  # Update with your email
    'EMAIL_PASSWORD': 'nrmp xrsx pqan zhrs',  # Update with your app password
    'FROM_NAME': 'HR Conclave 2026',
    'FROM_EMAIL': 'placements@sphoorthyengg.ac.in'
}

CONFIRMATION_CONFIG = {
    'status_pending': 'pending_review',
    'status_approved': 'approved',
    'status_rejected': 'rejected',
    'approval_days_limit': 3  # Admin has 3 days to review
}

# ================= DATABASE CONFIGURATION =================

DB_PATHS = {
    'hr_registrations': 'data/hr_registrations.json',  # Completed registrations
    'hr_pending_data': 'data/hr_pending_data.json',    # Uploaded but not invited yet
    'admins': 'data/admins.json',
    'events': 'data/events.json',
    'locations': 'data/locations.json',
    'paths': 'data/paths.json',
    'email_history': 'data/email_history.json'
}

def get_default_db(db_name):
    """Get default data structure for each database"""
    defaults = {
        'hr_registrations': {},  # Completed registrations
        'hr_pending_data': {},   # Uploaded HR data pending invitation
        
        'events': {
            'hr_conclave_2026': {
                'title': 'HR Conclave 2026 - Connecting the Future',
                'date': '2026-02-07',
                'venue': 'Sphoorthy Engineering College, Hyderabad',
                'description': (
                    'An industry-academia initiative bringing together senior HR professionals '
                    'to discuss talent transformation, leadership, and future workforce readiness.'
                ),
                'schedule': [
                    {'time': '09:00 AM - 10:00 AM', 'event': 'Check-in'},
                    {
                        'time': '10:00 AM - 10:20 AM',
                        'event': 'Inauguration (Lighting of Lamp & Classical Dance)'
                    },
                    {'time': '10:20 AM - 10:40 AM', 'event': 'Opening Session'},
                    {'time': '10:45 AM - 11:15 AM', 'event': 'Keynote Speakers'},
                    {'time': '11:15 AM - 11:20 AM', 'event': 'Break'},
                    {'time': '11:30 AM - 12:15 PM', 'event': 'Panel Discussion – 1'},
                    {'time': '12:15 PM - 01:00 PM', 'event': 'Awards & MOUs'},
                    {'time': '01:00 PM - 02:00 PM', 'event': 'Lunch Break'},
                    {'time': '02:00 PM - 02:45 PM', 'event': 'Panel Discussion – 2'},
                    {'time': '02:45 PM - 03:10 PM', 'event': 'Awards'},
                    {'time': '03:10 PM - 03:45 PM', 'event': 'Panel Discussion – 3'},
                    {'time': '03:50 PM - 04:15 PM', 'event': 'Awards'},
                    {'time': '04:30 PM - 04:45 PM', 'event': 'Vote of Thanks'},
                    {'time': '04:45 PM - 05:00 PM', 'event': 'Group Picture'}
                ],
                'contact': {
                    'tpo_name': 'Dr Hemanath Dussa',
                    'tpo_email': 'placements@sphoorthyengg.ac.in',
                    'marketing_heads': [
                        {
                            'name': 'Mahesh Bampalli',
                            'email': 'maheshbampalli@gmail.com',
                            'linkedin': 'https://www.linkedin.com/in/mahesh-bampalli-b35509324/'
                        },
                        {
                            'name': 'Laxmi Nivas Morishetty',
                            'email': 'morishettylaxminivas@gmail.com',
                            'linkedin': 'https://www.linkedin.com/in/laxmi-nivas-morishetty-02468m/'
                        }
                    ],
                    'college_linkedin': 'https://www.linkedin.com/in/sphoorthy-engineering-college/',
                    'phone': '+91-9121001921'
                }
            }
        },
        'locations': {},
        'paths': [],
        'email_history': {}
    }
    return defaults.get(db_name, {})

def load_db(db_name):
    """Load a specific database file"""
    filepath = DB_PATHS.get(db_name)
    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return get_default_db(db_name)
    return get_default_db(db_name)

def save_db(db_name, data):
    """Save data to a specific database file"""
    filepath = DB_PATHS.get(db_name)
    if filepath:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)



def log_email_history(hr_data, email_type, success, error_message=""):
    """Log email sending history"""
    try:
        email_history = load_db('email_history')
        email_id = f"EMAIL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hr_data.get('registration_id', 'NO_ID')}"

        email_history[email_id] = {
            'email_id': email_id,
            'registration_id': hr_data.get('registration_id', ''),
            'recipient': hr_data.get('office_email', ''),
            'recipient_name': hr_data.get('full_name', ''),
            'email_type': email_type,
            'status': 'sent' if success else 'failed',
            'error_message': error_message,
            'timestamp': datetime.now().isoformat(),
            'registration_status': hr_data.get('approval_status', 'pending_review')
        }

        save_db('email_history', email_history)
        print(f"✓ Email logged to history: {email_id}")
    except Exception as e:
        print(f"✗ Failed to log email history: {e}")

def generate_qr_for_registration(hr_data):
    """Generate and save QR code for registration"""
    try:
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr_string = f"HRC26|{hr_data.get('registration_id', '')}|{hr_data.get('full_name', '')}|{hr_data.get('office_email', '')}|{hr_data.get('organization', '')}"
        qr.add_data(qr_string)
        qr.make(fit=True)

        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")

        # Save to file
        qr_filename = f"HRC26_{hr_data.get('registration_id', 'NO_ID')}_QR.png"
        qr_path = os.path.join('static', 'qr_codes', qr_filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)

        qr_img.save(qr_path)
        print(f"✓ QR code saved to: {qr_path}")

        # Update HR registration with QR path
        hr_registrations = load_db('hr_registrations')
        reg_id = hr_data.get('registration_id', '')

        if reg_id and reg_id in hr_registrations:
            hr_registrations[reg_id]['qr_code_path'] = f"qr_codes/{qr_filename}"
            hr_registrations[reg_id]['qr_generated_at'] = datetime.now().isoformat()
            save_db('hr_registrations', hr_registrations)
            print(f"✓ QR path saved to registration record")

        return qr_path

    except Exception as e:
        print(f"✗ QR generation failed: {e}")
        return None


@app.route('/api/generate-registration-qr/<registration_id>')
def generate_registration_qr(registration_id):
    """Generate QR code for ANY registration status"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Find HR data
        hr_data = None
        reg_key = None

        # Try exact match
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
            reg_key = registration_id
        else:
            # Search by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    reg_key = hr_id
                    break

        if not hr_data:
            # For demo/testing, create basic data
            hr_data = {
                'registration_id': registration_id,
                'full_name': 'Test User',
                'office_email': 'test@example.com',
                'organization': 'Test Organization',
                'approval_status': 'pending_review'
            }

        # Use SIMPLE pipe-separated format for better scanning
        # Format: HRC26|REGISTRATION_ID|NAME|EMAIL|ORGANIZATION
        qr_string = f"HRC26|{hr_data.get('registration_id', registration_id)}|{hr_data.get('full_name', '')}|{hr_data.get('office_email', '')}|{hr_data.get('organization', '')}"

        print(f"Generating QR code with string: {qr_string}")

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)

        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        # Save QR code to database if real registration
        if reg_key and reg_key in hr_registrations:
            hr_registrations[reg_key]['registration_qr'] = img_str
            hr_registrations[reg_key]['qr_generated_at'] = datetime.now().isoformat()
            hr_registrations[reg_key]['qr_string'] = qr_string  # Store the QR string too
            save_db('hr_registrations', hr_registrations)

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'qr_string': qr_string,
            'registration_id': hr_data.get('registration_id', registration_id),
            'status': hr_data.get('approval_status', 'pending_review')
        })

    except Exception as e:
        print(f"Registration QR generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/simple-qr/<registration_id>')
def generate_simple_qr(registration_id):
    """Generate simple QR code - fallback endpoint"""
    try:
        # Simple QR code with just registration ID
        qr_string = f"HRC26|{registration_id}|REGISTRATION"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'registration_id': registration_id
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/email-logs')
def email_logs():
    """View email sending logs"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    # Load email history
    email_history = load_db('email_history')

    # Get recent emails
    recent_emails = []
    for email_id, email_data in sorted(email_history.items(),
                                      key=lambda x: x[1].get('timestamp', ''),
                                      reverse=True)[:50]:
        recent_emails.append(email_data)

    return render_template('admin_email_logs.html', emails=recent_emails)

def generate_event_schedule_pdf(hr_data):
    """Generate PDF schedule for HR professional"""
    try:
        event = get_event_data()

        # Create PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a56db'),
            alignment=1,
            spaceAfter=30
        )

        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#7e22ce'),
            spaceAfter=20
        )

        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=12
        )

        # Content
        content = []

        # Header
        content.append(Paragraph("HR Conclave 2026", title_style))
        content.append(Paragraph("Industry-Academia Initiative", subtitle_style))
        content.append(Paragraph("Connecting the Future", styles['Heading3']))
        content.append(Spacer(1, 20))

        # Personal Information
        content.append(Paragraph("Registration Details", subtitle_style))
        personal_data = [
            ['Registration ID:', hr_data['registration_id']],
            ['Name:', hr_data['full_name']],
            ['Organization:', hr_data['organization']],
            ['Designation:', hr_data['designation']],
            ['Email:', hr_data['office_email']],
            ['Mobile:', hr_data['mobile']]
        ]

        personal_table = Table(personal_data, colWidths=[150, 300])
        personal_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        content.append(personal_table)
        content.append(Spacer(1, 30))

        # Event Details
        content.append(Paragraph("Event Information", subtitle_style))
        event_info = [
            ['Date:', event.get('date', 'February 7, 2026')],
            ['Venue:', event.get('venue', 'Sphoorthy Engineering College, Hyderabad')],
            ['Time:', '9:00 AM - 5:00 PM'],
            ['Contact Email:', event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')],
            ['Contact Phone:', event.get('contact', {}).get('phone', '+91-9121001921')]
        ]

        event_table = Table(event_info, colWidths=[100, 350])
        event_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7e22ce')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d8b4fe'))
        ]))
        content.append(event_table)
        content.append(Spacer(1, 20))

        # Schedule
        content.append(Paragraph("Event Schedule", subtitle_style))
        schedule_data = [['Time', 'Activity']]
        for item in event.get('schedule', []):
            schedule_data.append([item.get('time', ''), item.get('event', '')])

        schedule_table = Table(schedule_data, colWidths=[100, 350])
        schedule_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecfdf5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#a7f3d0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
        ]))
        content.append(schedule_table)
        content.append(Spacer(1, 30))

        # Panel Interest (if any)
        if hr_data.get('panel_interest') == 'Yes':
            content.append(Paragraph("Panel Discussion Interest", subtitle_style))
            panel_info = [
                ['Panel Theme:', hr_data.get('panel_theme', '')],
                ['Expertise:', hr_data.get('panel_expertise', '')]
            ]
            panel_table = Table(panel_info, colWidths=[150, 300])
            content.append(panel_table)
            content.append(Spacer(1, 20))

        # Awards Interest
        if hr_data.get('award_interest'):
            content.append(Paragraph("Award Interest", subtitle_style))
            awards = hr_data['award_interest'].split(',')
            for award in awards:
                content.append(Paragraph(f"• {award.strip()}", normal_style))

        # Footer Note
        content.append(Spacer(1, 40))
        content.append(Paragraph("Important Notes:", styles['Heading4']))
        notes = [
            "1. Please bring this schedule and your government-issued ID for registration",
            "2. Parking is available near the main gate",
            "3. Wi-Fi credentials will be provided at the registration desk",
            "4. For any changes or queries, contact placements@sphoorthyengg.ac.in"
        ]
        for note in notes:
            content.append(Paragraph(note, normal_style))

        # Build PDF
        doc.build(content)

        # Save PDF to file
        pdf_filename = f"HRC26_{hr_data['registration_id']}_Schedule.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)

        with open(pdf_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())

        return pdf_path
    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        return None

# ==================== ROUTES ====================

@app.route('/')
def index():
    """Main landing page"""
    event = get_event_data()  # Use the new helper function

    hr_registrations = load_db('hr_registrations')

    # Statistics
    stats = {
        'total_registrations': len(hr_registrations),
        'confirmed_attendance': sum(1 for hr in hr_registrations.values()
                                   if hr.get('attendance') == 'Yes, I plan to attend'),
        'companies': len(set(hr.get('organization', '') for hr in hr_registrations.values())),
        'panel_participants': sum(1 for hr in hr_registrations.values()
                                 if hr.get('panel_interest') == 'Yes')
    }

    return render_template('index.html',
                         event=event,
                         stats=stats,
                         contact=event.get('contact', {}))

from PIL import Image
import io

@app.route('/admin/export-registrations-excel/<export_type>')
def export_registrations_excel(export_type):
    """Export registrations to Excel based on type"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    try:
        hr_registrations = load_db('hr_registrations')
        hr_pending_data = load_db('hr_pending_data')

        # Filter based on export type
        filtered_data = {}

        if export_type == 'registered':
            # Fully registered with HRC26 ID
            filtered_data = {k: v for k, v in hr_registrations.items()
                           if v.get('registration_id', '').startswith('HRC26') and 
                           v.get('status', '') == 'registered'}
            filename = 'registered_hr_data.xlsx'
            sheet_name = 'Registered HR'

        elif export_type == 'uploaded':
            # Data from hr_pending_data that's not registered
            filtered_data = hr_pending_data
            filename = 'uploaded_hr_data.xlsx'
            sheet_name = 'Uploaded HR'

        elif export_type == 'pending':
            # Data with pending invitation status
            filtered_data = {}
            for k, v in hr_pending_data.items():
                if v.get('status') == 'pending_invitation':
                    filtered_data[k] = v
            filename = 'pending_invitations.xlsx'
            sheet_name = 'Pending Invitations'

        else:  # 'all'
            # Combine both databases
            filtered_data = {**hr_registrations, **hr_pending_data}
            filename = 'all_hr_data.xlsx'
            sheet_name = 'All HR Data'

        if not filtered_data:
            # Create empty DataFrame with proper columns
            df = pd.DataFrame(columns=[
                'Registration ID', 'Name', 'Office Email', 'Personal Email',
                'Mobile', 'Organization', 'Designation', 'City', 'State',
                'Country', 'LinkedIn', 'Website', 'Panel Interest',
                'Panel Theme', 'Award Interest', 'Attendance', 'Source',
                'Status', 'Registration Date', 'Email Sent', 'Profile Photo',
                'Database Source'
            ])
        else:
            # Prepare data with proper formatting
            data = []
            for reg_id, hr in filtered_data.items():
                # Format mobile number
                mobile = str(hr.get('mobile', ''))
                if mobile and len(mobile) > 15:
                    mobile = mobile[:15]

                # Get registration ID (prefer registration_id field)
                reg_id_display = hr.get('registration_id', reg_id)
                
                # Determine status
                status = hr.get('status', '')
                if reg_id in hr_registrations and hr.get('registration_id', '').startswith('HRC26'):
                    status = 'Registered'
                elif hr.get('invitation_sent'):
                    status = 'Invitation Sent'
                elif hr.get('status') == 'pending_invitation':
                    status = 'Pending Invitation'
                elif hr.get('registration_complete'):
                    status = 'Completed Registration'
                
                # Determine database source
                db_source = 'Registrations' if reg_id in hr_registrations else 'Pending Data'
                
                # Format registration date
                reg_date = ''
                if hr.get('registered_at'):
                    reg_date = hr['registered_at'][:10] if len(hr['registered_at']) >= 10 else hr['registered_at']
                elif hr.get('uploaded_at'):
                    reg_date = hr['uploaded_at'][:10] if len(hr['uploaded_at']) >= 10 else hr['uploaded_at']
                
                # Format email sent status
                email_sent = 'Yes' if hr.get('email_sent') or hr.get('invitation_sent') else 'No'
                
                # Format profile photo status
                profile_photo = 'Yes' if hr.get('profile_photo') else 'No'

                data.append({
                    'Registration ID': reg_id_display,
                    'Name': hr.get('full_name', ''),
                    'Office Email': hr.get('office_email', ''),
                    'Personal Email': hr.get('personal_email', ''),
                    'Mobile': mobile,
                    'Organization': hr.get('organization', ''),
                    'Designation': hr.get('designation', ''),
                    'City': hr.get('city', ''),
                    'State': hr.get('state', ''),
                    'Country': hr.get('country', ''),
                    'LinkedIn': hr.get('linkedin', ''),
                    'Website': hr.get('website', ''),
                    'Panel Interest': hr.get('panel_interest', ''),
                    'Panel Theme': hr.get('panel_theme', ''),
                    'Award Interest': hr.get('award_interest', ''),
                    'Attendance': hr.get('attendance', ''),
                    'Source': hr.get('source', ''),
                    'Status': status,
                    'Registration Date': reg_date,
                    'Email Sent': email_sent,
                    'Profile Photo': profile_photo,
                    'Database Source': db_source
                })

            df = pd.DataFrame(data)

        # Create Excel file - IMPORTANT: Changed engine to 'xlsxwriter'
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Define formats for xlsxwriter
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#1a56db',
                'font_color': 'white',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'text_wrap': True
            })

            cell_format = workbook.add_format({
                'border': 1,
                'text_wrap': True,
                'valign': 'top',
                'font_size': 10
            })
            
            # Date format for xlsxwriter
            date_format = workbook.add_format({
                'num_format': 'yyyy-mm-dd',
                'border': 1,
                'valign': 'top',
                'font_size': 10
            })

            # Apply header format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Apply cell format to all data cells
            for row in range(1, len(df) + 1):
                for col in range(len(df.columns)):
                    cell_value = df.iat[row-1, col]
                    col_name = df.columns[col]
                    
                    # Apply date format for date columns
                    if col_name == 'Registration Date' and cell_value:
                        try:
                            # Try to parse date
                            if isinstance(cell_value, str):
                                worksheet.write(row, col, cell_value, date_format)
                            else:
                                worksheet.write(row, col, cell_value, cell_format)
                        except:
                            worksheet.write(row, col, cell_value, cell_format)
                    else:
                        worksheet.write(row, col, cell_value, cell_format)

            # Auto-adjust column widths
            for i, col in enumerate(df.columns):
                column_width = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                ) + 2
                # Limit maximum width
                column_width = min(column_width, 50)
                worksheet.set_column(i, i, column_width)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'hr_conclave_{filename}'
        )

    except Exception as e:
        print(f"Excel export error: {str(e)}")
        traceback.print_exc()
        flash(f'Error exporting Excel: {str(e)}', 'error')
        return redirect(url_for('admin_registrations'))
    

@app.route('/api/generate-qr/<registration_id>')
def generate_qr_code(registration_id):
    """Generate QR code for registration"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Find HR data
        hr_data = None
        reg_key = None

        # Try exact match
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
            reg_key = registration_id
        else:
            # Search by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    reg_key = hr_id
                    break

        if not hr_data:
            return jsonify({'success': False, 'error': 'Registration not found'})

        # QR code data - simple format for better scanning
        qr_data = {
            'id': hr_data.get('registration_id', reg_key),
            'name': hr_data.get('full_name', ''),
            'email': hr_data.get('office_email', ''),
            'org': hr_data.get('organization', ''),
            'type': 'HRC26'
        }

        # Convert to string format
        qr_string = f"HRC26|{qr_data['id']}|{qr_data['name']}|{qr_data['email']}|{qr_data['org']}"

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_string)
        qr.make(fit=True)

        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'registration_id': hr_data.get('registration_id', reg_key),
            'qr_string': qr_string
        })

    except Exception as e:
        print(f"QR generation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-qr/<registration_id>')
def get_qr_code(registration_id):
    """Get QR code for a registration"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Find HR data
        hr_data = None
        reg_key = None

        # Try exact match
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
            reg_key = registration_id
        else:
            # Search by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    reg_key = hr_id
                    break

        if not hr_data:
            return jsonify({'success': False, 'error': 'Registration not found'})

        # Check if QR code already exists in data
        if 'qr_code' in hr_data:
            return jsonify({
                'success': True,
                'qr_code': f"data:image/png;base64,{hr_data['qr_code']}",
                'registration_id': hr_data.get('registration_id', reg_key)
            })
        else:
            # Generate new QR code
            return generate_qr_code(registration_id)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/scan')
def admin_scan():
    """Admin QR scanning page - ADD AUTHENTICATION CHECK"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    return render_template('admin_scan.html')


@app.route('/api/scan-qr', methods=['POST'])
def scan_qr():
    """Process scanned QR code"""
    # Check if user is authenticated as admin
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({
            'success': False,
            'error': 'Unauthorized access. Please login as admin.'
        }), 401

    try:
        data = request.get_json()
        qr_data_str = data.get('qr_data', '')

        if not qr_data_str:
            return jsonify({'success': False, 'error': 'No QR data provided'})

        print(f"QR Data Received: {qr_data_str}")

        # Parse QR data - try multiple formats
        registration_id = None

        # Format 1: JSON format from our generated QR codes
        try:
            qr_data = json.loads(qr_data_str)
            if isinstance(qr_data, dict):
                registration_id = qr_data.get('registration_id') or qr_data.get('id')
                print(f"Found registration ID in JSON: {registration_id}")
        except json.JSONDecodeError:
            # Not JSON, try other formats
            pass

        # Format 2: Pipe-separated format (HRC26|REG_ID|...)
        if not registration_id and '|' in qr_data_str:
            parts = qr_data_str.split('|')
            if len(parts) >= 2:
                # Check if it's HRC26 format
                if parts[0] == 'HRC26':
                    registration_id = parts[1] if len(parts) > 1 else None
                else:
                    # Try to find HRC26 in any part
                    for part in parts:
                        if part.startswith('HRC26'):
                            registration_id = part
                            break
            print(f"Found registration ID in pipe format: {registration_id}")

        # Format 3: Try to extract any HRC26 ID from the string
        if not registration_id:
            import re
            # Look for HRC26 followed by alphanumeric characters
            hr_pattern = r'HRC26[A-Za-z0-9]+'
            matches = re.findall(hr_pattern, qr_data_str)
            if matches:
                registration_id = matches[0]
                print(f"Found registration ID via regex: {registration_id}")

        # Format 4: If it's a simple string that might be the ID itself
        if not registration_id and (qr_data_str.startswith('HRC26') or len(qr_data_str) >= 10):
            registration_id = qr_data_str
            print(f"Using raw string as registration ID: {registration_id}")

        if not registration_id:
            return jsonify({
                'success': False,
                'error': 'No registration ID found in QR code. QR content: ' + qr_data_str[:50] + '...'
            })

        # Clean up registration ID (remove quotes, whitespace)
        registration_id = registration_id.strip().strip('"').strip("'")
        print(f"Final registration ID: {registration_id}")

        # Load HR registrations
        hr_registrations = load_db('hr_registrations')

        # Try to find the registration
        hr_data = None
        reg_key = None

        # First try exact key match
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
            reg_key = registration_id
            print(f"Found by exact key match: {registration_id}")
        else:
            # Try to find by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    reg_key = hr_id
                    print(f"Found by registration_id field: {registration_id} -> {hr_id}")
                    break

        if not hr_data:
            # Search by name or email if ID not found
            for hr_id, hr in hr_registrations.items():
                if (hr.get('full_name', '').lower() in qr_data_str.lower() or
                    hr.get('office_email', '').lower() in qr_data_str.lower()):
                    hr_data = hr
                    reg_key = hr_id
                    print(f"Found by name/email match: {hr.get('full_name')}")
                    break

        if not hr_data:
            return jsonify({
                'success': False,
                'error': f'Registration not found for ID: {registration_id}'
            })

        # Check if already checked in
        if hr_data.get('attendance_status') == 'checked_in':
            last_time = hr_data.get('last_scanned_at', '')
            if last_time and len(last_time) >= 19:
                last_time = last_time[:19]
            return jsonify({
                'success': False,
                'error': f'{hr_data.get("full_name")} already checked in at {last_time}'
            })

        # Update attendance record
        attendance_record = {
            'scanned_at': datetime.now().isoformat(),
            'scanned_by': session.get('user_id', 'unknown'),
            'scanned_by_name': session.get('name', 'Admin'),
            'status': 'checked_in'
        }

        # Add to HR record
        if 'attendance_records' not in hr_data:
            hr_data['attendance_records'] = []

        hr_data['attendance_records'].append(attendance_record)
        hr_data['last_scanned_at'] = attendance_record['scanned_at']
        hr_data['attendance_status'] = 'checked_in'

        # Save updated data
        hr_registrations[reg_key] = hr_data
        save_db('hr_registrations', hr_registrations)

        # Create check-in history record
        checkin_history = load_db('checkin_history')
        checkin_id = f"CHECKIN_{datetime.now().strftime('%Y%m%d%H%M%S')}_{reg_key}"
        checkin_history[checkin_id] = {
            'checkin_id': checkin_id,
            'registration_id': reg_key,
            'hr_id': hr_data.get('registration_id', reg_key),
            'name': hr_data.get('full_name', ''),
            'organization': hr_data.get('organization', ''),
            'designation': hr_data.get('designation', ''),
            'email': hr_data.get('office_email', ''),
            'scanned_at': attendance_record['scanned_at'],
            'scanned_by': attendance_record['scanned_by'],
            'scanned_by_name': attendance_record['scanned_by_name'],
            'status': 'success'
        }
        save_db('checkin_history', checkin_history)

        print(f"✓ Check-in successful for: {hr_data.get('full_name')} ({reg_key})")

        return jsonify({
            'success': True,
            'message': 'Check-in successful!',
            'registration_id': reg_key,
            'hr_data': {
                'full_name': hr_data.get('full_name', ''),
                'organization': hr_data.get('organization', ''),
                'designation': hr_data.get('designation', ''),
                'email': hr_data.get('office_email', ''),
                'attendance_status': hr_data.get('attendance_status', 'pending'),
                'scanned_at': attendance_record['scanned_at'],
                'scanned_by': attendance_record['scanned_by_name']
            }
        })

    except Exception as e:
        print(f"✗ QR scanning error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check-attendance/<registration_id>')
def check_attendance_status(registration_id):
    """Check attendance status for a registration"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        # Try to find registration
        hr_data = None
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
        else:
            # Search by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    break

        if not hr_data:
            return jsonify({'success': False, 'error': 'Registration not found'})

        return jsonify({
            'success': True,
            'attendance_status': hr_data.get('attendance_status', 'not_checked_in'),
            'last_scanned_at': hr_data.get('last_scanned_at'),
            'attendance_records': hr_data.get('attendance_records', [])
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


import asyncio
import aiosmtplib
from concurrent.futures import ThreadPoolExecutor
import threading

# Optimized email sending function using threading
def send_bulk_email_fast(hr_list, email_template, attachments=None):
    """Send bulk emails using threading for parallel processing"""
    def send_single_email(hr_data, email_template, attachments):
        """Send single email - thread function"""
        try:
            if email_template == 'invitation':
                return send_invitation_email_v2(hr_data, generate_invitation_url(hr_data))
            else:  # reminder
                return send_reminder_email_v2(hr_data, generate_invitation_url(hr_data))
        except Exception as e:
            print(f"Error sending to {hr_data.get('office_email', 'unknown')}: {str(e)}")
            return False
    
    # Limit concurrent connections to avoid being flagged as spam
    max_workers = 5  # Adjust based on your SMTP server limits
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for hr_data in hr_list:
            future = executor.submit(send_single_email, hr_data, email_template, attachments)
            futures.append(future)
        
        results = []
        for future in futures:
            try:
                result = future.result(timeout=30)  # 30 seconds timeout per email
                results.append(result)
            except Exception as e:
                print(f"Thread error: {e}")
                results.append(False)
    
    return results

# Use connection pooling for SMTP
class EmailSenderPool:
    """Pool of SMTP connections for faster sending"""
    def __init__(self, max_connections=5):
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
    
    def get_connection(self):
        """Get or create SMTP connection"""
        with self.lock:
            if self.connections:
                return self.connections.pop()
            else:
                return self._create_connection()
    
    def _create_connection(self):
        """Create new SMTP connection"""
        context = ssl.create_default_context()
        server = smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT'])
        server.starttls(context=context)
        server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
        return server
    
    def release_connection(self, connection):
        """Return connection to pool"""
        with self.lock:
            if len(self.connections) < self.max_connections:
                self.connections.append(connection)
            else:
                connection.quit()
    
    def cleanup(self):
        """Cleanup all connections"""
        for conn in self.connections:
            try:
                conn.quit()
            except:
                pass
        self.connections.clear()

# Global email sender pool
email_pool = EmailSenderPool(max_connections=10)

def send_email_with_pool(to_email, subject, html_body, attachments=None):
    """Send email using connection pool"""
    connection = email_pool.get_connection()
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        # Add attachments if any (same as before)
        if attachments:
            for attachment in attachments[:3]:
                # ... attachment code ...
                pass
        
        connection.send_message(msg)
        return True
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        # Try to create new connection
        try:
            connection.quit()
        except:
            pass
        return False
    finally:
        email_pool.release_connection(connection)



@app.route('/admin/attendance')
def admin_attendance():
    """Attendance management dashboard - ADD AUTHENTICATION CHECK"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    hr_registrations = load_db('hr_registrations')
    checkin_history = load_db('checkin_history')

    # Calculate statistics
    total_registered = len(hr_registrations)
    checked_in = sum(1 for hr in hr_registrations.values()
                    if hr.get('attendance_status') == 'checked_in')
    pending_checkin = total_registered - checked_in

    # Get recent check-ins
    recent_checkins = []
    for checkin_id, checkin in sorted(checkin_history.items(),
                                     key=lambda x: x[1].get('scanned_at', ''),
                                     reverse=True)[:20]:
        recent_checkins.append(checkin)

    # Get all HR data with attendance status
    hr_attendance = []
    for hr_id, hr in hr_registrations.items():
        hr_attendance.append({
            'id': hr_id,
            'registration_id': hr.get('registration_id', hr_id),
            'full_name': hr.get('full_name', ''),
            'organization': hr.get('organization', ''),
            'designation': hr.get('designation', ''),
            'attendance_status': hr.get('attendance_status', 'not_checked_in'),
            'last_scanned_at': hr.get('last_scanned_at'),
            'attendance_records': hr.get('attendance_records', [])
        })

    # Sort by name
    hr_attendance.sort(key=lambda x: x['full_name'])

    return render_template('admin_attendance.html',
                         total_registered=total_registered,
                         checked_in=checked_in,
                         pending_checkin=pending_checkin,
                         recent_checkins=recent_checkins,
                         hr_attendance=hr_attendance)

# Add this to your initialization function
def initialize_databases():
    """Initialize all databases"""
    for db_name in DB_PATHS.keys():
        if not os.path.exists(DB_PATHS[db_name]):
            default_data = get_default_db(db_name)
            save_db(db_name, default_data)

    # Create checkin_history database if not exists
    checkin_history_path = 'data/checkin_history.json'
    if not os.path.exists(checkin_history_path):
        with open(checkin_history_path, 'w') as f:
            json.dump({}, f)


@app.route('/api/attendance-stats')
def get_attendance_stats():
    """Get attendance statistics - ADD AUTHENTICATION CHECK"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        hr_registrations = load_db('hr_registrations')
        checkin_history = load_db('checkin_history')

        print(f"Total HR registrations: {len(hr_registrations)}")
        print(f"Total checkin history entries: {len(checkin_history)}")

        # Total check-ins from checkin_history
        total_checkins = len(checkin_history)

        # Today's check-ins
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_checkins = 0

        # Method 1: Count from checkin_history
        for checkin_id, checkin in checkin_history.items():
            scanned_at = checkin.get('scanned_at', '')
            if scanned_at and scanned_at.startswith(today_str):
                today_checkins += 1

        print(f"Check-ins today: {today_checkins}")

        # Method 2: Also count from HR registrations (backup method)
        if today_checkins == 0:
            for hr_id, hr in hr_registrations.items():
                last_scanned = hr.get('last_scanned_at', '')
                if last_scanned and last_scanned.startswith(today_str):
                    today_checkins += 1
            print(f"Check-ins today (from HR registrations): {today_checkins}")

        return jsonify({
            'success': True,
            'total_checkins': total_checkins,
            'today_checkins': today_checkins,
            'total_registered': len(hr_registrations)
        })
    except Exception as e:
        print(f"Error in attendance stats: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/recent-checkins')
def get_recent_checkins():
    """Get recent check-ins"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        checkin_history = load_db('checkin_history')

        # Get recent check-ins (last 20)
        recent_checkins = []
        for checkin_id, checkin in sorted(checkin_history.items(),
                                         key=lambda x: x[1].get('scanned_at', ''),
                                         reverse=True)[:20]:
            recent_checkins.append({
                'id': checkin_id,
                'name': checkin.get('name', ''),
                'organization': checkin.get('organization', ''),
                'scanned_at': checkin.get('scanned_at', ''),
                'scanned_by': checkin.get('scanned_by', '')
            })

        return jsonify({
            'success': True,
            'checkins': recent_checkins
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/attendance-details/<attendee_id>')
def get_attendance_details(attendee_id):
    """Get detailed attendance info for an attendee"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        # Find attendee
        attendee = None
        if attendee_id in hr_registrations:
            attendee = hr_registrations[attendee_id]
            attendee['id'] = attendee_id
        else:
            # Search by registration_id
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == attendee_id:
                    attendee = hr
                    attendee['id'] = hr_id
                    break

        if not attendee:
            return jsonify({'success': False, 'error': 'Attendee not found'})

        return jsonify({
            'success': True,
            'attendee': attendee
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/manual-checkin/<attendee_id>', methods=['POST'])
def manual_checkin(attendee_id):
    """Manual check-in for an attendee"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        if attendee_id not in hr_registrations:
            return jsonify({'success': False, 'error': 'Attendee not found'})

        hr = hr_registrations[attendee_id]

        # Create check-in record
        checkin_record = {
            'scanned_at': datetime.now().isoformat(),
            'scanned_by': session.get('user_id', 'unknown'),
            'status': 'checked_in',
            'type': 'manual'
        }

        # Add to attendance records
        if 'attendance_records' not in hr:
            hr['attendance_records'] = []

        hr['attendance_records'].append(checkin_record)
        hr['last_scanned_at'] = checkin_record['scanned_at']
        hr['attendance_status'] = 'checked_in'

        # Save updated data
        hr_registrations[attendee_id] = hr
        save_db('hr_registrations', hr_registrations)

        # Add to check-in history
        checkin_history = load_db('checkin_history')
        checkin_id = f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{attendee_id}"
        checkin_history[checkin_id] = {
            'checkin_id': checkin_id,
            'registration_id': attendee_id,
            'hr_id': hr.get('registration_id', attendee_id),
            'name': hr.get('full_name', ''),
            'organization': hr.get('organization', ''),
            'scanned_at': checkin_record['scanned_at'],
            'scanned_by': checkin_record['scanned_by'],
            'status': 'success',
            'type': 'manual'
        }
        save_db('checkin_history', checkin_history)

        return jsonify({
            'success': True,
            'message': 'Manual check-in successful'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export-attendance')
def export_attendance_data():
    """Export attendance data to CSV"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    try:
        hr_registrations = load_db('hr_registrations')

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['Registration ID', 'Name', 'Organization', 'Designation',
                        'Email', 'Mobile', 'Attendance Status', 'Check-in Time',
                        'Check-in Count', 'Last Scanned By'])

        # Write data
        for reg_id, hr in hr_registrations.items():
            attendance_status = hr.get('attendance_status', 'not_checked_in')
            last_scanned = hr.get('last_scanned_at', '')
            checkin_count = len(hr.get('attendance_records', []))

            writer.writerow([
                hr.get('registration_id', reg_id),
                hr.get('full_name', ''),
                hr.get('organization', ''),
                hr.get('designation', ''),
                hr.get('office_email', ''),
                hr.get('mobile', ''),
                attendance_status,
                last_scanned[:19] if last_scanned else '',
                checkin_count,
                hr.get('attendance_records', [{}])[-1].get('scanned_by', '') if checkin_count > 0 else ''
            ])

        output.seek(0)

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=attendance_report.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/registration/<registration_id>')
def get_registration(registration_id):
    """Get registration details by ID"""
    try:
        hr_registrations = load_db('hr_registrations')
        hr_pending_data = load_db('hr_pending_data')

        # Search in both databases
        hr_data = None
        
        # First try registrations database
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
        else:
            # Search by registration_id field in registrations
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    break
            
            # If not found, try pending data
            if not hr_data and registration_id in hr_pending_data:
                hr_data = hr_pending_data[registration_id]
            elif not hr_data:
                # Search by ID field in pending data
                for hr_id, hr in hr_pending_data.items():
                    if hr.get('id') == registration_id:
                        hr_data = hr
                        break

        if not hr_data:
            return jsonify({'error': 'Registration not found'}), 404

        # Add database source info
        if registration_id in hr_registrations:
            hr_data['database_source'] = 'registrations'
        elif registration_id in hr_pending_data:
            hr_data['database_source'] = 'pending_data'
        else:
            hr_data['database_source'] = 'found_by_search'

        # Ensure consistent field names
        if 'full_name' not in hr_data and 'name' in hr_data:
            hr_data['full_name'] = hr_data['name']
        
        return jsonify(hr_data)

    except Exception as e:
        print(f"Error fetching registration: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/event-data')
def get_event_data_api():
    """Get event data for the thank you page"""
    try:
        event = get_event_data()

        # Format event data for the frontend
        event_response = {
            'date': event.get('date', 'February 7, 2026'),
            'time': '9:00 AM – 5:00 PM',
            'venue': event.get('venue', 'Sphoorthy Engineering College'),
            'location': 'Nadergul, Hyderabad',
            'contact': event.get('contact', {})
        }

        # Extract schedule times
        if 'schedule' in event and len(event['schedule']) > 0:
            times = []
            for item in event['schedule']:
                if 'time' in item:
                    times.append(item['time'])

            if times:
                event_response['time'] = f'{times[0]} – {times[-1]}'

        return jsonify(event_response)

    except Exception as e:
        print(f"Error fetching event data: {str(e)}")
        # Return default data
        return jsonify({
            'date': 'February 7, 2026',
            'time': '9:00 AM – 5:00 PM',
            'venue': 'Sphoorthy Engineering College',
            'location': 'Nadergul, Hyderabad',
            'contact': {
                'phone': '+91-9121001921',
                'tpo_email': 'placements@sphoorthyengg.ac.in',
                'tpo_name': 'Dr Hemanath Dussa - TPO'
            }
        })


# Add this function to update registration status
def update_registration_status(registration_id, status, admin_notes=""):
    """Update registration status and send appropriate emails"""
    try:
        hr_registrations = load_db('hr_registrations')

        if registration_id in hr_registrations:
            hr = hr_registrations[registration_id]

            # Update status
            hr['approval_status'] = status
            hr['approval_date'] = datetime.now().isoformat()
            hr['approval_admin'] = session.get('user_id', 'unknown')
            hr['admin_notes'] = admin_notes

            # Send appropriate email
            if status == 'approved':
                send_confirmation_approval_email(hr)
                hr['confirmation_email_sent'] = True
                hr['confirmation_sent_at'] = datetime.now().isoformat()
            elif status == 'rejected':
                send_rejection_email(hr, admin_notes)

            save_db('hr_registrations', hr_registrations)
            return True

        return False
    except Exception as e:
        print(f"Error updating registration status: {str(e)}")
        return False




@app.route('/admin/confirmations')
def admin_confirmations():
    """Admin confirmation panel - Only show completed registrations"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    hr_registrations = load_db('hr_registrations')

    # Categorize ONLY completed registrations (with HRC26 IDs)
    pending_review = []
    approved = []
    rejected = []

    for reg_id, hr in hr_registrations.items():
        # Check if this is a completed registration (has proper ID and registration status)
        registration_id = hr.get('registration_id', '')

        # Skip if not a proper registration (no registration ID or still pending)
        if not registration_id or not registration_id.startswith('HRC26'):
            continue  # Skip incomplete registrations

        # Check if registration is complete
        if hr.get('status') != 'registered':
            continue  # Skip if not fully registered

        status = hr.get('approval_status', 'pending_review')

        # Only process if it's a valid registration
        hr_copy = hr.copy()
        hr_copy['id'] = reg_id

        if status == 'pending_review':
            pending_review.append(hr_copy)
        elif status == 'approved':
            approved.append(hr_copy)
        elif status == 'rejected':
            rejected.append(hr_copy)

    # Also check for any registrations that might have registration_id but no approval_status
    for reg_id, hr in hr_registrations.items():
        registration_id = hr.get('registration_id', '')

        # If it has HRC26 ID but no approval status, it's pending review
        if (registration_id and registration_id.startswith('HRC26') and
            'approval_status' not in hr and hr.get('status') == 'registered'):

            hr_copy = hr.copy()
            hr_copy['id'] = reg_id
            hr_copy['approval_status'] = 'pending_review'
            pending_review.append(hr_copy)

    # Remove duplicates
    def remove_duplicates_by_id(hr_list):
        seen = set()
        unique_list = []
        for hr in hr_list:
            if hr['id'] not in seen:
                seen.add(hr['id'])
                unique_list.append(hr)
        return unique_list

    pending_review = remove_duplicates_by_id(pending_review)
    approved = remove_duplicates_by_id(approved)
    rejected = remove_duplicates_by_id(rejected)

    # Sort by registration date
    pending_review.sort(key=lambda x: x.get('registered_at', ''), reverse=True)
    approved.sort(key=lambda x: x.get('approval_date', ''), reverse=True)
    rejected.sort(key=lambda x: x.get('approval_date', ''), reverse=True)

    stats = {
        'total_pending': len(pending_review),
        'total_approved': len(approved),
        'total_rejected': len(rejected),
        'today_pending': sum(1 for hr in pending_review
                           if hr.get('registered_at', '').startswith(datetime.now().strftime('%Y-%m-%d')))
    }

    print(f"✓ Confirmation Panel Stats: {len(pending_review)} pending, {len(approved)} approved, {len(rejected)} rejected")

    return render_template('admin_confirmations.html',
                         pending_review=pending_review,
                         approved=approved,
                         rejected=rejected,
                         stats=stats)





@app.route('/admin/export-registrations-pdf/<export_type>')
def export_registrations_pdf(export_type):
    """Export registrations to PDF based on type"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    try:
        hr_registrations = load_db('hr_registrations')
        hr_pending_data = load_db('hr_pending_data')

        # Filter based on export type
        filtered_data = {}

        if export_type == 'registered':
            # Fully registered with HRC26 ID
            filtered_data = {k: v for k, v in hr_registrations.items()
                           if v.get('registration_id', '').startswith('HRC26') and 
                           v.get('status', '') == 'registered'}
            title = "Fully Registered HR Professionals"
            
        elif export_type == 'uploaded':
            # Data from hr_pending_data that's not invited yet
            filtered_data = hr_pending_data
            title = "Uploaded HR Data (Pending Invitation)"
            
        elif export_type == 'pending':
            # Data with pending invitation status
            filtered_data = {}
            for k, v in hr_pending_data.items():
                if v.get('status') == 'pending_invitation':
                    filtered_data[k] = v
            title = "Pending Invitations"
            
        else:  # 'all'
            # Combine both databases
            filtered_data = {**hr_registrations, **hr_pending_data}
            title = "All HR Data"

        if not filtered_data:
            # Create empty PDF with message
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            
            content = []
            content.append(Paragraph(f"HR Conclave 2026 - {title}", 
                                   styles['Heading1']))
            content.append(Paragraph(f"No data found for export type: {export_type}", 
                                   styles['Normal']))
            doc.build(content)
            pdf_buffer.seek(0)
            
            return send_file(
                pdf_buffer,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'hr_conclave_{export_type}_report_{datetime.now().strftime("%Y%m%d")}.pdf'
            )

        # Create PDF
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a56db'),
            alignment=1,
            spaceAfter=15
        )

        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            alignment=1,
            spaceAfter=20
        )

        small_style = ParagraphStyle(
            'SmallStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=10
        )

        # Content
        content = []

        # Header
        content.append(Paragraph("HR Conclave 2026", title_style))
        content.append(Paragraph(title, subtitle_style))
        content.append(Paragraph(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} by {session.get('name', 'Admin')}", 
                               styles['Normal']))
        content.append(Spacer(1, 15))

        # Summary
        summary_data = [
            ['Total Records', str(len(filtered_data))],
            ['Report Type', export_type.capitalize()],
            ['Generated By', session.get('name', 'Admin')],
            ['Generation Date', datetime.now().strftime('%Y-%m-%d %H:%M')]
        ]

        summary_table = Table(summary_data, colWidths=[150, 250])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc'))
        ]))
        content.append(summary_table)
        content.append(Spacer(1, 20))

        # Prepare table data
        table_data = [[
            Paragraph('Registration ID', small_style),
            Paragraph('Name', small_style),
            Paragraph('Organization', small_style),
            Paragraph('Email', small_style),
            Paragraph('Designation', small_style),
            Paragraph('Status', small_style),
            Paragraph('Date', small_style)
        ]]

        for reg_id, hr in filtered_data.items():
            # Get registration ID
            reg_id_display = hr.get('registration_id', reg_id)
            if len(reg_id_display) > 15:
                reg_id_display = reg_id_display[:12] + "..."

            # Get name
            name = hr.get('full_name', 'N/A')
            if len(name) > 20:
                name = name[:18] + "..."

            # Get organization
            org = hr.get('organization', 'N/A')
            if len(org) > 25:
                org = org[:23] + "..."

            # Get email
            email = hr.get('office_email', hr.get('email', 'N/A'))
            if len(email) > 25:
                email = email[:23] + "..."

            # Get designation
            designation = hr.get('designation', 'N/A')
            if len(designation) > 20:
                designation = designation[:18] + "..."

            # Get status
            status = hr.get('status', 'N/A')
            if hr.get('registration_id', '').startswith('HRC26'):
                status = 'Registered'
            elif hr.get('invitation_sent'):
                status = 'Invited'
            elif hr.get('status') == 'pending_invitation':
                status = 'Pending'
                
            if len(status) > 15:
                status = status[:13]

            # Get date
            reg_date = ''
            if hr.get('registered_at'):
                reg_date = hr['registered_at'][:10]
            elif hr.get('uploaded_at'):
                reg_date = hr['uploaded_at'][:10]

            table_data.append([
                Paragraph(reg_id_display, small_style),
                Paragraph(name, small_style),
                Paragraph(org, small_style),
                Paragraph(email, small_style),
                Paragraph(designation, small_style),
                Paragraph(status, small_style),
                Paragraph(reg_date, small_style)
            ])

        # Create table
        col_widths = [70, 70, 80, 90, 60, 50, 50]
        
        # Split data into pages if too many rows
        max_rows_per_page = 35
        total_rows = len(table_data) - 1
        
        if total_rows <= max_rows_per_page:
            # Single page
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            # Table style
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7e22ce')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
            ])
            
            table.setStyle(table_style)
            content.append(table)
        else:
            # Multiple pages
            num_pages = (total_rows + max_rows_per_page - 1) // max_rows_per_page
            
            for page_num in range(num_pages):
                start_idx = page_num * max_rows_per_page
                end_idx = min((page_num + 1) * max_rows_per_page, total_rows)
                
                page_data = [table_data[0]]  # Header
                page_data.extend(table_data[start_idx + 1:end_idx + 1])
                
                page_table = Table(page_data, colWidths=col_widths, repeatRows=1)
                page_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7e22ce')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
                ]))
                
                if page_num > 0:
                    content.append(PageBreak())
                    content.append(Paragraph(f"HR Conclave 2026 - {title} (Page {page_num + 1})", 
                                           styles['Heading2']))
                
                content.append(page_table)

        # Footer
        content.append(Spacer(1, 20))
        content.append(Paragraph("Confidential - HR Conclave 2026 Organizing Committee",
                                ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=1)))
        content.append(Paragraph(f"Page 1 of {max(1, num_pages)}",
                                ParagraphStyle('PageNumber', parent=styles['Normal'], fontSize=7, alignment=1)))

        # Build PDF
        doc.build(content)

        pdf_buffer.seek(0)

        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'hr_conclave_{export_type}_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        )

    except Exception as e:
        print(f"PDF export error: {str(e)}")
        flash(f'Error exporting PDF: {str(e)}', 'error')
        return redirect(url_for('admin_registrations'))
        
@app.route('/api/get-registration-qr/<registration_id>')
def get_registration_qr(registration_id):
    """Get QR code for a registration"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Find HR data
        hr_data = None
        for hr_id, hr in hr_registrations.items():
            if hr.get('registration_id') == registration_id or hr_id == registration_id:
                hr_data = hr
                break

        if not hr_data:
            return jsonify({'success': False, 'error': 'Registration not found'})

        # Generate QR code if not exists
        if 'qr_code' not in hr_data:
            # Generate QR code
            qr_string = f"HRC26|{hr_data.get('registration_id', '')}|{hr_data.get('full_name', '')}|{hr_data.get('office_email', '')}|{hr_data.get('organization', '')}"

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            # Save to database
            hr_data['qr_code'] = img_str
            hr_data['qr_string'] = qr_string
            hr_data['qr_generated_at'] = datetime.now().isoformat()

            hr_registrations[hr_id] = hr_data
            save_db('hr_registrations', hr_registrations)
        else:
            img_str = hr_data['qr_code']

        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'registration_id': hr_data.get('registration_id', ''),
            'full_name': hr_data.get('full_name', '')
        })

    except Exception as e:
        print(f"QR code error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/approve-registration/<registration_id>', methods=['POST'])
def approve_registration(registration_id):
    """Approve a registration"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        admin_notes = data.get('notes', '')

        if update_registration_status(registration_id, 'approved', admin_notes):
            return jsonify({
                'success': True,
                'message': 'Registration approved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Registration not found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/admin/reject-registration/<registration_id>', methods=['POST'])
def reject_registration(registration_id):
    """Reject a registration"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        admin_notes = data.get('notes', '')

        if update_registration_status(registration_id, 'rejected', admin_notes):
            return jsonify({
                'success': True,
                'message': 'Registration rejected'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Registration not found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/admin/bulk-approve', methods=['POST'])
def bulk_approve():
    """Bulk approve registrations"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        registration_ids = data.get('registration_ids', [])
        admin_notes = data.get('notes', 'Bulk approval')

        approved_count = 0
        failed = []

        for reg_id in registration_ids:
            if update_registration_status(reg_id, 'approved', admin_notes):
                approved_count += 1
            else:
                failed.append(reg_id)

        return jsonify({
            'success': True,
            'message': f'Approved {approved_count} registrations',
            'approved_count': approved_count,
            'failed': failed
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/admin/resend-confirmation/<registration_id>', methods=['POST'])
def resend_confirmation(registration_id):
    """Resend confirmation email"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        if registration_id in hr_registrations:
            hr = hr_registrations[registration_id]

            if send_confirmation_approval_email(hr):
                # Update timestamp
                hr['confirmation_email_sent'] = True
                hr['confirmation_sent_at'] = datetime.now().isoformat()
                hr['confirmation_resent'] = hr.get('confirmation_resent', 0) + 1

                save_db('hr_registrations', hr_registrations)

                return jsonify({
                    'success': True,
                    'message': 'Confirmation email resent successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to send email'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Registration not found'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/confirmation-stats')
def get_confirmation_stats():
    """Get confirmation statistics"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        stats = {
            'total_registered': len([hr for hr in hr_registrations.values() if hr.get('status') == 'registered']),
            'pending_review': len([hr for hr in hr_registrations.values() if hr.get('approval_status') == 'pending_review']),
            'approved': len([hr for hr in hr_registrations.values() if hr.get('approval_status') == 'approved']),
            'rejected': len([hr for hr in hr_registrations.values() if hr.get('approval_status') == 'rejected']),
            'confirmation_sent': len([hr for hr in hr_registrations.values() if hr.get('confirmation_email_sent')]),
            'awaiting_confirmation': len([hr for hr in hr_registrations.values()
                                         if hr.get('approval_status') == 'approved' and not hr.get('confirmation_email_sent')])
        }

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/registration/thank-you')
def registration_thank_you():
    """Thank you page route"""
    print("=== THANK YOU PAGE ACCESSED ===")

    # Get registration ID from session or query parameters
    registration_id = request.args.get('reg_id') or session.get('last_registration_id')

    print(f"Looking for registration ID: {registration_id}")

    if not registration_id:
        # Try to get from session registration data
        session_data = session.get('hr_registration', {})
        registration_id = session_data.get('registration_id')
        print(f"Got from session data: {registration_id}")

    # Get HR data
    hr_data = None
    if registration_id:
        hr_registrations = load_db('hr_registrations')
        print(f"Total registrations in DB: {len(hr_registrations)}")

        # Try exact match first
        if registration_id in hr_registrations:
            hr_data = hr_registrations[registration_id]
            print(f"Found by exact match: {registration_id}")
        else:
            # Search by registration_id field
            for hr_id, hr in hr_registrations.items():
                if hr.get('registration_id') == registration_id:
                    hr_data = hr
                    print(f"Found by registration_id field: {registration_id}")
                    break

        if not hr_data:
            print("Registration not found in database")
            hr_data = {
                'registration_id': registration_id,
                'full_name': session.get('hr_registration', {}).get('full_name', 'Guest'),
                'office_email': session.get('hr_registration', {}).get('office_email', ''),
                'organization': session.get('hr_registration', {}).get('organization', ''),
                'designation': session.get('hr_registration', {}).get('designation', ''),
                'attendance': session.get('hr_registration', {}).get('attendance', ''),
                'approval_status': 'pending_review'
            }
        else:
            # Ensure approval_status exists
            if 'approval_status' not in hr_data:
                # Default to pending_review for newly registered users
                hr_data['approval_status'] = 'pending_review'
                print(f"Set default approval_status: {hr_data['approval_status']}")
    else:
        hr_data = {}
        print("No registration ID found")

    event = get_event_data()

    print(f"Rendering thank you page for: {hr_data.get('full_name', 'Unknown')}")

    return render_template('registration_thankyou.html',
                         hr_data=hr_data,
                         event=event)


@app.route('/registration/clear')
def clear_registration():
    """Clear registration session data"""
    session.pop('hr_registration', None)
    return redirect(url_for('hr_registration'))

# ================= ADMIN ROUTES =================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        admins = load_db('admins')

        if username in admins:
            admin = admins[username]
            if admin['password'] == password:
                session['user_id'] = username
                session['role'] = 'admin'
                session['name'] = admin.get('name', 'Admin')
                return redirect(url_for('admin_dashboard'))

        return render_template('admin_login.html', error='Invalid credentials')

    return render_template('admin_login.html')


from datetime import datetime

@app.route('/admin/registrations')
def admin_registrations():
    """View all HR registrations"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    hr_registrations = load_db('hr_registrations')

    # Get current datetime
    current_datetime = datetime.now()

    return render_template('admin_registrations.html',
                         registrations=hr_registrations,
                         current_datetime=current_datetime)

# Add these routes and update existing ones

# Add the missing API routes first
@app.route('/api/statistics')
def get_statistics():
    """Get live statistics for the home page"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Calculate statistics
        total_registrations = len(hr_registrations)

        # Count unique companies
        companies = set()
        for hr in hr_registrations.values():
            org = hr.get('organization', '').strip()
            if org:
                companies.add(org)

        # Count panel participants
        panel_participants = sum(1 for hr in hr_registrations.values()
                               if hr.get('panel_interest') == 'Yes')

        # Count confirmed attendance
        confirmed_attendance = sum(1 for hr in hr_registrations.values()
                                  if hr.get('attendance') == 'Yes, I plan to attend')

        return jsonify({
            'total_registrations': total_registrations,
            'companies': len(companies),
            'panel_participants': panel_participants,
            'confirmed_attendance': confirmed_attendance
        })

    except Exception as e:
        print(f"Error calculating statistics: {str(e)}")
        return jsonify({
            'total_registrations': 145,
            'companies': 68,
            'panel_participants': 15,
            'confirmed_attendance': 127
        })



@app.route('/download/hr-upload-template')
def download_hr_upload_template():
    """Download HR upload template with required columns"""
    try:
        # Create sample data
        sample_data = {
            'organization': ['Tech Solutions Inc.', 'Global Corp', 'Innovate Labs'],
            'email': ['hr@techsolutions.com', 'contact@globalcorp.com', 'info@innovatelabs.com'],
            'full_name': ['John Smith', 'Sarah Johnson', 'Raj Kumar'],
            'mobile': ['+91-9876543210', '+91-9876543211', '+91-9876543212'],
            'designation': ['HR Manager', 'HR Director', 'Talent Lead'],
            'city': ['Hyderabad', 'Bangalore', 'Chennai'],
            'state': ['Telangana', 'Karnataka', 'Tamil Nadu'],
            'country': ['India', 'India', 'India']
        }
        
        # Create DataFrame
        df = pd.DataFrame(sample_data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Template', index=False)
            
            workbook = writer.book
            worksheet = writer.sheets['Template']
            
            # Define formats
            required_format = workbook.add_format({
                'bold': True,
                'bg_color': '#ef4444',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            optional_format = workbook.add_format({
                'bold': True,
                'bg_color': '#fbbf24',
                'font_color': 'black',
                'border': 1,
                'align': 'center'
            })
            
            # Apply formats based on column
            for col_num, column in enumerate(df.columns):
                if column in ['organization', 'email']:
                    worksheet.write(0, col_num, f"{column} (REQUIRED)", required_format)
                else:
                    worksheet.write(0, col_num, f"{column} (OPTIONAL)", optional_format)
            
            # Add instructions sheet
            instructions_data = [
                ['Column Name', 'Required/Optional', 'Description', 'Example'],
                ['organization', 'REQUIRED', 'Company/Organization name', 'Tech Solutions Inc.'],
                ['email', 'REQUIRED', 'Work email address', 'hr@company.com'],
                ['full_name', 'OPTIONAL', 'Full name (auto-generated if empty)', 'John Smith'],
                ['mobile', 'OPTIONAL', 'Mobile number', '+91-9876543210'],
                ['designation', 'OPTIONAL', 'Job title/designation', 'HR Manager'],
                ['city', 'OPTIONAL', 'City', 'Hyderabad'],
                ['state', 'OPTIONAL', 'State/Province', 'Telangana'],
                ['country', 'OPTIONAL', 'Country', 'India'],
                ['linkedin', 'OPTIONAL', 'LinkedIn profile URL', 'https://linkedin.com/in/johnsmith'],
                ['website', 'OPTIONAL', 'Company website', 'https://company.com']
            ]
            
            instructions_df = pd.DataFrame(instructions_data[1:], columns=instructions_data[0])
            instructions_df.to_excel(writer, sheet_name='Instructions', index=False)
            
            # Format instructions sheet
            instr_worksheet = writer.sheets['Instructions']
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#1a56db',
                'font_color': 'white',
                'border': 1
            })
            
            for col_num, value in enumerate(instructions_data[0]):
                instr_worksheet.write(0, col_num, value, header_format)
            
            # Auto-adjust column widths
            worksheet.set_column('A:H', 20)
            instr_worksheet.set_column('A:D', 25)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='hr_conclave_upload_template.xlsx'
        )
        
    except Exception as e:
        print(f"Template download error: {str(e)}")
        return "Error generating template", 500
    
@app.route('/api/hr-registrations')
def get_hr_registrations():
    """Get all HR registrations (for statistics fallback)"""
    try:
        hr_registrations = load_db('hr_registrations')
        return jsonify(hr_registrations)
    except Exception as e:
        print(f"Error fetching registrations: {str(e)}")
        return jsonify({})
   
def save_profile_photo(file, registration_id):
    """Save profile photo with registration ID as filename"""
    print(f"=== SAVING PROFILE PHOTO ===")
    print(f"File: {file.filename if file else 'No file'}")
    print(f"Registration ID: {registration_id}")

    if file and file.filename:
        # Create directories if they don't exist
        static_profile_dir = 'static/profile_photos'
        config_profile_dir = app.config['PROFILE_PHOTOS']

        # Check if directories are the same
        same_dir = os.path.abspath(static_profile_dir) == os.path.abspath(config_profile_dir)

        # Create directories
        os.makedirs(static_profile_dir, exist_ok=True)
        if not same_dir:
            os.makedirs(config_profile_dir, exist_ok=True)

        # Create secure filename
        ext = os.path.splitext(file.filename)[1].lower()
        # Ensure extension is valid
        if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
            ext = '.png'  # Default to PNG if invalid

        filename = f"{registration_id}{ext}"

        # Save to static/profile_photos directory
        filepath = os.path.join(static_profile_dir, filename)

        print(f"Saving to: {filepath}")

        try:
            # Save the file
            file.save(filepath)
            print(f"File saved successfully to: {filepath}")

            # Only copy to config directory if they're different
            if not same_dir:
                config_filepath = os.path.join(config_profile_dir, filename)
                try:
                    import shutil
                    shutil.copy2(filepath, config_filepath)
                    print(f"Copied profile photo to: {config_filepath}")
                except shutil.SameFileError:
                    # They're the same file, that's fine
                    pass
                except Exception as e:
                    print(f"Error copying profile photo: {str(e)}")

            # Return relative path for web access
            return f"profile_photos/{filename}"
        except Exception as e:
            print(f"Error saving file: {str(e)}")
            return None
    else:
        print("No file to save")
        return None

# Helper function to generate invitation token
def generate_invitation_token():
    return secrets.token_urlsafe(32)

@app.route('/hr-registration/step4')
def hr_registration_step4():
    """Direct access to step 4"""
    session_data = session.get('hr_registration', {})
    if not session_data or session_data.get('step') != '5':
        # If not coming from step 5, go to current step
        return redirect(url_for('hr_registration'))

    # Change step to 4
    session_data['step'] = '4'
    session['hr_registration'] = session_data

    return render_template('hr_registration_step4.html',
                         event=get_event_data(),
                         session_data=session_data)

@app.route('/hr-registration', methods=['GET', 'POST'])
def hr_registration():
    """HR Registration Portal - Multi-step form"""
    event = get_event_data()

    # Check for invitation token
    invitation_token = request.args.get('invite')
    invitation_data = None
    pending_hr_id = None

    if invitation_token:
        # Find HR data by invitation token in pending data
        hr_pending_data = load_db('hr_pending_data')
        for hr_id, hr in hr_pending_data.items():
            if hr.get('invitation_token') == invitation_token:
                invitation_data = hr
                pending_hr_id = hr_id
                # Pre-fill session with invitation data
                session['hr_registration'] = {
                    'pending_hr_id': hr_id,
                    'full_name': hr.get('full_name', ''),
                    'office_email': hr.get('office_email', ''),
                    'personal_email': hr.get('personal_email', ''),
                    'mobile': hr.get('mobile', ''),
                    'organization': hr.get('organization', ''),
                    'designation': hr.get('designation', ''),
                    'city': hr.get('city', ''),
                    'state': hr.get('state', ''),
                    'country': hr.get('country', ''),
                    'linkedin': hr.get('linkedin', ''),
                    'website': hr.get('website', ''),
                    'invitation_token': invitation_token,
                    'step': '1'
                }
                break

    # Handle GET request with back parameter
    if request.method == 'GET' and request.args.get('back') == 'true':
        session_data = session.get('hr_registration', {})
        current_step = session_data.get('step', '1')

        # Go back one step
        if current_step == '4':
            session_data['step'] = '3'
        elif current_step == '3':
            session_data['step'] = '2'
        elif current_step == '2':
            session_data['step'] = '1'

        session['hr_registration'] = session_data
        return redirect(url_for('hr_registration'))

    if request.method == 'POST':
        step = request.form.get('step', '1')
        session_data = session.get('hr_registration', {})

        # Update with invitation data if present
        if invitation_data and step == '1':
            for key in ['full_name', 'office_email', 'mobile', 'organization', 'designation', 'city', 'state', 'country']:
                if key in invitation_data and invitation_data[key]:
                    session_data[key] = invitation_data[key]

        # Handle back navigation from step 4
        if step == '3_back':
            # Save current form data from step 4
            session_data.update({
                'award_interest': request.form.get('award_interest', session_data.get('award_interest', '')),
                'panel_interest': request.form.get('panel_interest', session_data.get('panel_interest', '')),
                'panel_theme': request.form.get('panel_theme', session_data.get('panel_theme', '')),
                'panel_expertise': request.form.get('panel_expertise', session_data.get('panel_expertise', '')),
                'source': request.form.get('source', session_data.get('source', '')),
            })

            # Go back to step 3
            session_data['step'] = '3'
            session['hr_registration'] = session_data
            return redirect(url_for('hr_registration'))

        # Handle back navigation from step 3
        if step == '2_back':
            # Save current form data from step 3
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename:
                    # Generate registration ID early for filename
                    if 'registration_id' not in session_data:
                        registration_id = generate_registration_id()
                        session_data['registration_id'] = registration_id

                    # Save profile photo
                    photo_path = save_profile_photo(file, session_data['registration_id'])
                    if photo_path:
                        session_data['profile_photo'] = photo_path

            # Go back to step 2
            session_data['step'] = '2'
            session['hr_registration'] = session_data
            return redirect(url_for('hr_registration'))

        # Handle back navigation from step 2
        if step == '1_back':
            # Save current form data from step 2
            session_data.update({
                'organization': request.form.get('organization', session_data.get('organization', '')),
                'designation': request.form.get('designation', session_data.get('designation', '')),
                'linkedin': request.form.get('linkedin', session_data.get('linkedin', '')),
                'website': request.form.get('website', session_data.get('website', '')),
            })

            # Go back to step 1
            session_data['step'] = '1'
            session['hr_registration'] = session_data
            return redirect(url_for('hr_registration'))

        # Handle back navigation from step 5
        if step == '4_back':
            # Save current form data from step 5
            session_data.update({
                'declaration': request.form.get('declaration') == 'on',
                'consent': request.form.get('consent') == 'on',
                'attendance': request.form.get('attendance', session_data.get('attendance', '')),
            })

            # Go back to step 4
            session_data['step'] = '4'
            session['hr_registration'] = session_data
            return redirect(url_for('hr_registration'))

        if step == '1':
            # Section 1: Personal Information
            session_data.update({
                'full_name': request.form.get('full_name') or session_data.get('full_name', ''),
                'office_email': request.form.get('office_email') or session_data.get('office_email', ''),
                'personal_email': request.form.get('personal_email') or session_data.get('personal_email', ''),
                'mobile': request.form.get('mobile') or session_data.get('mobile', ''),
                'city': request.form.get('city') or session_data.get('city', ''),
                'state': request.form.get('state') or session_data.get('state', ''),
                'country': request.form.get('country') or session_data.get('country', ''),
                'step': '2'
            })

        elif step == '2':
            # Section 2: Professional Details
            session_data.update({
                'organization': request.form.get('organization') or session_data.get('organization', ''),
                'designation': request.form.get('designation') or session_data.get('designation', ''),
                'linkedin': request.form.get('linkedin', '') or session_data.get('linkedin', ''),
                'website': request.form.get('website', '') or session_data.get('website', ''),
                'step': '3'
            })

        elif step == '3':
            # Section 3: Profile Photo
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename:
                    # Generate registration ID early for filename
                    if 'registration_id' not in session_data:
                        registration_id = generate_registration_id()
                        session_data['registration_id'] = registration_id

                    # Save profile photo
                    photo_path = save_profile_photo(file, session_data['registration_id'])
                    if photo_path:
                        session_data['profile_photo'] = photo_path

            session_data['step'] = '4'

        elif step == '4':
            # Section 4: Awards & Panel Interest
            session_data.update({
                'award_interest': request.form.get('award_interest', ''),
                'panel_interest': request.form.get('panel_interest'),
                'panel_theme': request.form.get('panel_theme', ''),
                'panel_expertise': request.form.get('panel_expertise', ''),
                'source': request.form.get('source', ''),
                'step': '5'
            })

        elif step == '5':
            print("=== REGISTRATION COMPLETION STARTED ===")
            # Section 5: Declaration & Final
            session_data.update({
                'declaration': request.form.get('declaration') == 'on',
                'consent': request.form.get('consent') == 'on',
                'attendance': request.form.get('attendance'),
                'step': 'complete'
            })

            # Check if required fields are present
            if not session_data.get('declaration') or not session_data.get('consent'):
                flash('Please agree to the declaration and consent to continue', 'error')
                session_data['step'] = '5'
                session['hr_registration'] = session_data
                return redirect(url_for('hr_registration'))

            # Generate registration ID if not already generated
            if 'registration_id' not in session_data:
                registration_id = generate_registration_id()
                session_data['registration_id'] = registration_id
                print(f"Generated registration ID: {registration_id}")

            session_data['registered_at'] = datetime.now().isoformat()
            session_data['status'] = 'registered'

            # Add approval_status with default value
            session_data['approval_status'] = 'pending_review'

            print(f"Session data ready: {session_data.get('full_name')}, {session_data.get('registration_id')}")

            # Move from pending to registered
            hr_registrations = load_db('hr_registrations')
            hr_pending_data = load_db('hr_pending_data')

            # Get pending HR ID
            pending_hr_id = session_data.get('pending_hr_id')
            print(f"Pending HR ID: {pending_hr_id}")

            if pending_hr_id and pending_hr_id in hr_pending_data:
                print(f"Found pending HR data for ID: {pending_hr_id}")
                # Update pending data to mark as completed
                hr_pending_data[pending_hr_id]['registration_complete'] = True
                hr_pending_data[pending_hr_id]['actual_registration_id'] = session_data['registration_id']
                hr_pending_data[pending_hr_id]['completed_at'] = datetime.now().isoformat()
                save_db('hr_pending_data', hr_pending_data)
                print("Updated pending HR data")

            # Save to registrations database
            hr_registrations[session_data['registration_id']] = session_data
            save_db('hr_registrations', hr_registrations)
            print(f"Saved to registrations database: {session_data['registration_id']}")

            # Generate PDF schedule
            try:
                pdf_path = generate_event_schedule_pdf(session_data)
                if pdf_path:
                    print(f"Generated PDF: {pdf_path}")
                else:
                    print("PDF generation failed")
            except Exception as e:
                print(f"PDF generation error: {e}")

            # Send confirmation email with PDF
            try:
                email_sent = send_confirmation_email(session_data, pdf_path if 'pdf_path' in locals() else None)
                session_data['email_sent'] = email_sent
                print(f"Email sent: {email_sent}")
            except Exception as e:
                print(f"Email sending error: {e}")
                session_data['email_sent'] = False

            # Store registration data in session for thank you page
            session['last_registration_id'] = session_data['registration_id']
            session['last_registration_data'] = session_data

            # Clear current registration session but keep last registration
            session.pop('hr_registration', None)

            print(f"=== REDIRECTING TO THANK YOU PAGE: {session_data['registration_id']} ===")

            # Redirect to thank you page with registration ID
            return redirect(url_for('registration_thank_you', reg_id=session_data['registration_id']))

        # Save session data for normal forward navigation
        session['hr_registration'] = session_data
        return redirect(url_for('hr_registration'))

    # GET request - show current step
    current_step = session.get('hr_registration', {}).get('step', '1')

    # If step is 'complete', redirect to thank you page
    if current_step == 'complete':
        registration_id = session.get('hr_registration', {}).get('registration_id')
        if registration_id:
            return redirect(url_for('registration_thank_you', reg_id=registration_id))
        else:
            # If no registration ID, go back to step 1
            session['hr_registration'] = {'step': '1'}
            current_step = '1'

    return render_template(f'hr_registration_step{current_step}.html',
                         event=event,
                         session_data=session.get('hr_registration', {}),
                         invitation_data=invitation_data)



# ================= MAP API ROUTES =================

@app.route('/api/map/save_location', methods=['POST'])
def save_map_location():
    """Save location to database"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()

        # Generate unique ID for location
        location_id = f"LOC_{uuid.uuid4().hex[:8].upper()}"

        location_data = {
            'id': location_id,
            'name': data.get('name', ''),
            'type': data.get('type', 'other'),
            'description': data.get('description', ''),
            'coordinates': data.get('coordinates', [0, 0]),
            'created_at': datetime.now().isoformat(),
            'created_by': session.get('user_id', 'unknown')
        }

        # Load existing locations
        locations = load_db('locations')
        locations[location_id] = location_data
        save_db('locations', locations)

        return jsonify({
            'success': True,
            'message': 'Location saved successfully',
            'location_id': location_id
        })

    except Exception as e:
        print(f"Error saving location: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/map/get_all_data')
def get_all_map_data():
    """Get all map data (locations and paths)"""
    try:
        locations = load_db('locations')
        paths = load_db('paths')

        return jsonify({
            'success': True,
            'locations': locations,
            'paths': paths
        })

    except Exception as e:
        print(f"Error getting map data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/map/update_location/<location_id>', methods=['POST'])
def update_map_location(location_id):
    """Update location in database"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        locations = load_db('locations')

        if location_id not in locations:
            return jsonify({'success': False, 'error': 'Location not found'})

        # Update location data
        locations[location_id].update({
            'name': data.get('name', locations[location_id]['name']),
            'type': data.get('type', locations[location_id]['type']),
            'description': data.get('description', locations[location_id]['description']),
            'coordinates': data.get('coordinates', locations[location_id]['coordinates']),
            'updated_at': datetime.now().isoformat(),
            'updated_by': session.get('user_id', 'unknown')
        })

        save_db('locations', locations)

        return jsonify({
            'success': True,
            'message': 'Location updated successfully'
        })

    except Exception as e:
        print(f"Error updating location: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/map/delete_location/<location_id>', methods=['POST'])
def delete_map_location(location_id):
    """Delete location from database"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        locations = load_db('locations')

        if location_id not in locations:
            return jsonify({'success': False, 'error': 'Location not found'})

        # Delete location
        del locations[location_id]
        save_db('locations', locations)

        return jsonify({
            'success': True,
            'message': 'Location deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting location: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


def generate_smart_greeting(hr_data):
    """Generate smart greeting for emails"""
    hr_name = hr_data.get('full_name', '')
    organization = hr_data.get('organization', '')
    
    # If no name or name is N/A, use organization
    if not hr_name or hr_name == 'N/A' or hr_name.strip() == '':
        if organization:
            return f"{organization} Team"
        else:
            return "HR Professional"
    else:
        return hr_name

def get_smart_greeting(hr_data):
    """Generate smart greeting based on available data"""
    hr_name = str(hr_data.get('full_name', '')).strip()
    organization = str(hr_data.get('organization', '')).strip()
    
    # Debug info
    print(f"Greeting Debug: Name='{hr_name}', Organization='{organization}'")
    
    # Define invalid names
    invalid_names = ['', 'n/a', 'nan', 'null', 'undefined', ' ', 'N/A', 'hr professional']
    
    if not hr_name or hr_name.lower() in invalid_names or hr_name == 'N/A':
        # No valid name, use organization with "Team"
        if organization and organization.lower() not in invalid_names:
            return f"{organization} Team"
        else:
            return "HR Professional"
    else:
        # Valid name exists
        return hr_name
    
@app.route('/api/map/save_path', methods=['POST'])
def save_map_path():
    """Save path to database"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()

        path_data = {
            'id': f"PATH_{uuid.uuid4().hex[:8].upper()}",
            'name': data.get('name', 'New Path'),
            'from': data.get('from', ''),
            'to': data.get('to', ''),
            'path_points': data.get('path_points', []),
            'color': data.get('color', '#ff0000'),
            'weight': data.get('weight', 3),
            'created_at': datetime.now().isoformat(),
            'created_by': session.get('user_id', 'unknown')
        }

        # Load existing paths
        paths = load_db('paths')
        paths.append(path_data)
        save_db('paths', paths)

        return jsonify({
            'success': True,
            'message': 'Path saved successfully',
            'path_id': path_data['id']
        })

    except Exception as e:
        print(f"Error saving path: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.template_filter('date_short')
def date_short_filter(value, default=''):
    """Format date to show only first 10 characters (YYYY-MM-DD)"""
    if not value:
        return default
    return str(value)[:10] if len(str(value)) >= 10 else str(value)

@app.template_filter('date_format')
def date_format_filter(value, format='%Y-%m-%d'):
    """Format date string"""
    if not value:
        return ''
    try:
        # Try to parse ISO format
        if 'T' in value:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(value, '%Y-%m-%d')
        return dt.strftime(format)
    except:
        # If parsing fails, return first 10 chars
        return str(value)[:10] if len(str(value)) >= 10 else str(value)

@app.template_filter('profile_photo')
def profile_photo_filter(photo_path, name):
    """Return profile photo URL or default avatar"""
    if photo_path and os.path.exists(os.path.join('static', photo_path)):
        return url_for('static', filename=photo_path)
    else:
        # Return default avatar based on name
        return f"https://ui-avatars.com/api/?name={name}&background=random&color=fff&size=40"

# Update the get_profile_photo route
@app.route('/profile_photos/<filename>')
def get_profile_photo(filename):
    """Serve profile photos"""
    try:
        # Try multiple possible locations
        directories_to_try = [
            'static/profile_photos',
            app.config['PROFILE_PHOTOS'],
            'uploads'
        ]

        for directory in directories_to_try:
            filepath = os.path.join(directory, filename)
            if os.path.exists(filepath):
                print(f"Found profile photo at: {filepath}")
                return send_from_directory(directory, filename)

        print(f"Profile photo not found: {filename}")
        # Return default avatar
        name = filename.split('.')[0] if '.' in filename else 'User'
        return redirect(f"https://ui-avatars.com/api/?name={name}&background=random&color=fff&size=40")

    except Exception as e:
        print(f"Error serving profile photo: {str(e)}")
        # Return default avatar
        return redirect("https://ui-avatars.com/api/?name=User&background=random&color=fff&size=40")

@app.route('/admin/upload-hr', methods=['GET', 'POST'])
def admin_upload_hr():
    """Upload HR data via Excel - NO automatic invitation sending"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    # Load both datasets for display
    hr_pending_data = load_db('hr_pending_data')
    hr_registrations = load_db('hr_registrations')

    # Calculate statistics for display
    total_uploaded_count = len(hr_pending_data)
    
    # Count pending (no invitation sent)
    pending_count = 0
    new_no_name_count = 0
    new_with_name_count = 0
    
    for hr in hr_pending_data.values():
        if not hr.get('invitation_sent', False):
            pending_count += 1
            # Check if has name or organization only
            if not hr.get('full_name') or hr.get('full_name', '') == '':
                new_no_name_count += 1
            else:
                new_with_name_count += 1
    
    invited_count = sum(1 for hr in hr_pending_data.values() if hr.get('invitation_sent', False))
    registered_count = sum(1 for hr in hr_pending_data.values() if hr.get('registration_complete', False))

    # Combine all HR data for the table
    all_uploaded_hr = []
    
    # Categorize HR data properly
    for hr_id, hr in hr_pending_data.items():
        hr_data = hr.copy()
        hr_data['id'] = hr_id
        
        # Add categorization flags
        hr_data['is_new'] = not hr.get('invitation_sent', False)
        hr_data['has_name'] = bool(hr.get('full_name') and hr.get('full_name', '').strip() != '')
        hr_data['is_org_only'] = not hr_data['has_name']
        
        # Generate display name
        if hr_data['is_org_only']:
            hr_data['display_name'] = f"{hr.get('organization', 'Unknown')} Team"
        else:
            hr_data['display_name'] = hr.get('full_name', '')
        
        all_uploaded_hr.append(hr_data)

    # Calculate dashboard stats
    stats = calculate_stats()
    
    # Update stats with new counts
    stats['org_only_count'] = new_no_name_count
    stats['new_no_invitation'] = pending_count
    stats['new_no_name'] = new_no_name_count
    stats['new_with_name'] = new_with_name_count

    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            return render_template('admin_upload_hr.html',
                                 error='No file selected',
                                 stats=stats,
                                 all_uploaded_hr=all_uploaded_hr,
                                 total_uploaded_count=total_uploaded_count,
                                 pending_count=pending_count,
                                 invited_count=invited_count,
                                 registered_count=registered_count,
                                 new_no_name_count=new_no_name_count,
                                 new_with_name_count=new_with_name_count)

        file = request.files['file']

        # Check if filename is empty
        if file.filename == '':
            return render_template('admin_upload_hr.html',
                                 error='No file selected',
                                 stats=stats,
                                 all_uploaded_hr=all_uploaded_hr,
                                 total_uploaded_count=total_uploaded_count,
                                 pending_count=pending_count,
                                 invited_count=invited_count,
                                 registered_count=registered_count,
                                 new_no_name_count=new_no_name_count,
                                 new_with_name_count=new_with_name_count)

        # Check file extension
        if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            return render_template('admin_upload_hr.html',
                                 error='Only Excel (.xlsx, .xls) or CSV files are allowed',
                                 stats=stats,
                                 all_uploaded_hr=all_uploaded_hr,
                                 total_uploaded_count=total_uploaded_count,
                                 pending_count=pending_count,
                                 invited_count=invited_count,
                                 registered_count=registered_count,
                                 new_no_name_count=new_no_name_count,
                                 new_with_name_count=new_with_name_count)

        try:
            # Save file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # REMOVED: Check if send_invitations checkbox was checked
            # We will NOT send invitations automatically anymore
            # send_invitations = request.form.get('send_invitations') == 'on'

            # Process file based on extension
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            # Check required columns
            required_columns = ['organization', 'email']
            
            # Handle different column name variations
            column_mapping = {
                'organization': ['organization', 'company', 'org', 'company_name', 'employer', 'organisation'],
                'email': ['email', 'office_email', 'email_address', 'contact_email', 'work_email'],
                'full_name': ['full_name', 'name', 'contact_name', 'employee_name', 'hr_name'],
                'mobile': ['mobile', 'phone', 'mobile_number', 'contact_number', 'phone_number'],
                'designation': ['designation', 'title', 'position', 'job_title', 'role'],
                'city': ['city', 'location', 'city_name'],
                'state': ['state', 'region', 'province'],
                'country': ['country', 'nation'],
                'linkedin': ['linkedin', 'linkedin_profile', 'linkedin_url'],
                'website': ['website', 'company_website', 'web', 'url']
            }
            
            # Normalize column names (strip whitespace and convert to lowercase)
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            
            # Find email column
            email_column = None
            for possible_name in column_mapping['email']:
                if possible_name in df.columns:
                    email_column = possible_name
                    break
            
            # Find organization column
            org_column = None
            for possible_name in column_mapping['organization']:
                if possible_name in df.columns:
                    org_column = possible_name
                    break
            
            if not email_column or not org_column:
                return render_template('admin_upload_hr.html',
                                     error='File must contain at least "organization" and "email" columns',
                                     stats=stats,
                                     all_uploaded_hr=all_uploaded_hr,
                                     total_uploaded_count=total_uploaded_count,
                                     pending_count=pending_count,
                                     invited_count=invited_count,
                                     registered_count=registered_count,
                                     new_no_name_count=new_no_name_count,
                                     new_with_name_count=new_with_name_count)

            # Load pending HR data
            hr_pending_data = load_db('hr_pending_data')
            
            added = 0
            # REMOVED: newly_invited variable since we're not sending invitations
            skipped = 0
            errors = []
            newly_added_users = []  # Store newly added users for display
            org_only_added = 0
            with_name_added = 0
            
            for index, row in df.iterrows():
                try:
                    # Extract email - REQUIRED
                    email = str(row.get(email_column, '')).strip()
                    if not email or '@' not in email:
                        skipped += 1
                        errors.append(f"Row {index+2}: Invalid email format - {email[:50]}")
                        continue
                    
                    # Extract organization - REQUIRED
                    organization = str(row.get(org_column, '')).strip()
                    if not organization:
                        skipped += 1
                        errors.append(f"Row {index+2}: Missing organization")
                        continue
                    
                    # Extract name - OPTIONAL (leave empty if not provided)
                    full_name = ''
                    for possible_name in column_mapping['full_name']:
                        if possible_name in df.columns:
                            name_val = str(row.get(possible_name, '')).strip()
                            if name_val and name_val.lower() not in ['n/a', 'na', 'null', 'undefined']:
                                full_name = name_val
                                break
                    
                    # Check if organization-only (no valid name)
                    is_org_only = False
                    if not full_name:
                        is_org_only = True
                        # DO NOT generate name from email - leave it empty
                        full_name = ''
                        org_only_added += 1
                    else:
                        with_name_added += 1
                    
                    # Extract mobile - OPTIONAL
                    mobile = ''
                    for possible_name in column_mapping['mobile']:
                        if possible_name in df.columns:
                            mobile_val = str(row.get(possible_name, '')).strip()
                            if mobile_val:
                                mobile = mobile_val[:15]  # Limit to 15 chars
                                break
                    
                    # Extract designation - OPTIONAL
                    designation = ''
                    for possible_name in column_mapping['designation']:
                        if possible_name in df.columns:
                            designation_val = str(row.get(possible_name, '')).strip()
                            if designation_val:
                                designation = designation_val
                                break
                    
                    # Extract other optional fields
                    city = str(row.get('city', '')).strip() if 'city' in df.columns else ''
                    state = str(row.get('state', '')).strip() if 'state' in df.columns else ''
                    country = str(row.get('country', '')).strip() if 'country' in df.columns else ''
                    linkedin = str(row.get('linkedin', '')).strip() if 'linkedin' in df.columns else ''
                    website = str(row.get('website', '')).strip() if 'website' in df.columns else ''
                    
                    # Check if email already exists
                    email_exists = False
                    for hr_id, existing_hr in hr_pending_data.items():
                        if existing_hr.get('office_email') == email:
                            email_exists = True
                            break
                    
                    if email_exists:
                        skipped += 1
                        continue
                    
                    # Generate unique ID for pending HR
                    pending_id = f"PENDING_{uuid.uuid4().hex[:8].upper()}"
                    
                    hr_data = {
                        'id': pending_id,
                        'full_name': full_name,  # Will be empty if not provided
                        'office_email': email,
                        'organization': organization,
                        'mobile': mobile,
                        'designation': designation,
                        'city': city,
                        'state': state,
                        'country': country,
                        'linkedin': linkedin,
                        'website': website,
                        'uploaded_at': datetime.now().isoformat(),
                        'status': 'pending_invitation',
                        'source': 'bulk_upload',
                        'invitation_sent': False,  # Always False initially
                        'invitation_sent_at': None,
                        'registration_complete': False,
                        'registered_at': None,
                        'is_org_only': is_org_only,  # Track if organization only
                        'has_full_name': not is_org_only  # Track if has full name
                    }
                    
                    # Generate smart greeting for display
                    if is_org_only:
                        display_name = f"{organization} Team"
                        greeting = f"{organization} Team"
                    else:
                        display_name = full_name
                        greeting = full_name
                    
                    # Add to newly added users list for display
                    newly_added_users.append({
                        'id': pending_id,
                        'full_name': display_name,
                        'office_email': email,
                        'organization': organization,
                        'designation': designation,
                        'mobile': mobile,
                        'invitation_sent': False,  # Always False
                        'registration_complete': False,
                        'is_org_only': is_org_only,
                        'greeting': greeting,
                        'has_full_name': not is_org_only
                    })
                    
                    # Store in pending data
                    hr_pending_data[pending_id] = hr_data
                    added += 1
                    
                    # REMOVED: Automatic invitation sending section
                    # We will NOT send invitations automatically after upload
                    # Invitations will be sent manually from the "Invitations" page
                    
                except Exception as row_error:
                    errors.append(f"Row {index+2}: {str(row_error)[:100]}")
                    continue
            
            # Save updated pending data
            save_db('hr_pending_data', hr_pending_data)
            
            # Reload data for display after upload
            hr_pending_data = load_db('hr_pending_data')
            
            # Recalculate statistics
            total_uploaded_count = len(hr_pending_data)
            pending_count = sum(1 for hr in hr_pending_data.values() if not hr.get('invitation_sent', False))
            invited_count = sum(1 for hr in hr_pending_data.values() if hr.get('invitation_sent', False))
            registered_count = sum(1 for hr in hr_pending_data.values() if hr.get('registration_complete', False))
            
            # Update new counts
            new_no_name_count = 0
            new_with_name_count = 0
            for hr in hr_pending_data.values():
                if not hr.get('invitation_sent', False):
                    if hr.get('is_org_only'):
                        new_no_name_count += 1
                    else:
                        new_with_name_count += 1
            
            # Update all_uploaded_hr list
            all_uploaded_hr = []
            for hr_id, hr in hr_pending_data.items():
                hr_data = hr.copy()
                hr_data['id'] = hr_id
                all_uploaded_hr.append(hr_data)
            
            # Update dashboard stats
            stats = calculate_stats()
            stats['org_only_count'] = new_no_name_count
            stats['new_no_invitation'] = pending_count
            stats['new_no_name'] = new_no_name_count
            stats['new_with_name'] = new_with_name_count
            
            # Prepare success message - Updated to reflect no automatic invitations
            success_message = f'Successfully uploaded {added} HR professionals to pending data. '
            if org_only_added > 0:
                success_message += f'({org_only_added} organization-only, {with_name_added} with names). '
            
            success_message += 'Invitations have NOT been sent automatically. '
            success_message += 'You can send invitations manually from the "Invitations" page.'
            
            if skipped > 0:
                success_message += f' {skipped} rows were skipped.'
            
            if errors:
                success_message += f' {len(errors)} errors occurred.'
            
            return render_template('admin_upload_hr.html',
                                 success=success_message,
                                 added_count=added,
                                 invited_count=invited_count,
                                 skipped_count=skipped,
                                 error_count=len(errors),
                                 newly_added_users=newly_added_users,
                                 # REMOVED: send_invitations parameter
                                 stats=stats,
                                 all_uploaded_hr=all_uploaded_hr,
                                 total_uploaded_count=total_uploaded_count,
                                 pending_count=pending_count,
                                 registered_count=registered_count,
                                 new_no_name_count=new_no_name_count,
                                 new_with_name_count=new_with_name_count,
                                 org_only_added=org_only_added,
                                 with_name_added=with_name_added)
            
        except Exception as e:
            print(f"Upload error: {str(e)}")
            traceback.print_exc()
            return render_template('admin_upload_hr.html',
                                 error=f'Error processing file: {str(e)}',
                                 stats=stats,
                                 all_uploaded_hr=all_uploaded_hr,
                                 total_uploaded_count=total_uploaded_count,
                                 pending_count=pending_count,
                                 invited_count=invited_count,
                                 registered_count=registered_count,
                                 new_no_name_count=new_no_name_count,
                                 new_with_name_count=new_with_name_count)
    
    # GET request - show all uploaded HR data
    return render_template('admin_upload_hr.html',
                         stats=stats,
                         all_uploaded_hr=all_uploaded_hr,
                         total_uploaded_count=total_uploaded_count,
                         pending_count=pending_count,
                         invited_count=invited_count,
                         registered_count=registered_count,
                         new_no_name_count=new_no_name_count,
                         new_with_name_count=new_with_name_count)

# Remove the duplicate route or keep it but make sure it's different
@app.route('/static/profile_photos/<filename>')
def static_profile_photos(filename):
    """Serve profile photos from static folder"""
    return send_from_directory('static/profile_photos', filename)

def send_custom_invitation_email(hr_data, invitation_url, custom_subject="", custom_message=""):
    """Send invitation email with custom content (updated format)"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data['office_email']

        # Use custom subject or default
        subject = custom_subject if custom_subject else '🎉 Invitation to Register - HR Conclave 2026'
        msg['Subject'] = subject

        # Get event data
        event = get_event_data()
        
        # SMART GREETING LOGIC
        hr_name = str(hr_data.get('full_name', '')).strip()
        organization = str(hr_data.get('organization', '')).strip()
        
        invalid_patterns = ['', 'n/a', 'nan', 'null', 'undefined', ' ', 'N/A']
        
        if hr_name and hr_name.lower() not in invalid_patterns:
            greeting = f"Dear {hr_name},"
        elif organization and organization.lower() not in invalid_patterns:
            greeting = f"Dear {organization} Team,"
        else:
            greeting = "Dear HR Professional,"
        
        # Schedule HTML
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """

        # Use custom message or default
        if custom_message:
            personalized_content = custom_message.replace('{{name}}', hr_name if hr_name else (organization + " Team" if organization else "HR Professional"))\
                                                .replace('{{invitation_url}}', invitation_url)
        else:
            personalized_content = f"""
            <p>{greeting}</p>
            <p>You have been invited to register for <strong>HR Conclave 2026</strong> - an industry-academia initiative bringing together senior HR professionals.</p>
            """

        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HR Conclave 2026 Invitation</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">🎉 Custom Invitation</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">HR Conclave 2026 - Connecting the Future</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Personalized Message -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: #7e22ce; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ✉️
                    </div>
                    <div style="background: #f8fafc; padding: 25px; border-radius: 10px; margin-top: 20px; text-align: left;">
                        {personalized_content}
                    </div>
                </div>

                <!-- Action Card -->
                <div style="background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border: 2px solid #bae6fd; border-radius: 15px; padding: 25px; text-align: center; margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; margin-bottom: 20px;">
                        <i class="fas fa-user-plus"></i> Complete Your Registration
                    </h3>
                    
                    <a href="{invitation_url}"
                       style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold; font-size: 16px; margin: 10px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        📝 Complete Registration
                    </a>
                    
                    <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 20px;">
                        <p style="margin: 0; font-size: 13px; color: #64748b;">
                            <i class="fas fa-link"></i> Registration Link:<br>
                            <code style="display: inline-block; background: #f8fafc; padding: 8px 12px; border-radius: 5px; margin-top: 5px; font-family: monospace; font-size: 12px; word-break: break-all;">
                                {invitation_url}
                            </code>
                        </p>
                    </div>
                </div>

                <!-- Event Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📅 Event Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                            <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Time:</strong></td>
                            <td style="padding: 8px 0;">9:00 AM - 5:00 PM</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                            <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                        </tr>
                    </table>
                </div>

                <!-- Schedule -->
                <div style="margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">⏰ Event Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white;">
                                <th style="padding: 15px; text-align: left;">Time</th>
                                <th style="padding: 15px; text-align: left;">Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html}
                        </tbody>
                    </table>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Custom invitation email sent to {hr_data['office_email']}")
        return True
    except Exception as e:
        print(f"✗ Custom invitation email sending error: {str(e)}")
        return False
    

def send_rejection_email(hr_data, admin_notes=""):
    """Send rejection email (updated format)"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data['office_email']
        msg['Subject'] = 'HR Conclave 2026 - Registration Status Update'
        
        # Get event data
        event = get_event_data()

        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HR Conclave 2026 - Status Update</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #dc2626, #ef4444); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">Registration Status Update</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">HR Conclave 2026</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Status Section -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: #dc2626; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ⚠️
                    </div>
                    <h2 style="color: #dc2626; margin: 0;">Update on Your Registration</h2>
                    <p style="margin: 10px 0; color: #4b5563;">
                        Dear {hr_data.get('full_name', 'HR Professional')},
                    </p>
                </div>

                <!-- Status Card -->
                <div style="background: #fee2e2; border: 2px solid #fca5a5; border-radius: 15px; padding: 25px; margin: 30px 0;">
                    <h3 style="color: #dc2626; margin-top: 0; margin-bottom: 15px;">
                        <i class="fas fa-info-circle"></i> Registration Status
                    </h3>
                    
                    <div style="background: white; padding: 15px; border-radius: 10px; margin: 15px 0;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #dc2626;">Current Status:</p>
                        <div style="background: #dc2626; color: white; padding: 8px 20px; border-radius: 20px; display: inline-block; font-weight: bold;">
                            ❌ Not Approved
                        </div>
                    </div>
                    
                    <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 15px;">
                        <p style="margin: 0 0 8px 0; font-weight: bold; color: #dc2626;">Reason:</p>
                        <p style="margin: 0; color: #666; line-height: 1.5;">
                            {admin_notes if admin_notes else 'Due to overwhelming response and limited seating capacity, we were unable to approve your registration at this time.'}
                        </p>
                    </div>
                </div>

                <!-- Appreciation -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">🙏 Thank You</h3>
                    <p style="color: #4b5563;">
                        We sincerely appreciate your interest in HR Conclave 2026 and the time you took to submit your registration. 
                        The response has been overwhelming, and we regret that we cannot accommodate all applicants.
                    </p>
                    
                    <div style="background: #dbeafe; padding: 15px; border-radius: 8px; margin-top: 15px;">
                        <p style="margin: 0; color: #1e40af; font-weight: bold;">
                            <i class="fas fa-calendar-alt"></i> Future Opportunities
                        </p>
                        <p style="margin: 8px 0 0 0; color: #4b5563;">
                            We hope to have you at our future events and will keep you informed about upcoming HR initiatives.
                        </p>
                    </div>
                </div>

                <!-- Event Details (for information) -->
                <div style="background: #f8fafc; border-radius: 10px; padding: 20px; margin: 30px 0;">
                    <h4 style="color: #1a56db; margin-top: 0;">📅 About HR Conclave 2026</h4>
                    <p style="margin: 10px 0; color: #4b5563;">
                        HR Conclave 2026 is an industry-academia initiative bringing together senior HR professionals 
                        to discuss talent transformation, leadership, and future workforce readiness.
                    </p>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #4b5563;">
                        <li><strong>Date:</strong> {event.get('date', 'February 7, 2026')}</li>
                        <li><strong>Venue:</strong> {event.get('venue', 'Sphoorthy Engineering College')}</li>
                        <li><strong>Theme:</strong> Connecting the Future</li>
                    </ul>
                </div>

                <!-- Stay Connected -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">
                        <i class="fas fa-handshake"></i> Stay Connected
                    </h4>
                    <p style="margin: 10px 0; color: #92400e;">
                        Follow us on LinkedIn for updates on future events and HR initiatives:
                    </p>
                    <a href="{event.get('contact', {}).get('college_linkedin', 'https://www.linkedin.com/in/sphoorthy-engineering-college/')}"
                       style="display: inline-block; background: #0077b5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin-top: 10px;">
                        <i class="fab fa-linkedin"></i> Follow on LinkedIn
                    </a>
                </div>

                <!-- Contact Information -->
                <div style="background: #f3f4f6; border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0;">📞 Contact Us</h4>
                    <p style="margin: 10px 0;">
                        For any queries regarding this decision or future events:<br>
                        <strong>Email:</strong> {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}<br>
                        <strong>Phone:</strong> {event.get('contact', {}).get('phone', '+91-9121001921')}
                    </p>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p>Thank you for your understanding and continued interest in our initiatives.</p>
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        This is an automated status update email. Please do not reply to this address.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Rejection email sent to {hr_data['office_email']}")
        return True
    except Exception as e:
        print(f"✗ Rejection email sending error: {str(e)}")
        return False

# Update the send_panel_acceptance_email function
def send_panel_acceptance_email(hr_data, email_subject, email_message):
    """Send panel acceptance email (updated format)"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data.get('office_email', '')

        if not msg['To'] or '@' not in msg['To']:
            print(f"Invalid email address: {msg['To']}")
            return False

        msg['Subject'] = email_subject

        # Get event data
        event = get_event_data()
        
        # Schedule HTML
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """

        # Personalize the message
        personalized_message = email_message
        personalized_message = personalized_message.replace('[[name]]', hr_data.get('full_name', ''))
        personalized_message = personalized_message.replace('[[panel_theme]]', hr_data.get('panel_theme', ''))
        personalized_message = personalized_message.replace('[[organization]]', hr_data.get('organization', ''))
        personalized_message = personalized_message.replace('\n', '<br>')

        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Panel Discussion Acceptance</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">🎉 Panel Discussion Acceptance!</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">HR Conclave 2026</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Congratulations -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: #10b981; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ✓
                    </div>
                    <h2 style="color: #059669; margin: 0;">Congratulations {hr_data.get('full_name', '')}!</h2>
                    <p style="margin: 10px 0; color: #4b5563;">
                        You have been selected to participate in our panel discussion at HR Conclave 2026.
                    </p>
                </div>

                <!-- Personalized Message -->
                <div style="background: #f0f9ff; border: 2px solid #bae6fd; border-radius: 15px; padding: 25px; margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; margin-bottom: 15px;">
                        <i class="fas fa-comments"></i> Panel Details
                    </h3>
                    <div style="background: white; padding: 20px; border-radius: 10px;">
                        {personalized_message}
                    </div>
                </div>

                <!-- Panelist Info -->
                <div style="background: #f8fafc; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">👤 Your Information</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 150px;"><strong>Name:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('full_name', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Organization:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('organization', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Designation:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('designation', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Panel Theme:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('panel_theme', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Expertise Area:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('panel_expertise', '')}</td>
                        </tr>
                    </table>
                </div>

                <!-- Next Steps -->
                <div style="background: linear-gradient(135deg, #fef3c7, #fde68a); border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">
                        <i class="fas fa-clipboard-list"></i> Next Steps
                    </h4>
                    <ol style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                        <li style="margin-bottom: 10px;">Our team will contact you within 48 hours with detailed discussion points</li>
                        <li style="margin-bottom: 10px;">Please confirm your availability and participation</li>
                        <li style="margin-bottom: 10px;">Prepare a brief introduction (2-3 minutes) about yourself</li>
                        <li style="margin-bottom: 10px;">Review any preparatory materials sent by our team</li>
                        <li>Arrive 45 minutes before your panel session for briefing</li>
                    </ol>
                </div>

                <!-- Event Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📅 Event Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                            <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                            <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Reporting Time:</strong></td>
                            <td style="padding: 8px 0;">45 minutes before panel session</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Dress Code:</strong></td>
                            <td style="padding: 8px 0;">Professional/Business Attire</td>
                        </tr>
                    </table>
                </div>

                <!-- Schedule -->
                <div style="margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">⏰ Event Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white;">
                                <th style="padding: 15px; text-align: left;">Time</th>
                                <th style="padding: 15px; text-align: left;">Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html}
                        </tbody>
                    </table>
                </div>

                <!-- Important Information -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">⚠️ Important Information</h4>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                        <li style="margin-bottom: 8px;">Please arrive at the venue 45 minutes before your panel session</li>
                        <li style="margin-bottom: 8px;">Professional/business attire is mandatory</li>
                        <li style="margin-bottom: 8px;">Wi-Fi credentials will be provided at the registration desk</li>
                        <li style="margin-bottom: 8px;">Lunch and refreshments will be served to all panelists</li>
                        <li>Parking is available near Gate No. 1 (reserved for panelists)</li>
                    </ul>
                </div>

                <!-- Recognition -->
                <div style="background: linear-gradient(135deg, #dbeafe, #93c5fd); border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1e40af; margin-top: 0;">
                        <i class="fas fa-award"></i> Panelist Recognition
                    </h4>
                    <p style="color: #1e40af; margin: 10px 0;">
                        As a panelist, you will receive:
                    </p>
                    <div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 10px; margin-top: 15px;">
                        <span style="background: white; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; color: #1e40af;">
                            🏆 Panelist Certificate
                        </span>
                        <span style="background: white; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; color: #1e40af;">
                            📸 Group Photos
                        </span>
                        <span style="background: white; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; color: #1e40af;">
                            🎁 Special Kit
                        </span>
                        <span style="background: white; padding: 8px 15px; border-radius: 20px; font-size: 12px; font-weight: bold; color: #1e40af;">
                            💼 Networking Opportunities
                        </span>
                    </div>
                </div>

                <!-- Contact Information -->
                <div style="background: #f3f4f6; border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0;">📞 Need Assistance?</h4>
                    <p style="margin: 10px 0;">
                        For any questions regarding your panel participation:<br>
                        <strong>Panel Coordinator:</strong> {event.get('contact', {}).get('tpo_name', 'Dr Hemanath Dussa')}<br>
                        <strong>Email:</strong> {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}<br>
                        <strong>Phone:</strong> {event.get('contact', {}).get('phone', '+91-9121001921')}
                    </p>
                    <a href="https://maps.app.goo.gl/?link=https://maps.google.com/?q=Sphoorthy+Engineering+College+Nadergul+Hyderabad"
                       style="display: inline-block; background: #1a56db; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin-top: 10px;">
                        📍 Venue Location
                    </a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p>We are excited to have you as part of our distinguished panel!</p>
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        This is an official panel acceptance email. Please do not reply to this address.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Panel acceptance email sent to {hr_data['office_email']}")
        return True

    except Exception as e:
        print(f"✗ Panel email sending error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def send_bulk_custom_email(hr_data, email_subject, email_message):
    """Send bulk custom email with consistent professional format"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data.get('office_email', '')
        
        if not msg['To'] or '@' not in msg['To']:
            print(f"Invalid email address: {msg['To']}")
            return False
        
        msg['Subject'] = email_subject
        
        # SMART GREETING
        hr_name = hr_data.get('full_name', '')
        organization = hr_data.get('organization', '')
        
        if not hr_name or hr_name == 'N/A' or hr_name.strip() == '':
            greeting_name = f"{organization} Team" if organization else "HR Professional"
        else:
            greeting_name = hr_name
        
        # Get event data for consistent formatting
        event = get_event_data()
        
        # Schedule HTML
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """
        
        # Personalize message
        personalized_message = email_message
        personalized_message = personalized_message.replace('[[name]]', hr_name if hr_name else '')
        personalized_message = personalized_message.replace('[[organization]]', organization if organization else '')
        personalized_message = personalized_message.replace('[[designation]]', hr_data.get('designation', ''))
        personalized_message = personalized_message.replace('[[registration_id]]', hr_data.get('registration_id', hr_data.get('id', '')))
        personalized_message = personalized_message.replace('[[city]]', hr_data.get('city', ''))
        personalized_message = personalized_message.replace('[[greeting]]', greeting_name)  # SMART GREETING
        personalized_message = personalized_message.replace('\n', '<br>')
        
        # Email body with consistent format
        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HR Conclave 2026 - Update</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                    .action-button {{ width: 100% !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">HR Conclave 2026 Update</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">Connecting the Future</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Personalized Section -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: #1a56db; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ✉️
                    </div>
                    <h2 style="color: #1a56db; margin: 0;">Dear {greeting_name}!</h2>
                    <p style="margin: 10px 0; color: #4b5563;">
                        Important update regarding your participation in HR Conclave 2026
                    </p>
                </div>

                <!-- Message Card -->
                <div style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 15px; padding: 25px; margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; margin-bottom: 20px;">
                        <i class="fas fa-bullhorn"></i> Message from Organizing Committee
                    </h3>
                    
                    <div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; line-height: 1.6;">
                        {personalized_message}
                    </div>
                    
                    <!-- Registration Info -->
                    <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; margin-top: 20px;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #1a56db;">
                            <i class="fas fa-user-circle"></i> Your Registration Details:
                        </p>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 5px 0; width: 120px;"><strong>Name:</strong></td>
                                <td style="padding: 5px 0;">{hr_data.get('full_name', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Organization:</strong></td>
                                <td style="padding: 5px 0;">{hr_data.get('organization', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Designation:</strong></td>
                                <td style="padding: 5px 0;">{hr_data.get('designation', 'N/A')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Registration ID:</strong></td>
                                <td style="padding: 5px 0; font-weight: bold; color: #7e22ce;">
                                    {hr_data.get('registration_id', hr_data.get('id', 'Not assigned'))}
                                </td>
                            </tr>
                        </table>
                    </div>
                </div>

                <!-- Quick Actions -->
                <div style="background: linear-gradient(135deg, #f0f9ff, #e0f2fe); border-radius: 10px; padding: 20px; margin: 25px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0; margin-bottom: 15px;">
                        <i class="fas fa-bolt"></i> Quick Actions
                    </h4>
                    
                    <div style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;">
                        <a href="{request.host_url}registration/thank-you?reg_id={hr_data.get('registration_id', hr_data.get('id', ''))}"
                           style="background: #10b981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 14px; margin: 5px;">
                            🔍 Check Registration Status
                        </a>
                        
                        <a href="{request.host_url}event-schedule"
                           style="background: #1a56db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 14px; margin: 5px;">
                            📅 View Event Schedule
                        </a>
                        
                        <a href="https://maps.app.goo.gl/?link=https://maps.google.com/?q=Sphoorthy+Engineering+College+Nadergul+Hyderabad"
                           style="background: #7e22ce; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 14px; margin: 5px;">
                            📍 Get Directions
                        </a>
                    </div>
                </div>

                <!-- Event Reminder -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">
                        <i class="fas fa-calendar-check"></i> Event Details
                    </h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                            <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Time:</strong></td>
                            <td style="padding: 8px 0;">9:00 AM - 5:00 PM</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                            <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Location:</strong></td>
                            <td style="padding: 8px 0;">Nadergul, Hyderabad</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Theme:</strong></td>
                            <td style="padding: 8px 0;">Connecting the Future</td>
                        </tr>
                    </table>
                </div>

                <!-- Schedule Preview -->
                <div style="margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">
                        <i class="fas fa-clock"></i> Event Schedule (Preview)
                    </h3>
                    <div style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px;">
                        <table style="width: 100%; border-collapse: collapse; background: white;">
                            <thead>
                                <tr style="background: #f3f4f6;">
                                    <th style="padding: 12px; text-align: left; font-size: 14px;">Time</th>
                                    <th style="padding: 12px; text-align: left; font-size: 14px;">Activity</th>
                                </tr>
                            </thead>
                            <tbody>
                                {schedule_html[:5]}  <!-- Show only first 5 schedule items -->
                            </tbody>
                        </table>
                    </div>
                    <p style="text-align: center; margin-top: 10px; font-size: 13px; color: #64748b;">
                        <i class="fas fa-external-link-alt"></i> 
                        <a href="{request.host_url}event-schedule" style="color: #1a56db;">View full schedule on website</a>
                    </p>
                </div>

                <!-- Important Information -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">
                        <i class="fas fa-info-circle"></i> Important Information
                    </h4>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                        <li style="margin-bottom: 8px;">Registration/Check-in starts at 8:30 AM</li>
                        <li style="margin-bottom: 8px;">Carry government-issued ID for verification</li>
                        <li style="margin-bottom: 8px;">Parking available at Gate No. 1</li>
                        <li style="margin-bottom: 8px;">Professional attire recommended</li>
                        <li>Wi-Fi credentials provided at registration desk</li>
                    </ul>
                </div>

                <!-- Contact Information -->
                <div style="background: #f3f4f6; border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0;">📞 Contact & Support</h4>
                    <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; margin-top: 15px;">
                        <div style="text-align: center;">
                            <div style="background: #1a56db; color: white; width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                                👤
                            </div>
                            <p style="margin: 5px 0; font-weight: bold;">TPO Contact</p>
                            <p style="margin: 5px 0; font-size: 14px;">
                                {event.get('contact', {}).get('tpo_name', 'Dr Hemanath Dussa')}
                            </p>
                        </div>
                        
                        <div style="text-align: center;">
                            <div style="background: #7e22ce; color: white; width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                                ✉️
                            </div>
                            <p style="margin: 5px 0; font-weight: bold;">Email</p>
                            <p style="margin: 5px 0; font-size: 14px;">
                                {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}
                            </p>
                        </div>
                        
                        <div style="text-align: center;">
                            <div style="background: #10b981; color: white; width: 40px; height: 40px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 8px;">
                                📞
                            </div>
                            <p style="margin: 5px 0; font-weight: bold;">Phone</p>
                            <p style="margin: 5px 0; font-size: 14px;">
                                {event.get('contact', {}).get('phone', '+91-9121001921')}
                            </p>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px;">
                        <a href="{event.get('contact', {}).get('college_linkedin', 'https://www.linkedin.com/in/sphoorthy-engineering-college/')}"
                           style="display: inline-block; background: #0077b5; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                            <i class="fab fa-linkedin"></i> Follow on LinkedIn
                        </a>
                        
                        <a href="https://maps.app.goo.gl/?link=https://maps.google.com/?q=Sphoorthy+Engineering+College+Nadergul+Hyderabad"
                           style="display: inline-block; background: #1a56db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                            📍 Get Directions
                        </a>
                    </div>
                </div>

                <!-- Response Required (if applicable) -->
                <div style="background: linear-gradient(135deg, #dbeafe, #93c5fd); border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1e40af; margin-top: 0; margin-bottom: 15px;">
                        <i class="fas fa-exclamation-circle"></i> Action Required
                    </h4>
                    <p style="color: #1e40af; margin-bottom: 15px;">
                        If this message requires a response or confirmation, please reply to this email or contact us using the information above.
                    </p>
                    <a href="mailto:{event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}?subject=Regarding: {email_subject}"
                       style="background: white; color: #1e40af; padding: 10px 25px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; border: 2px solid #1e40af;">
                       📧 Reply to this Email
                    </a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p>Thank you for being part of HR Conclave 2026!</p>
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                    
                    <div style="margin-top: 20px; padding: 15px; background: #f8fafc; border-radius: 8px;">
                        <p style="margin: 0; font-size: 12px; color: #64748b;">
                            <i class="fas fa-shield-alt"></i> This is an official communication from HR Conclave 2026 Organizing Committee.<br>
                            Please do not reply to this automated address. For inquiries, use the contact information above.
                        </p>
                    </div>
                    
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        © 2026 HR Conclave. All rights reserved.<br>
                        Sphoorthy Engineering College, Nadergul, Hyderabad
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Bulk custom email sent to {hr_data.get('office_email', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"✗ Bulk email sending error to {hr_data.get('office_email', 'unknown')}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False  
def send_confirmation_approval_email(hr_data, approval_details=None):
    """Send detailed confirmation email after admin approval with QR code attached"""
    try:
        event = get_event_data()

        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data['office_email']
        msg['Subject'] = f'🎉 Approved! Your Registration for HR Conclave 2026 - ID: {hr_data.get("registration_id", "")}'

        # Generate QR code
        qr_code_data = None
        qr_image_data = None

        try:
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr_string = f"HRC26|{hr_data.get('registration_id', '')}|{hr_data.get('full_name', '')}|{hr_data.get('office_email', '')}|{hr_data.get('organization', '')}"
            qr.add_data(qr_string)
            qr.make(fit=True)

            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Convert to bytes
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_image_data = qr_buffer.getvalue()

            # Convert to base64 for HTML embedding
            qr_code_data = base64.b64encode(qr_image_data).decode()

        except Exception as qr_error:
            print(f"QR generation error for email: {qr_error}")
            qr_code_data = None
            qr_image_data = None

        # Get schedule for the day
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """

        # Get status indicator based on approval
        status_color = "#10b981"  # green for approved
        status_text = "✅ Approved"
        status_message = "Your registration has been <strong>approved</strong> by our organizing committee."

        # Email body with consistent format
        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HR Conclave 2026 - Registration Approved</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                    .qr-code {{ width: 200px !important; height: 200px !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">✅ Registration Approved!</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">HR Conclave 2026 - Connecting the Future</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Congratulations -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: {status_color}; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ✓
                    </div>
                    <h2 style="color: #1a56db; margin: 0;">Congratulations {hr_data.get('full_name', '')}!</h2>
                    <p style="margin: 10px 0; color: #4b5563;">
                        {status_message}
                    </p>
                </div>

                <!-- QR Code Section -->
                <div style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 15px; padding: 25px; text-align: center; margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; margin-bottom: 20px;">
                        <i class="fas fa-qrcode"></i> Your Check-in QR Code
                    </h3>

                    <div style="margin-bottom: 20px;">
                        {"<img src='cid:registration_qr' alt='Registration QR Code' style='width: 250px; height: 250px; border: 5px solid white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);' class='qr-code'>" if qr_code_data else "<div style='background: #e2e8f0; width: 250px; height: 250px; margin: 0 auto; border-radius: 10px; display: flex; align-items: center; justify-content: center;'><span style='color: #64748b;'>QR Code Attached</span></div>"}
                    </div>

                    <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 20px;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #1a56db;">Registration ID:</p>
                        <p style="margin: 0; font-family: monospace; font-size: 18px; font-weight: bold; color: #7e22ce;">
                            {hr_data.get('registration_id', '')}
                        </p>
                        <p style="margin: 15px 0 0 0; font-size: 14px; color: #64748b;">
                            <i class="fas fa-info-circle"></i> Show this QR code at registration desk for quick check-in
                        </p>
                    </div>

                    <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                        <p style="margin: 0; font-size: 13px; color: #64748b;">
                            <strong>Tip:</strong> Save this QR code to your phone or print it for easy access
                        </p>
                    </div>
                </div>

                <!-- Registration Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📋 Registration Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 150px;"><strong>Registration ID:</strong></td>
                            <td style="padding: 8px 0; font-weight: bold; color: #1a56db;">{hr_data.get('registration_id', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Name:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('full_name', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Organization:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('organization', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Designation:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('designation', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Email:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('office_email', '')}</td>
                        </tr>
                    </table>
                </div>

                <!-- Event Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📅 Event Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                            <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Time:</strong></td>
                            <td style="padding: 8px 0;">9:00 AM - 5:00 PM</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                            <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Location:</strong></td>
                            <td style="padding: 8px 0;">Nadergul, Hyderabad</td>
                        </tr>
                    </table>
                </div>

                <!-- Schedule -->
                <div style="margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">⏰ Detailed Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white;">
                                <th style="padding: 15px; text-align: left;">Time</th>
                                <th style="padding: 15px; text-align: left;">Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html}
                        </tbody>
                    </table>
                </div>

                <!-- Status Badge -->
                <div style="background: #d1fae5; border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #065f46; margin-top: 0;">
                        <i class="fas fa-badge-check"></i> Registration Status
                    </h4>
                    <div style="display: flex; align-items: center; gap: 15px; margin-top: 10px;">
                        <span style="background: #10b981; color: white; padding: 8px 20px; border-radius: 20px; font-weight: bold;">
                            ✅ Approved & Confirmed
                        </span>
                        <span style="color: #065f46; font-weight: bold;">
                            Your spot is reserved!
                        </span>
                    </div>
                    <p style="margin: 15px 0 0 0; color: #065f46;">
                        <i class="fas fa-check-circle"></i> Your registration is complete and approved. We look forward to seeing you at the event!
                    </p>
                </div>

                <!-- QR Code Instructions -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">
                        <i class="fas fa-qrcode"></i> How to Use Your QR Code
                    </h4>
                    <ol style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                        <li style="margin-bottom: 8px;">Save this QR code on your phone or print it</li>
                        <li style="margin-bottom: 8px;">Show it at the registration desk during check-in</li>
                        <li style="margin-bottom: 8px;">Our team will scan it to mark your attendance</li>
                        <li>Collect your event badge and materials after scanning</li>
                    </ol>
                </div>

                <!-- Important Notes -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">⚠️ Important Information</h4>
                    <ul style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                        <li>Please arrive 30 minutes before the event starts</li>
                        <li>Carry a government-issued ID for verification</li>
                        <li>Parking available at Gate No. 1</li>
                        <li>Wi-Fi credentials will be provided at registration</li>
                        <li>Lunch will be served at 1:00 PM in the cafeteria</li>
                    </ul>
                </div>

                <!-- Contact Information -->
                <div style="background: #f3f4f6; border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0;">📞 Need Help?</h4>
                    <p style="margin: 10px 0;">
                        <strong>TPO:</strong> {event.get('contact', {}).get('tpo_name', 'Dr Hemanath Dussa')}<br>
                        <strong>Email:</strong> {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}<br>
                        <strong>Phone:</strong> {event.get('contact', {}).get('phone', '+91-9121001921')}
                    </p>
                    <a href="https://maps.app.goo.gl/?link=https://maps.google.com/?q=Sphoorthy+Engineering+College+Nadergul+Hyderabad"
                       style="display: inline-block; background: #1a56db; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin-top: 10px;">
                        📍 Open in Google Maps
                    </a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p>We look forward to welcoming you at HR Conclave 2026!</p>
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        This is an automated confirmation email. Please do not reply to this address.<br>
                        For queries, contact: placements@sphoorthyengg.ac.in
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Attach QR code as inline image
        if qr_image_data:
            qr_attachment = MIMEImage(qr_image_data, name=f"{hr_data.get('registration_id', 'registration')}_qr.png")
            qr_attachment.add_header('Content-ID', '<registration_qr>')
            qr_attachment.add_header('Content-Disposition', 'inline; filename="registration_qr.png"')
            msg.attach(qr_attachment)

        # Also attach QR code as downloadable file
        if qr_image_data:
            qr_file = MIMEBase('application', 'octet-stream')
            qr_file.set_payload(qr_image_data)
            encoders.encode_base64(qr_file)
            qr_file.add_header('Content-Disposition',
                              f'attachment; filename="HRC26_{hr_data.get("registration_id", "")}_QR.png"')
            msg.attach(qr_file)

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Confirmation email with QR code sent to {hr_data['office_email']}")
        return True

    except Exception as e:
        print(f"✗ Email sending error: {str(e)}")
        traceback.print_exc()
        return False

@app.route('/admin/send-bulk-email-fast', methods=['POST'])
def send_bulk_email_fast_endpoint():
    """Fast bulk email sending endpoint using threading"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        # Get form data
        data = request.get_json()
        hr_ids = data.get('hr_ids', [])
        email_type = data.get('email_type', 'invitation')  # invitation or reminder
        
        if not hr_ids:
            return jsonify({'success': False, 'error': 'No recipients selected'})

        # Load HR data
        hr_pending_data = load_db('hr_pending_data')
        hr_registrations = load_db('hr_registrations')
        
        # Collect HR data
        hr_list = []
        for hr_id in hr_ids:
            hr = None
            if hr_id in hr_pending_data:
                hr = hr_pending_data[hr_id]
            elif hr_id in hr_registrations:
                hr = hr_registrations[hr_id]
            
            if hr and hr.get('office_email'):
                hr_list.append(hr)
        
        if not hr_list:
            return jsonify({'success': False, 'error': 'No valid recipients found'})

        # Use threading for parallel sending
        print(f"Starting fast email sending for {len(hr_list)} recipients...")
        start_time = datetime.now()
        
        # Prepare email sending function
        def send_single_email(hr_data):
            try:
                # Generate invitation URL
                invitation_token = secrets.token_urlsafe(32)
                invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"
                
                if email_type == 'invitation':
                    # Use your existing send_invitation_email_v2 function
                    return send_invitation_email_v2(hr_data, invitation_url)
                else:
                    # Use your existing send_bulk_custom_email function with reminder template
                    subject = "Reminder | HR Conclave 2026 - Complete Your Registration"
                    message = f"""Dear {hr_data.get('full_name', 'HR Professional')},

This is a reminder to complete your registration for HR Conclave 2026.

Please use this link to complete your registration: {invitation_url}

Event Details:
Date: February 7, 2026
Time: 9:00 AM - 5:00 PM
Venue: Sphoorthy Engineering College, Hyderabad

Best regards,
HR Conclave 2026 Organizing Committee"""
                    return send_bulk_custom_email(hr_data, subject, message)
                    
            except Exception as e:
                print(f"Error sending to {hr_data.get('office_email', 'unknown')}: {str(e)}")
                return False
        
        # Use threading for parallel sending
        import concurrent.futures
        
        sent_count = 0
        max_workers = 10  # Number of concurrent emails
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all email sending tasks
            future_to_hr = {executor.submit(send_single_email, hr): hr for hr in hr_list}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_hr):
                hr = future_to_hr[future]
                try:
                    result = future.result(timeout=30)
                    if result:
                        sent_count += 1
                        
                        # Update invitation status if this is a new invitation
                        if email_type == 'invitation':
                            hr_id = hr.get('id')
                            if hr_id and hr_id in hr_pending_data:
                                hr_pending_data[hr_id]['invitation_sent'] = True
                                hr_pending_data[hr_id]['invitation_sent_at'] = datetime.now().isoformat()
                                hr_pending_data[hr_id]['invitation_token'] = secrets.token_urlsafe(32)
                                hr_pending_data[hr_id]['status'] = 'invitation_sent'
                                
                except Exception as e:
                    print(f"Error processing email: {str(e)}")
        
        # Save updated pending data
        if email_type == 'invitation':
            save_db('hr_pending_data', hr_pending_data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"Email sending completed in {duration:.2f} seconds")
        print(f"Sent: {sent_count}, Failed: {len(hr_list) - sent_count}")
        print(f"Average time per email: {duration/len(hr_list):.2f} seconds")
        
        # Log to history
        email_history = load_db('email_history')
        email_id = f"BULK_FAST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        email_history[email_id] = {
            'id': email_id,
            'email_type': email_type,
            'total_recipients': len(hr_list),
            'sent_count': sent_count,
            'failed_count': len(hr_list) - sent_count,
            'duration_seconds': duration,
            'average_time_per_email': duration/len(hr_list),
            'timestamp': datetime.now().isoformat(),
            'status': 'completed'
        }
        save_db('email_history', email_history)
        
        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'failed_count': len(hr_list) - sent_count,
            'duration_seconds': duration,
            'average_time_per_email': duration/len(hr_list),
            'message': f'Sent {sent_count} emails in {duration:.1f} seconds ({duration/len(hr_list):.2f}s each)'
        })

    except Exception as e:
        print(f"Fast bulk email error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
        

def send_confirmation_email(hr_data, pdf_path=None):
    """Send confirmation email to HR professional with QR code for ALL statuses"""
    
    # Check if email is properly configured
    if not EMAIL_CONFIG.get('EMAIL_PASSWORD') or EMAIL_CONFIG['EMAIL_PASSWORD'] == 'phns xmml nsqt ckue':
        print("⚠️ Email not configured properly - using fallback mode")
        print("📧 Email content would be:")
        print(f"Subject: Registration Received - HR Conclave 2026")
        print(f"To: {hr_data.get('office_email', 'No email')}")
        print(f"Name: {hr_data.get('full_name', 'No name')}")
        print(f"Registration ID: {hr_data.get('registration_id', 'No ID')}")

        # Save registration locally for reference
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{timestamp}] REG: {hr_data.get('registration_id', 'NO_ID')} | NAME: {hr_data.get('full_name', 'NO_NAME')} | EMAIL: {hr_data.get('office_email', 'NO_EMAIL')} | STATUS: {hr_data.get('approval_status', 'pending_review')}\n"

            with open('registrations_log.txt', 'a', encoding='utf-8') as f:
                f.write(log_entry)
            print(f"✓ Registration logged to local file")
        except Exception as e:
            print(f"✗ Failed to log registration: {e}")

        # Still generate QR code even without email
        try:
            generate_qr_for_registration(hr_data)
            print(f"✓ QR code generated for offline reference")
        except Exception as e:
            print(f"✗ QR generation failed: {e}")

        return True  # Return True to simulate success

    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data.get('office_email', '')

        if not msg['To'] or '@' not in msg['To']:
            print(f"✗ Invalid email address: {msg['To']}")
            return False

        # Set subject based on status
        status = hr_data.get('approval_status', 'pending_review')
        if status == 'approved':
            msg['Subject'] = '🎉 Registration Approved! - HR Conclave 2026'
        elif status == 'rejected':
            msg['Subject'] = 'HR Conclave 2026 - Registration Status Update'
        else:
            msg['Subject'] = 'Thank You for Registering - HR Conclave 2026'

        print(f"Email subject: {msg['Subject']}")

        # Generate QR code for ALL registrations
        qr_code_data = None
        qr_image_data = None

        try:
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr_string = f"HRC26|{hr_data.get('registration_id', '')}|{hr_data.get('full_name', '')}|{hr_data.get('office_email', '')}|{hr_data.get('organization', '')}"
            qr.add_data(qr_string)
            qr.make(fit=True)

            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Convert to bytes
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_image_data = qr_buffer.getvalue()

            # Convert to base64 for HTML embedding
            qr_code_data = base64.b64encode(qr_image_data).decode()
            print(f"✓ QR code generated successfully")

        except Exception as qr_error:
            print(f"✗ QR generation error: {qr_error}")
            qr_code_data = None
            qr_image_data = None

        # Get event data for email content
        event = get_event_data()

        # Generate registration link for status checking
        registration_link = f"{request.host_url}registration/thank-you?reg_id={hr_data.get('registration_id', '')}"

        # Schedule HTML
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """

        # Email body with QR code
        body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>HR Conclave 2026</title>
            <style>
                @media only screen and (max-width: 600px) {{
                    .mobile-center {{ text-align: center !important; }}
                    .mobile-block {{ display: block !important; width: 100% !important; }}
                    .mobile-padding {{ padding: 10px !important; }}
                    .qr-code {{ width: 200px !important; height: 200px !important; }}
                }}
            </style>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">{"✅ Registration Approved!" if status == 'approved' else "📝 Registration Received!" if status == 'pending_review' else "📋 Registration Update"}</h1>
                <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">HR Conclave 2026 - Connecting the Future</p>
            </div>

            <!-- Main Content -->
            <div style="max-width: 600px; margin: 0 auto; padding: 30px 20px;">

                <!-- Congratulations -->
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: #10b981; color: white; width: 60px; height: 60px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 30px; margin-bottom: 20px;">
                        ✓
                    </div>
                    <h2 style="color: #1a56db; margin: 0;">Congratulations {hr_data.get('full_name', '')}!</h2>
                    <p style="margin: 10px 0; color: #4b5563;">
                        {"Your registration has been <strong>approved</strong> by our organizing committee." if status == 'approved' else
                         "Thank you for registering for <strong>HR Conclave 2026</strong>! We're thrilled to have you join us." if status == 'pending_review' else
                         "Thank you for your interest in <strong>HR Conclave 2026</strong>."}
                    </p>
                </div>

                <!-- QR Code Section -->
                <div style="background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 15px; padding: 25px; text-align: center; margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; margin-bottom: 20px;">
                        <i class="fas fa-qrcode"></i> Your Check-in QR Code
                    </h3>

                    <div style="margin-bottom: 20px;">
                        {"<img src='cid:confirmation_qr' alt='Registration QR Code' style='width: 250px; height: 250px; border: 5px solid white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);' class='qr-code'>" if qr_code_data else "<div style='background: #e2e8f0; width: 250px; height: 250px; margin: 0 auto; border-radius: 10px; display: flex; align-items: center; justify-content: center;'><span style='color: #64748b;'>QR Code Available on Website</span></div>"}
                    </div>

                    <div style="background: white; padding: 15px; border-radius: 10px; margin-top: 20px;">
                        <p style="margin: 0 0 10px 0; font-weight: bold; color: #1a56db;">Registration ID:</p>
                        <p style="margin: 0; font-family: monospace; font-size: 18px; font-weight: bold; color: #7e22ce;">
                            {hr_data.get('registration_id', '')}
                        </p>
                        <p style="margin: 15px 0 0 0; font-size: 14px; color: #64748b;">
                            <i class="fas fa-info-circle"></i> Show this QR code at registration desk for quick check-in
                        </p>
                    </div>

                    <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                        <p style="margin: 0; font-size: 13px; color: #64748b;">
                            <strong>Tip:</strong> Save this QR code to your phone or print it for easy access
                        </p>
                    </div>
                </div>

                <!-- Registration Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📋 Registration Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 150px;"><strong>Registration ID:</strong></td>
                            <td style="padding: 8px 0; font-weight: bold; color: #1a56db;">{hr_data.get('registration_id', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Name:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('full_name', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Organization:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('organization', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Designation:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('designation', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Email:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('office_email', '')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Mobile:</strong></td>
                            <td style="padding: 8px 0;">{hr_data.get('mobile', '')}</td>
                        </tr>
                    </table>
                </div>

                <!-- Event Details -->
                <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                    <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📅 Event Details</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                            <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Time:</strong></td>
                            <td style="padding: 8px 0;">9:00 AM - 5:00 PM</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                            <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0;"><strong>Location:</strong></td>
                            <td style="padding: 8px 0;">Nadergul, Hyderabad</td>
                        </tr>
                    </table>
                </div>

                <!-- Schedule -->
                <div style="margin: 30px 0;">
                    <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">⏰ Detailed Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white;">
                                <th style="padding: 15px; text-align: left;">Time</th>
                                <th style="padding: 15px; text-align: left;">Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html}
                        </tbody>
                    </table>
                </div>

                <!-- Registration Status -->
                <div style="background: {"#d1fae5" if status == 'approved' else "#fef3c7" if status == 'pending_review' else "#fee2e2"};
                         border-left: 4px solid {"#10b981" if status == 'approved' else "#f59e0b" if status == 'pending_review' else "#dc2626"};
                         padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: {"#065f46" if status == 'approved' else "#92400e" if status == 'pending_review' else "#991b1b"}; margin-top: 0;">
                        <i class="fas fa-info-circle"></i> Registration Status
                    </h4>
                    <p style="margin: 8px 0;">
                        <strong>Current Status:</strong>
                        <span style="background: {"#10b981" if status == 'approved' else "#f59e0b" if status == 'pending_review' else "#dc2626"};
                                 color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold;">
                            {"✅ Approved" if status == 'approved' else "⏳ Under Review" if status == 'pending_review' else "❌ Not Approved"}
                        </span>
                    </p>
                    <p style="margin: 8px 0; color: {"#065f46" if status == 'approved' else "#92400e" if status == 'pending_review' else "#991b1b"};">
                        {"Your spot is confirmed! We look forward to seeing you at the event." if status == 'approved' else
                         "Your registration is being reviewed by our organizing committee. You'll receive an update within 24-48 hours." if status == 'pending_review' else
                         "Due to limited seating capacity, we couldn't approve your registration at this time."}
                    </p>
                </div>

                <!-- Check Status Button -->
                <div style="text-align: center; margin: 30px 0; padding: 20px; background: linear-gradient(135deg, #f8fafc, #e2e8f0); border-radius: 10px;">
                    <h3 style="color: #1a56db; margin-bottom: 15px;">Check Your Registration Status</h3>
                    <p style="margin-bottom: 20px; color: #4b5563;">
                        You can check your registration status anytime using the link below:
                    </p>
                    <a href="{registration_link}"
                       style="background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold; font-size: 16px; margin: 10px 0;">
                        🔍 Check Registration Status
                    </a>
                </div>

                <!-- Important Notes -->
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 20px; border-radius: 8px; margin: 30px 0;">
                    <h4 style="color: #92400e; margin-top: 0;">⚠️ Important Information</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>Please arrive 30 minutes before the event starts</li>
                        <li>Carry a government-issued ID for verification</li>
                        <li>Parking available at Gate No. 1</li>
                        <li>Wi-Fi credentials will be provided at registration</li>
                        <li>Lunch will be served at 1:00 PM in the cafeteria</li>
                    </ul>
                </div>

                <!-- Contact Information -->
                <div style="background: #f3f4f6; border-radius: 10px; padding: 20px; margin: 30px 0; text-align: center;">
                    <h4 style="color: #1a56db; margin-top: 0;">📞 Need Help?</h4>
                    <p style="margin: 10px 0;">
                        <strong>TPO:</strong> {event.get('contact', {}).get('tpo_name', 'Dr Hemanath Dussa')}<br>
                        <strong>Email:</strong> {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}<br>
                        <strong>Phone:</strong> {event.get('contact', {}).get('phone', '+91-9121001921')}
                    </p>
                    <a href="https://maps.app.goo.gl/?link=https://maps.google.com/?q=Sphoorthy+Engineering+College+Nadergul+Hyderabad"
                       style="display: inline-block; background: #1a56db; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; margin-top: 10px;">
                        📍 Open in Google Maps
                    </a>
                </div>

                <!-- Footer -->
                <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                    <p>We look forward to welcoming you at HR Conclave 2026!</p>
                    <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                    Sphoorthy Engineering College</p>
                    <p style="font-size: 12px; color: #999; margin-top: 20px;">
                        This is an automated confirmation email. Please do not reply to this address.<br>
                        For queries, contact: placements@sphoorthyengg.ac.in
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(body, 'html'))

        # Attach QR code as inline image
        if qr_image_data:
            qr_attachment = MIMEImage(qr_image_data, name=f"{hr_data.get('registration_id', 'registration')}_qr.png")
            qr_attachment.add_header('Content-ID', '<confirmation_qr>')
            qr_attachment.add_header('Content-Disposition', 'inline; filename="registration_qr.png"')
            msg.attach(qr_attachment)

        # Also attach QR code as downloadable file for ALL registrations
        if qr_image_data:
            qr_file = MIMEBase('application', 'octet-stream')
            qr_file.set_payload(qr_image_data)
            encoders.encode_base64(qr_file)
            qr_file.add_header('Content-Disposition',
                              f'attachment; filename="HRC26_{hr_data.get("registration_id", "")}_Registration_QR.png"')
            msg.attach(qr_file)

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Email sent successfully to {hr_data['office_email']}")

        # Log email in history
        log_email_history(hr_data, 'confirmation', True)

        return True

    except Exception as e:
        print(f"✗ Email sending error: {str(e)}")

        # Log failed email attempt
        log_email_history(hr_data, 'confirmation', False, str(e))

        # Save to local file as backup
        try:
            error_log = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {hr_data.get('registration_id', 'NO_ID')} | {hr_data.get('office_email', 'NO_EMAIL')} | {str(e)[:100]}\n"
            with open('email_errors.log', 'a', encoding='utf-8') as f:
                f.write(error_log)
        except:
            pass

        return False
    

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    stats = calculate_stats()
    event = get_event_data()

    # Recent registrations
    hr_registrations = load_db('hr_registrations')
    recent_registrations = []
    for hr in hr_registrations.values():
        if hr.get('status') == 'registered' and 'registered_at' in hr:
            recent_registrations.append(hr)

    recent_registrations = sorted(
        recent_registrations,
        key=lambda x: x.get('registered_at', ''),
        reverse=True
    )[:10]

    # Pending invitations
    hr_pending_data = load_db('hr_pending_data')
    pending_invitations = [
        hr for hr in hr_pending_data.values()
        if not hr.get('invitation_sent', False)
    ][:5]

    # Company distribution
    companies = {}
    for hr in hr_registrations.values():
        if hr.get('status') == 'registered':
            org = hr.get('organization', 'Unknown')
            companies[org] = companies.get(org, 0) + 1

    return render_template('admin_dashboard.html',
                         stats=stats,
                         recent_registrations=recent_registrations,
                         pending_invitations=pending_invitations,
                         companies=companies,
                         event=event)

@app.route('/admin/send-selected-invitations', methods=['POST'])
def send_selected_invitations():
    """Send invitations to selected HR professionals"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        hr_ids = data.get('hr_ids', [])
        custom_subject = data.get('subject', '')
        custom_message = data.get('message', '')

        if not hr_ids:
            return jsonify({'success': False, 'error': 'No HR selected'}), 400

        hr_registrations = load_db('hr_registrations')

        sent_count = 0
        errors = []

        for hr_id in hr_ids:
            if hr_id in hr_registrations:
                hr = hr_registrations[hr_id]
                try:
                    # Generate unique invitation URL
                    invitation_token = secrets.token_urlsafe(32)
                    invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"

                    # Send email with custom content
                    email_sent = send_custom_invitation_email(
                        hr,
                        invitation_url,
                        custom_subject,
                        custom_message
                    )

                    if email_sent:
                        # Update HR record
                        hr['invitation_sent'] = True
                        hr['invitation_sent_at'] = datetime.now().isoformat()
                        hr['invitation_token'] = invitation_token
                        hr['invitation_url'] = invitation_url
                        hr['status'] = 'invitation_sent'

                        hr_registrations[hr_id] = hr
                        sent_count += 1
                    else:
                        errors.append(f"Failed to send email to {hr.get('office_email', 'Unknown email')}")

                except Exception as e:
                    errors.append(f"Error sending to {hr.get('office_email', 'Unknown email')}: {str(e)}")

        save_db('hr_registrations', hr_registrations)

        if errors:
            return jsonify({
                'success': True,
                'sent_count': sent_count,
                'message': f'Sent {sent_count} invitations. Some errors occurred.',
                'errors': errors[:5]
            })

        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Successfully sent {sent_count} invitations to selected HR professionals'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/resend-invitations', methods=['POST'])
def resend_invitations():
    """Resend invitations to all sent HRs"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')
        resent_count = 0

        for hr_id, hr in hr_registrations.items():
            if hr.get('invitation_sent') and not hr.get('registration_complete'):
                if send_invitation_email_v2(hr):
                    hr['invitation_sent'] = True
                    hr['invitation_sent_at'] = datetime.now().isoformat()
                    resent_count += 1

        save_db('hr_registrations', hr_registrations)

        return jsonify({
            'success': True,
            'message': f'Invitations resent to {resent_count} HR professionals'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/export-invitations', methods=['GET'])
def export_invitations():
    """Export invitations to CSV"""
    try:
        hr_registrations = load_db('hr_registrations')

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write headers
        writer.writerow(['ID', 'Name', 'Email', 'Organization', 'Designation',
                         'Mobile', 'Status', 'Invitation Sent At', 'Completed At',
                         'Registration ID', 'Invitation URL'])

        # Write data
        for hr_id, hr in hr_registrations.items():
            status = 'Completed' if hr.get('registration_complete') else \
                    'Sent' if hr.get('invitation_sent') else 'Pending'

            invitation_sent_at = hr.get('invitation_sent_at', '')
            if invitation_sent_at and len(invitation_sent_at) >= 10:
                invitation_sent_at = invitation_sent_at[:10]

            completed_at = hr.get('completed_at', '')
            if completed_at and len(completed_at) >= 10:
                completed_at = completed_at[:10]

            writer.writerow([
                hr_id,
                hr.get('full_name', ''),
                hr.get('office_email', ''),
                hr.get('organization', ''),
                hr.get('designation', ''),
                hr.get('mobile', ''),
                status,
                invitation_sent_at,
                completed_at,
                hr.get('actual_registration_id', ''),
                hr.get('invitation_url', '')
            ])

        # Prepare response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment;filename=invitations_export.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )

    except Exception as e:
        flash(f'Error exporting: {str(e)}', 'error')
        return redirect(url_for('admin_invitations'))


# Add analytics dashboard
@app.route('/admin/analytics')
def admin_analytics():
    """Analytics dashboard"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    hr_registrations = load_db('hr_registrations')

    # Registration trends by date
    date_counts = {}
    for hr in hr_registrations.values():
        if hr.get('registered_at'):
            date = hr['registered_at'][:10]  # YYYY-MM-DD
            date_counts[date] = date_counts.get(date, 0) + 1

    # Company-wise distribution
    company_counts = {}
    for hr in hr_registrations.values():
        if hr.get('status') == 'registered':
            org = hr.get('organization', 'Unknown')
            company_counts[org] = company_counts.get(org, 0) + 1

    # City-wise distribution
    city_counts = {}
    for hr in hr_registrations.values():
        if hr.get('status') == 'registered':
            city = hr.get('city', 'Unknown')
            city_counts[city] = city_counts.get(city, 0) + 1

    # Panel participation
    panel_data = {
        'interested': sum(1 for hr in hr_registrations.values()
                         if hr.get('panel_interest') == 'Yes'),
        'not_interested': sum(1 for hr in hr_registrations.values()
                            if hr.get('panel_interest') == 'No'),
        'not_specified': sum(1 for hr in hr_registrations.values()
                           if not hr.get('panel_interest'))
    }

    # Attendance status
    attendance_data = {
        'confirmed': sum(1 for hr in hr_registrations.values()
                        if hr.get('attendance') == 'Yes, I plan to attend'),
        'tentative': sum(1 for hr in hr_registrations.values()
                        if hr.get('attendance') == 'Maybe'),
        'declined': sum(1 for hr in hr_registrations.values()
                       if hr.get('attendance') == 'No'),
        'not_specified': sum(1 for hr in hr_registrations.values()
                           if not hr.get('attendance'))
    }

    return render_template('admin_analytics.html',
                         date_counts=sorted(date_counts.items()),
                         company_counts=sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:10],
                         city_counts=sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10],
                         panel_data=panel_data,
                         attendance_data=attendance_data)

# Add email templates management
@app.route('/admin/email-templates')
def admin_email_templates():
    """Email templates management"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    # Default email templates
    templates = {
        'invitation': {
            'name': 'Invitation Email',
            'subject': 'Invitation to Register - HR Conclave 2026',
            'description': 'Sent to uploaded HR data for registration completion'
        },
        'confirmation': {
            'name': 'Confirmation Email',
            'subject': 'Registration Confirmation - HR Conclave 2026',
            'description': 'Sent after successful registration'
        },
        'reminder': {
            'name': 'Reminder Email',
            'subject': 'Reminder: Complete Your Registration - HR Conclave 2026',
            'description': 'Sent to pending registrations'
        }
    }

    return render_template('admin_email_templates.html', templates=templates)

# Add settings page
@app.route('/admin/settings')
def admin_settings():
    """Admin settings"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    event = get_event_data()
    admins = load_db('admins')

    return render_template('admin_settings.html',
                         event=event,
                         admins=admins,
                         email_config=EMAIL_CONFIG)

@app.route('/admin/update-event', methods=['POST'])
def update_event():
    """Update event details"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        events = load_db('events')
        event = events.get('hr_conclave_2026', {})

        # Update event details
        event['title'] = request.form.get('title', event.get('title', ''))
        event['date'] = request.form.get('date', event.get('date', ''))
        event['venue'] = request.form.get('venue', event.get('venue', ''))
        event['description'] = request.form.get('description', event.get('description', ''))

        # Update contact info
        if 'contact' not in event:
            event['contact'] = {}
        event['contact']['tpo_name'] = request.form.get('tpo_name', event.get('contact', {}).get('tpo_name', ''))
        event['contact']['tpo_email'] = request.form.get('tpo_email', event.get('contact', {}).get('tpo_email', ''))
        event['contact']['phone'] = request.form.get('phone', event.get('contact', {}).get('phone', ''))

        events['hr_conclave_2026'] = event
        save_db('events', events)

        return jsonify({'success': True, 'message': 'Event details updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/update-email-config', methods=['POST'])
def update_email_config():
    """Update email configuration"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        # In a real application, you would save this to a secure configuration file
        # For demo purposes, we'll just update the global variable
        global EMAIL_CONFIG
        EMAIL_CONFIG['EMAIL_USER'] = request.form.get('email_user', EMAIL_CONFIG['EMAIL_USER'])
        EMAIL_CONFIG['FROM_NAME'] = request.form.get('from_name', EMAIL_CONFIG['FROM_NAME'])
        EMAIL_CONFIG['FROM_EMAIL'] = request.form.get('from_email', EMAIL_CONFIG['FROM_EMAIL'])

        return jsonify({'success': True, 'message': 'Email configuration updated successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Add admin logout
@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.clear()
    return redirect(url_for('admin_login'))

# Update main function to ensure all templates are available
def create_template_files():
    """Create all necessary template files"""
    templates_dir = 'templates'
    os.makedirs(templates_dir, exist_ok=True)

    # List of required template files
    templates = [
        'admin_dashboard.html',
        'admin_upload_hr.html',
        'admin_registrations.html',
        'admin_invitations.html',
        'admin_analytics.html',
        'admin_email_templates.html',
        'admin_settings.html',
        'admin_map.html'
    ]

    # Create basic template files if they don't exist
    for template in templates:
        template_path = os.path.join(templates_dir, template)
        if not os.path.exists(template_path):
            with open(template_path, 'w') as f:
                f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - {template.replace('_', ' ').title()}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gray-100">
    <div class="min-h-screen">
        <nav class="bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg">
            <div class="container mx-auto px-4">
                <div class="flex justify-between items-center py-4">
                    <div class="flex items-center space-x-3">
                        <a href="{{ url_for('admin_dashboard') }}" class="text-xl font-bold">Admin Panel</a>
                        <span class="text-sm opacity-75">| {template.replace('_', ' ').title()}</span>
                    </div>
                    <div class="flex items-center space-x-4">
                        <span class="text-sm">Welcome, {{ session.get('name', 'Admin') }}</span>
                        <a href="{{ url_for('admin_logout') }}" class="bg-white text-blue-600 px-3 py-1 rounded hover:bg-blue-50">
                            Logout
                        </a>
                    </div>
                </div>
            </div>
        </nav>

        <div class="container mx-auto px-4 py-8">
            <h1 class="text-3xl font-bold text-gray-800 mb-6">{template.replace('_', ' ').title()}</h1>
            <div class="bg-white rounded-lg shadow p-6">
                <p class="text-gray-600">This page is under construction. Content will be added soon.</p>
            </div>
        </div>
    </div>
</body>
</html>""")





@app.route('/admin/export-registrations')
def export_registrations():
    """Export all registrations to Excel"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    try:
        hr_registrations = load_db('hr_registrations')

        if not hr_registrations:
            # Return empty Excel file
            df = pd.DataFrame(columns=['Registration ID', 'Name', 'Organization', 'Email', 'Mobile',
                                       'Designation', 'City', 'State', 'Attendance Status', 'Registered At'])
        else:
            # Prepare data
            data = []
            for reg_id, hr in hr_registrations.items():
                data.append({
                    'Registration ID': reg_id,
                    'Name': hr.get('full_name', ''),
                    'Organization': hr.get('organization', ''),
                    'Office Email': hr.get('office_email', ''),
                    'Personal Email': hr.get('personal_email', ''),
                    'Mobile': hr.get('mobile', ''),
                    'Designation': hr.get('designation', ''),
                    'City': hr.get('city', ''),
                    'State': hr.get('state', ''),
                    'Country': hr.get('country', ''),
                    'LinkedIn': hr.get('linkedin', ''),
                    'Website': hr.get('website', ''),
                    'Award Interest': hr.get('award_interest', ''),
                    'Panel Interest': hr.get('panel_interest', ''),
                    'Panel Theme': hr.get('panel_theme', ''),
                    'Source': hr.get('source', ''),
                    'Attendance': hr.get('attendance', ''),
                    'Registered At': hr.get('registered_at', ''),
                    'Email Sent': 'Yes' if hr.get('email_sent') else 'No'
                })

            df = pd.DataFrame(data)

        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Registrations', index=False)

            # Format
            workbook = writer.book
            worksheet = writer.sheets['Registrations']

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#1a56db',
                'font_color': 'white',
                'border': 1
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'hr_conclave_registrations_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )

    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

# ================= MAP NAVIGATION ROUTES =================

@app.route('/campus/navigation')
def campus_navigation():
    """Campus navigation page"""
    locations = load_db('locations')
    return render_template('navigation.html', locations=locations)


@app.route('/api/map/init')
def init_map():
    """Initialize campus map - satellite view disabled"""
    try:
        locations = load_db('locations')

        # Create map centered on college
        campus_map = folium.Map(
            location=[17.123456, 78.123456],
            zoom_start=17,
            tiles='cartodbpositron',  # Use street view only
            control_scale=True
        )

        # Disable satellite layer addition
        # Remove any code that adds satellite/terrain layers

        # Add markers
        for loc_id, location in locations.items():
            folium.Marker(
                location=location['coordinates'],
                popup=f"<b>{location['name']}</b><br>{location['description']}",
                tooltip=location['name'],
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(campus_map)

        # Add paths
        paths = load_db('paths')
        for path in paths:
            if path.get('path_points'):
                folium.PolyLine(
                    path['path_points'],
                    color='red',
                    weight=3,
                    opacity=0.7,
                    popup=f"{path['from']} to {path['to']}"
                ).add_to(campus_map)

        map_html = campus_map._repr_html_()

        return jsonify({
            'success': True,
            'map_html': map_html,
            'locations': locations,
            'satellite_disabled': True  # Add this flag
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/map')
def admin_map():
    """Admin map management"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    locations = load_db('locations')
    return render_template('admin_map.html', locations=locations)

# ================= OTHER ROUTES =================


from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime

@app.route('/api/download-schedule-pdf')
def download_schedule_pdf():
    """Generate PDF schedule for download"""
    try:
        # Get event data
        event = get_event_data()

        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               topMargin=0.5*inch, bottomMargin=0.5*inch,
                               leftMargin=0.5*inch, rightMargin=0.5*inch)

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1a56db'),
            alignment=1,
            spaceAfter=20
        )

        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#7e22ce'),
            spaceAfter=15
        )

        # Content
        content = []

        # Header
        content.append(Paragraph("HR Conclave 2026", title_style))
        content.append(Paragraph("Event Schedule", subtitle_style))
        content.append(Paragraph(f"Date: {event.get('date', 'February 7, 2026')}", styles['Normal']))
        content.append(Paragraph(f"Venue: {event.get('venue', 'Sphoorthy Engineering College, Hyderabad')}", styles['Normal']))
        content.append(Spacer(1, 20))

        # Schedule Table
        schedule_data = [['Time', 'Activity']]
        if 'schedule' in event:
            for item in event.get('schedule', []):
                schedule_data.append([
                    item.get('time', ''),
                    item.get('event', '')
                ])

        table = Table(schedule_data, colWidths=[150, 350])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
        ]))

        content.append(table)
        content.append(Spacer(1, 30))

        # Footer
        content.append(Paragraph("For more information:", styles['Normal']))
        content.append(Paragraph(f"Email: {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}", styles['Normal']))
        content.append(Paragraph(f"Phone: {event.get('contact', {}).get('phone', '+91-9121001921')}", styles['Normal']))
        content.append(Spacer(1, 20))
        content.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                               ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8)))

        # Build PDF
        doc.build(content)

        buffer.seek(0)

        # Send as PDF file
        return send_file(
            buffer,
            as_attachment=True,
            download_name='HR-Conclave-2026-Schedule.pdf',
            mimetype='application/pdf'
        )

    except Exception as e:
        print(f"PDF generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/event-schedule')
def event_schedule():
    """Event schedule page"""
    event = get_event_data()
    return render_template('event_schedule.html', event=event)

@app.route('/contact')
def contact():
    """Contact page"""
    event = get_event_data()
    return render_template('contact.html', contact=event.get('contact', {}))


@app.route('/admin/panel-discussion')
def admin_panel_discussion():
    """Admin panel discussion management"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    return render_template('admin_panel_discussion.html')


@app.route('/api/panel-participants')
def get_panel_participants():
    """Get all registrations interested in panel discussion"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_registrations = load_db('hr_registrations')

        # Filter for panel discussion interested participants
        panel_participants = []
        for reg_id, hr in hr_registrations.items():
            if hr.get('panel_interest') == 'Yes':
                participant = {
                    'registration_id': reg_id,
                    'full_name': hr.get('full_name', ''),
                    'office_email': hr.get('office_email', ''),
                    'mobile': hr.get('mobile', ''),
                    'organization': hr.get('organization', ''),
                    'designation': hr.get('designation', ''),
                    'panel_theme': hr.get('panel_theme', ''),
                    'panel_expertise': hr.get('panel_expertise', ''),
                    'panel_status': hr.get('panel_status', 'pending'),  # pending, accepted, rejected, invited
                    'registered_at': hr.get('registered_at', ''),
                    'profile_photo': hr.get('profile_photo', '')
                }
                panel_participants.append(participant)

        # Sort by registration date (newest first)
        panel_participants.sort(key=lambda x: x.get('registered_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'participants': panel_participants,
            'total': len(panel_participants)
        })

    except Exception as e:
        print(f"Error fetching panel participants: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update-panel-status/<registration_id>', methods=['POST'])
def update_panel_status(registration_id):
    """Update panel discussion status for a participant"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        status = data.get('status', 'pending')  # pending, accepted, rejected

        if status not in ['pending', 'accepted', 'rejected']:
            return jsonify({'success': False, 'error': 'Invalid status'})

        hr_registrations = load_db('hr_registrations')

        if registration_id in hr_registrations:
            hr = hr_registrations[registration_id]
            hr['panel_status'] = status
            hr['panel_status_updated_at'] = datetime.now().isoformat()
            hr['panel_status_updated_by'] = session.get('user_id', 'admin')

            save_db('hr_registrations', hr_registrations)

            return jsonify({
                'success': True,
                'message': f'Panel status updated to {status}'
            })
        else:
            return jsonify({'success': False, 'error': 'Registration not found'})

    except Exception as e:
        print(f"Error updating panel status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/send-panel-invites', methods=['POST'])
def send_panel_invites():
    """Send panel acceptance emails to selected participants"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        data = request.get_json()
        participant_ids = data.get('participant_ids', [])
        email_subject = data.get('subject', '')
        email_message = data.get('message', '')

        if not participant_ids:
            return jsonify({'success': False, 'error': 'No participants selected'})

        if not email_subject or not email_message:
            return jsonify({'success': False, 'error': 'Subject and message are required'})

        hr_registrations = load_db('hr_registrations')
        sent_count = 0
        errors = []

        for reg_id in participant_ids:
            if reg_id in hr_registrations:
                hr = hr_registrations[reg_id]

                # Check if already invited
                if hr.get('panel_status') == 'invited':
                    errors.append(f"{hr.get('full_name')} already invited")
                    continue

                # Send email
                if send_panel_acceptance_email(hr, email_subject, email_message):
                    # Update status
                    hr['panel_status'] = 'invited'
                    hr['panel_invite_sent_at'] = datetime.now().isoformat()
                    hr['panel_invite_sent_by'] = session.get('user_id', 'admin')
                    hr['panel_email_subject'] = email_subject

                    hr_registrations[reg_id] = hr
                    sent_count += 1
                    print(f"✓ Panel invite sent to {hr.get('full_name')}")
                else:
                    errors.append(f"Failed to send email to {hr.get('full_name')}")
            else:
                errors.append(f"Registration {reg_id} not found")

        # Save updated data
        save_db('hr_registrations', hr_registrations)

        # Log the email sending
        email_history = load_db('email_history')
        email_id = f"PANEL_INVITE_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        email_history[email_id] = {
            'email_id': email_id,
            'type': 'panel_acceptance',
            'subject': email_subject,
            'recipients': len(participant_ids),
            'sent_count': sent_count,
            'errors': errors,
            'sent_by': session.get('user_id', 'admin'),
            'timestamp': datetime.now().isoformat()
        }
        save_db('email_history', email_history)

        return jsonify({
            'success': True,
            'message': f'Panel acceptance emails sent to {sent_count} participants',
            'sent_count': sent_count,
            'errors': errors[:5] if errors else []
        })

    except Exception as e:
        print(f"Error sending panel invites: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/about')
def about():
    """About page"""
    event = get_event_data()
    return render_template('about.html', event=event)

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('index'))

# ================= TEMPLATE ROUTES =================

@app.route('/download/template')
def download_hr_template():
    """Download HR template Excel file"""
    try:
        # Create sample HR data
        hr_data = {
            'full_name': ['John Smith', 'Sarah Johnson'],
            'office_email': ['john@techsolutions.com', 'sarah@globalcorp.com'],
            'personal_email': ['john.personal@email.com', 'sarah.personal@email.com'],
            'mobile': ['+91-9876543210', '+91-9876543211'],
            'organization': ['Tech Solutions Inc.', 'Global Corp'],
            'designation': ['HR Manager', 'HR Director'],
            'city': ['Hyderabad', 'Bangalore'],
            'state': ['Telangana', 'Karnataka'],
            'country': ['India', 'India'],
            'linkedin': ['https://linkedin.com/in/johnsmith', 'https://linkedin.com/in/sarahjohnson'],
            'website': ['https://techsolutions.com', 'https://globalcorp.com']
        }

        # Create DataFrame
        df = pd.DataFrame(hr_data)

        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='HR Professionals', index=False)

            workbook = writer.book
            worksheet = writer.sheets['HR Professionals']

            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#1a56db',
                'font_color': 'white',
                'border': 1
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

        output.seek(0)

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='hr_conclave_template.xlsx'
        )

    except Exception as e:
        print(f"Template generation error: {str(e)}")
        # Return a simple error message
        return "Error generating template. Please try again later.", 500
# ================= INITIALIZATION =================

# ================= STATISTICS CALCULATION =================

def calculate_stats():
    """Calculate statistics for admin pages"""
    hr_pending_data = load_db('hr_pending_data')
    hr_registrations = load_db('hr_registrations')

    # Pending stats from pending data
    total_pending = sum(1 for hr in hr_pending_data.values()
                       if not hr.get('invitation_sent', False))
    total_invited = sum(1 for hr in hr_pending_data.values()
                       if hr.get('invitation_sent'))
    total_completed = sum(1 for hr in hr_pending_data.values()
                         if hr.get('registration_complete'))
    total_registered = len(hr_registrations)  # From registrations DB

    # Count today's registrations
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_registrations = 0
    for hr in hr_registrations.values():
        registered_at = hr.get('registered_at', '')
        if registered_at and registered_at.startswith(today_str):
            today_registrations += 1

    # Count unique companies (from both datasets)
    companies = set()
    for hr in hr_pending_data.values():
        org = hr.get('organization', '').strip()
        if org:
            companies.add(org)
    for hr in hr_registrations.values():
        org = hr.get('organization', '').strip()
        if org:
            companies.add(org)

    # Count panel participants (from registrations)
    panel_participants = sum(1 for hr in hr_registrations.values()
                           if hr.get('panel_interest') == 'Yes')

    # Count confirmed attendance (from registrations)
    confirmed_attendance = sum(1 for hr in hr_registrations.values()
                             if hr.get('attendance') == 'Yes, I plan to attend')

    # Count pending emails (from pending data)
    pending_emails = sum(1 for hr in hr_pending_data.values()
                        if not hr.get('invitation_sent', False))

    return {
        'total_pending': total_pending,
        'total_invited': total_invited,
        'total_completed': total_completed,
        'total_registered': total_registered,
        'today_registrations': today_registrations,
        'companies': len(companies),
        'panel_participants': panel_participants,
        'confirmed_attendance': confirmed_attendance,
        'pending_emails': pending_emails
    }
@app.route('/admin/invitations')
def admin_invitations():
    """View and manage pending invitations"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('admin_login'))

    # Load both datasets
    hr_pending_data = load_db('hr_pending_data')
    hr_registrations = load_db('hr_registrations')

    print(f"Pending HR data: {len(hr_pending_data)}")
    print(f"Registered HR: {len(hr_registrations)}")

    # Categorize pending HR data
    pending_invitations = []      # Not invited yet
    sent_invitations = []         # Invited but not registered
    completed_invitations = []    # Invited and registered (from pending)
    
    # Track new (no name) recipients separately
    new_no_name_count = 0
    new_with_name_count = 0
    sent_no_name_count = 0
    sent_with_name_count = 0

    for hr_id, hr in hr_pending_data.items():
        hr_copy = hr.copy()
        hr_copy['id'] = hr_id
        
        # Check if organization-only (no name)
        if not hr.get('full_name') or hr.get('full_name', '') == 'N/A' or hr.get('full_name', '').strip() == '':
            hr_copy['is_org_only'] = True
            hr_copy['display_name'] = f"{hr.get('organization', 'Unknown')} Team"
            if not hr.get('invitation_sent', False):
                new_no_name_count += 1
            else:
                sent_no_name_count += 1
        else:
            hr_copy['is_org_only'] = False
            hr_copy['display_name'] = hr.get('full_name', '')
            if not hr.get('invitation_sent', False):
                new_with_name_count += 1
            else:
                sent_with_name_count += 1

        if hr.get('registration_complete'):
            completed_invitations.append(hr_copy)
        elif hr.get('invitation_sent'):
            sent_invitations.append(hr_copy)
        else:
            pending_invitations.append(hr_copy)

    # Get registered HRs from registrations database
    registered_hrs = []
    registered_no_name_count = 0
    registered_with_name_count = 0
    
    for reg_id, hr in hr_registrations.items():
        hr_copy = hr.copy()
        hr_copy['id'] = reg_id
        
        # Check if organization-only
        if not hr.get('full_name') or hr.get('full_name', '') == 'N/A' or hr.get('full_name', '').strip() == '':
            hr_copy['is_org_only'] = True
            hr_copy['display_name'] = f"{hr.get('organization', 'Unknown')} Team"
            registered_no_name_count += 1
        else:
            hr_copy['is_org_only'] = False
            hr_copy['display_name'] = hr.get('full_name', '')
            registered_with_name_count += 1
            
        registered_hrs.append(hr_copy)

    # Combine all for "All HR" tab
    all_hr_list = []
    # Add pending data
    for hr_id, hr in hr_pending_data.items():
        hr_copy = hr.copy()
        hr_copy['id'] = hr_id
        all_hr_list.append(hr_copy)
    # Add registrations
    for reg_id, hr in hr_registrations.items():
        hr_copy = hr.copy()
        hr_copy['id'] = reg_id
        all_hr_list.append(hr_copy)

    print(f"New (no name): {new_no_name_count}, New (with name): {new_with_name_count}")
    print(f"Sent (no name): {sent_no_name_count}, Sent (with name): {sent_with_name_count}")
    print(f"Registered (no name): {registered_no_name_count}, Registered (with name): {registered_with_name_count}")
    print(f"Pending: {len(pending_invitations)}, Sent: {len(sent_invitations)}, Completed: {len(completed_invitations)}, Registered: {len(registered_hrs)}")

    return render_template('admin_invitations.html',
                         pending_invitations=pending_invitations,
                         sent_invitations=sent_invitations,
                         completed_invitations=completed_invitations,
                         registered_hrs=registered_hrs,
                         total_registrations=len(registered_hrs),
                         all_hr_list=all_hr_list,
                         new_no_name_count=new_no_name_count,
                         new_with_name_count=new_with_name_count,
                         total_new_count=new_no_name_count + new_with_name_count,
                         sent_no_name_count=sent_no_name_count,
                         sent_with_name_count=sent_with_name_count,
                         registered_no_name_count=registered_no_name_count,
                         registered_with_name_count=registered_with_name_count)


# ================= SEND ALL INVITATIONS ROUTE =================

@app.route('/admin/send-all-invitations', methods=['POST'])
def send_all_invitations():
    """Send invitations to ALL pending HR professionals"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_pending_data = load_db('hr_pending_data')

        # Get all pending HR records (not invited yet)
        pending_hrs = []
        for hr_id, hr in hr_pending_data.items():
            if not hr.get('invitation_sent', False):
                pending_hrs.append((hr_id, hr))

        print(f"Found {len(pending_hrs)} pending HRs to send invitations to")

        if not pending_hrs:
            return jsonify({
                'success': False,
                'error': 'No pending invitations found'
            }), 400

        sent_count = 0
        errors = []

        for hr_id, hr in pending_hrs:
            try:
                # Check if email exists
                recipient_email = hr.get('office_email', '')
                if not recipient_email or '@' not in recipient_email:
                    errors.append(f"No valid email for {hr.get('full_name', 'Unknown')}")
                    continue

                # Generate unique invitation URL
                invitation_token = secrets.token_urlsafe(32)
                invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"

                # Send email - USING THE UPDATED send_invitation_email_v2
                email_sent = send_invitation_email_v2(hr, invitation_url)

                if email_sent:
                    # Update HR record in pending data
                    hr['invitation_sent'] = True
                    hr['invitation_sent_at'] = datetime.now().isoformat()
                    hr['invitation_token'] = invitation_token
                    hr['invitation_url'] = invitation_url
                    hr['status'] = 'invitation_sent'

                    hr_pending_data[hr_id] = hr
                    sent_count += 1
                    print(f"✓ Sent invitation to {recipient_email}")
                else:
                    errors.append(f"Failed to send email to {recipient_email}")

            except Exception as e:
                errors.append(f"Error sending to {hr.get('office_email', 'Unknown email')}: {str(e)}")

        # Save updated pending data
        save_db('hr_pending_data', hr_pending_data)

        # Print summary
        print(f"\n=== Invitation Send Summary ===")
        print(f"Total attempted: {len(pending_hrs)}")
        print(f"Successfully sent: {sent_count}")
        print(f"Errors: {len(errors)}")

        if errors:
            return jsonify({
                'success': True,
                'sent_count': sent_count,
                'message': f'Sent {sent_count} invitations. Some errors occurred.',
                'errors': errors[:5]  # Return first 5 errors
            })

        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'message': f'Successfully sent {sent_count} invitations'
        })

    except Exception as e:
        print(f"Error in send_all_invitations: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    

# ================= SEND SINGLE INVITATION ROUTE =================
@app.route('/admin/send-invitation/<hr_id>', methods=['POST'])
def send_single_invitation(hr_id):
    """Send invitation to single HR"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        hr_pending_data = load_db('hr_pending_data')

        if hr_id not in hr_pending_data:
            return jsonify({'success': False, 'error': 'HR not found in pending data'}), 404

        hr = hr_pending_data[hr_id]

        # Check if already sent
        if hr.get('invitation_sent', False):
            return jsonify({
                'success': False,
                'error': 'Invitation already sent to this HR'
            })

        # Check if email exists
        recipient_email = hr.get('office_email', '')
        if not recipient_email or '@' not in recipient_email:
            return jsonify({
                'success': False,
                'error': 'No valid email address for this HR'
            })

        # Generate unique invitation token
        invitation_token = secrets.token_urlsafe(32)
        invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"

        print(f"\n=== SENDING SINGLE INVITATION ===")
        print(f"HR ID: {hr_id}")
        print(f"Email: {recipient_email}")

        # Send email
        email_sent = send_invitation_email_v2(hr, invitation_url)

        if email_sent:
            # Update HR record in pending data
            hr['invitation_sent'] = True
            hr['invitation_sent_at'] = datetime.now().isoformat()
            hr['invitation_token'] = invitation_token
            hr['invitation_url'] = invitation_url
            hr['status'] = 'invitation_sent'

            hr_pending_data[hr_id] = hr
            save_db('hr_pending_data', hr_pending_data)

            print(f"✓ Invitation sent and record updated for {hr_id}")

            return jsonify({
                'success': True,
                'message': f'Invitation sent to {hr.get("full_name", "HR")} ({hr.get("office_email", "")})',
                'hr_id': hr_id,
                'email': recipient_email
            })
        else:
            print(f"✗ Failed to send email for {hr_id}")
            return jsonify({
                'success': False,
                'error': 'Failed to send email. Check email configuration.'
            }), 500

    except Exception as e:
        print(f"Error in send_single_invitation: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
         
@app.route('/admin/send-bulk-email', methods=['POST'])
def send_bulk_email():
    """Send bulk email to selected HR professionals with attachments using predefined templates"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        # Get form data
        hr_ids_json = request.form.get('hr_ids', '[]')
        hr_ids = json.loads(hr_ids_json)
        email_type = request.form.get('email_type', 'invitation')  # invitation or reminder
        attachments = request.files.getlist('attachments')

        print(f"Bulk email request for {len(hr_ids)} HRs with {len(attachments)} attachments")
        print(f"Email type: {email_type}")

        if not hr_ids:
            return jsonify({'success': False, 'error': 'No recipients selected'})

        # Load both datasets
        hr_pending_data = load_db('hr_pending_data')
        hr_registrations = load_db('hr_registrations')
        sent_count = 0
        errors = []
        successful_emails = []

        for hr_id in hr_ids:
            try:
                # Find HR in pending data
                hr = None
                dataset_name = 'pending'

                if hr_id in hr_pending_data:
                    hr = hr_pending_data[hr_id]
                elif hr_id in hr_registrations:
                    hr = hr_registrations[hr_id]
                    dataset_name = 'registered'
                else:
                    # Search by ID field
                    for hr_key, hr_data in hr_pending_data.items():
                        if hr_data.get('id') == hr_id:
                            hr = hr_data
                            hr_id = hr_key
                            break

                    if not hr:
                        for hr_key, hr_data in hr_registrations.items():
                            if hr_data.get('registration_id') == hr_id or hr_data.get('id') == hr_id:
                                hr = hr_data
                                hr_id = hr_key
                                dataset_name = 'registered'
                                break

                if not hr:
                    errors.append(f"HR ID {hr_id} not found")
                    continue

                # Get recipient email
                recipient_email = hr.get('office_email', hr.get('email', ''))
                if not recipient_email or '@' not in recipient_email:
                    errors.append(f"No valid email for {hr.get('full_name', 'Unknown')}")
                    continue

                # Generate invitation URL if needed (for invitation emails)
                invitation_url = ''
                if email_type == 'invitation' and 'invitation_url' not in hr:
                    # Generate invitation token
                    invitation_token = secrets.token_urlsafe(32)
                    invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"
                    
                    # Store in database
                    if hr_id in hr_pending_data:
                        hr_pending_data[hr_id]['invitation_token'] = invitation_token
                        hr_pending_data[hr_id]['invitation_url'] = invitation_url
                        save_db('hr_pending_data', hr_pending_data)
                elif 'invitation_url' in hr:
                    invitation_url = hr['invitation_url']

                # Determine subject based on email type
                if email_type == 'invitation':
                    subject = "Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad"
                else:
                    subject = "Reminder | HR Conclave 2026 – Don't Miss Out on This Opportunity | 7 Feb | Hyderabad"

                # Send email with attachments
                if send_bulk_email_template(
                    recipient_email, 
                    subject, 
                    hr.get('full_name', ''),
                    hr.get('organization', ''),
                    attachments[:3],  # Limit to 3 attachments
                    email_type,
                    invitation_url
                ):
                    sent_count += 1
                    successful_emails.append(recipient_email)
                    print(f"✓ {email_type} email sent to {recipient_email} ({dataset_name})")
                    
                    # Update invitation status if this is a new recipient and invitation email
                    if email_type == 'invitation' and hr_id in hr_pending_data and not hr.get('invitation_sent'):
                        hr_pending_data[hr_id]['invitation_sent'] = True
                        hr_pending_data[hr_id]['invitation_sent_at'] = datetime.now().isoformat()
                        save_db('hr_pending_data', hr_pending_data)
                else:
                    errors.append(f"Failed to send email to {recipient_email}")

            except Exception as e:
                error_msg = f"Error sending to {hr_id}: {str(e)}"
                errors.append(error_msg)
                print(f"Error: {error_msg}")

        # Save email to history
        email_history = load_db('email_history')
        email_id = str(uuid.uuid4())
        email_history[email_id] = {
            'id': email_id,
            'subject': subject,
            'email_type': email_type,
            'recipients': len(hr_ids),
            'sent_count': sent_count,
            'successful_emails': successful_emails,
            'errors': errors,
            'attachments': len(attachments),
            'timestamp': datetime.now().isoformat(),
            'status': 'sent' if sent_count > 0 else 'failed'
        }
        save_db('email_history', email_history)

        return jsonify({
            'success': True,
            'sent_count': sent_count,
            'email_type': email_type,
            'message': f'{email_type.capitalize()} email sent to {sent_count} recipients',
            'successful_emails': successful_emails[:5],  # Return first 5 successful emails
            'errors': errors[:5] if errors else []
        })

    except Exception as e:
        print(f"Error in send_bulk_email: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

def send_invitation_email_v2(hr_data, invitation_url):
    """Send invitation email with consistent format - FIXED for organization-only recipients"""
    try:
        print(f"\n=== SENDING INVITATION EMAIL ===")
        print(f"Recipient: {hr_data.get('office_email', 'No email')}")
        print(f"HR Data: {hr_data.get('full_name', 'No name')} from {hr_data.get('organization', 'No org')}")
        print(f"Invitation URL: {invitation_url}")
        
        # Check if email is properly configured
        if not EMAIL_CONFIG.get('EMAIL_PASSWORD') or EMAIL_CONFIG['EMAIL_PASSWORD'] == 'nrmp xrsx pqan zhrs':
            print("⚠️ Email not configured properly - using fallback mode")
            print("📧 Email content would be:")
            print(f"Subject: Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad")
            print(f"To: {hr_data.get('office_email', 'No email')}")
            
            # Log the invitation attempt
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"[{timestamp}] INVITATION: {hr_data.get('full_name', 'NO_NAME')} | EMAIL: {hr_data.get('office_email', 'NO_EMAIL')} | ORG: {hr_data.get('organization', 'NO_ORG')} | URL: {invitation_url}\n"

            with open('invitation_log.txt', 'a', encoding='utf-8') as f:
                f.write(log_entry)
            print(f"✓ Invitation logged to local file")
            
            # Still update the HR record to mark as sent
            hr_pending_data = load_db('hr_pending_data')
            for hr_id, hr in hr_pending_data.items():
                if hr.get('office_email') == hr_data.get('office_email'):
                    hr['invitation_sent'] = True
                    hr['invitation_sent_at'] = datetime.now().isoformat()
                    hr['invitation_token'] = secrets.token_urlsafe(32)
                    hr['invitation_url'] = invitation_url
                    hr['status'] = 'invitation_sent'
                    hr_pending_data[hr_id] = hr
                    save_db('hr_pending_data', hr_pending_data)
                    print(f"✓ HR record updated as invitation sent")
                    break
            
            return True  # Return True to simulate success

        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = hr_data.get('office_email', '')
        
        # Check if email is valid
        recipient_email = msg['To']
        if not recipient_email or '@' not in recipient_email:
            print(f"✗ Invalid email address: {recipient_email}")
            return False
        
        msg['Subject'] = 'Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad'
        
        # Get event data
        event = get_event_data()
        
        # UPDATED SMART GREETING: Only use name if explicitly provided
        hr_name = hr_data.get('full_name', '')
        organization = hr_data.get('organization', '')
        
        print(f"Name check: '{hr_name}' (type: {type(hr_name)})")
        print(f"Organization: '{organization}'")
        
        # Determine greeting - FIXED LOGIC
        # Clean the name and organization
        hr_name = str(hr_name or '').strip()
        organization = str(organization or '').strip()
        
        # Define invalid patterns
        invalid_patterns = ['', 'n/a', 'nan', 'null', 'undefined', ' ']
        
        # Check if name is valid (not empty, not invalid pattern, not just spaces)
        if hr_name and hr_name.lower() not in invalid_patterns and len(hr_name) > 1:
            # Valid name exists - use it
            greeting_name = hr_name
            print(f"Using name greeting: {greeting_name}")
            greeting_line = f"Dear {hr_name},"
        elif organization and organization.lower() not in invalid_patterns:
            # No valid name, but has valid organization
            greeting_name = f"{organization} Team"
            print(f"Using organization greeting: {greeting_name}")
            greeting_line = f"Dear {organization} Team,"
        else:
            # No valid name or organization
            greeting_name = "HR Professional"
            print(f"Using default greeting: {greeting_name}")
            greeting_line = f"Dear HR Professional,"
        
        # Get contact information
        contact = event.get('contact', {})
        tpo_name = contact.get('tpo_name', 'Dr D Hemanath Dussa')
        tpo_email = contact.get('tpo_email', 'placements@sphoorthyengg.ac.in')
        phone_numbers = contact.get('phone', '9121001921, 9885700310')
        linkedin = contact.get('linkedin', 'https://www.linkedin.com/in/sphoorthy-engineering-college/')
        maps_url = contact.get('maps_url', 'https://maps.app.goo.gl/nLvSyUAiA1KRkFTh9?g_st=ic')
        
        # Technical Head and Marketing Head info
        technical_head = {
            'name': 'Laxmi Nivas Morishetty',
            'title': 'Technical Head',
            'email': 'laxminivas@sphoorthyengg.ac.in',
            'phone': '9059160424',
            'linkedin': 'https://www.linkedin.com/in/sphoorthy-engineering-college/'
        }
        
        marketing_head = {
            'name': 'Mahesh Bampalli',
            'title': 'Marketing & Communication Head',
            'email': 'mahesh@sphoorthyengg.ac.in',
            'phone': '9885700310',
            'linkedin': 'https://www.linkedin.com/in/sphoorthy-engineering-college/'
        }
        
        # Format phone numbers for tel: links
        phone1 = phone_numbers.split(',')[0].strip().replace(' ', '').replace('-', '')
        tech_phone = technical_head['phone'].replace(' ', '').replace('-', '')
        marketing_phone = marketing_head['phone'].replace(' ', '').replace('-', '')
        
        # Email body with EXACT format as requested
        body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HR Conclave 2026 - Invitation</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .container {{
                width: 100% !important;
                padding: 10px !important;
            }}
            .section {{
                margin: 15px 0 !important;
                padding: 0 !important;
            }}
            .section-title {{
                margin: 15px 0 8px 0 !important;
            }}
            .contact-grid {{
                grid-template-columns: 1fr !important;
                gap: 15px !important;
            }}
            .contact-card {{
                padding: 15px !important;
                text-align: center !important;
            }}
            .icon-row {{
                gap: 15px !important;
                justify-content: center !important;
            }}
            .icon-item {{
                min-width: 60px !important;
                margin: 5px !important;
            }}
            .header h1 {{
                font-size: 18px !important;
            }}
            .contact-name {{
                font-size: 13px !important;
            }}
            .contact-title {{
                font-size: 11px !important;
            }}
            .section-content {{
                font-size: 13px !important;
            }}
            .bullet-list li {{
                font-size: 13px !important;
            }}
            .icon {{
                width: 35px !important;
                height: 35px !important;
                font-size: 18px !important;
                line-height: 35px !important;
            }}
            .icon-label {{
                font-size: 10px !important;
            }}
            .event-details {{
                padding: 10px !important;
            }}
            .event-details div {{
                font-size: 13px !important;
            }}
            .registration-box {{
                padding: 10px !important;
            }}
            .registration-box a {{
                font-size: 12px !important;
            }}
        }}
        
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 0;
            background: #f8f9fa;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 15px 0;
            border-bottom: 2px solid #1a56db;
            margin-bottom: 15px;
        }}
        .section {{
            margin: 15px 0;
            padding: 0;
        }}
        .section-title {{
            color: #1a56db;
            font-size: 16px;
            font-weight: bold;
            margin: 15px 0 8px 0;
            padding-bottom: 4px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .section-content {{
            margin: 5px 0 10px 0;
            color: #444;
            font-size: 14px;
            line-height: 1.4;
        }}
        .bullet-list {{
            margin: 5px 0 10px 20px;
            padding: 0;
        }}
        .bullet-list li {{
            margin: 4px 0;
            color: #444;
            font-size: 14px;
        }}
        .registration-box {{
            background: #f0f8ff;
            border-left: 4px solid #1a56db;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 0 4px 4px 0;
        }}
        .contact-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 15px 0;
        }}
        .contact-card {{
            background: #f9f9f9;
            border-radius: 6px;
            padding: 15px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }}
        .contact-name {{
            font-weight: bold;
            color: #1a56db;
            margin-bottom: 5px;
            font-size: 14px;
        }}
        .contact-title {{
            color: #666;
            font-size: 12px;
            margin-bottom: 10px;
        }}
        .icon-row {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 10px;
        }}
        .icon-item {{
            text-align: center;
            min-width: 70px;
        }}
        .icon {{
            font-size: 22px;
            margin-bottom: 4px;
            display: block;
            height: 40px;
            width: 40px;
            line-height: 40px;
            border-radius: 50%;
            background: #f0f0f0;
            margin: 0 auto 6px auto;
            text-decoration: none !important;
        }}
        .icon.email {{
            color: #ea4335;
            background: #fce8e6;
        }}
        .icon.linkedin {{
            color: #0077b5;
            background: #e8f4f9;
        }}
        .icon.phone {{
            color: #34a853;
            background: #e6f4ea;
        }}
        .icon.location {{
            color: #4285f4;
            background: #e8f0fe;
        }}
        .icon-label {{
            font-size: 11px;
            color: #666;
            margin-top: 2px;
        }}
        .event-details {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            margin: 15px 0;
            text-align: center;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 13px;
        }}
        .signature {{
            margin: 15px 0;
            line-height: 1.3;
            font-size: 13px;
        }}
        a {{
            color: #1a56db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .divider {{
            height: 1px;
            background: #e0e0e0;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1 style="margin: 0; color: #1a56db; font-size: 20px;">
                Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad
            </h1>
        </div>

        <!-- Greeting -->
        <div class="section">
            <p style="margin: 0 0 10px 0; font-size: 14px;">
                <strong>{greeting_line}</strong>
            </p>
            <p style="margin: 0 0 15px 0; color: #444; font-size: 14px;">
                Warm greetings from <strong>Sphoorthy Engineering College</strong>, Hyderabad.
            </p>
        </div>

        <div class="divider"></div>

        <!-- Conclave Objective -->
        <div class="section">
            <div class="section-title">Conclave Objective</div>
            <div class="section-content">
                <strong>HR Conclave 2026</strong> is an industry–academia initiative bringing together senior HR professionals from technology organizations to discuss talent transformation, leadership, and future workforce readiness.
            </div>
        </div>

        <!-- Panel Themes -->
        <div class="section">
            <div class="section-title">Panel Themes</div>
            <div class="section-content">
                HR professionals may participate in or observe panel discussions on:
                <ul class="bullet-list">
                    <li><strong>AI & Automation in Talent Acquisition</strong> – Redefining hiring practices</li>
                    <li><strong>Industry–Academia Collaboration</strong> – Creating employable graduates</li>
                    <li><strong>Skill Up: The New Learning Curve</strong> – Building tomorrow's talent through continuous learning and upskilling</li>
                </ul>
            </div>
        </div>

        <!-- Collaborating Associations -->
        <div class="section">
            <div class="section-title">Collaborating Associations</div>
            <div class="section-content">
                The conclave is being organized in collaboration with leading professional and industry bodies:
                <ul class="bullet-list">
                    <li><strong>NHRD</strong> – National Human Resource Development Network</li>
                    <li><strong>ISTD</strong> – Indian Society for Training & Development</li>
                    <li><strong>FTCCI</strong> – Federation of Telangana Chambers of Commerce and Industry</li>
                    <li><strong>DEET</strong> – Digital Employment Exchange of Telangana</li>
                    <li><strong>ICT</strong> – Information and Communication Technology Academy</li>
                    <li><strong>TASK</strong> – Telangana Academy for Skill and Knowledge</li>
                </ul>
            </div>
        </div>

        <!-- Event Details -->
        <div class="section">
            <div class="event-details">
                <div style="margin: 8px 0; font-size: 14px;">
                    <span style="color: #1a56db;">📅</span> <strong>Date:</strong> 7 February 2026
                </div>
                <div style="margin: 8px 0; font-size: 14px;">
                    <span style="color: #1a56db;">📍</span> <strong>Venue:</strong> Sphoorthy Engineering College, Hyderabad
                </div>
            </div>
        </div>

        <!-- Recognition & Participation -->
        <div class="section">
            <div class="section-title">Recognition & Participation</div>
            <div class="section-content">
                All registered and attending HR professionals will receive formal recognition as part of the conclave.<br>
                During registration, participants may select the recognition category aligned with their professional expertise.
            </div>
        </div>

        <!-- Registration -->
        <div class="section">
            <div class="section-title">Registration</div>
            <div class="section-content">
                If this aligns with your interests, we would be honoured by your presence.<br>
                Kindly register using the link below:
                <div class="registration-box">
                    <div style="margin: 8px 0;">
                        <span style="color: #1a56db;">🔗</span> <strong>Registration Link:</strong>
                    </div>
                    <div style="margin: 8px 0;">
                        <a href="{invitation_url}" style="color: #1a56db; word-break: break-all; font-size: 13px;">
                            {invitation_url}
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Venue Location -->
        <div class="section">
            <div class="section-title">Venue Location</div>
            <div class="section-content">
                <div style="margin: 8px 0;">
                    <span style="color: #1a56db;">📍</span> Sphoorthy Engineering College, Hyderabad
                </div>
                <div style="margin: 8px 0;">
                    <a href="{maps_url}" style="color: #1a56db; word-break: break-all; font-size: 13px;">
                        {maps_url}
                    </a>
                </div>
            </div>
        </div>

        <div class="divider"></div>

        <!-- Contact Information -->
        <div class="section">
            <div class="section-title">Contact Information</div>
            <div class="section-content" style="text-align: center; margin-bottom: 10px;">
                For any clarifications, please feel free to contact us:
            </div>
            
            <div class="contact-grid">
                <!-- TPO -->
                <div class="contact-card">
                    <div class="contact-name">{tpo_name}</div>
                    <div class="contact-title">Training and Placement Officer</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{tpo_email}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="tel:{phone1}" style="text-decoration: none; color: inherit;">
                                <div class="icon phone">📱</div>
                                <div class="icon-label">Call</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Technical Head -->
                <div class="contact-card">
                    <div class="contact-name">{technical_head['name']}</div>
                    <div class="contact-title">{technical_head['title']}</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{technical_head['email']}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="tel:{tech_phone}" style="text-decoration: none; color: inherit;">
                                <div class="icon phone">📱</div>
                                <div class="icon-label">Call</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Marketing Head -->
                <div class="contact-card">
                    <div class="contact-name">{marketing_head['name']}</div>
                    <div class="contact-title">{marketing_head['title']}</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{marketing_head['email']}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="tel:{marketing_phone}" style="text-decoration: none; color: inherit;">
                                <div class="icon phone">📱</div>
                                <div class="icon-label">Call</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- LinkedIn & Location -->
                <div class="contact-card">
                    <div class="contact-name">Connect with Us</div>
                    <div class="contact-title">Social Media & Location</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="{linkedin}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon linkedin">in</div>
                                <div class="icon-label">LinkedIn</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="{maps_url}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon location">📍</div>
                                <div class="icon-label">Location</div>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Closing -->
        <div class="section" style="text-align: center; margin: 15px 0;">
            <p style="margin: 0; color: #444; font-size: 14px;">
                We sincerely look forward to the opportunity of welcoming you to HR Conclave 2026.
            </p>
        </div>

        <!-- Signature -->
        <div class="footer">
            <div class="signature">
                <p style="margin: 0 0 5px 0;"><strong>Warm regards,</strong></p>
                <p style="margin: 5px 0;"><strong>{tpo_name}</strong></p>
                <p style="margin: 5px 0;">Training and Placement Officer</p>
                <p style="margin: 5px 0;">{phone_numbers}</p>
                <p style="margin: 5px 0;">Sphoorthy Engineering College, Hyderabad.</p>
            </div>
        </div>
    </div>
</body>
</html>"""

        msg.attach(MIMEText(body, 'html'))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Invitation email sent to {recipient_email}")
        return True
    except Exception as e:
        print(f"✗ Invitation email sending error: {str(e)}")
        traceback.print_exc()
        return False
    
def send_bulk_email_template(to_email, subject, recipient_name, organization, attachments, email_type='invitation', invitation_url=''):
    """Send bulk email using predefined templates - FIXED & UPDATED to match exact format"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = to_email
        
        # Use provided subject or default
        if not subject or subject.strip() == '':
            msg['Subject'] = 'Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad'
        else:
            msg['Subject'] = subject

        # UPDATED SMART GREETING: Only use name if explicitly provided
        recipient_name = str(recipient_name or '').strip()
        organization = str(organization or '').strip()
        
        invalid_patterns = ['', 'n/a', 'nan', 'null', 'undefined', ' ']
        
        # Determine greeting - match the exact format
        if (recipient_name and 
            recipient_name.lower() not in invalid_patterns and 
            len(recipient_name) > 1):
            # Valid name exists - use it
            greeting = f"Dear {recipient_name},"
            print(f"Using name greeting: {greeting}")
        elif organization and organization.lower() not in invalid_patterns:
            # No valid name, but has organization - USE ORGANIZATION TEAM
            greeting = f"Dear {organization} Team,"
            print(f"Using organization greeting: {greeting}")
        else:
            # No valid name or organization
            greeting = "Dear HR Professional,"
            print(f"Using default greeting: {greeting}")
        
        print(f"Email to: {to_email}, Greeting: {greeting}")
        
        # Get event data
        event = get_event_data()
        contact = event.get('contact', {})
        tpo_name = contact.get('tpo_name', 'Dr D Hemanath Dussa')
        tpo_email = contact.get('tpo_email', 'placements@sphoorthyengg.ac.in')
        phone_numbers = contact.get('phone', '9121001921, 9885700310')
        linkedin = contact.get('college_linkedin', 'https://www.linkedin.com/in/sphoorthy-engineering-college/')
        maps_url = contact.get('maps_url', 'https://maps.app.goo.gl/nLvSyUAiA1KRkFTh9?g_st=ic')
        
        # Technical Head and Marketing Head info with LinkedIn profiles
        technical_head = {
            'name': 'Laxmi Nivas Morishetty',
            'title': 'Technical Head',
            'email': 'morishettylaxminivas@gmail.com',
            'phone': '9059160424',
            'linkedin': 'https://www.linkedin.com/in/laxmi-nivas-morishetty-02468m/'
        }
        
        marketing_head = {
            'name': 'Mahesh Bampalli',
            'title': 'Marketing & Communication Head',
            'email': 'maheshbampalli@gmail.com',
            'phone': '6304708314',
            'linkedin': 'https://www.linkedin.com/in/mahesh-bampalli-b35509324/'
        }
        
        # Format phone numbers for tel: links
        phone1 = phone_numbers.split(',')[0].strip().replace(' ', '').replace('-', '')
        tech_phone = technical_head['phone'].replace(' ', '').replace('-', '')
        marketing_phone = marketing_head['phone'].replace(' ', '').replace('-', '')
        
        # Generate invitation URL if not provided
        if not invitation_url and email_type == 'invitation':
            invitation_token = secrets.token_urlsafe(32)
            invitation_url = f"{request.host_url}hr-registration?invite={invitation_token}"
        
        # Prepare reminder content
        reminder_header = ""
        reminder_content = ""
        if email_type == 'reminder':
            reminder_header = '<h1 style="margin: 0; color: #1a56db; font-size: 20px;">⏰ REMINDER: HR Conclave 2026 – Don\'t Miss This Opportunity!</h1>'
            reminder_content = '<div class="reminder-highlight">This is a friendly reminder about your invitation to HR Conclave 2026. Time is running out to secure your spot at this exclusive event!</div>'
        else:
            reminder_header = '<h1 style="margin: 0; color: #1a56db; font-size: 20px;">Invitation | HR Conclave 2026 – Talent, Leadership & Future Workforce | 7 Feb | Hyderabad</h1>'
        
        # Email body with EXACT format as requested
        body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HR Conclave 2026 - {email_type.capitalize()}</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .container {{
                width: 100% !important;
                padding: 10px !important;
            }}
            .section {{
                margin: 15px 0 !important;
                padding: 0 !important;
            }}
            .section-title {{
                margin: 15px 0 8px 0 !important;
            }}
            .contact-grid {{
                grid-template-columns: 1fr !important;
                gap: 15px !important;
            }}
            .contact-card {{
                padding: 15px !important;
                text-align: center !important;
            }}
            .icon-row {{
                gap: 15px !important;
                justify-content: center !important;
            }}
            .icon-item {{
                min-width: 60px !important;
                margin: 5px !important;
            }}
            .header h1 {{
                font-size: 18px !important;
            }}
            .contact-name {{
                font-size: 13px !important;
            }}
            .contact-title {{
                font-size: 11px !important;
            }}
            .section-content {{
                font-size: 13px !important;
            }}
            .bullet-list li {{
                font-size: 13px !important;
            }}
            .icon {{
                width: 35px !important;
                height: 35px !important;
                font-size: 18px !important;
                line-height: 35px !important;
            }}
            .icon-label {{
                font-size: 10px !important;
            }}
            .event-details {{
                padding: 10px !important;
            }}
            .event-details div {{
                font-size: 13px !important;
            }}
            .registration-box {{
                padding: 10px !important;
            }}
            .registration-box a {{
                font-size: 12px !important;
            }}
        }}
        
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.5;
            color: #333;
            margin: 0;
            padding: 0;
            background: #f8f9fa;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 15px 0;
            border-bottom: 2px solid #1a56db;
            margin-bottom: 15px;
        }}
        .section {{
            margin: 15px 0;
            padding: 0;
        }}
        .section-title {{
            color: #1a56db;
            font-size: 16px;
            font-weight: bold;
            margin: 15px 0 8px 0;
            padding-bottom: 4px;
            border-bottom: 1px solid #e0e0e0;
        }}
        .section-content {{
            margin: 5px 0 10px 0;
            color: #444;
            font-size: 14px;
            line-height: 1.4;
        }}
        .bullet-list {{
            margin: 5px 0 10px 20px;
            padding: 0;
        }}
        .bullet-list li {{
            margin: 4px 0;
            color: #444;
            font-size: 14px;
        }}
        .registration-box {{
            background: #f0f8ff;
            border-left: 4px solid #1a56db;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 0 4px 4px 0;
        }}
        .contact-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 15px 0;
        }}
        .contact-card {{
            background: #f9f9f9;
            border-radius: 6px;
            padding: 15px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }}
        .contact-name {{
            font-weight: bold;
            color: #1a56db;
            margin-bottom: 5px;
            font-size: 14px;
        }}
        .contact-title {{
            color: #666;
            font-size: 12px;
            margin-bottom: 10px;
        }}
        .icon-row {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 10px;
        }}
        .icon-item {{
            text-align: center;
            min-width: 70px;
        }}
        .icon {{
            font-size: 22px;
            margin-bottom: 4px;
            display: block;
            height: 40px;
            width: 40px;
            line-height: 40px;
            border-radius: 50%;
            background: #f0f0f0;
            margin: 0 auto 6px auto;
            text-decoration: none !important;
        }}
        .icon.email {{
            color: #ea4335;
            background: #fce8e6;
        }}
        .icon.linkedin {{
            color: #0077b5;
            background: #e8f4f9;
        }}
        .icon.phone {{
            color: #34a853;
            background: #e6f4ea;
        }}
        .icon.location {{
            color: #4285f4;
            background: #e8f0fe;
        }}
        .icon-label {{
            font-size: 11px;
            color: #666;
            margin-top: 2px;
        }}
        .event-details {{
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            margin: 15px 0;
            text-align: center;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 13px;
        }}
        .signature {{
            margin: 15px 0;
            line-height: 1.3;
            font-size: 13px;
        }}
        a {{
            color: #1a56db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .divider {{
            height: 1px;
            background: #e0e0e0;
            margin: 10px 0;
        }}
        .reminder-highlight {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px 15px;
            margin: 15px 0;
            border-radius: 0 4px 4px 0;
            color: #856404;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Greeting -->
        <div class="section">
            <p style="margin: 0 0 10px 0; font-size: 14px;">
                <strong>{greeting}</strong>
            </p>
            <p style="margin: 0 0 15px 0; color: #444; font-size: 14px;">
                Warm greetings from <strong>Sphoorthy Engineering College</strong>, Hyderabad.
            </p>
            
            {reminder_content}
        </div>

        <div class="divider"></div>

        <!-- Conclave Objective -->
        <div class="section">
            <div class="section-title">Conclave Objective</div>
            <div class="section-content">
                <strong>HR Conclave 2026</strong> is an industry–academia initiative bringing together senior HR professionals from technology organizations to discuss talent transformation, leadership, and future workforce readiness.
            </div>
        </div>

        <!-- Panel Themes -->
        <div class="section">
            <div class="section-title">Panel Themes</div>
            <div class="section-content">
                HR professionals may participate in or observe panel discussions on:
                <ul class="bullet-list">
                    <li><strong>AI & Automation in Talent Acquisition</strong> – Redefining hiring practices</li>
                    <li><strong>Industry–Academia Collaboration</strong> – Creating employable graduates</li>
                    <li><strong>Skill Up: The New Learning Curve</strong> – Building tomorrow's talent through continuous learning and upskilling</li>
                </ul>
            </div>
        </div>

        <!-- Collaborating Associations -->
        <div class="section">
            <div class="section-title">Collaborating Associations</div>
            <div class="section-content">
                The conclave is being organized in collaboration with leading professional and industry bodies:
                <ul class="bullet-list">
                    <li><strong>NHRD</strong> – National Human Resource Development Network</li>
                    <li><strong>ISTD</strong> – Indian Society for Training & Development</li>
                    <li><strong>FTCCI</strong> – Federation of Telangana Chambers of Commerce and Industry</li>
                    <li><strong>DEET</strong> – Digital Employment Exchange of Telangana</li>
                    <li><strong>ICT</strong> – Information and Communication Technology Academy</li>
                    <li><strong>TASK</strong> – Telangana Academy for Skill and Knowledge</li>
                </ul>
            </div>
        </div>

        <!-- Event Details -->
        <div class="section">
            <div class="event-details">
                <div style="margin: 8px 0; font-size: 14px;">
                    <span style="color: #1a56db;">📅</span> <strong>Date:</strong> 7 February 2026
                </div>
                <div style="margin: 8px 0; font-size: 14px;">
                    <span style="color: #1a56db;">📍</span> <strong>Venue:</strong> Sphoorthy Engineering College, Hyderabad
                </div>
            </div>
        </div>

        <!-- Recognition & Participation -->
        <div class="section">
            <div class="section-title">Recognition & Participation</div>
            <div class="section-content">
                All registered and attending HR professionals will receive formal recognition as part of the conclave.<br>
                During registration, participants may select the recognition category aligned with their professional expertise.
            </div>
        </div>

        <!-- Registration -->
        <div class="section">
            <div class="section-title">Registration</div>
            <div class="section-content">
                If this aligns with your interests, we would be honoured by your presence.<br>
                Kindly tap on <strong>Register</strong> below:
                <div class="registration-box">                 
                    <div style="margin: 8px 0;">
                        <a href="{invitation_url}" style="color: #1a56db; word-break: break-all; font-size: 13px;">
                             <span style="color: #1a56db;">🔗</span> <strong>Registration Link</strong>
                        </a>
                    </div>
                </div>
            </div>
        </div>

        <!-- Venue Location -->
        <div class="section">
            <div class="section-title">Venue Location</div>
            <div class="section-content">
                
                <div style="margin: 8px 0;">
                    <a href="{maps_url}" style="color: #1a56db; word-break: break-all; font-size: 13px;">
                        <span style="color: #1a56db;">📍</span> Sphoorthy Engineering College, Hyderabad
                    </a>
                </div>
            </div>
        </div>

        <div class="divider"></div>

        <!-- Contact Information -->
        <div class="section">
            <div class="section-title">Contact Information</div>
            <div class="section-content" style="text-align: center; margin-bottom: 10px;">
                For any clarifications, please feel free to contact us:
            </div>
            
            <div class="contact-grid">
                <!-- TPO -->
                <div class="contact-card">
                    <div class="contact-name">{tpo_name}</div>
                    <div class="contact-title">Training and Placement Officer</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{tpo_email}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="tel:{phone1}" style="text-decoration: none; color: inherit;">
                                <div class="icon phone">📱</div>
                                <div class="icon-label">Call</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Technical Head -->
                <div class="contact-card">
                    <div class="contact-name">{technical_head['name']}</div>
                    <div class="contact-title">{technical_head['title']}</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{technical_head['email']}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        
                        <div class="icon-item">
                            <a href="{technical_head['linkedin']}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon linkedin">in</div>
                                <div class="icon-label">LinkedIn</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Marketing Head -->
                <div class="contact-card">
                    <div class="contact-name">{marketing_head['name']}</div>
                    <div class="contact-title">{marketing_head['title']}</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="mailto:{marketing_head['email']}" style="text-decoration: none; color: inherit;">
                                <div class="icon email">📧</div>
                                <div class="icon-label">Email</div>
                            </a>
                        </div>
                        
                        <div class="icon-item">
                            <a href="{marketing_head['linkedin']}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon linkedin">in</div>
                                <div class="icon-label">LinkedIn</div>
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- College LinkedIn & Location -->
                <div class="contact-card">
                    <div class="contact-name">Connect with College</div>
                    <div class="contact-title">Social Media & Location</div>
                    <div class="icon-row">
                        <div class="icon-item">
                            <a href="{linkedin}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon linkedin">in</div>
                                <div class="icon-label">LinkedIn</div>
                            </a>
                        </div>
                        <div class="icon-item">
                            <a href="{maps_url}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="icon location">📍</div>
                                <div class="icon-label">Location</div>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Closing -->
        <div class="section" style="text-align: center; margin: 15px 0;">
            <p style="margin: 0; color: #444; font-size: 14px;">
                We sincerely look forward to the opportunity of welcoming you to HR Conclave 2026.
            </p>
        </div>

        <!-- Signature -->
        <div class="footer">
            <div class="signature">
                <p style="margin: 0 0 5px 0;"><strong>Warm regards,</strong></p>
                <p style="margin: 5px 0;"><strong>{tpo_name}</strong></p>
                <p style="margin: 5px 0;">Training and Placement Officer</p>
                <p style="margin: 5px 0;">{phone_numbers}</p>
                <p style="margin: 5px 0;">Sphoorthy Engineering College, Hyderabad.</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(body, 'html'))

        # Attach files
        for attachment in attachments[:3]:
            if attachment.filename:
                file_data = attachment.read()
                attachment.seek(0)
                
                maintype, subtype = 'application', 'octet-stream'
                if attachment.mimetype:
                    maintype, subtype = attachment.mimetype.split('/', 1)
                
                part = MIMEBase(maintype, subtype)
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{attachment.filename}"')
                msg.attach(part)

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ {email_type} email with attachments sent to {to_email}")
        return True

    except Exception as e:
        print(f"✗ {email_type} email sending error: {str(e)}")
        traceback.print_exc()
        return False
@app.route('/api/delete-registration/<registration_id>', methods=['DELETE'])
def delete_registration(registration_id):
    """Delete a registration"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        hr_registrations = load_db('hr_registrations')
        
        if registration_id in hr_registrations:
            # Get HR data before deleting for logging
            hr_data = hr_registrations[registration_id]
            
            # Delete from registrations database
            del hr_registrations[registration_id]
            save_db('hr_registrations', hr_registrations)
            
            # Also check and delete from pending data
            hr_pending_data = load_db('hr_pending_data')
            email_to_delete = hr_data.get('office_email')
            
            if email_to_delete:
                # Find and delete by email in pending data
                pending_to_delete = []
                for pending_id, pending_hr in hr_pending_data.items():
                    if pending_hr.get('office_email') == email_to_delete:
                        pending_to_delete.append(pending_id)
                
                for pending_id in pending_to_delete:
                    del hr_pending_data[pending_id]
                
                if pending_to_delete:
                    save_db('hr_pending_data', hr_pending_data)
            
            # Log the deletion
            try:
                deletion_log = {
                    'deleted_at': datetime.now().isoformat(),
                    'deleted_by': session.get('user_id', 'unknown'),
                    'registration_id': registration_id,
                    'name': hr_data.get('full_name', ''),
                    'email': hr_data.get('office_email', ''),
                    'organization': hr_data.get('organization', '')
                }
                
                # Load deletion history
                deletion_history_path = 'data/deletion_history.json'
                deletion_history = {}
                if os.path.exists(deletion_history_path):
                    with open(deletion_history_path, 'r') as f:
                        deletion_history = json.load(f)
                
                deletion_id = f"DEL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                deletion_history[deletion_id] = deletion_log
                
                with open(deletion_history_path, 'w') as f:
                    json.dump(deletion_history, f, indent=2)
                    
            except Exception as log_error:
                print(f"Error logging deletion: {log_error}")
            
            print(f"✓ Registration deleted: {registration_id}")
            return jsonify({
                'success': True,
                'message': 'Registration deleted successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Registration not found'}), 404
            
    except Exception as e:
        print(f"✗ Delete error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
      
def send_email_with_attachments(to_email, subject, message, recipient_name, organization, attachments):
    """Send email with attachments displayed prominently"""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"{EMAIL_CONFIG['FROM_NAME']} <{EMAIL_CONFIG['FROM_EMAIL']}>"
        msg['To'] = to_email
        msg['Subject'] = subject

        # SMART GREETING: Fixed logic
        greeting = ""
        
        # Clean and check recipient_name
        recipient_name = str(recipient_name or '').strip()
        organization = str(organization or '').strip()
        
        # Define invalid patterns
        invalid_patterns = ['', 'n/a', 'nan', 'null', 'undefined', ' ', 'hr professional', 'N/A']
        
        if (recipient_name and 
            recipient_name.lower() not in invalid_patterns and 
            len(recipient_name) > 1 and
            recipient_name != 'N/A'):
            # Valid name exists
            greeting = f"Dear {recipient_name},"
            print(f"Using name greeting: {greeting}")
        elif organization and organization.lower() not in invalid_patterns:
            # No valid name, but has organization - USE ORGANIZATION TEAM
            greeting = f"Dear {organization} Team,"
            print(f"Using organization greeting: {greeting}")
        else:
            # No valid name or organization
            greeting = "Dear HR Professional,"
            print(f"Using default greeting: {greeting}")
        
        # Get event data for consistent formatting
        event = get_event_data()
        
        # Schedule HTML
        schedule_html = ""
        if 'schedule' in event:
            for item in event['schedule']:
                schedule_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee; font-weight: bold;">{item.get('time', '')}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.get('event', '')}</td>
                </tr>
                """
        
        # Pre-process the message for HTML
        # Replace newlines with <br> tags and escape any HTML special characters
        html_message_content = message.replace('\n', '<br>')
        
        # Create HTML message with proper styling - using string concatenation to avoid backslash issues
        html_message = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .mobile-center {{ text-align: center !important; }}
            .mobile-block {{ display: block !important; width: 100% !important; }}
            .mobile-padding {{ padding: 10px !important; }}
            .qr-code {{ width: 200px !important; height: 200px !important; }}
            .attachment-card {{ flex-direction: column !important; }}
        }}
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f8fafc; }}
        .container {{ max-width: 100%; width: 600px; margin: 0 auto; background: white; }}
        .header {{ background: linear-gradient(135deg, #1a56db, #7e22ce); color: white; padding: 30px 20px; text-align: center; }}
        .content {{ padding: 30px 20px; }}
        .attachment-card {{
            background: #f0f9ff;
            border: 2px solid #bae6fd;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        .attachment-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #1a56db, #7e22ce);
            color: white;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }}
        .attachment-info {{ flex: 1; }}
        .attachment-name {{
            font-weight: bold;
            color: #1a56db;
            margin-bottom: 5px;
            word-break: break-all;
        }}
        .attachment-type {{
            font-size: 12px;
            color: #64748b;
        }}
        .important-box {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .contact-box {{
            background: #f3f4f6;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}
    </style>
</head>
<body>
    <!-- Email Container -->
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1 style="margin: 0; font-size: 28px;">HR Conclave 2026</h1>
            <p style="margin: 10px 0 0 0; font-size: 18px; opacity: 0.9;">Connecting the Future</p>
        </div>

        <!-- Main Content -->
        <div class="content">
            <!-- Greeting Section -->
            <div style="margin-bottom: 30px;">
                <h2 style="color: #1a56db; margin: 0 0 15px 0;">{greeting}</h2>
                <div style="background: #f8fafc; padding: 20px; border-radius: 10px; line-height: 1.8;">
                    {html_message_content}
                </div>
            </div>"""
        
        # Add attachments section if there are attachments
        if attachments:
            attachments_html = f"""<!-- Attachments Section -->
            <div style="margin: 30px 0;">
                <h3 style="color: #1a56db; margin-bottom: 15px;"><i class="fas fa-paperclip"></i> Attachments ({len(attachments)})</h3>"""
            
            for attachment in attachments[:3]:
                attachments_html += f"""
                <div class="attachment-card">
                    <div class="attachment-icon">
                        <i class="fas fa-file"></i>
                    </div>
                    <div class="attachment-info">
                        <div class="attachment-name">{attachment.filename}</div>
                        <div class="attachment-type">Please find this file attached</div>
                    </div>
                </div>"""
            
            attachments_html += "</div>"
            html_message += attachments_html
        
        # Add event details and schedule
        html_message += f"""<!-- Event Details -->
            <div style="background: #f0f9ff; border-radius: 10px; padding: 25px; margin: 25px 0;">
                <h3 style="color: #1a56db; margin-top: 0; border-bottom: 2px solid #bae6fd; padding-bottom: 10px;">📅 Event Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; width: 120px;"><strong>Date:</strong></td>
                        <td style="padding: 8px 0;">{event.get('date', 'February 7, 2026')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Time:</strong></td>
                        <td style="padding: 8px 0;">9:00 AM - 5:00 PM</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Venue:</strong></td>
                        <td style="padding: 8px 0;">{event.get('venue', 'Sphoorthy Engineering College')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;"><strong>Location:</strong></td>
                        <td style="padding: 8px 0;">Nadergul, Hyderabad</td>
                    </tr>
                </table>
            </div>

            <!-- Schedule Preview -->
            <div style="margin: 30px 0;">
                <h3 style="color: #1a56db; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;">⏰ Event Schedule (Preview)</h3>
                <div style="max-height: 200px; overflow-y: auto; border: 1px solid #e2e8f0; border-radius: 8px;">
                    <table style="width: 100%; border-collapse: collapse; background: white;">
                        <thead>
                            <tr style="background: #f3f4f6;">
                                <th style="padding: 12px; text-align: left; font-size: 14px;">Time</th>
                                <th style="padding: 12px; text-align: left; font-size: 14px;">Activity</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_html[:5] if schedule_html else '<tr><td colspan="2" style="padding: 15px; text-align: center; color: #666;">Schedule details available on website</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Important Information -->
            <div class="important-box">
                <h4 style="color: #92400e; margin-top: 0;">⚠️ Important Information</h4>
                <ul style="margin: 10px 0; padding-left: 20px; color: #92400e;">
                    <li style="margin-bottom: 8px;">Registration/Check-in starts at 8:30 AM</li>
                    <li style="margin-bottom: 8px;">Carry government-issued ID for verification</li>
                    <li style="margin-bottom: 8px;">Parking available at Gate No. 1</li>
                    <li style="margin-bottom: 8px;">Professional attire recommended</li>
                    <li>Wi-Fi credentials provided at registration desk</li>
                </ul>
            </div>

            <!-- Contact Information -->
            <div class="contact-box">
                <h4 style="color: #1a56db; margin-top: 0;">📞 Contact & Support</h4>
                <p style="margin: 10px 0;">
                    <strong>TPO:</strong> {event.get('contact', {}).get('tpo_name', 'Dr Hemanath Dussa')}<br>
                    <strong>Email:</strong> {event.get('contact', {}).get('tpo_email', 'placements@sphoorthyengg.ac.in')}<br>
                    <strong>Phone:</strong> {event.get('contact', {}).get('phone', '+91-9121001921')}
                </p>
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; color: #666; font-size: 14px;">
                <p><strong>HR Conclave 2026 Organizing Committee</strong><br>
                Sphoorthy Engineering College</p>
                <p style="font-size: 12px; color: #999; margin-top: 20px;">
                    This is an official communication from HR Conclave 2026 Organizing Committee.
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""

        msg.attach(MIMEText(html_message, 'html'))

        # Attach files
        for attachment in attachments[:3]:  # Limit to 3 attachments
            if attachment.filename:
                # Get file data
                file_data = attachment.read()
                attachment.seek(0)
                
                # Determine MIME type
                maintype, subtype = 'application', 'octet-stream'
                if attachment.mimetype:
                    maintype, subtype = attachment.mimetype.split('/', 1)
                
                # Create attachment
                part = MIMEBase(maintype, subtype)
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{attachment.filename}"')
                msg.attach(part)

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP(EMAIL_CONFIG['SMTP_SERVER'], EMAIL_CONFIG['SMTP_PORT']) as server:
            server.starttls(context=context)
            server.login(EMAIL_CONFIG['EMAIL_USER'], EMAIL_CONFIG['EMAIL_PASSWORD'])
            server.send_message(msg)

        print(f"✓ Email with attachments sent to {to_email}")
        return True

    except Exception as e:
        print(f"✗ Email sending error: {str(e)}")
        traceback.print_exc()
        return False
           
@app.route('/api/generate-invitation-token/<hr_id>')
def generate_invitation_token_api(hr_id):
    """Generate an invitation token for an HR"""
    try:
        # Generate token
        token = secrets.token_urlsafe(32)
        
        # Store in database if needed
        hr_pending_data = load_db('hr_pending_data')
        if hr_id in hr_pending_data:
            hr_pending_data[hr_id]['invitation_token'] = token
            hr_pending_data[hr_id]['invitation_url'] = f"{request.host_url}hr-registration?invite={token}"
            save_db('hr_pending_data', hr_pending_data)
        
        return jsonify({
            'success': True,
            'token': token,
            'invitation_url': f"{request.host_url}hr-registration?invite={token}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
         
def generate_registration_id():
    """Generate unique registration ID"""
    return f"HRC26{datetime.now().strftime('%m%d')}{uuid.uuid4().hex[:6].upper()}"

def get_event_data():
    """Get event data with fallback to default"""
    events = load_db('events')
    # Handle different event key formats
    if 'hr_conclave_2026' in events:
        return events['hr_conclave_2026']
    elif 'hr_conclave' in events:
        return events['hr_conclave']
    else:
        # Get first event in the dictionary
        for key, value in events.items():
            if isinstance(value, dict) and 'title' in value:
                return value
        # Fallback to default
        return get_default_db('events')['hr_conclave_2026']

@app.route('/admin/email-history')
def get_email_history():
    """Get email history"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    email_history = load_db('email_history')
    emails = list(email_history.values())
    emails.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    return jsonify({
        'success': True,
        'emails': emails[:50]  # Last 50 emails
    })

@app.route('/admin/resend-email/<email_id>', methods=['POST'])
def resend_email(email_id):
    """Resend an email"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    try:
        email_history = load_db('email_history')
        if email_id in email_history:
            email_data = email_history[email_id]

            # For now, just mark as resent
            email_data['resent_at'] = datetime.now().isoformat()
            email_data['resent_count'] = email_data.get('resent_count', 0) + 1

            save_db('email_history', email_history)

            return jsonify({'success': True, 'message': 'Email marked as resent'})
        else:
            return jsonify({'success': False, 'error': 'Email not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/view-email/<email_id>')
def view_email_details(email_id):
    """View email details"""
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})

    email_history = load_db('email_history')
    if email_id in email_history:
        return jsonify({
            'success': True,
            'email': email_history[email_id]
        })
    else:
        return jsonify({'success': False, 'error': 'Email not found'})

def initialize_databases():
    """Initialize all databases"""
    for db_name in DB_PATHS.keys():
        if not os.path.exists(DB_PATHS[db_name]):
            default_data = get_default_db(db_name)
            save_db(db_name, default_data)

    # Create sample HR registration if empty
    hr_registrations = load_db('hr_registrations')
    

    # Initialize email_history if not exists
    if not os.path.exists('data/email_history.json'):
        save_db('email_history', {})
# ================= APPLICATION INITIALIZATION =================

if __name__ == '__main__':
    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/profile_photos', exist_ok=True)

    # Initialize databases
    initialize_databases()


    # Start the application
    print("\n=== HR Conclave 2026 Admin Panel ===")
    print("Dashboard URL: http://localhost:5000/admin/dashboard")
    print("Admin Login: admin / admin123")
    print("\nStarting server...")

    app.run(debug=True, port=5000)
