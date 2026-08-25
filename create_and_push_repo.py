"""
Initialize git, create GitHub repository, and push AggregationLearn project to GitHub.
"""

import subprocess
import urllib.request
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

CWD = r"c:\Users\prana\OneDrive\Desktop\AggregationLearn"
REPO_NAME = "MediationZone9-Aggregation-Deduplication"
REPO_DESC = "MediationZone 9 (InfoZone) Aggregation, Deduplication & REST Server Agent Pipeline Implementation"

# 1. Create .gitignore
gitignore_content = """__pycache__/
*.pyc
*.log
.DS_Store
"""
with open(os.path.join(CWD, ".gitignore"), "w", encoding="utf-8") as f:
    f.write(gitignore_content)

# 2. Git init & add
print("================================================================================")
print(" 1. INITIALIZING GIT REPOSITORY & COMMITTING LOCAL FILES")
print("================================================================================")

subprocess.run(["git", "init"], cwd=CWD)
subprocess.run(["git", "config", "user.name", "Developer"], cwd=CWD)
subprocess.run(["git", "config", "user.email", "developer@earthlink.iq"], cwd=CWD)
subprocess.run(["git", "add", "."], cwd=CWD)
subprocess.run(["git", "commit", "-m", "Initial commit: MediationZone 9 Aggregation, Deduplication & REST Agent Pipeline"], cwd=CWD)
subprocess.run(["git", "branch", "-M", "main"], cwd=CWD)

# 3. Retrieve GitHub credentials via Git Credential Manager
def get_git_credential():
    p = subprocess.Popen(['git', 'credential', 'fill'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate(input='protocol=https\nhost=github.com\n\n')
    user, token = None, None
    for line in out.splitlines():
        if line.startswith('username='):
            user = line.split('=', 1)[1]
        elif line.startswith('password='):
            token = line.split('=', 1)[1]
    return user, token

user, token = get_git_credential()

if not user or not token:
    # Try gh auth token
    gh_token_res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if gh_token_res.returncode == 0:
        token = gh_token_res.stdout.strip()
        user_res = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)
        if user_res.returncode == 0:
            user = user_res.stdout.strip()

print(f"GitHub User Detected: {user}")

if not token or not user:
    print("❌ Error: Could not retrieve GitHub credentials.")
    sys.exit(1)

# 4. Create Repository on GitHub via API
print("\n" + "=" * 80)
print(f" 2. CREATING GITHUB REPOSITORY '{REPO_NAME}' ")
print("=" * 80)

url = "https://api.github.com/user/repos"
payload = {
    "name": REPO_NAME,
    "description": REPO_DESC,
    "private": False,
    "has_issues": True,
    "has_projects": True,
    "has_wiki": True
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
    "Content-Type": "application/json",
    "User-Agent": "Antigravity-AI-Agent"
})

repo_html_url = f"https://github.com/{user}/{REPO_NAME}"

try:
    with urllib.request.urlopen(req) as resp:
        res_data = json.loads(resp.read().decode('utf-8'))
        repo_html_url = res_data.get("html_url", repo_html_url)
        print(f"✅ Repository successfully created on GitHub!")
        print(f"   URL: {repo_html_url}")
except urllib.error.HTTPError as e:
    if e.code == 422:
        print(f"ℹ️ Repository '{REPO_NAME}' already exists on GitHub. Proceeding to push updates.")
    else:
        print(f"⚠️ GitHub API returned HTTP {e.code}: {e.read().decode('utf-8')}")

# 5. Add Remote & Push
auth_remote_url = f"https://{user}:{token}@github.com/{user}/{REPO_NAME}.git"
subprocess.run(["git", "remote", "remove", "origin"], cwd=CWD, stderr=subprocess.DEVNULL)
subprocess.run(["git", "remote", "add", "origin", auth_remote_url], cwd=CWD)

print("\n" + "=" * 80)
print(" 3. PUSHING CODE TO GITHUB 'main' BRANCH ")
print("=" * 80)

push_res = subprocess.run(["git", "push", "-u", "origin", "main", "--force"], cwd=CWD, capture_output=True, text=True)

if push_res.returncode == 0:
    print(f"\n🎉 SUCCESS! Your MediationZone Aggregation repository is LIVE on GitHub:")
    print(f"👉 {repo_html_url}")
else:
    print(f"❌ Git Push Error: {push_res.stderr}")
