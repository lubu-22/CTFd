from flask import Blueprint, render_template, request, redirect, url_for
from CTFd.models import db
from CTFd.utils.decorators import admins_only
from CTFd.utils.uploads import upload_file

class Sponsors(db.Model):
    __tablename__ = "sponsors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    link = db.Column(db.String(512))
    image = db.Column(db.String(512))
    description = db.Column(db.Text)

    def __init__(self, name, link, image, description):
        self.name = name
        self.link = link
        self.image = image
        self.description = description

def load(app):
    with app.app_context():
        db.create_all()

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
                
                new_sponsor = Sponsors(name=name, link=link, image=image_path, description=description)
                db.session.add(new_sponsor)
                db.session.commit()
                
            return redirect(url_for('sponsors_manager.admin_sponsors'))

        all_sponsors = Sponsors.query.all()
        return render_template('admin_sponsors.html', sponsors=all_sponsors)

    app.register_blueprint(plugin_bp)

    # Automatically hooks the navigation menu into the admin view pipeline
    @app.after_request
    def inject_admin_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = '<ul class="navbar-nav mr-auto">'
            
            if target_marker in html_content:
                # Creates a clean, styled dropdown box right on your navbar line
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
        return dict(dynamic_sponsors=Sponsors.query.all())
