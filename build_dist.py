import os
import shutil
import subprocess
import tempfile

def run(cmd):
    print("Running:", cmd)
    subprocess.check_call(cmd, shell=True)


print("Building assistant_server...")
run("pyinstaller -y --noconsole --onedir --paths automation --hidden-import test_real_irctc_v1_direct --collect-all playwright assistant_server.py")

print("Building launcher...")
run("pyinstaller -y --noconsole --onefile launcher.py")

print("Assembling distribution...")
dist_dir = "IRCTC_Tatkal_Assistant"

# Preserve chrome_profile across rebuilds so the user's saved IRCTC
# login session and cookies are never deleted.
profile_backup = None
profile_src = os.path.join(dist_dir, "chrome_profile")
if os.path.exists(profile_src):
    profile_backup = tempfile.mkdtemp(prefix="irctc_profile_backup_")
    print(f"Backing up chrome_profile to {profile_backup} ...")
    shutil.copytree(profile_src, os.path.join(profile_backup, "chrome_profile"),
                    dirs_exist_ok=True)

if os.path.exists(dist_dir):
    print(f"Removing old {dist_dir} ...")
    shutil.rmtree(dist_dir)

# Move assistant_server onedir contents to dist_dir
shutil.copytree("dist/assistant_server", dist_dir)

# Copy launcher
shutil.copy("dist/launcher.exe", os.path.join(dist_dir, "Launch_IRCTC_Assistant.exe"))

# Copy templates and static
shutil.copytree("templates", os.path.join(dist_dir, "templates"))
shutil.copytree("static", os.path.join(dist_dir, "static"))

# Copy config
shutil.copy("v1_config.json", os.path.join(dist_dir, "v1_config.json"))

# Restore chrome_profile if it was backed up
if profile_backup:
    restored_path = os.path.join(dist_dir, "chrome_profile")
    print(f"Restoring chrome_profile from backup ...")
    shutil.copytree(os.path.join(profile_backup, "chrome_profile"), restored_path,
                    dirs_exist_ok=True)
    shutil.rmtree(profile_backup)
    print("chrome_profile restored.")

print("Done building IRCTC_Tatkal_Assistant!")
