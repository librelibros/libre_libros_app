#!/bin/bash
set -euo pipefail

GITLAB_CONTAINER_NAME="${GITLAB_CONTAINER_NAME:-libre-libros-gitlab}"
GITLAB_INTERNAL_URL="${GITLAB_INTERNAL_URL:-http://gitlab}"
GITLAB_PUBLIC_URL="${GITLAB_PUBLIC_URL:-http://127.0.0.1:8081}"
GITLAB_RUNTIME_ENV_PATH="${GITLAB_RUNTIME_ENV_PATH:-/workspace/data/debug/gitlab-runtime.env}"
GITLAB_DEBUG_ADMIN_EMAIL="${GITLAB_DEBUG_ADMIN_EMAIL:-admin@example.com}"
GITLAB_DEBUG_ADMIN_PASSWORD="${GITLAB_DEBUG_ADMIN_PASSWORD:-admin12345}"
GITLAB_DEBUG_ADMIN_TOKEN="${GITLAB_DEBUG_ADMIN_TOKEN:-libre-libros-debug-token}"
GITLAB_DEBUG_PROJECT_PATH="${GITLAB_DEBUG_PROJECT_PATH:-librelibrosrepo}"
GITLAB_DEBUG_PROJECT_NAME="${GITLAB_DEBUG_PROJECT_NAME:-Libre Libros Content}"
GITLAB_DEBUG_OAUTH_APP_NAME="${GITLAB_DEBUG_OAUTH_APP_NAME:-Libre Libros Debug}"
GITLAB_DEBUG_OAUTH_CLIENT_SECRET="${GITLAB_DEBUG_OAUTH_CLIENT_SECRET:-libre-libros-oauth-debug-secret}"
GITLAB_DEBUG_OAUTH_REDIRECT_URI="${GITLAB_DEBUG_OAUTH_REDIRECT_URI:-http://libre-libros:8000/auth/gitlab/callback\nhttp://127.0.0.1:8000/auth/gitlab/callback}"

mkdir -p "$(dirname "$GITLAB_RUNTIME_ENV_PATH")"

gitlab_ready="false"
for _ in $(seq 1 180); do
  status_code="$(curl -sS -o /dev/null -w '%{http_code}' "${GITLAB_INTERNAL_URL}/users/sign_in" || true)"
  if [ "$status_code" = "200" ] || [ "$status_code" = "302" ]; then
    gitlab_ready="true"
    break
  fi
  sleep 5
done

if [ "$gitlab_ready" != "true" ]; then
  echo "GitLab did not become ready in time" >&2
  exit 1
fi

RUBY_SCRIPT="$(mktemp)"
cat >"$RUBY_SCRIPT" <<'RUBY'
require "json"

admin_email = ENV.fetch("GITLAB_DEBUG_ADMIN_EMAIL")
admin_password = ENV.fetch("GITLAB_DEBUG_ADMIN_PASSWORD")
admin_token = ENV.fetch("GITLAB_DEBUG_ADMIN_TOKEN")
project_path = ENV.fetch("GITLAB_DEBUG_PROJECT_PATH")
project_name = ENV.fetch("GITLAB_DEBUG_PROJECT_NAME")
oauth_name = ENV.fetch("GITLAB_DEBUG_OAUTH_APP_NAME")
oauth_client_secret = ENV.fetch("GITLAB_DEBUG_OAUTH_CLIENT_SECRET")
redirect_uri = ENV.fetch("GITLAB_DEBUG_OAUTH_REDIRECT_URI")

admin_username = admin_email.split("@").first.gsub(/[^a-zA-Z0-9_]/, "-")
admin_username = "libreadmin" if admin_username == "admin"
admin_user = User.find_by_email(admin_email)
admin_user ||= User.new(email: admin_email)
admin_user.username = admin_username
admin_user.name = "Libre Libros Admin" if admin_user.name.blank?
admin_user.admin = true
admin_user.password = admin_password
admin_user.password_confirmation = admin_password
admin_user.confirmed_at ||= Time.now
admin_user.skip_confirmation!
admin_user.save!(validate: false)
if admin_user.namespace.nil? && admin_user.respond_to?(:assign_personal_namespace)
  default_organization = Organizations::Organization.default_organization
  admin_user.assign_personal_namespace(default_organization)
  admin_user.save!(validate: false)
  admin_user.reload
