# SecureHR - Privacy-Preserving Talent Matching Platform

SecureHR is an AI-powered talent matching platform that enables privacy-preserving recruitment through encrypted vector search using CyborgDB.

## Project Structure

```
securehr/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── models/         # Data models
│   │   ├── services/       # Business logic
│   │   ├── middleware/     # Security & audit middleware
│   │   └── config.py       # Configuration
│   ├── tests/              # Backend tests
│   ├── migrations/         # Database migrations
│   ├── main.py             # FastAPI app entry point
│   ├── requirements.txt    # Python dependencies
│   └── pyproject.toml      # Python project configuration
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── contexts/       # React contexts
│   │   ├── services/       # API services
│   │   ├── styles/         # CSS styles
│   │   └── types/          # TypeScript types
│   ├── public/
│   └── package.json        # Node.js dependencies
├── docker-compose.yml      # Docker services configuration
└── README.md
```

## Prerequisites

- Python 3.9+
- Node.js 18+
- Docker and Docker Compose
- pip (Python package manager)
- npm (Node.js package manager)

## Quick Start

### 1. Configure CyborgDB API Key

Before starting the services, you need to set your CyborgDB API key in `docker-compose.yml`:

1. Open `docker-compose.yml`
2. Find the `cyborgdb` service section
3. Replace `<replace_with_your_api_key>` with your actual CyborgDB API key:

```yaml
cyborgdb:
  image: cyborginc/cyborgdb-service:latest
  environment:
    CYBORGDB_API_KEY: your-actual-api-key-here  # Replace this
    # ... other settings
```

