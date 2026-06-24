import yaml
import subprocess
from pathlib import Path
from hashlib import sha256


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
    if r.returncode != 0:
        raise RuntimeError(f"cmd {cmd} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def optional_run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
    return r.stdout.strip() if r.returncode == 0 else None


project_path = Path.cwd()

branch = run(["git", "branch", "--show-current"])
head_sha = run(["git", "rev-parse", "HEAD"])
base_sha = run(["git", "rev-parse", "--verify", "origin/main"])
merge_base_sha = run(["git", "merge-base", "HEAD", "origin/main"])
root = run(["git", "rev-parse", "--show-toplevel"])
git_dir = run(["git", "rev-parse", "--git-dir"])
remote_url = optional_run(["git", "config", "--get", "remote.origin.url"])

# Strip credentials
if remote_url:
    import re
    remote_url = re.sub(r'https?://[^@]+@', 'https://', remote_url)

# Compute root commit SHAs (first ancestors)
root_commits_raw = optional_run(["git", "log", "--max-parents=0", "--format=%H", "HEAD"])
root_commit_shas = sorted(set(root_commits_raw.splitlines())) if root_commits_raw else []

# Normalize remote URL for fingerprint
def normalize_git_url(url):
    if not url:
        return None
    url = re.sub(r'https?://([^/]+)/(.+)', r'\1/\2', url)
    url = re.sub(r'git@([^:]+):(.+)', r'\1/\2', url)
    url = re.sub(r'/+', '/', url).strip('/')
    if url.lower().endswith('.git'):
        url = url[:-4]
    host = url.split('/')[0].lower()
    known = ('github.com', 'gitlab.com', 'bitbucket.org')
    if host in known:
        url = url.lower()
    if not host:
        return None
    return url

normalized_remote = normalize_git_url(remote_url)

# Compute repository fingerprint
if root_commit_shas and normalized_remote:
    lines = ["repository-id-v1"] + root_commit_shas + [normalized_remote]
    repository_id = sha256("\n".join(lines).encode("utf-8")).hexdigest()
    strength = "strong"
    version = 1
elif root_commit_shas:
    repository_id = root_commit_shas[0]
    strength = "weak"
    version = None
else:
    repository_id = normalized_remote
    strength = "none"
    version = None

identity = {
    "root": root.replace("\\", "/"),
    "branch": branch,
    "head_sha": head_sha,
    "requested_base_ref": "origin/main",
    "base_sha": base_sha,
    "merge_base_sha": merge_base_sha,
    "git_dir": git_dir.replace("\\", "/"),
    "detached_head": False,
    "shallow_clone": False,
    "remote_url": remote_url,
    "normalized_remote_url": normalized_remote,
    "root_commit_shas": root_commit_shas,
    "repository_id": repository_id,
    "repository_id_strength": strength,
    "repository_id_version": version,
}

out_path = Path("scratch/host_identity.yaml")
out_path.parent.mkdir(exist_ok=True)
out_path.write_text(yaml.safe_dump(identity, sort_keys=False), encoding="utf-8")

print(f"Host identity written to: {out_path}")
print(f"  branch:         {branch}")
print(f"  head_sha:       {head_sha}")
print(f"  base_sha:       {base_sha}")
print(f"  merge_base_sha: {merge_base_sha}")
print(f"  repository_id:  {repository_id}")
print(f"  strength:       {strength}")
print(f"  remote_url:     {remote_url}")
