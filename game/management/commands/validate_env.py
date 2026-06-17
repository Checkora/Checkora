import os
import sys
import shutil
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "[Diagnose] Diagnoses local development environment dependencies, database connections, and C++ engine compilation status."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Checkora Developer Environment Diagnostics ==="))
        self.stdout.write("=" * 60)

        # Check 1: Django Secret Key Strength
        self.stdout.write("\n1. [Settings] Django Settings Check:")
        secret_key = getattr(settings, 'SECRET_KEY', '')
        if secret_key == 'django-insecure-dev-key-for-local-testing':
            self.stdout.write(self.style.WARNING("   [WARN] SECRET_KEY is using the insecure default value. (OK for local development)"))
        elif len(secret_key) < 32:
            self.stdout.write(self.style.WARNING("   [WARN] SECRET_KEY is too short (less than 32 characters)."))
        else:
            self.stdout.write(self.style.SUCCESS("   [OK] Django settings are configured correctly."))

        # Check 2: g++ compiler presence
        self.stdout.write("\n2. [Compiler] C++ Compiler Status:")
        gxx_path = shutil.which("g++")
        if gxx_path:
            self.stdout.write(self.style.SUCCESS(f"   [OK] C++ compiler (g++) found at: {gxx_path}"))
            try:
                result = subprocess.run(["g++", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                version_line = result.stdout.splitlines()[0] if result.stdout else "unknown version"
                self.stdout.write(f"      Version: {version_line}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"      Could not retrieve compiler version: {e}"))
        else:
            self.stdout.write(self.style.WARNING(
                "   [WARN] g++ compiler was NOT found in your PATH.\n"
                "      Checkora will fallback to the slower Python engine execution during gameplay."
            ))

        # Check 3: Compiled chess engine presence and readability
        self.stdout.write("\n3. [Engine] Chess Engine Status:")
        engine_dir = Path(settings.BASE_DIR) / 'game' / 'engine'
        binary_name = "main.exe" if os.name == 'nt' else "main"
        engine_binary = engine_dir / binary_name
        fallback_script = engine_dir / "main.py"

        if engine_binary.exists():
            is_executable = os.access(engine_binary, os.X_OK)
            status_text = "Executable" if is_executable else "Found but not executable (permissions issue)"
            self.stdout.write(self.style.SUCCESS(f"   [OK] Primary engine binary found: {engine_binary} ({status_text})"))
        else:
            self.stdout.write(self.style.WARNING(
                f"   [WARN] Compiled binary '{binary_name}' was NOT found in game/engine/.\n"
                "      Please compile it by running: g++ -O2 -std=c++17 game/engine/main.cpp -o game/engine/main"
            ))

        if fallback_script.exists():
            self.stdout.write(self.style.SUCCESS(f"   [OK] Python fallback engine script found: {fallback_script}"))
        else:
            self.stdout.write(self.style.ERROR(f"   [FAIL] Python fallback engine '{fallback_script}' is missing!"))

        # Check 4: Database Connection and Migrations status
        self.stdout.write("\n4. [Database] Database & Migration Status:")
        try:
            db_conn = connections['default']
            db_conn.cursor()  # Trigger connection check
            self.stdout.write(self.style.SUCCESS("   [OK] Database connection successful."))
            
            executor = MigrationExecutor(db_conn)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                self.stdout.write(self.style.WARNING(f"   [WARN] There are {len(plan)} unapplied migrations. Run 'python manage.py migrate' to apply them."))
            else:
                self.stdout.write(self.style.SUCCESS("   [OK] All database migrations are up-to-date."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   [FAIL] Database connection failed: {e}"))

        # Check 5: Static directories structure
        self.stdout.write("\n5. [Directories] Directory Structure Check:")
        staticfiles_dir = Path(settings.BASE_DIR) / 'game' / 'static'
        if staticfiles_dir.exists() and staticfiles_dir.is_dir():
            self.stdout.write(self.style.SUCCESS(f"   [OK] Static folder found: {staticfiles_dir}"))
        else:
            self.stdout.write(self.style.ERROR("   [FAIL] Critical: game/static/ directory is missing!"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Diagnostics Completed!"))
