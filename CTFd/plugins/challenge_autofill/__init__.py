from flask import Blueprint, render_template, request, redirect, url_for
from CTFd.utils import get_config, set_config
from CTFd.utils.decorators import admins_only

def load(app):
    plugin_bp = Blueprint('challenge_autofill', __name__, template_folder='templates')

    @plugin_bp.route('/admin/autofill/settings', methods=['GET', 'POST'])
    @admins_only
    def autofill_settings():
        if request.method == 'POST':
            # --- STANDARD PREFERENCE TRACKERS ---
            set_config('autofill_std_category', request.form.get('std_category', 'Lab-Standard'))
            set_config('autofill_std_value', request.form.get('std_value', '100'))
            set_config('autofill_std_state', request.form.get('std_state', 'visible')) # SPLIT
            set_config('autofill_std_template', request.form.get('std_template', ''))
            
            # --- DYNAMIC PREFERENCE TRACKERS ---
            set_config('autofill_dyn_category', request.form.get('dyn_category', 'Lab-Dynamic'))
            set_config('autofill_dyn_initial', request.form.get('dyn_initial', '500'))
            set_config('autofill_dyn_minimum', request.form.get('dyn_minimum', '100'))
            set_config('autofill_dyn_decay', request.form.get('dyn_decay', '20'))
            set_config('autofill_dyn_state', request.form.get('dyn_state', 'hidden')) # SPLIT
            set_config('autofill_dyn_template', request.form.get('dyn_template', ''))
            
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
        return render_template('autofill_settings.html', settings=current_settings)

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
                        // --- APPLY DYNAMIC CHALLENGE DEFAULT PREFERENCES ---
                        if (categoryInput && categoryInput.value === "") categoryInput.value = "{DYN_CAT}";
                        if (initialInput && initialInput.value === "") initialInput.value = "{DYN_INI}";
                        if (minimumInput && minimumInput.value === "") minimumInput.value = "{DYN_MIN}";
                        if (decayInput && decayInput.value === "") decayInput.value = "{DYN_DEC}";
                        if (mdEditor && mdEditor.CodeMirror && mdEditor.CodeMirror.getValue() === "") {
                            mdEditor.CodeMirror.setValue("{DYN_TPL}");
                        }
                        // Step 2 State Selection for Dynamic
                        if (stateSelect) stateSelect.value = "{DYN_STE}";
                    } else {
                        // --- APPLY STANDARD CHALLENGE DEFAULT PREFERENCES ---
                        if (categoryInput && categoryInput.value === "") categoryInput.value = "{STD_CAT}";
                        if (valueInput && valueInput.value === "") valueInput.value = "{STD_VAL}";
                        if (mdEditor && mdEditor.CodeMirror && mdEditor.CodeMirror.getValue() === "") {
                            mdEditor.CodeMirror.setValue("{STD_TPL}");
                        }
                        // Step 2 State Selection for Standard
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
