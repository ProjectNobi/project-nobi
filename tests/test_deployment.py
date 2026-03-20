"""
Tests for deployment configuration files.
Validates Docker Compose, Dockerfiles, Nginx, systemd, deploy script, and env docs.
"""

import os
import re
import yaml
import subprocess
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY_DIR = os.path.join(PROJECT_ROOT, "deploy")


# ─── Docker Compose ──────────────────────────────────────────

class TestDockerCompose:
    """Validate docker-compose.yml syntax and structure."""

    @pytest.fixture
    def compose_data(self):
        path = os.path.join(DEPLOY_DIR, "docker-compose.yml")
        assert os.path.exists(path), "docker-compose.yml not found"
        with open(path) as f:
            return yaml.safe_load(f)

    def test_compose_yaml_valid(self, compose_data):
        """Docker Compose file is valid YAML."""
        assert compose_data is not None
        assert isinstance(compose_data, dict)

    def test_compose_has_services(self, compose_data):
        """Docker Compose defines required services."""
        assert "services" in compose_data
        services = compose_data["services"]
        assert "api" in services, "Missing 'api' service"
        assert "webapp" in services, "Missing 'webapp' service"
        assert "nginx" in services, "Missing 'nginx' service"

    def test_api_service_config(self, compose_data):
        """API service has correct port and health check."""
        api = compose_data["services"]["api"]
        assert "8042:8042" in api.get("ports", [])
        assert "healthcheck" in api
        assert api["healthcheck"]["test"] is not None

    def test_webapp_service_config(self, compose_data):
        """Webapp service has correct port and depends on API."""
        webapp = compose_data["services"]["webapp"]
        assert "3000:3000" in webapp.get("ports", [])
        assert "depends_on" in webapp

    def test_nginx_service_config(self, compose_data):
        """Nginx service has correct ports and volumes."""
        nginx = compose_data["services"]["nginx"]
        ports = nginx.get("ports", [])
        assert "80:80" in ports
        assert "443:443" in ports
        assert "volumes" in nginx

    def test_compose_has_networks(self, compose_data):
        """Docker Compose defines a network."""
        assert "networks" in compose_data

    def test_compose_has_volumes(self, compose_data):
        """Docker Compose defines named volumes."""
        assert "volumes" in compose_data
        assert "nobi-data" in compose_data["volumes"]


# ─── Dockerfiles ─────────────────────────────────────────────

class TestDockerfiles:
    """Validate Dockerfile syntax and content."""

    def _read_dockerfile(self, name):
        path = os.path.join(DEPLOY_DIR, name, "Dockerfile")
        assert os.path.exists(path), f"{name}/Dockerfile not found"
        with open(path) as f:
            return f.read()

    def test_api_dockerfile_exists(self):
        """API Dockerfile exists."""
        path = os.path.join(DEPLOY_DIR, "api", "Dockerfile")
        assert os.path.exists(path)

    def test_api_dockerfile_base_image(self):
        """API Dockerfile uses Python 3.12."""
        content = self._read_dockerfile("api")
        assert "python:3.12" in content

    def test_api_dockerfile_has_healthcheck(self):
        """API Dockerfile has HEALTHCHECK instruction."""
        content = self._read_dockerfile("api")
        assert "HEALTHCHECK" in content

    def test_api_dockerfile_exposes_port(self):
        """API Dockerfile exposes port 8042."""
        content = self._read_dockerfile("api")
        assert "EXPOSE 8042" in content

    def test_api_dockerfile_has_cmd(self):
        """API Dockerfile has CMD to run gunicorn."""
        content = self._read_dockerfile("api")
        assert "gunicorn" in content

    def test_webapp_dockerfile_exists(self):
        """Webapp Dockerfile exists."""
        path = os.path.join(DEPLOY_DIR, "webapp", "Dockerfile")
        assert os.path.exists(path)

    def test_webapp_dockerfile_base_image(self):
        """Webapp Dockerfile uses Node 20."""
        content = self._read_dockerfile("webapp")
        assert "node:20" in content

    def test_webapp_dockerfile_multistage(self):
        """Webapp Dockerfile uses multi-stage build."""
        content = self._read_dockerfile("webapp")
        assert content.count("FROM ") >= 2, "Expected multi-stage build"

    def test_webapp_dockerfile_has_healthcheck(self):
        """Webapp Dockerfile has HEALTHCHECK instruction."""
        content = self._read_dockerfile("webapp")
        assert "HEALTHCHECK" in content

    def test_webapp_dockerfile_exposes_port(self):
        """Webapp Dockerfile exposes port 3000."""
        content = self._read_dockerfile("webapp")
        assert "EXPOSE 3000" in content


