from flask import Blueprint, render_template, abort
from CTFd.models import db, Users, Teams, Solves, Submissions, Challenges, Unlocks, Hints
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user

def load(app):
    plugin_bp = Blueprint('user_performance_report', __name__, template_folder='templates')

    @plugin_bp.route('/performance/team', methods=['GET'])
    @authed_only
    def user_team_performance():
        user = get_current_user()
        if not user or not user.team_id:
            abort(403)

        team_id = user.team_id
        team_obj = db.session.query(Teams).filter_by(id=team_id).first()
        
        students = db.session.query(Users, Teams).join(Teams, Teams.id == Users.team_id)\
                             .filter(Teams.id == team_id).all()
                            
        categories = db.session.query(Challenges.category).distinct().all()
        # FIXED: Accesses the tuple item using [0] to resolve the AttributeError crash
        category_list = [c[0].strip() for c in categories if c and c[0] and c[0].strip() != ""]

        performance_matrix = []

        for u, t in students:
            total_solves = db.session.query(Solves).filter_by(user_id=u.id).count()
            total_subs = db.session.query(Submissions).filter_by(user_id=u.id).count()
            solve_percentage = int((total_solves / total_subs) * 100) if total_subs > 0 else 0

            interacted_challenge_ids = db.session.query(Submissions.challenge_id).filter(Submissions.user_id == u.id).distinct().all()
            
            conquered_challenges = []
            failed_breakdown = []
            stuck_challenges = []

            for (chal_id,) in interacted_challenge_ids:
                chal_name = db.session.query(Challenges.name).filter(Challenges.id == chal_id).scalar() or "Unknown"
                total_tries = db.session.query(Submissions).filter_by(user_id=u.id, challenge_id=chal_id).count()
                is_solved = db.session.query(Solves).filter_by(user_id=u.id, challenge_id=chal_id).first() is not None
                fail_count = db.session.query(Submissions).filter_by(user_id=u.id, challenge_id=chal_id, type='incorrect').count()

                if is_solved:
                    conquered_challenges.append(f"{chal_name} ({total_tries} try{'s' if total_tries > 1 else ''})")
                    if fail_count > 0:
                        failed_breakdown.append(f"{chal_name} ({fail_count} wrong)")
                else:
                    failed_breakdown.append(f"{chal_name} ({fail_count} wrong)")
                    if fail_count >= 3:
                        stuck_challenges.append(f"{chal_name} ({fail_count} fails)")

            unlocked_records = db.session.query(Hints.id, Hints.title, Challenges.name).join(Unlocks, Unlocks.target == Hints.id)\
                                         .join(Challenges, Challenges.id == Hints.challenge_id)\
                                         .filter(Unlocks.user_id == u.id, Unlocks.type == 'hints').all()
            
            hints_used = []
            for h_id, h_title, chal in unlocked_records:
                if h_title and h_title.strip() != "":
                    hints_used.append(f"{chal}: {h_title}")
                else:
                    all_chal_hints = db.session.query(Hints).filter_by(challenge_id=db.session.query(Hints.challenge_id).filter_by(id=h_id).scalar()).order_by(Hints.cost.asc(), Hints.id.asc()).all()
                    hint_index = next((i + 1 for i, h in enumerate(all_chal_hints) if h.id == h_id), 1)
                    hints_used.append(f"{chal}: Hint #{hint_index}")

            category_breakdown = {}
            for cat in category_list:
                cat_solves = db.session.query(Solves).join(Challenges, Challenges.id == Solves.challenge_id)\
                                       .filter(Solves.user_id == u.id, Challenges.category == cat).count()
                category_breakdown[cat] = cat_solves

            performance_matrix.append({
                'user_id': u.id,
                'user_name': u.name,
                'team_name': t.name,
                'score': u.score or 0,
                'solves_count': total_solves,
                'submissions_count': total_subs,
                'solve_efficiency': solve_percentage,
                'conquered': conquered_challenges,
                'failed_breakdown': failed_breakdown,
                'stuck': stuck_challenges,
                'hints_used': hints_used,
                'categories': category_breakdown
            })

        return render_template(
            'user_team_report.html',
            matrix=performance_matrix,
            team=team_obj,
            categories=category_list
        )

    app.register_blueprint(plugin_bp)
