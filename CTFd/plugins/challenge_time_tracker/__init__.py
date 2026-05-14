from flask import Blueprint, render_template, request
from CTFd.models import db, Solves, Challenges, Teams
from CTFd.utils.decorators import admins_only
from CTFd.utils.user import get_current_user
import datetime

class ChallengeTimeTrack(db.Model):
    __tablename__ = "challenge_time_track"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'))
    first_opened = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    solved_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)

    def __init__(self, team_id, challenge_id):
        self.team_id = team_id
        self.challenge_id = challenge_id

class ChallengeClicks(db.Model):
    __tablename__ = "challenge_clicks"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'))
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'))
    opened_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, team_id, challenge_id):
        self.team_id = team_id
        self.challenge_id = challenge_id

def load(app):
    with app.app_context():
        db.create_all()

    plugin_bp = Blueprint('challenge_time_tracker', __name__, template_folder='templates')

    @app.after_request
    def track_challenge_opens(response):
        if request.blueprint == 'api' and request.path.startswith('/api/v1/challenges/') and request.method == 'GET':
            user = get_current_user()
            if user and user.team_id:
                try:
                    chal_id = int(request.path.split('/')[-1])
                    click_entry = ChallengeClicks(team_id=user.team_id, challenge_id=chal_id)
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
            team_clicks = ChallengeClicks.query.filter_by(team_id=team.id).order_by(ChallengeClicks.opened_at.asc()).all()
            if not team_clicks:
                continue

            for chal in all_challenges:
                solve_entry = Solves.query.filter_by(team_id=team.id, challenge_id=chal.id).first()
                if not solve_entry:
                    continue 

                total_active_seconds = 0
                chal_clicks = [c for c in team_clicks if c.challenge_id == chal.id and c.opened_at <= solve_entry.date]
                
                if not chal_clicks:
                    continue

                for click in chal_clicks:
                    next_global_click = next((c for c in team_clicks if c.opened_at > click.opened_at), None)
                    
                    if next_global_click and next_global_click.opened_at < solve_entry.date:
                        end_of_focus = next_global_click.opened_at
                    else:
                        end_of_focus = solve_entry.date

                    delta = (end_of_focus - click.opened_at).total_seconds()
                    
                    if delta > MAX_SESSION_WINDOW:
                        delta = MAX_SESSION_WINDOW
                    
                    if delta > 0:
                        total_active_seconds += int(delta)

                # --- NEW: WRITE PERMANENTLY TO THE PHYSICAL SQL TABLE ---
                # Check if this calculation row already exists on the disk
                existing_record = ChallengeTimeTrack.query.filter_by(team_id=team.id, challenge_id=chal.id).first()
                
                if existing_record:
                    # Keep it synchronized if updates occurred
                    existing_record.solved_at = solve_entry.date
                    existing_record.duration_seconds = total_active_seconds
                else:
                    # Stams a new permanent record into your hard drive database table
                    new_track = ChallengeTimeTrack(team_id=team.id, challenge_id=chal.id)
                    new_track.first_opened = chal_clicks[0].opened_at
                    new_track.solved_at = solve_entry.date
                    new_track.duration_seconds = total_active_seconds
                    db.session.add(new_track)
                
                db.session.commit()

        # Query the rows straight out of the physical database table to render the UI screen
        report_data = db.session.query(
            Teams.name.label('team_name'),
            Challenges.name.label('challenge_name'),
            ChallengeTimeTrack.first_opened,
            ChallengeTimeTrack.solved_at,
            ChallengeTimeTrack.duration_seconds
        ).join(Teams, Teams.id == ChallengeTimeTrack.team_id)\
         .join(Challenges, Challenges.id == ChallengeTimeTrack.challenge_id)\
         .order_by(ChallengeTimeTrack.duration_seconds.asc()).all()

        return render_template('admin_time_tracking.html', records=report_data)

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_tracking_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            
            if target_marker in html_content:
                # Appends a clean sub-link option inside the drop container layout panel
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/time-tracking"><i class="fas fa-stopwatch mr-2"></i>Time Tracking</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