# ─── Nginx Configuration ────────────────────────────────────

class TestNginxConfig:
    """Validate nginx.conf structure and directives."""

    @pytest.fixture
    def nginx_content(self):
        path = os.path.join(DEPLOY_DIR, "nginx", "nginx.conf")
        assert os.path.exists(path), "nginx.conf not found"
        with open(path) as f:
            return f.read()

    def test_nginx_has_upstream_api(self, nginx_content):
        """Nginx defines upstream for API backend."""
        assert "upstream api_backend" in nginx_content

    def test_nginx_has_upstream_webapp(self, nginx_content):
        """Nginx defines upstream for webapp backend."""
        assert "upstream webapp_backend" in nginx_content

    def test_nginx_has_ssl_config(self, nginx_content):
        """Nginx has SSL/TLS configuration."""
        assert "ssl_certificate" in nginx_content
        assert "ssl_protocols" in nginx_content

    def test_nginx_has_gzip(self, nginx_content):
        """Nginx has gzip compression enabled."""
        assert "gzip on" in nginx_content

    def test_nginx_has_rate_limiting(self, nginx_content):
        """Nginx has rate limiting configured."""
        assert "limit_req_zone" in nginx_content

    def test_nginx_has_security_headers(self, nginx_content):
        """Nginx sets security headers."""
        assert "X-Frame-Options" in nginx_content
        assert "X-Content-Type-Options" in nginx_content
        assert "Strict-Transport-Security" in nginx_content

    def test_nginx_has_cors(self, nginx_content):
        """Nginx has CORS configuration."""
        assert "Access-Control-Allow-Origin" in nginx_content

    def test_nginx_api_proxy(self, nginx_content):
        """Nginx proxies /api/ to API backend."""
        assert "location /api/" in nginx_content
        assert "proxy_pass http://api_backend" in nginx_content

    def test_nginx_http_redirect(self, nginx_content):
        """Nginx redirects HTTP to HTTPS."""
        assert "return 301 https://" in nginx_content


# ─── Deploy Script ───────────────────────────────────────────

