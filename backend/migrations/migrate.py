"""
Database migration runner.

Simple migration system for SecureHR database schema.
"""

import importlib
import os
from pathlib import Path
from sqlalchemy import create_engine, text
from typing import List

from app.config import settings


class MigrationRunner:
    """Simple database migration runner."""
    
    def __init__(self, database_url: str = None):
        """
        Initialize migration runner.
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(self.database_url)
        self.migrations_dir = Path(__file__).parent
    
    def get_migration_files(self) -> List[str]:
        """
        Get list of migration files in order.
        
        Returns:
            List of migration file names (without .py extension)
        """
        migration_files = []
        for file in sorted(self.migrations_dir.glob("*.py")):
            if file.name.startswith("00") and file.name != "__init__.py" and file.name != "migrate.py":
                migration_files.append(file.stem)
        return migration_files
    
    def create_migrations_table(self):
        """Create migrations tracking table if it doesn't exist."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
    
    def get_applied_migrations(self) -> List[str]:
        """
        Get list of applied migrations.
        
        Returns:
            List of applied migration versions
        """
        self.create_migrations_table()
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
            return [row[0] for row in result]
    
    def mark_migration_applied(self, version: str):
        """
        Mark a migration as applied.
        
        Args:
            version: Migration version to mark as applied
        """
        with self.engine.connect() as conn:
            conn.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version}
            )
            conn.commit()
    
    def run_migration(self, migration_name: str, direction: str = "upgrade"):
        """
        Run a specific migration.
        
        Args:
            migration_name: Name of migration file (without .py)
            direction: 'upgrade' or 'downgrade'
        """
        module_name = f"migrations.{migration_name}"
        migration_module = importlib.import_module(module_name)
        
        if direction == "upgrade":
            migration_module.upgrade(self.engine)
            self.mark_migration_applied(migration_name)
            print(f"Applied migration: {migration_name}")
        elif direction == "downgrade":
            migration_module.downgrade(self.engine)
            # Remove from applied migrations
            with self.engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM schema_migrations WHERE version = :version"),
                    {"version": migration_name}
                )
                conn.commit()
            print(f"Rolled back migration: {migration_name}")
    
    def migrate_up(self):
        """Run all pending migrations."""
        migration_files = self.get_migration_files()
        applied_migrations = self.get_applied_migrations()
        
        pending_migrations = [m for m in migration_files if m not in applied_migrations]
        
        if not pending_migrations:
            print("No pending migrations.")
            return
        
        for migration in pending_migrations:
            self.run_migration(migration, "upgrade")
        
        print(f"Applied {len(pending_migrations)} migrations.")
    
    def migrate_down(self, steps: int = 1):
        """
        Roll back migrations.
        
        Args:
            steps: Number of migrations to roll back
        """
        applied_migrations = self.get_applied_migrations()
        
        if not applied_migrations:
            print("No migrations to roll back.")
            return
        
        migrations_to_rollback = applied_migrations[-steps:]
        migrations_to_rollback.reverse()  # Roll back in reverse order
        
        for migration in migrations_to_rollback:
            self.run_migration(migration, "downgrade")
        
        print(f"Rolled back {len(migrations_to_rollback)} migrations.")


def main():
    """Main migration runner entry point."""
    import sys
    
    runner = MigrationRunner()
    
    if len(sys.argv) < 2:
        print("Usage: python migrate.py [up|down] [steps]")
        return
    
    command = sys.argv[1]
    
    if command == "up":
        runner.migrate_up()
    elif command == "down":
        steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        runner.migrate_down(steps)
    else:
        print("Unknown command. Use 'up' or 'down'.")


if __name__ == "__main__":
    main()
