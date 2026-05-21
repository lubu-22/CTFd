import csv
import io
from flask import Blueprint, render_template, request, Response
from CTFd.models import db, Solves, Challenges, Teams, Users
from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user
import datetime

class ChallengeTimeTrack(db.Model):
    __tablename__ = "challenge_time_track"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'))
    first_opened = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    solved_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    def __init__(self, team_id, challenge_id, user_id=None):
        self.team_id = team_id
        self.challenge_id = challenge_id
        self.user_id = user_id

class ChallengeClicks(db.Model):
    __tablename__ = "challenge_clicks"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'))
    opened_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, team_id, challenge_id, user_id=None):
        self.team_id = team_id
        self.challenge_id = challenge_id
        self.user_id = user_id

def load(app):
    with app.app_context():
        db.create_all()
        
        try:
            db.session.execute(db.text("ALTER TABLE challenge_clicks ADD COLUMN user_id INTEGER NULL;"))
            db.session.execute(db.text("ALTER TABLE challenge_time_track ADD COLUMN user_id INTEGER NULL;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    plugin_bp = Blueprint('challenge_time_tracker', __name__, template_folder='templates')

    @app.after_request
    def track_challenge_opens(response):
        if request.blueprint == 'api' and request.path.startswith('/api/v1/challenges/') and request.method == 'GET':
            user = get_current_user()
            if user and user.team_id:
                try:
                    chal_id = int(request.path.split('/')[-1])
                    click_entry = ChallengeClicks(team_id=user.team_id, challenge_id=chal_id, user_id=user.id)
                    db.session.add(click_entry)
                    db.session.commit()
                except ValueError:
                    pass
        return response

    @plugin_bp.route('/admin/time-tracking', methods=['GET'])
    @admins_only
    def admin_time_tracking():
        all_teams = Teams.query.all()
        all_challenges = Challenges.query.all()
        MAX_SESSION_WINDOW = 900 

        for team in all_teams:
            team_users = db.session.query(Users).filter(Users.team_id == team.id).all()
            
            for user_obj in team_users:
                user_clicks = ChallengeClicks.query.filter_by(team_id=team.id, user_id=user_obj.id).order_by(ChallengeClicks.opened_at.asc()).all()
                if not user_clicks:
                    continue

                for chal in all_challenges:
                    solve_entry = Solves.query.filter_by(team_id=team.id, challenge_id=chal.id).first()
                    if not solve_entry:
                        continue 

                    total_active_seconds = 0
                    chal_clicks = [c for c in user_clicks if c.challenge_id == chal.id and c.opened_at <= solve_entry.date]
                    if not chal_clicks:
                        continue

                    for click in chal_clicks:
                        next_global_click = next((c for c in user_clicks if c.opened_at > click.opened_at), None)
                        if next_global_click and next_global_click.opened_at < solve_entry.date:
                            end_of_focus = next_global_click.opened_at
                        else:
                            end_of_focus = solve_entry.date

                        delta = (end_of_focus - click.opened_at).total_seconds()
                        if delta > MAX_SESSION_WINDOW:
                            delta = MAX_SESSION_WINDOW
                        if delta > 0:
                            total_active_seconds += int(delta)

                    existing_record = ChallengeTimeTrack.query.filter_by(team_id=team.id, user_id=user_obj.id, challenge_id=chal.id).first()
                    if existing_record:
                        existing_record.solved_at = solve_entry.date
                        existing_record.duration_seconds = total_active_seconds
                    else:
                        new_track = ChallengeTimeTrack(team_id=team.id, challenge_id=chal.id, user_id=user_obj.id)
                        new_track.first_opened = chal_clicks.opened_at
                        new_track.solved_at = solve_entry.date
                        new_track.duration_seconds = total_active_seconds
                        db.session.add(new_track)
                    db.session.commit()

        report_data = db.session.query(
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            ChallengeTimeTrack.first_opened,
            ChallengeTimeTrack.solved_at,
            ChallengeTimeTrack.duration_seconds
        ).join(Teams, Teams.id == ChallengeTimeTrack.team_id)\
         .join(Users, Users.id == ChallengeTimeTrack.user_id)\
         .join(Challenges, Challenges.id == ChallengeTimeTrack.challenge_id)\
         .order_by(ChallengeTimeTrack.duration_seconds.asc()).all()

        return render_template('admin_time_tracking.html', records=report_data)

    # --- NEW: BACKEND EXCEL CSV TIME TRACKING EXPORT ROUTE ---
    @plugin_bp.route('/admin/time-tracking/export/csv', methods=['GET'])
    @admins_only
    def admin_time_tracking_export_csv():
        report_data = db.session.query(
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            ChallengeTimeTrack.first_opened,
            ChallengeTimeTrack.solved_at,
            ChallengeTimeTrack.duration_seconds
        ).join(Teams, Teams.id == ChallengeTimeTrack.team_id)\
         .join(Users, Users.id == ChallengeTimeTrack.user_id)\
         .join(Challenges, Challenges.id == ChallengeTimeTrack.challenge_id)\
         .order_by(ChallengeTimeTrack.duration_seconds.asc()).all()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow(['Team Name', 'Player Name', 'Challenge Name', 'First Opened At (UTC)', 'Solved At (UTC)', 'Duration (Seconds)'])
        
        for r in report_data:
            writer.writerow([
                r.team_name,
                r.user_name,
                r.challenge_name,
                r.first_opened.strftime('%Y-%m-%d %H:%M:%S'),
                r.solved_at.strftime('%Y-%m-%d %H:%M:%S'),
                r.duration_seconds
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=classroom_time_tracking_report.csv"}
        )

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_tracking_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/time-tracking"><i class="fas fa-stopwatch mr-2"></i>Time Tracking</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