end
if admin_user.namespace && admin_user.namespace.path != admin_username
  default_organization = Organizations::Organization.default_organization
  admin_user.namespace.path = admin_username
  admin_user.namespace.name = admin_username
  admin_user.namespace.organization_id ||= default_organization&.id
  admin_user.namespace.save!(validate: false)
  admin_user.reload
end

application = Doorkeeper::Application.find_or_initialize_by(name: oauth_name)
application.redirect_uri = redirect_uri
application.scopes = "read_user api"
application.secret = oauth_client_secret
application.save!

project = Project.find_by_full_path("#{admin_user.username}/#{project_path}")
unless project
  project = Projects::CreateService.new(
    admin_user,
    {
      name: project_name,
      path: project_path,
      namespace_id: admin_user.namespace.id,
      visibility_level: Gitlab::VisibilityLevel::PUBLIC,
      initialize_with_readme: true,
      default_branch: "main"
    }
  ).execute
end

personal_token = admin_user.personal_access_tokens.active.find_by(name: "Libre Libros Debug Token")
unless personal_token
  personal_token = admin_user.personal_access_tokens.build(
    name: "Libre Libros Debug Token",
    scopes: [:api],
    expires_at: 1.year.from_now
  )
  personal_token.set_token(admin_token)
  personal_token.save!
end

puts(
  {
    admin_username: admin_user.username,
    project_path: project.path,
    project_id: project.id,
    client_id: application.uid,
    client_secret: application.secret
  }.to_json
)
RUBY

BOOTSTRAP_JSON="$(
  cat "$RUBY_SCRIPT" | docker exec -i \
    -e GITLAB_DEBUG_ADMIN_EMAIL="$GITLAB_DEBUG_ADMIN_EMAIL" \
    -e GITLAB_DEBUG_ADMIN_PASSWORD="$GITLAB_DEBUG_ADMIN_PASSWORD" \
    -e GITLAB_DEBUG_ADMIN_TOKEN="$GITLAB_DEBUG_ADMIN_TOKEN" \
    -e GITLAB_DEBUG_PROJECT_PATH="$GITLAB_DEBUG_PROJECT_PATH" \
    -e GITLAB_DEBUG_PROJECT_NAME="$GITLAB_DEBUG_PROJECT_NAME" \
    -e GITLAB_DEBUG_OAUTH_APP_NAME="$GITLAB_DEBUG_OAUTH_APP_NAME" \
    -e GITLAB_DEBUG_OAUTH_CLIENT_SECRET="$GITLAB_DEBUG_OAUTH_CLIENT_SECRET" \
    -e GITLAB_DEBUG_OAUTH_REDIRECT_URI="$GITLAB_DEBUG_OAUTH_REDIRECT_URI" \
    "$GITLAB_CONTAINER_NAME" \
    bash -lc 'cat >/tmp/libre_libros_bootstrap.rb && gitlab-rails runner /tmp/libre_libros_bootstrap.rb'
)"

ADMIN_USERNAME="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["admin_username"])' <<<"$BOOTSTRAP_JSON")"
CLIENT_ID="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["client_id"])' <<<"$BOOTSTRAP_JSON")"
CLIENT_SECRET="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["client_secret"])' <<<"$BOOTSTRAP_JSON")"
PROJECT_PATH="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["project_path"])' <<<"$BOOTSTRAP_JSON")"
PROJECT_ID="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["project_id"])' <<<"$BOOTSTRAP_JSON")"

if [ -d /workspace/data/repo/.git ]; then
  GITLAB_INTERNAL_URL="$GITLAB_INTERNAL_URL" \
  GITLAB_DEBUG_ADMIN_TOKEN="$GITLAB_DEBUG_ADMIN_TOKEN" \
  PROJECT_ID="$PROJECT_ID" \
  python3 - <<'PY'
