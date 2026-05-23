import csv
import io
from flask import Blueprint, render_template, request, Response
from CTFd.models import db, Challenges, Teams, Users, Ratings
from CTFd.utils.decorators import admins_only

def load(app):
    plugin_bp = Blueprint('challenge_reviews', __name__, template_folder='templates')

    @plugin_bp.route('/admin/reviews', methods=['GET'])
    @admins_only
    def admin_reviews_dashboard():
        # Metric A: Calculate total positive upvotes vs downvotes per challenge node
        summary_stats = db.session.query(
            Challenges.name.label('challenge_name'),
            db.func.count(Ratings.id).label('total_reviews'),
            db.func.sum(db.case([(Ratings.value == 1, 1)], else_=0)).label('upvotes'),
            db.func.sum(db.case([(Ratings.value == -1, 1)], else_=0)).label('downvotes')
        ).join(Ratings, Ratings.challenge_id == Challenges.id)\
         .group_by(Challenges.id).all()

        # Metric B: Detailed timeline log ledger passing raw binary integer flags
        detailed_reviews = db.session.query(
            Ratings.date.label('timestamp'),
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            Ratings.value.label('vote_score'),  # Will pass exactly 1 or -1
            Ratings.review.label('text_feedback')
        ).join(Challenges, Challenges.id == Ratings.challenge_id)\
         .join(Users, Users.id == Ratings.user_id)\
         .outerjoin(Teams, Teams.id == Users.team_id)\
         .order_by(Ratings.date.desc()).all()

        return render_template(
            'admin_challenge_reviews.html',
            summary_stats=summary_stats,
            detailed_reviews=detailed_reviews
        )

    # --- NEW: BACKEND EXCEL CSV CHALLENGE REVIEWS EXPORT ROUTE ---
    @plugin_bp.route('/admin/reviews/export/csv', methods=['GET'])
    @admins_only
    def admin_reviews_export_csv():
        detailed_reviews = db.session.query(
            Ratings.date.label('timestamp'),
            Teams.name.label('team_name'),
            Users.name.label('user_name'),
            Challenges.name.label('challenge_name'),
            Ratings.value.label('vote_score'),
            Ratings.review.label('text_feedback')
        ).join(Challenges, Challenges.id == Ratings.challenge_id)\
         .join(Users, Users.id == Ratings.user_id)\
         .outerjoin(Teams, Teams.id == Users.team_id)\
         .order_by(Ratings.date.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        # Write clean spreadsheet tracking column headers
        writer.writerow(['Timestamp (UTC)', 'Team Name', 'Player Name', 'Challenge Name', 'Vote Score', 'Student Review Text'])
        
        for r in detailed_reviews:
            writer.writerow([
                r.timestamp.strftime('%Y-%m-%d %H:%M:%S') if r.timestamp else 'N/A',
                r.team_name if r.team_name else 'N/A',
                r.user_name if r.user_name else 'Unknown',
                r.challenge_name,
                'Upvote' if r.vote_score == 1 else 'Downvote',
                r.text_feedback if r.text_feedback else ''
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=challenge_reviews_report.csv"}
        )

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_reviews_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/reviews"><i class="fas fa-comments mr-2"></i>Challenge Reviews</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
