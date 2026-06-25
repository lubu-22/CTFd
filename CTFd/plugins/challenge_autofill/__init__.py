from flask import Blueprint, render_template, request, redirect, url_for
from CTFd.models import db, Challenges
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only

def load(app):
    # Initialize blueprint pinned to local templates subdirectory context
    plugin_bp = Blueprint('challenge_autofill', __name__, template_folder='templates')

    # CONFIGURATION INTERFACE ROUTE FOR ORGANIZERS
    @plugin_bp.route('/admin/autofill/settings', methods=['GET', 'POST'])
    @admins_only
    def autofill_settings():
        if request.method == 'POST':
            action_type = request.form.get('action_type', 'save_defaults')

            # --- ACTION A: SAVE THE DEFAULT WIZARD CONFIGURATIONS ---
            if action_type == 'save_defaults':
                set_config('autofill_std_category', request.form.get('std_category', 'Lab-Standard'))
                set_config('autofill_std_value', request.form.get('std_value', '100'))
                set_config('autofill_std_state', request.form.get('std_state', 'visible'))
                set_config('autofill_std_template', request.form.get('std_template', ''))
                
                set_config('autofill_dyn_category', request.form.get('dyn_category', 'Lab-Dynamic'))
                set_config('autofill_dyn_initial', request.form.get('dyn_initial', '500'))
                set_config('autofill_dyn_minimum', request.form.get('dyn_minimum', '100'))
                set_config('autofill_dyn_decay', request.form.get('dyn_decay', '20'))
                set_config('autofill_dyn_state', request.form.get('dyn_state', 'hidden'))
                set_config('autofill_dyn_template', request.form.get('dyn_template', ''))
            
            # --- ACTION B: STANDARD-ONLY BULK OPERATIONS ---
            elif action_type == 'bulk_modify_standard':
                target_cat = request.form.get('std_target_category', '').strip()
                new_value = request.form.get('std_new_value', '').strip()
                new_state = request.form.get('std_new_state', '').strip()

                if target_cat:
                    challenges = db.session.query(Challenges).filter(
                        Challenges.category == target_cat,
                        Challenges.type != 'dynamic'
                    ).all()
                    
                    for chal in challenges:
                        if new_value:
                            chal.value = int(new_value)
                        if new_state in ['visible', 'hidden']:
                            chal.state = new_state
                    db.session.commit()

                        # --- ACTION C: DYNAMIC-ONLY BULK OPERATIONS (FIXED CACHE REFRESH) ---
            elif action_type == 'bulk_modify_dynamic':
                target_cat = request.form.get('dyn_target_category', '').strip()
                new_initial = request.form.get('dyn_new_initial', '').strip()
                new_minimum = request.form.get('dyn_new_minimum', '').strip()
                new_state = request.form.get('dyn_new_state', '').strip()

                if target_cat:
                    challenges = db.session.query(Challenges).filter(
                        Challenges.category == target_cat,
                        Challenges.type == 'dynamic'
                    ).all()
                    
                    for chal in challenges:
                        if new_state in ['visible', 'hidden']:
                            chal.state = new_state
                        
                        # FIXED: Use core SQLAlchemy object binding to update fields and auto-refresh the cache
                        if new_initial:
                            chal.value = int(new_initial)
                            # Update the attached dynamic properties directly through object mapping
                            if hasattr(chal, 'initial'):
                                chal.initial = int(new_initial)
                            else:
                                # Fallback query targeting the exact framework model mapping safely
                                db.session.execute(
                                    db.text("UPDATE dynamic_challenge SET initial = :val WHERE id = :id"),
                                    {"val": int(new_initial), "id": chal.id}
                                )
                                
                        if new_minimum:
                            if hasattr(chal, 'minimum'):
                                chal.minimum = int(new_minimum)
                            else:
                                # Fallback query targeting the exact framework model mapping safely
                                db.session.execute(
                                    db.text("UPDATE dynamic_challenge SET minimum = :val WHERE id = :id"),
                                    {"val": int(new_minimum), "id": chal.id}
                                )
                                
                    db.session.commit() # Flush and lock the changes straight onto the database hard drive



            return redirect(url_for('challenge_autofill.autofill_settings'))

        current_settings = {
            'std_category': get_config('autofill_std_category') or 'Lab-Standard',
            'std_value': get_config('autofill_std_value') or '100',
            'std_state': get_config('autofill_std_state') or 'visible',
            'std_template': get_config('autofill_std_template') or '### Standard Description\n[Insert text details here]',
            'dyn_category': get_config('autofill_dyn_category') or 'Lab-Dynamic',
            'dyn_initial': get_config('autofill_dyn_initial') or '500',
            'dyn_minimum': get_config('autofill_dyn_minimum') or '100',
            'dyn_decay': get_config('autofill_dyn_decay') or '20',
            'dyn_state': get_config('autofill_dyn_state') or 'hidden',
            'dyn_template': get_config('autofill_dyn_template') or '### Dynamic Decay Challenge\n[Insert text details here]'
        }

        # DYNAMIC FILTERS: Extract distinct categories grouped by specific type
        db_std_cats = db.session.query(Challenges.category).filter(Challenges.type != 'dynamic').distinct().all()
        std_categories = [c.category.strip() for c in db_std_cats if c and c.category and c.category.strip() != ""]

        db_dyn_cats = db.session.query(Challenges.category).filter(Challenges.type == 'dynamic').distinct().all()
        dyn_categories = [c.category.strip() for c in db_dyn_cats if c and c.category and c.category.strip() != ""]

        return render_template(
            'autofill_settings.html', 
            settings=current_settings, 
            std_categories=std_categories, 
            dyn_categories=dyn_categories
        )

    app.register_blueprint(plugin_bp)
    @app.after_request
    def inject_autofill_script(response):
        path = request.path
        if (path.startswith("/admin") or path.startswith("/api/v1/admin")) and response.mimetype == "text/html":
            html_content = response.get_data(as_text=True)
            
            std_cat = get_config('autofill_std_category') or 'Lab-Standard'
            std_val = get_config('autofill_std_value') or '100'
            std_ste = get_config('autofill_std_state') or 'visible'
            std_tpl = (get_config('autofill_std_template') or '').replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '').replace('"', '\\"')
            
            dyn_cat = get_config('autofill_dyn_category') or 'Lab-Dynamic'
            dyn_ini = get_config('autofill_dyn_initial') or '500'
            dyn_min = get_config('autofill_dyn_minimum') or '100'
            dyn_dec = get_config('autofill_dyn_decay') or '20'
            dyn_ste = get_config('autofill_dyn_state') or 'hidden'
            dyn_tpl = (get_config('autofill_dyn_template') or '').replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '').replace('"', '\\"')

            autofill_js = """
            <script>
            (function() {
                function runAutofillAutomation() {
                    const initialInput = document.querySelector('input[name="initial"]') || document.querySelector('#initial');
                    const isDynamicActive = initialInput && (initialInput.offsetParent !== null);
                    
                    const categoryInput = document.querySelector('input[name="category"]') || document.querySelector('#category');
                    const valueInput = document.querySelector('input[name="value"]') || document.querySelector('#value');
                    const minimumInput = document.querySelector('input[name="minimum"]') || document.querySelector('#minimum');
                    const decayInput = document.querySelector('input[name="decay"]') || document.querySelector('#decay');
                    const mdEditor = document.querySelector('.CodeMirror');
                    const stateSelect = document.querySelector('select[name="state"]') || document.getElementById('state') || document.querySelector('.modal-body select');

                    if (isDynamicActive) {
                        if (categoryInput && categoryInput.value === "") categoryInput.value = "{DYN_CAT}";
                        if (initialInput && initialInput.value === "") initialInput.value = "{DYN_INI}";
                        if (minimumInput && minimumInput.value === "") minimumInput.value = "{DYN_MIN}";
                        if (decayInput && decayInput.value === "") decayInput.value = "{DYN_DEC}";
                        if (mdEditor && mdEditor.CodeMirror && mdEditor.CodeMirror.getValue() === "") {
                            mdEditor.CodeMirror.setValue("{DYN_TPL}");
                        }
                        if (stateSelect) stateSelect.value = "{DYN_STE}";
                    } else {
                        if (categoryInput && categoryInput.value === "") categoryInput.value = "{STD_CAT}";
                        if (valueInput && valueInput.value === "") valueInput.value = "{STD_VAL}";
                        if (mdEditor && mdEditor.CodeMirror && mdEditor.CodeMirror.getValue() === "") {
                            mdEditor.CodeMirror.setValue("{STD_TPL}");
                        }
                        if (stateSelect) stateSelect.value = "{STD_STE}";
                    }
                }

                const observer = new MutationObserver(function(mutations) {
                    runAutofillAutomation();
                });

                observer.observe(document.body, { childList: true, subtree: true });
                setTimeout(runAutofillAutomation, 500);
            })();
            </script>
            """.replace("{STD_CAT}", str(std_cat))\
               .replace("{STD_VAL}", str(std_val))\
               .replace("{STD_STE}", str(std_ste))\
               .replace("{STD_TPL}", std_tpl)\
               .replace("{DYN_CAT}", str(dyn_cat))\
               .replace("{DYN_INI}", str(dyn_ini))\
               .replace("{DYN_MIN}", str(dyn_min))\
               .replace("{DYN_DEC}", str(dyn_dec))\
               .replace("{DYN_STE}", str(dyn_ste))\
               .replace("{DYN_TPL}", dyn_tpl)
            
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{autofill_js}\n</body>", 1)

            target_marker = 'href="/admin/sponsors"'
            if target_marker in html_content:
                new_link = 'href="/admin/sponsors"><i class="fas fa-handshake mr-2"></i>Sponsors</a>\n                    <a class="dropdown-item" href="/admin/autofill/settings"><i class="fas fa-magic mr-2"></i>Autofill Settings</a>'
                html_content = html_content.replace('href="/admin/sponsors">Sponsors</a>', new_link, 1)
                html_content = html_content.replace('href="/admin/sponsors"><i class="fas fa-handshake mr-2"></i>Sponsors</a>', new_link, 1)
                
            response.set_data(html_content)
                
        return response