import base64
import os
from pathlib import Path

import requests

base_url = os.environ["GITLAB_INTERNAL_URL"].rstrip("/")
token = os.environ["GITLAB_DEBUG_ADMIN_TOKEN"]
project_id = os.environ["PROJECT_ID"]
repo_root = Path("/workspace/data/repo")
branch_name = "main"

session = requests.Session()
session.headers.update({"PRIVATE-TOKEN": token})

project_response = session.get(f"{base_url}/api/v4/projects/{project_id}", timeout=30)
project_response.raise_for_status()
project = project_response.json()
default_branch = project.get("default_branch") or branch_name

branch_response = session.get(
    f"{base_url}/api/v4/projects/{project_id}/repository/branches/{branch_name}",
    timeout=30,
)
if branch_response.status_code == 404 and default_branch and default_branch != branch_name:
    create_branch = session.post(
        f"{base_url}/api/v4/projects/{project_id}/repository/branches",
        params={"branch": branch_name, "ref": default_branch},
        timeout=30,
    )
    create_branch.raise_for_status()
elif branch_response.status_code not in (200, 404):
    branch_response.raise_for_status()

existing_files: set[str] = set()
page = 1
while True:
    tree_response = session.get(
        f"{base_url}/api/v4/projects/{project_id}/repository/tree",
        params={"path": "", "ref": branch_name, "recursive": True, "per_page": 100, "page": page},
        timeout=30,
    )
    if tree_response.status_code == 404:
        break
    tree_response.raise_for_status()
    payload = tree_response.json()
    if not payload:
        break
    for entry in payload:
        if entry.get("type") == "blob":
            existing_files.add(entry["path"])
    next_page = tree_response.headers.get("X-Next-Page")
    if not next_page:
        break
    page = int(next_page)

source_files: dict[str, bytes] = {}
for path in repo_root.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    source_files[path.relative_to(repo_root).as_posix()] = path.read_bytes()

actions = []
for rel_path, content in sorted(source_files.items()):
    actions.append(
        {
            "action": "update" if rel_path in existing_files else "create",
            "file_path": rel_path,
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }
    )

for rel_path in sorted(existing_files - set(source_files)):
    actions.append({"action": "delete", "file_path": rel_path})

if actions:
    commit_response = session.post(
        f"{base_url}/api/v4/projects/{project_id}/repository/commits",
        json={
            "branch": branch_name,
            "commit_message": "Seed GitLab debug content",
            "actions": actions,
        },
        timeout=60,
    )
    commit_response.raise_for_status()
PY
fi

cat >"$GITLAB_RUNTIME_ENV_PATH" <<EOF
LIBRE_LIBROS_EXTERNAL_AUTH_ONLY='true'
LIBRE_LIBROS_GITLAB_ENABLED='true'
LIBRE_LIBROS_GITLAB_NAME='GitLab Debug'
LIBRE_LIBROS_GITLAB_URL='${GITLAB_PUBLIC_URL}'
LIBRE_LIBROS_GITLAB_INTERNAL_URL='${GITLAB_INTERNAL_URL}'
LIBRE_LIBROS_GITLAB_CLIENT_ID='${CLIENT_ID}'
LIBRE_LIBROS_GITLAB_CLIENT_SECRET='${GITLAB_DEBUG_OAUTH_CLIENT_SECRET}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PROVIDER='gitlab'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_NAME='Repositorio GitLab Debug'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_SLUG='repositorio-gitlab-debug'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_URL='${GITLAB_INTERNAL_URL}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_NAMESPACE='${ADMIN_USERNAME}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_NAME_REMOTE='${PROJECT_PATH}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_USERNAME='${GITLAB_DEBUG_ADMIN_EMAIL}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_TOKEN='${GITLAB_DEBUG_ADMIN_TOKEN}'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_DEFAULT_BRANCH='main'
LIBRE_LIBROS_BOOTSTRAP_REPOSITORY_PUBLIC='true'
EOF

rm -f "$RUBY_SCRIPT"
