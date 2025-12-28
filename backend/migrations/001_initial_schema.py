"""
Initial database schema migration.

Creates users and cv_vectors tables.
"""

from sqlalchemy import text


def upgrade(engine):
    """
    Apply migration: Create initial schema.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    with engine.connect() as conn:
        # Create users table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE NOT NULL,
                first_name VARCHAR,
                last_name VARCHAR,
                cv_uploaded_at TIMESTAMP WITH TIME ZONE,
                cv_processing_status VARCHAR,
                vector_id VARCHAR,
                company_name VARCHAR,
                job_title VARCHAR
            )
        """))
        
        # Create index on email
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """))
        
        # Create cv_vectors table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS cv_vectors (
                id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                cyborgdb_vector_id VARCHAR NOT NULL,
                vector_dimensions VARCHAR NOT NULL,
                original_filename VARCHAR,
                file_hash VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create index on candidate_id
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cv_vectors_candidate_id ON cv_vectors(candidate_id)
        """))
        
        # Create index on cyborgdb_vector_id
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cv_vectors_cyborgdb_id ON cv_vectors(cyborgdb_vector_id)
        """))
        
        conn.commit()


def downgrade(engine):
    """
    Rollback migration: Drop initial schema.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS cv_vectors"))
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.commit()