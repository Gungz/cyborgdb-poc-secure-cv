"""Add saved searches table for recruiters."""

from sqlalchemy import text


def upgrade(engine):
    """Add saved_searches table."""
    with engine.connect() as connection:
        connection.execute(text("""
            CREATE TABLE saved_searches (
                id TEXT PRIMARY KEY,
                recruiter_id TEXT NOT NULL,
                name TEXT NOT NULL,
                requirements TEXT NOT NULL,
                filters TEXT,  -- JSON stored as TEXT
                "limit" TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                use_count TEXT DEFAULT '0',
                FOREIGN KEY (recruiter_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """))
        
        # Create index on recruiter_id for faster queries
        connection.execute(text("""
            CREATE INDEX idx_saved_searches_recruiter_id ON saved_searches (recruiter_id)
        """))
        
        connection.commit()


def downgrade(engine):
    """Remove saved_searches table."""
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS saved_searches"))
        connection.commit()