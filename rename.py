import os

files = [
    "./templates/base.html",
    "./templates/landing.html",
    "./templates/accounts/register_choice.html",
    "./templates/accounts/register_form.html",
    "./templates/accounts/login.html",
    "./templates/accounts/super_admin/sys_metrics.html",
    "./templates/accounts/super_admin/org_stats.html",
    "./templates/accounts/super_admin/global_worker_detail.html",
    "./templates/accounts/super_admin/global_workers.html",
    "./core/settings.py",
    "./accounts/views.py",
    "./accounts/context_processors.py",
    "./accounts/forms.py",
    "./README.md"
]

for file_path in files:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace occurrences
        new_content = content.replace("SafeWork", "Sopline")
        new_content = new_content.replace("safework", "sopline")
        new_content = new_content.replace("SAFEWORK", "SOPLINE")
        
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path}")

print("Replacement complete.")
