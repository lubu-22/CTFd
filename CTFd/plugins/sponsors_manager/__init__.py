from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from CTFd.models import db, Pages
from CTFd.utils.decorators import admins_only
from CTFd.utils.uploads import upload_file

class Sponsors(db.Model):
    __tablename__ = "sponsors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    link = db.Column(db.String(512))
    image = db.Column(db.String(512))
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=0)

    def __init__(self, name, link, image, description, sort_order=0):
        self.name = name
        self.link = link
        self.image = image
        self.description = description
        self.sort_order = sort_order

def load(app):
    with app.app_context():
        db.create_all()

        # Schema Migration Safety Check
        try:
            db.session.execute(db.text("ALTER TABLE sponsors ADD COLUMN sort_order INTEGER DEFAULT 0;"))
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 1. Auto-create mandatory index page route if missing
        existing_page = Pages.query.filter_by(route="index").first()
        if not existing_page:
            new_index_page = Pages(
                title="Home",
                route="index",
                content="", 
                draft=False, hidden=False, auth_required=False
            )
            db.session.add(new_index_page)
            db.session.commit()

        # 2. Auto-seed placeholder sponsor data on fresh clones
        if Sponsors.query.count() == 0:
            default_sponsor = Sponsors(
                name="University Lab Partner",
                link="https://example.com",
                image="/themes/core/static/img/logo.png",
                description="Default classroom partner. Customize or replace this placeholder within the admin sponsors extensions tab.",
                sort_order=1
            )
            db.session.add(default_sponsor)
            db.session.commit()

    plugin_bp = Blueprint('sponsors_manager', __name__, template_folder='templates')

    @plugin_bp.route('/admin/sponsors', methods=['GET', 'POST'])
    @admins_only
    def admin_sponsors():
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'delete':
                sponsor_id = request.form.get('id')
                Sponsors.query.filter_by(id=sponsor_id).delete()
                db.session.commit()
                
            elif action == 'update':
                sponsor_id = request.form.get('id')
                sponsor = Sponsors.query.filter_by(id=sponsor_id).first()
                if sponsor:
                    sponsor.name = request.form.get('name')
                    sponsor.link = request.form.get('link')
                    sponsor.description = request.form.get('description')
                    
                    # FIXED: Correctly parses and saves image file uploads during edits
                    file = request.files.get('image_file')
                    if file and file.filename != '':
                        file_obj = upload_file(file=file, challenge_id=None)
                        sponsor.image = f"/files/{file_obj.location}"
                    
                    db.session.commit()
                    
            else:
                name = request.form.get('name')
                link = request.form.get('link')
                description = request.form.get('description')
                image_path = ""

                file = request.files.get('image_file')
                if file and file.filename != '':
                    file_obj = upload_file(file=file, challenge_id=None)
                    image_path = f"/files/{file_obj.location}"
                
                max_order = db.session.query(db.func.max(Sponsors.sort_order)).scalar() or 0
                new_sponsor = Sponsors(name=name, link=link, image=image_path, description=description, sort_order=max_order + 1)
                db.session.add(new_sponsor)
                db.session.commit()
                
            return redirect(url_for('sponsors_manager.admin_sponsors'))

        all_sponsors = Sponsors.query.order_by(Sponsors.sort_order.asc(), Sponsors.id.asc()).all()
        return render_template('admin_sponsors.html', sponsors=all_sponsors)

    # BACKEND REORDER ROUTE: SHIFT SPONSOR UP
    @plugin_bp.route('/admin/sponsors/up/<int:sponsor_id>', methods=['POST'])
    @admins_only
    def admin_sponsors_up(sponsor_id):
        current_sponsor = Sponsors.query.get_or_404(sponsor_id)
        previous_sponsor = Sponsors.query.filter(Sponsors.sort_order < current_sponsor.sort_order)\
                                         .order_by(Sponsors.sort_order.desc()).first()
        if previous_sponsor:
            temp_order = current_sponsor.sort_order
            current_sponsor.sort_order = previous_sponsor.sort_order
            previous_sponsor.sort_order = temp_order
            db.session.commit()
            
        return redirect(url_for('sponsors_manager.admin_sponsors'))

    # BACKEND REORDER ROUTE: SHIFT SPONSOR DOWN
    @plugin_bp.route('/admin/sponsors/down/<int:sponsor_id>', methods=['POST'])
    @admins_only
    def admin_sponsors_down(sponsor_id):
        current_sponsor = Sponsors.query.get_or_404(sponsor_id)
        next_sponsor = Sponsors.query.filter(Sponsors.sort_order > current_sponsor.sort_order)\
                                     .order_by(Sponsors.sort_order.asc()).first()
        if next_sponsor:
            temp_order = current_sponsor.sort_order
            current_sponsor.sort_order = next_sponsor.sort_order
            next_sponsor.sort_order = temp_order
            db.session.commit()
            
        return redirect(url_for('sponsors_manager.admin_sponsors'))

    app.register_blueprint(plugin_bp)

    @app.after_request
    def inject_admin_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = '<ul class="navbar-nav mr-auto">'
            
            if target_marker in html_content:
                dropdown_markup = (
                    f'{target_marker}\n'
                    f'            <li class="nav-item dropdown">\n'
                    f'                <a class="nav-link dropdown-toggle" href="#" id="extensionsDropdown" role="button" data-toggle="dropdown" aria-has_popup="true" aria-expanded="false">\n'
                    f'                    <i class="fas fa-tools mr-1"></i> Extensions\n'
                    f'                </a>\n'
                    f'                <div class="dropdown-menu" aria-labelledby="extensionsDropdown" id="custom-extensions-menu">\n'
                    f'                    <a class="dropdown-item" href="{url_for("sponsors_manager.admin_sponsors")}"><i class="fas fa-handshake mr-2"></i>Sponsors</a>\n'
                    f'                </div>\n'
                    f'            </li>'
                )
                html_content = html_content.replace(target_marker, dropdown_markup, 1)
                response.set_data(html_content)
        return response

    @app.context_processor
    def inject_sponsors():
        return dict(dynamic_sponsors=Sponsors.query.order_by(Sponsors.sort_order.asc()).all())