class TestDeployScript:
    """Validate deploy.sh syntax and content."""

    @pytest.fixture
    def deploy_content(self):
        path = os.path.join(DEPLOY_DIR, "deploy.sh")
        assert os.path.exists(path), "deploy.sh not found"
        with open(path) as f:
            return f.read()

    def test_deploy_script_exists(self):
        """Deploy script exists and is executable."""
        path = os.path.join(DEPLOY_DIR, "deploy.sh")
        assert os.path.exists(path)
        assert os.access(path, os.X_OK), "deploy.sh is not executable"

    def test_deploy_script_bash_syntax(self):
        """Deploy script passes bash syntax check."""
        path = os.path.join(DEPLOY_DIR, "deploy.sh")
        result = subprocess.run(
            ["bash", "-n", path],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"

    def test_deploy_script_has_env_flag(self, deploy_content):
        """Deploy script supports --env flag."""
        assert "--env" in deploy_content

    def test_deploy_script_has_rollback(self, deploy_content):
        """Deploy script has rollback functionality."""
        assert "rollback" in deploy_content.lower()

    def test_deploy_script_has_health_check(self, deploy_content):
        """Deploy script performs health checks."""
        assert "health" in deploy_content.lower()

    def test_deploy_script_has_set_euo(self, deploy_content):
        """Deploy script uses strict error handling."""
        assert "set -euo pipefail" in deploy_content


# ─── Environment Documentation ───────────────────────────────

class TestEnvironmentDocs:
    """Validate .env.example completeness."""

    @pytest.fixture
    def env_vars(self):
        path = os.path.join(DEPLOY_DIR, ".env.example")
        assert os.path.exists(path), ".env.example not found"
        with open(path) as f:
            content = f.read()
        # Extract variable names (lines with = that aren't comments)
        vars_found = []
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var_name = line.split("=")[0].strip()
                vars_found.append(var_name)
        return vars_found

    def test_env_has_chutes_key(self, env_vars):
        """env.example documents CHUTES_API_KEY."""
        assert "CHUTES_API_KEY" in env_vars

    def test_env_has_openrouter_key(self, env_vars):
        """env.example documents OPENROUTER_API_KEY."""
        assert "OPENROUTER_API_KEY" in env_vars

    def test_env_has_stripe_key(self, env_vars):
        """env.example documents STRIPE_API_KEY."""
        assert "STRIPE_API_KEY" in env_vars

    def test_env_has_stripe_webhook(self, env_vars):
        """env.example documents STRIPE_WEBHOOK_SECRET."""
        assert "STRIPE_WEBHOOK_SECRET" in env_vars

    def test_env_has_db_path(self, env_vars):
        """env.example documents NOBI_DB_PATH."""
        assert "NOBI_DB_PATH" in env_vars

    def test_env_has_api_port(self, env_vars):
        """env.example documents NOBI_API_PORT."""
        assert "NOBI_API_PORT" in env_vars

    def test_env_has_api_url(self, env_vars):
        """env.example documents NEXT_PUBLIC_API_URL."""
        assert "NEXT_PUBLIC_API_URL" in env_vars


# ─── Systemd Services ───────────────────────────────────────

class TestSystemdServices:
    """Validate systemd unit files."""

    def test_api_service_exists(self):
        """nobi-api.service exists."""
        path = os.path.join(DEPLOY_DIR, "systemd", "nobi-api.service")
        assert os.path.exists(path)

    def test_webapp_service_exists(self):
        """nobi-webapp.service exists."""
        path = os.path.join(DEPLOY_DIR, "systemd", "nobi-webapp.service")
        assert os.path.exists(path)

    def test_api_service_has_sections(self):
        """nobi-api.service has required systemd sections."""
        path = os.path.join(DEPLOY_DIR, "systemd", "nobi-api.service")
        with open(path) as f:
            content = f.read()
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content

    def test_webapp_service_has_sections(self):
        """nobi-webapp.service has required systemd sections."""
        path = os.path.join(DEPLOY_DIR, "systemd", "nobi-webapp.service")
        with open(path) as f:
            content = f.read()
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content

    def test_api_service_security_hardening(self):
        """nobi-api.service has security hardening."""
        path = os.path.join(DEPLOY_DIR, "systemd", "nobi-api.service")
        with open(path) as f:
            content = f.read()
        assert "NoNewPrivileges" in content
        assert "ProtectSystem" in content


# ─── Vercel Config ───────────────────────────────────────────

class TestVercelConfig:
    """Validate vercel.json."""

    def test_vercel_json_exists(self):
        """vercel.json exists in webapp directory."""
        path = os.path.join(PROJECT_ROOT, "webapp", "vercel.json")
        assert os.path.exists(path)

    def test_vercel_json_valid(self):
        """vercel.json is valid JSON with required fields."""
        import json
        path = os.path.join(PROJECT_ROOT, "webapp", "vercel.json")
        with open(path) as f:
            data = json.load(f)
        assert data.get("framework") == "nextjs"
        assert "buildCommand" in data
        assert "outputDirectory" in data


# ─── Deploy README ───────────────────────────────────────────

class TestDeployReadme:
    """Validate deployment documentation."""

    def test_deploy_readme_exists(self):
        """deploy/README.md exists."""
        path = os.path.join(DEPLOY_DIR, "README.md")
        assert os.path.exists(path)

    def test_deploy_readme_has_sections(self):
        """deploy/README.md has key sections."""
        path = os.path.join(DEPLOY_DIR, "README.md")
        with open(path) as f:
            content = f.read()
        assert "Docker" in content
        assert "SSL" in content or "TLS" in content
        assert "systemd" in content
        assert "Backup" in content

    def test_main_readme_has_deployment(self):
        """Main README.md has deployment section."""
        path = os.path.join(PROJECT_ROOT, "README.md")
        with open(path) as f:
            content = f.read()
        assert "Deployment" in content
        assert "docker" in content.lower() or "Docker" in content
