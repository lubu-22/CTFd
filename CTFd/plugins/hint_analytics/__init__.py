import csv
import io
from flask import Blueprint, render_template, request, Response
from CTFd.models import db, Unlocks, Hints, Challenges, Teams, Users
from CTFd.utils.decorators import admins_only

def load(app):
    # Register our new independent analytics blueprint engine layout channels
    plugin_bp = Blueprint('hint_analytics', __name__, template_folder='templates')

    @plugin_bp.route('/admin/hints-analytics', methods=['GET'])
    @admins_only
    def admin_hints_analytics():
        # Metric A: Challenges generating the most hint request queries
        challenge_stats = db.session.query(
            Challenges.name.label('challenge_name'),
            db.func.count(Unlocks.id).label('total_unlocks')
        ).join(Hints, Hints.challenge_id == Challenges.id)\
         .join(Unlocks, Unlocks.target == Hints.id)\
         .filter(Unlocks.type == 'hints')\
         .group_by(Challenges.id)\
         .order_by(db.desc('total_unlocks')).all()

        # Metric B: High-reliance student profiles tracking team structures
        player_stats = db.session.query(
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            db.func.count(Unlocks.id).label('total_unlocks')
        ).join(Teams, Teams.id == Unlocks.team_id)\
         .join(Users, Users.id == Unlocks.user_id)\
         .filter(Unlocks.type == 'hints')\
         .group_by(Users.id)\
         .order_by(db.desc('total_unlocks')).all()

        # Metric C: Grand matrix of individual raw transactions
        detailed_logs = db.session.query(
            Unlocks.date.label('timestamp'),
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            Hints.content.label('hint_text'),
            Hints.cost.label('hint_cost')
        ).join(Teams, Teams.id == Unlocks.team_id)\
         .join(Users, Users.id == Unlocks.user_id)\
         .join(Hints, Hints.id == Unlocks.target)\
         .join(Challenges, Challenges.id == Hints.challenge_id)\
         .filter(Unlocks.type == 'hints')\
         .order_by(Unlocks.date.desc()).all()

        return render_template(
            'admin_hints_analytics.html',
            challenge_stats=challenge_stats,
            player_stats=player_stats,
            detailed_logs=detailed_logs
        )

    # --- NATIVE EXCEL CSV LOG GENERATOR EXPORTER ---
    @plugin_bp.route('/admin/hints-analytics/export/csv', methods=['GET'])
    @admins_only
    def admin_hints_analytics_export_csv():
        detailed_logs = db.session.query(
            Unlocks.date.label('timestamp'),
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            Hints.content.label('hint_text'),
            Hints.cost.label('hint_cost')
        ).join(Teams, Teams.id == Unlocks.team_id)\
         .join(Users, Users.id == Unlocks.user_id)\
         .join(Hints, Hints.id == Unlocks.target)\
         .join(Challenges, Challenges.id == Hints.challenge_id)\
         .filter(Unlocks.type == 'hints')\
         .order_by(Unlocks.date.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        writer.writerow(['Timestamp (UTC)', 'Team Name', 'Player Name', 'Challenge Context', 'Hint Content Payload', 'Point Cost Deduction'])
        
        for log in detailed_logs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.team_name,
                log.user_name,
                log.challenge_name,
                log.hint_text,
                log.hint_cost
            ])
            
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=classroom_hint_usage_report.csv"}
        )

    app.register_blueprint(plugin_bp)

    # Automatically hooks this new screen into your existing custom shared Extensions navbar menu
    @app.after_request
    def inject_hints_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/hints-analytics"><i class="fas fa-lightbulb mr-2"></i>Hint Usage Analytics</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
