import datetime
import calendar
from flask import Blueprint, render_template, request, redirect, url_for
from CTFd.models import db
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only

def load(app):
    plugin_bp = Blueprint('scoreboard_freeze', __name__, template_folder='templates')

    @plugin_bp.route('/admin/freeze/settings', methods=['GET', 'POST'])
    @admins_only
    def freeze_settings():
        if request.method == 'POST':
            enabled = request.form.get('freeze_enabled', '0')
            target_time_str = request.form.get('freeze_time', '')
            
            set_config('scheduled_freeze_enabled', enabled)
            set_config('scheduled_freeze_time', target_time_str)
            
            if enabled == '0':
                set_config('freeze', None)
            else:
                try:
                    dt = datetime.datetime.strptime(target_time_str, '%Y-%m-%dT%H:%M')
                    unix_timestamp = int(calendar.timegm(dt.utctimetuple()))
                    set_config('freeze', unix_timestamp)
                except Exception:
                    pass
                
            return redirect(url_for('scoreboard_freeze.freeze_settings'))

        current_settings = {
            'enabled': get_config('scheduled_freeze_enabled') or '0',
            'time': get_config('scheduled_freeze_time') or ''
        }
        return render_template('freeze_settings.html', settings=current_settings)

    app.register_blueprint(plugin_bp)

    @app.before_request
    def check_scoreboard_freeze_schedule():
        is_enabled = get_config('scheduled_freeze_enabled') == '1'
        freeze_time_str = get_config('scheduled_freeze_time')
        
        if is_enabled and freeze_time_str:
            try:
                dt = datetime.datetime.strptime(freeze_time_str, '%Y-%m-%dT%H:%M')
                current_time = datetime.datetime.utcnow()
                
                if current_time >= dt:
                    unix_timestamp = int(calendar.timegm(dt.utctimetuple()))
                    if str(get_config('freeze')) != str(unix_timestamp):
                        set_config('freeze', unix_timestamp)
            except Exception:
                pass 

    @app.after_request
    def inject_freeze_nav(response):
        if response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            target_marker = 'href="/admin/sponsors"'
            if target_marker in html_content:
                new_link = 'href="/admin/sponsors"><i class="fas fa-handshake mr-2"></i>Sponsors</a>\n                    <a class="dropdown-item" href="/admin/freeze/settings"><i class="fas fa-clock mr-2"></i>Scoreboard Freeze</a>'
                html_content = html_content.replace('href="/admin/sponsors">Sponsors</a>', new_link, 1)
                html_content = html_content.replace('href="/admin/sponsors"><i class="fas fa-handshake mr-2"></i>Sponsors</a>', new_link, 1)
                response.set_data(html_content)
        return response