You can obtain a CyborgDB API key from [CyborgDB](https://cyborg.co).

### 2. Start Infrastructure Services

Start PostgreSQL and CyborgDB using Docker Compose:

```bash
# Start PostgreSQL and CyborgDB services
docker-compose up -d

# Verify services are running
docker-compose ps
```

This starts:
- **PostgreSQL** on port 5432 - shared database for user data and CyborgDB vector storage
- **CyborgDB** on port 8100 - encrypted vector database service backed by PostgreSQL

### 2. Verify Infrastructure

Run the verification script to ensure all services are running:

```bash
python verify_setup.py
```

## Backend Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database Configuration - PostgreSQL (shared with CyborgDB)
DATABASE_URL=postgresql://securehr:securehr_password@localhost:5432/securehr

# CyborgDB Configuration
CYBORGDB_HOST=localhost
CYBORGDB_PORT=8100
CYBORGDB_API_KEY=your-cyborgdb-api-key
CYBORGDB_DB_TYPE=postgres
CYBORGDB_CONNECTION_STRING=postgresql://securehr:securehr_password@localhost:5432/securehr
CYBORGDB_INDEX_KEY_FILE=/path/to/your/index_key

# Security Configuration
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Vector Configuration
VECTOR_DIMENSION=384
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 4. Generate CyborgDB Index Key

CyborgDB uses encrypted indexes for privacy-preserving vector storage. You need to generate an index key before using the application.

For more details, see the [CyborgDB Encrypted Indexes documentation](https://docs.cyborg.co/versions/v0.14.x/service/guides/encrypted-indexes/create-index).

Generate the index key using the CyborgDB Python client:

```python
from cyborgdb import Client

# Initialize the client
client = Client(
    base_url="http://localhost:8100",
    api_key="your-cyborgdb-api-key"
)

# Generate and save the index key
# This saves the key to ~/.cyborgdb/index_key by default
index_key = client.generate_key(save=True)
print(f"Index key saved to ~/.cyborgdb/index_key")
```

Or run this one-liner:

```bash
python -c "from cyborgdb import Client; Client(base_url='http://localhost:8100', api_key='your-api-key').generate_key(save=True); print('Index key saved to ~/.cyborgdb/index_key')"
```

Then update your `.env` file to point to the key file:

```env
CYBORGDB_INDEX_KEY_FILE=/Users/your-username/.cyborgdb/index_key
```

**Important Notes:**
- The index key is used to encrypt/decrypt your vector data - keep it secure!
- Never commit the index key file to version control
- Back up your index key - if lost, you cannot decrypt your stored vectors
- The application will automatically create the index on first CV upload

### 5. Run Database Migrations

```bash
cd backend
python -m migrations.migrate up
```

### 6. Start the Backend Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Seed Test Candidates (Optional)

To populate the database with test candidates and their CVs for testing the search functionality:

```bash
cd backend
python seed_candidates.py
```

This script will:
- Create 10 test candidate accounts with sample CVs from the `test_cvs/` folder
- Process each CV and store encrypted vectors in CyborgDB
- If a user already exists, it will update their CV instead of creating a new user

**Test Candidates Created:**
| Role | Email | Password |
|------|-------|----------|
| Software Engineer | alex.chen@email.com | secureHRPa55$ |
| Data Scientist | sarah.johnson@email.com | secureHRPa55$ |
| Product Manager | michael.rodriguez@email.com | secureHRPa55$ |
| UX Designer | emily.park@email.com | secureHRPa55$ |
| DevOps Engineer | james.wilson@email.com | secureHRPa55$ |
| Marketing Manager | jennifer.martinez@email.com | secureHRPa55$ |
| Financial Analyst | david.kim@email.com | secureHRPa55$ |
| HR Manager | amanda.thompson@email.com | secureHRPa55$ |
| Sales Executive | robert.anderson@email.com | secureHRPa55$ |
| Project Manager | lisa.chen@email.com | secureHRPa55$ |

The script outputs timing statistics for CyborgDB vector storage operations.

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
REACT_APP_API_URL=http://localhost:8000
```

### 3. Start the Frontend Server

```bash
npm start
```

The frontend will be available at http://localhost:3000

## Docker Compose Setup (All-in-One)

The `docker-compose.yml` is pre-configured with all services sharing a single PostgreSQL database.

**Important:** Before starting, edit `docker-compose.yml` and replace `<replace_with_your_api_key>` with your actual CyborgDB API key in the `cyborgdb` service section.

```yaml
version: '3.8'

services:
  # PostgreSQL database - shared by both user data and CyborgDB
  postgres:
    image: postgres:15
    container_name: securehr-postgres
    environment:
      POSTGRES_USER: securehr
      POSTGRES_PASSWORD: securehr_password
      POSTGRES_DB: securehr
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # CyborgDB encrypted vector database service
  cyborgdb:
    image: cyborginc/cyborgdb-service:latest
    container_name: securehr-cyborgdb
    depends_on:
      - postgres
    environment:
      CYBORGDB_API_KEY: <replace_with_your_api_key>  # <-- Replace this!
      CYBORGDB_DB_TYPE: postgres
      CYBORGDB_CONNECTION_STRING: host=postgres port=5432 dbname=securehr user=securehr password=securehr_password
    ports:
      - "8100:8000"

volumes:
  postgres_data:
```

Start all services:

```bash
docker-compose up -d
```

## Running Tests

### Backend Tests

```bash
cd backend
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run property-based tests only
pytest -k "property"
```

### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run tests with coverage
npm test -- --coverage
```

## Development Tools

The project includes the following development tools:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing framework
- **hypothesis**: Property-based testing

Run linting and formatting:

```bash
cd backend
black .
isort .
flake8 .
mypy .
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Features

- **Candidate Registration**: Secure account creation for job seekers
- **CV Upload & Processing**: Automated CV text extraction and vectorization
- **Encrypted Vector Storage**: Privacy-preserving storage using CyborgDB
- **Recruiter Search**: Similarity-based candidate matching
- **Privacy Protection**: No exposure of candidate personal information
- **Secure Authentication**: JWT-based session management
- **Rate Limiting**: DDoS protection and request throttling
- **Audit Logging**: Comprehensive security event tracking

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Backend│    │    CyborgDB     │
│                 │    │                 │    │                 │
│ - Candidate UI  │◄──►│ - Auth Service  │◄──►│ - Encrypted     │
│ - Recruiter UI  │    │ - CV Processor  │    │   Vectors       │
│ - Login/Signup  │    │ - Search Engine │    │ - Similarity    │
└─────────────────┘    └─────────────────┘    │   Search        │
                              │               └─────────────────┘
                              │                       │
                              ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   SQLite/       │    │   PostgreSQL    │
                       │   PostgreSQL    │    │   (CyborgDB     │
                       │   (User Data)   │    │    Backend)     │
                       └─────────────────┘    └─────────────────┘
```

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# View PostgreSQL logs
docker logs securehr-postgres

# Connect to PostgreSQL directly
docker exec -it securehr-postgres psql -U securehr -d securehr
```

### CyborgDB Connection Issues

```bash
# Check if CyborgDB is running
docker ps | grep cyborgdb

# View CyborgDB logs
docker logs securehr-cyborgdb

# Test CyborgDB health endpoint
curl http://localhost:8100/health
```

### Backend Issues

```bash
# Check backend logs
docker logs securehr-backend

# Run backend in debug mode
uvicorn main:app --reload --log-level debug
```

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Backend│    │    CyborgDB     │
│                 │    │                 │    │   (port 8100)   │
│ - Candidate UI  │◄──►│ - Auth Service  │◄──►│ - Encrypted     │
│ - Recruiter UI  │    │ - CV Processor  │    │   Vectors       │
│ - Login/Signup  │    │ - Search Engine │    │ - Similarity    │
└─────────────────┘    └─────────────────┘    │   Search        │
                              │               └────────┬────────┘
                              │                        │
                              ▼                        ▼
                       ┌──────────────────────────────────────┐
                       │           PostgreSQL                  │
                       │         (port 5432)                   │
                       │  - User Data (securehr tables)        │
                       │  - CyborgDB Vector Storage            │
                       └──────────────────────────────────────┘
```

## License

This project is for demonstration purposes.
