from flask import Blueprint, render_template, request, jsonify
from functools import wraps
from CTFd.models import db, Submissions, Solves, Teams, Challenges, Users
from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user
import datetime

class SecurityAlerts(db.Model):
    __tablename__ = "security_alerts"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True) # New user track column
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'), nullable=True)
    alert_type = db.Column(db.String(64))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, team_id, challenge_id, alert_type, details, timestamp, user_id=None):
        self.team_id = team_id
        self.challenge_id = challenge_id
        self.alert_type = alert_type
        self.details = details
        self.timestamp = timestamp
        self.user_id = user_id

class ClassroomOpenLogs(db.Model):
    __tablename__ = "classroom_open_logs"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'))
    last_opened = db.Column(db.DateTime, default=datetime.datetime.utcnow)

def load(app):
    with app.app_context():
        db.create_all()
        
        # Schema Migrations Layer: Automatically inject user tracking keys into old db setups
        try:
            db.session.execute(db.text("ALTER TABLE security_alerts ADD COLUMN user_id INTEGER NULL;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    plugin_bp = Blueprint('security_monitor', __name__, template_folder='templates')

    BRUTE_FORCE_LIMIT = 5       
    BRUTE_FORCE_WINDOW = 120    
    LOCKOUT_DURATION = 180      
    LEAK_TIME_LIMIT = 15        

    @app.after_request
    def track_classroom_clicks(response):
        if request.blueprint == 'api' and request.path.startswith('/api/v1/challenges/') and request.method == 'GET':
            user = get_current_user()
            if user and user.team_id:
                try:
                    chal_id = int(request.path.split('/')[-1])
                    existing = ClassroomOpenLogs.query.filter_by(team_id=user.team_id, challenge_id=chal_id).first()
                    
                    if existing:
                        existing.last_opened = datetime.datetime.utcnow()
                    else:
                        log_entry = ClassroomOpenLogs(team_id=user.team_id, challenge_id=chal_id)
                        db.session.add(log_entry)
                        
                    db.session.commit()
                except ValueError:
                    pass
        return response

    def classroom_submission_wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == 'POST':
                user = get_current_user()
                if user and user.team_id:
                    try:
                        req_data = request.get_json() or request.form or {}
                        chal_id = int(req_data.get('challenge_id'))
                    except Exception:
                        return f(*args, **kwargs)

                    now = datetime.datetime.utcnow()
                    time_window = now - datetime.timedelta(seconds=BRUTE_FORCE_WINDOW)

                    wrong_count = Submissions.query.filter(
                        Submissions.team_id == user.team_id,
                        Submissions.challenge_id == chal_id,
                        Submissions.type == 'incorrect',
                        Submissions.date >= time_window
                    ).count()

                    if wrong_count >= BRUTE_FORCE_LIMIT:
                        last_wrong = Submissions.query.filter_by(
                            team_id=user.team_id, challenge_id=chal_id, type='incorrect'
                        ).order_by(Submissions.date.desc()).first()
                        
                        if last_wrong:
                            elapsed = (now - last_wrong.date).total_seconds()
                            remaining = int(LOCKOUT_DURATION - elapsed)
                            
                            if remaining > 0:
                                return jsonify({
                                    'success': True,
                                    'data': {
                                        'status': 'incorrect',
                                        'message': f'Workstation Locked! Too many wrong flags. Try again in {remaining} seconds.'
                                    }
                                }), 200
            return f(*args, **kwargs)
        return decorated_function

    if 'api.challenges_challenge_attempt' in app.view_functions:
        app.view_functions['api.challenges_challenge_attempt'] = classroom_submission_wrapper(app.view_functions['api.challenges_challenge_attempt'])
    if 'api.challenges_challenge_submission' in app.view_functions:
        app.view_functions['api.challenges_challenge_submission'] = classroom_submission_wrapper(app.view_functions['api.challenges_challenge_submission'])

    @plugin_bp.route('/admin/security', methods=['GET'])
    @admins_only
    def admin_security():
        all_teams = Teams.query.all()
        all_challenges = Challenges.query.all()

        for team in all_teams:
            for chal in all_challenges:
                
                wrong_subs = Submissions.query.filter_by(
                    team_id=team.id, 
                    challenge_id=chal.id, 
                    type='incorrect'
                ).order_by(Submissions.date.asc()).all()

                last_logged_alert_time = None

                for i in range(len(wrong_subs)):
                    window_start = wrong_subs[i].date
                    
                    if last_logged_alert_time and window_start <= last_logged_alert_time:
                        continue

                    subs_in_window = [s for s in wrong_subs[i:] if (s.date - window_start).total_seconds() <= BRUTE_FORCE_WINDOW]
                    match_count = len(subs_in_window)

                    if match_count >= BRUTE_FORCE_LIMIT:
                        latest_submission_time = subs_in_window[-1].date
                        # Capture which specific user triggered the threshold breach
                        triggering_sub = subs_in_window[-1]
                        details_text = f'Classroom alert: Team submitted {match_count} or more distinct incorrect flags within a 2-minute window.'
                        
                        existing_alert = SecurityAlerts.query.filter_by(
                            team_id=team.id, 
                            challenge_id=chal.id, 
                            alert_type='Brute-Force', 
                            timestamp=latest_submission_time
                        ).first()

                        if not existing_alert:
                            db_alert = SecurityAlerts(
                                team_id=team.id, 
                                challenge_id=chal.id, 
                                alert_type='Brute-Force', 
                                details=details_text, 
                                timestamp=latest_submission_time,
                                user_id=triggering_sub.user_id # Log specific user
                            )
                            db.session.add(db_alert)
                            db.session.commit()
                        
                        last_logged_alert_time = latest_submission_time

                solve_entry = Solves.query.filter_by(team_id=team.id, challenge_id=chal.id).first()
                if solve_entry:
                    open_record = ClassroomOpenLogs.query.filter_by(team_id=team.id, challenge_id=chal.id).first()
                    
                    if open_record:
                        time_to_solve = (solve_entry.date - open_record.last_opened).total_seconds()
                        if 0 <= time_to_solve < LEAK_TIME_LIMIT:
                            details_text = f'Instant solve anomaly! Solved in {int(time_to_solve)}s from opening. Suspect answer-sharing inside the lab.'
                            
                            existing_leak = SecurityAlerts.query.filter_by(
                                team_id=team.id, 
                                challenge_id=chal.id, 
                                alert_type='Flag Leak Suspect', 
                                timestamp=solve_entry.date
                            ).first()

                            if not existing_leak:
                                db_leak = SecurityAlerts(
                                    team_id=team.id, 
                                    challenge_id=chal.id, 
                                    alert_type='Flag Leak Suspect', 
                                    details=details_text, 
                                    timestamp=solve_entry.date,
                                    user_id=solve_entry.user_id # Log specific user
                                )
                                db.session.add(db_leak)
                                db.session.commit()

        # FIXED: Added native query connection to Users model table schema
        alerts = db.session.query(
            SecurityAlerts.id, SecurityAlerts.alert_type, SecurityAlerts.details, SecurityAlerts.timestamp,
            Teams.name.label('team_name'), Users.name.label('user_name'), Challenges.name.label('challenge_name')
        ).join(Teams, Teams.id == SecurityAlerts.team_id)\
         .outerjoin(Users, Users.id == SecurityAlerts.user_id)\
         .outerjoin(Challenges, Challenges.id == SecurityAlerts.challenge_id)\
         .order_by(SecurityAlerts.timestamp.desc()).all()

        return render_template('admin_security.html', alerts=alerts)

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_security_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/security"><i class="fas fa-shield-alt mr-2"></i>Security Monitor</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
