import csv
import io
from flask import Blueprint, render_template, request, Response
from sqlalchemy.sql import and_
from CTFd.models import db, Users, Teams, Solves, Submissions, Challenges, Unlocks, Hints
from CTFd.utils.decorators import admins_only

def load(app):
    plugin_bp = Blueprint('performance_reports', __name__, template_folder='templates')

    @plugin_bp.route('/admin/performance', methods=['GET'])
    @admins_only
    def admin_performance_dashboard():
        team_filter = request.args.get('team_id', '')
        category_filter = request.args.get('category', '')

        user_query = db.session.query(Users, Teams).join(Teams, Teams.id == Users.team_id)
        if team_filter:
            user_query = user_query.filter(Teams.id == int(team_filter))
            
        students = user_query.all()
        
        # FIXED: Safely unpack database tuples and drop completely empty or blank string categories
        categories = db.session.query(Challenges.category).distinct().all()
        category_list = [c[0].strip() for c in categories if c and c[0] and c[0].strip() != ""]

        performance_matrix = []

        for user, team in students:
            total_solves = Solves.query.filter_by(user_id=user.id).count()
            total_subs = Submissions.query.filter_by(user_id=user.id).count()
            solve_percentage = int((total_solves / total_subs) * 100) if total_subs > 0 else 0

            # Itemize challenge-by-challenge engagement metrics per student
            interacted_challenge_ids = db.session.query(Submissions.challenge_id).filter(Submissions.user_id == user.id).distinct().all()
            
            conquered_challenges = []
            failed_breakdown = []
            stuck_challenges = []

            for (chal_id,) in interacted_challenge_ids:
                chal_name = db.session.query(Challenges.name).filter(Challenges.id == chal_id).scalar() or "Unknown"
                total_tries = Submissions.query.filter_by(user_id=user.id, challenge_id=chal_id).count()
                is_solved = Solves.query.filter_by(user_id=user.id, challenge_id=chal_id).first() is not None
                fail_count = Submissions.query.filter_by(user_id=user.id, challenge_id=chal_id, type='incorrect').count()

                if is_solved:
                    conquered_challenges.append(f"{chal_name} ({total_tries} try{'s' if total_tries > 1 else ''})")
                    if fail_count > 0:
                        failed_breakdown.append(f"{chal_name} ({fail_count} wrong)")
                else:
                    failed_breakdown.append(f"{chal_name} ({fail_count} wrong)")
                    if fail_count >= 3:
                        stuck_challenges.append(f"{chal_name} ({fail_count} fails)")

            # Process Hint Titles with a numeric fallback chain for tracking footprints
            unlocked_records = db.session.query(Hints.id, Hints.title, Challenges.name).join(Unlocks, Unlocks.target == Hints.id)\
                                         .join(Challenges, Challenges.id == Hints.challenge_id)\
                                         .filter(Unlocks.user_id == user.id, Unlocks.type == 'hints').all()
            
            hints_used = []
            for h_id, h_title, chal in unlocked_records:
                if h_title and h_title.strip() != "":
                    hints_used.append(f"{chal}: {h_title}")
                else:
                    all_chal_hints = Hints.query.filter_by(challenge_id=db.session.query(Hints.challenge_id).filter_by(id=h_id).scalar()).order_by(Hints.cost.asc(), Hints.id.asc()).all()
                    hint_index = next((i + 1 for i, h in enumerate(all_chal_hints) if h.id == h_id), 1)
                    hints_used.append(f"{chal}: Hint #{hint_index}")

            category_breakdown = {}
            for cat in category_list:
                cat_solves = db.session.query(Solves).join(Challenges, Challenges.id == Solves.challenge_id)\
                                       .filter(Solves.user_id == user.id, Challenges.category == cat).count()
                category_breakdown[cat] = cat_solves

            if category_filter and category_breakdown.get(category_filter, 0) == 0:
                continue

            performance_matrix.append({
                'user_id': user.id,
                'user_name': user.name,
                'team_name': team.name,
                'score': user.score or 0,
                'solves_count': total_solves,
                'submissions_count': total_subs,
                'solve_efficiency': solve_percentage,
                'conquered': conquered_challenges,
                'failed_breakdown': failed_breakdown,
                'stuck': stuck_challenges,
                'hints_used': hints_used,
                'categories': category_breakdown
            })

        all_teams = Teams.query.all()

        return render_template(
            'admin_performance_report.html',
            matrix=performance_matrix,
            teams=all_teams,
            categories=category_list,
            selected_team=team_filter,
            selected_cat=category_filter
        )

    @plugin_bp.route('/admin/performance/export/csv', methods=['GET'])
    @admins_only
    def admin_performance_export_csv():
        students = db.session.query(Users, Teams).join(Teams, Teams.id == Users.team_id).all()
        
        # FIXED: Safely unpack database tuples and drop completely empty or blank string categories inside exporter
        categories = db.session.query(Challenges.category).distinct().all()
        category_list = [c[0].strip() for c in categories if c and c[0] and c[0].strip() != ""]

        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        
        headers = ['Player Name', 'Team Name', 'Total Score', 'Total Solves', 'Total Attempts', 'Accuracy %', 'Hints Unlocked Details', 'Solved Challenges (Attempts)', 'Failed Attempts Breakdown', 'Currently Stuck On']
        for cat in category_list:
            headers.append(f'Solves: {cat}')
            
        writer.writerow(headers)

        for user, team in students:
            total_solves = Solves.query.filter_by(user_id=user.id).count()
            total_subs = Submissions.query.filter_by(user_id=user.id).count()
            accuracy = int((total_solves / total_subs) * 100) if total_subs > 0 else 0

            interacted_ids = db.session.query(Submissions.challenge_id).filter(Submissions.user_id == user.id).distinct().all()
            conquered_list = []
            failed_list = []
            stuck_list = []

            for (c_id,) in interacted_ids:
                c_name = db.session.query(Challenges.name).filter(Challenges.id == c_id).scalar() or "Unknown"
                t_tries = Submissions.query.filter_by(user_id=user.id, challenge_id=c_id).count()
                is_solved = Solves.query.filter_by(user_id=user.id, challenge_id=c_id).first() is not None
                f_count = Submissions.query.filter_by(user_id=user.id, challenge_id=c_id, type='incorrect').count()

                if is_solved:
                    conquered_list.append(f"{c_name} ({t_tries} tries)")
                    if f_count > 0:
                        failed_list.append(f"{c_name} ({f_count} wrong)")
                else:
                    failed_list.append(f"{c_name} ({f_count} wrong)")
                    if f_count >= 3:
                        stuck_list.append(f"{c_name} ({f_count} fails)")

            unlocked_records = db.session.query(Hints.id, Hints.title, Challenges.name).join(Unlocks, Unlocks.target == Hints.id)\
                                         .join(Challenges, Challenges.id == Hints.challenge_id)\
                                         .filter(Unlocks.user_id == user.id, Unlocks.type == 'hints').all()
            csv_hints = []
            for h_id, h_title, chal in unlocked_records:
                if h_title and h_title.strip() != "":
                    csv_hints.append(f"[{chal}] {h_title}")
                else:
                    all_chal_hints = Hints.query.filter_by(challenge_id=db.session.query(Hints.challenge_id).filter_by(id=h_id).scalar()).order_by(Hints.cost.asc(), Hints.id.asc()).all()
                    hint_index = next((i + 1 for i, h in enumerate(all_chal_hints) if h.id == h_id), 1)
                    csv_hints.append(f"[{chal}] Hint #{hint_index}")

            row = [user.name, team.name, user.score or 0, total_solves, total_subs, accuracy, "; ".join(csv_hints), "; ".join(conquered_list), "; ".join(failed_list), "; ".join(stuck_list)]
            for cat in category_list:
                cat_solves = db.session.query(Solves).join(Challenges, Challenges.id == Solves.challenge_id)\
                                       .filter(Solves.user_id == user.id, Challenges.category == cat).count()
                row.append(cat_solves)
                
            writer.writerow(row)

        output.seek(0)
        return Response(output.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=user_performance_report.csv"})

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_performance_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'id="custom-extensions-menu">'
            if target_marker in html_content:
                new_link = f'{target_marker}\n                    <a class="dropdown-item" href="/admin/performance"><i class="fas fa-chart-line mr-2"></i>User Performance Matrix</a>'
                html_content = html_content.replace(target_marker, new_link, 1)
                response.set_data(html_content)
        return response
