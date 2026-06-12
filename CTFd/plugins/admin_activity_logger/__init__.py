import csv
import io
import datetime
from flask import Blueprint, render_template, request, Response
from CTFd.models import db, Users
from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user

class AdminActivityLogs(db.Model):
    __tablename__ = "admin_activity_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'))
    admin_name = db.Column(db.String(128))
    action_type = db.Column(db.String(16))
    target_url = db.Column(db.Text)
    payload_data = db.Column(db.Text)
    ip_address = db.Column(db.String(46))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, user_id, admin_name, action_type, target_url, payload_data, ip_address):
        self.user_id = user_id
        self.admin_name = admin_name
        self.action_type = action_type
        self.target_url = target_url
        self.payload_data = payload_data
        self.ip_address = ip_address

def load(app):
    with app.app_context():
        db.create_all()

    plugin_bp = Blueprint('admin_activity_logger', __name__, template_folder='templates')

    @app.before_request
    def log_admin_activity():
        path = request.path
        
        # FIXED: Expanded path list boundaries to capture users, teams, and hint system changes
        is_admin_route = (
            path.startswith('/admin') or 
            path.startswith('/api/v1/admin') or 
            path.startswith('/api/v1/challenges') or
            path.startswith('/api/v1/users') or
            path.startswith('/api/v1/teams') or
            path.startswith('/api/v1/hints')
        )
        is_mutating_method = request.method in ['POST', 'PATCH', 'PUT', 'DELETE']
        
        if is_admin_route and is_mutating_method:
            user = get_current_user()
            if user and user.type == 'admin':
                try:
                    raw_data = request.get_json(silent=True) or request.form.to_dict() or {}
                    data_str = str(raw_data)[:500] if raw_data else "No payload parameters passed"
                except Exception:
                    data_str = "Error parsing action parameter logs"

                try:
                    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1')
                    client_ip = raw_ip.split(',')[0].strip()
                except Exception:
                    client_ip = "127.0.0.1"

                log_entry = AdminActivityLogs(
                    user_id=user.id,
                    admin_name=user.name,
                    action_type=request.method,
                    target_url=path,
                    payload_data=data_str,
                    ip_address=client_ip
                )
                db.session.add(log_entry)
                db.session.commit()

    @plugin_bp.route('/admin/activity-logs', methods=['GET'])
    @admins_only
    def admin_activity_dashboard():
        raw_logs = AdminActivityLogs.query.order_by(AdminActivityLogs.timestamp.desc()).all()
        processed_logs = []
        
        for l in raw_logs:
            # FIXED: Added explicit string checks to route categories correctly
            if 'challenges' in l.target_url:
                category = "Challenge Setup"
            elif 'hints' in l.target_url:
                category = "Hint Config"
            elif 'users' in l.target_url:
                category = "User Management"
            elif 'teams' in l.target_url:
                category = "Team Management"
            elif 'sponsors' in l.target_url:
                category = "Sponsor Adjust"
            elif 'reviews' in l.target_url or 'ratings' in l.target_url:
                category = "Feedback Review"
            else:
                category = "Platform Settings"
                
            payload_size = len(l.payload_data) if l.payload_data else 0
            
            processed_logs.append({
                'timestamp': l.timestamp,
                'admin_name': l.admin_name,
                'action_type': l.action_type,
                'target_url': l.target_url,
                'ip_address': l.ip_address,
                'payload_data': l.payload_data,
                'category': category,
                'size': payload_size
            })
            
        return render_template('admin_activity_logs.html', logs=processed_logs)

    @plugin_bp.route('/admin/activity-logs/export/csv', methods=['GET'])
    @admins_only
    def admin_activity_export_csv():
        raw_logs = AdminActivityLogs.query.order_by(AdminActivityLogs.timestamp.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow(['Timestamp (UTC)', 'Admin Name', 'Action Method', 'Category Context', 'Target URL Route', 'Client IP Address', 'Payload Size (Chars)', 'Payload Parameters'])
        
        for l in raw_logs:
            if 'challenges' in l.target_url:
                category = "Challenge Setup"
            elif 'hints' in l.target_url:
                category = "Hint Config"
            elif 'users' in l.target_url:
                category = "User Management"
            elif 'teams' in l.target_url:
                category = "Team Management"
            elif 'sponsors' in l.target_url:
                category = "Sponsor Adjust"
            else:
                category = "Platform Settings"
            payload_size = len(l.payload_data) if l.payload_data else 0
            
            writer.writerow([
                l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                l.admin_name,
                l.action_type,
                category,
                l.target_url,
                l.ip_address,
                payload_size,
                l.payload_data
            ])
            
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=admin_activity_report.csv"}
        )

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_activity_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/activity-logs"><i class="fas fa-history mr-2"></i>Admin Activity Log</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
