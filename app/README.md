# API Documentation Generator - Backend

A powerful FastAPI backend service for generating beautiful, interactive API documentation from multiple sources including OpenAPI specifications, cURL commands, backend ZIP files, and GitHub repositories.

## Features

- **Multiple Input Methods**: Parse OpenAPI JSON/YAML, cURL commands, backend ZIP files, and GitHub repositories
- **AI-Powered Descriptions**: Generate intelligent endpoint descriptions using OpenAI GPT-4
- **Interactive Testing**: Real-time API endpoint testing with comprehensive response handling
- **Google OAuth Authentication**: Secure user authentication with session management
- **Analytics Tracking**: Track feature usage with detailed statistics
- **Database Integration**: PostgreSQL with async SQLAlchemy for data persistence
- **Code Analysis**: Automatic API discovery from Python/FastAPI codebases

## Tech Stack

- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy** - Python SQL toolkit with async support
- **PostgreSQL** - Robust relational database
- **OpenAI GPT-4** - AI-powered endpoint description generation
- **Google OAuth 2.0** - Secure authentication system
- **Authlib** - OAuth client library
- **httpx** - Async HTTP client for API testing
- **Pydantic** - Data validation using Python type annotations

## Prerequisites

Make sure the following are installed:

- **Python** - v3.13.2 (Preferred 3.8+)
- **FastAPI & Uvicorn**
- **PostgreSQL**
- **pip** - Python package installer

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── authentication.py    # Google OAuth endpoints
│   │       │   ├── openapi.py          # OpenAPI upload & parsing
│   │       │   ├── curl.py             # cURL command parsing
│   │       │   ├── code.py             # Code analysis endpoints
│   │       │   ├── test.py             # API testing endpoints
│   │       │   └── analytics.py        # Usage tracking
│   │       └── api.py                  # API router configuration
│   ├── core/
│   │   └── config.py                   # Application settings
│   ├── db/
│   │   └── database.py                 # Database configuration
│   ├── models/                         # SQLAlchemy models
│   │   ├── user.py                     # User model
│   │   ├── project.py                  # Project model
│   │   ├── endpoint.py                 # API endpoint model
│   │   ├── versionlog.py               # Version tracking
│   │   └── analytics.py                # Usage analytics
│   ├── schemas/                        # Pydantic schemas
│   │   ├── auth.py                     # Authentication schemas
│   │   ├── openapi.py                  # OpenAPI schemas
│   │   ├── curl.py                     # cURL schemas
│   │   └── analytics.py                # Analytics schemas
│   ├── services/                       # Business logic
│   │   ├── ai_service.py               # OpenAI integration
│   │   ├── openapi_parser.py           # OpenAPI parsing logic
│   │   ├── curl_parser.py              # cURL parsing logic
│   │   └── code_parser.py              # Code analysis service
│   └── main.py                         # FastAPI application entry point
├── requirements.txt                    # Python dependencies
├── .env                               # Environment variables (create this)
├── .gitignore                         # Git ignore rules
└── README.md                          # This file
```

## Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd api-docs-backend
   ```

2. **Create and activate virtual environment**

   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**

   ```bash
   # Create database
   createdb api_docs_db

   # Or using psql
   psql -U postgres
   CREATE DATABASE api_docs_db;
   ```

5. **Environment Configuration**
   Create a `.env` file in the backend root directory:

   ```env
   # Database
   DATABASE_URL=postgresql+asyncpg://username:password@localhost/api_docs_db

   # OpenAI API (for AI descriptions)
   OPENAI_API_KEY=your_openai_api_key_here

   # Google OAuth (for authentication)
   CLIENT_ID=your_google_oauth_client_id
   CLIENT_SECRET=your_google_oauth_client_secret

   # Application URLs
   FRONTEND_URL=http://localhost:5173
   BACKEND_URL=http://127.0.0.1:8000

   # Security
   SECRET_KEY=your_secret_key_here_use_strong_random_string
   ```

6. **Start the development server**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Verify installation**
   Navigate to `http://localhost:8000/docs` for interactive API documentation

## API Endpoints

### Authentication (`/api/v1/authentication`)

- `GET /login` - Initiate Google OAuth login
- `GET /callback` - Handle OAuth callback
- `GET /user` - Get current user profile
- `POST /logout` - Logout user
- `GET /debug-urls` - Debug OAuth URL generation

### OpenAPI Processing (`/api/v1/openapi`)

- `POST /upload` - Upload OpenAPI spec from URL
- `POST /upload-file` - Upload OpenAPI file (JSON/YAML)
- `GET /project/{project_id}/templates` - Generate API testing templates

### cURL Processing (`/api/v1/curl`)

- `POST /upload` - Parse and convert cURL commands

### Code Analysis (`/api/v1/code`)

- `POST /upload-backend-zip` - Analyze backend ZIP file
- `POST /upload-github-repo` - Clone and analyze GitHub repository

### API Testing (`/api/v1`)

- `POST /test-endpoint` - Test API endpoints with real requests

### Analytics (`/api/v1/analytics`)

- `POST /track` - Track feature usage
- `GET /global` - Get global usage statistics
- `GET /user/{user_id}` - Get user-specific statistics

## Core Features Explained

### OpenAPI Parser

- Supports both JSON and YAML formats
- Resolves `$ref` references in schemas
- Extracts request/response schemas automatically
- Handles authentication requirements detection

### AI-Powered Descriptions

- Uses OpenAI GPT-4 to generate endpoint descriptions
- Provides context-aware, technical documentation
- Falls back gracefully when AI service is unavailable

### cURL Command Parser

- Converts cURL commands to structured API documentation
- Supports various content types (JSON, form-urlencoded, multipart)
- Extracts authentication headers automatically

### Code Analysis

- Analyzes Python/FastAPI codebases for API discovery
- Supports ZIP file uploads and GitHub repository cloning
- Generates OpenAPI specifications from code

### Authentication System

- Google OAuth 2.0 integration
- JWT token-based session management
- Secure cookie handling with proper CORS setup

## Database Models

### User

- Email, name, Google ID, profile picture
- Activity tracking and session management

### Project

- Container for API documentation projects
- Base URL and project metadata

### Endpoint

- Individual API endpoints with full specifications
- Method, path, authentication requirements
- Request/response schema storage

### VersionLog

- Historical tracking of OpenAPI specifications
- Raw data preservation for audit trails

### FeatureUsage

- Analytics tracking for feature usage
- User behavior insights and statistics

## Development Guidelines

### Database Operations

- Use async SQLAlchemy sessions
- Implement proper transaction handling
- Follow database migration best practices

### API Design

- Follow RESTful conventions
- Use appropriate HTTP status codes
- Implement comprehensive error responses
- Validate all input data with Pydantic

## Environment Variables

| Variable         | Description                        | Default                 |
| ---------------- | ---------------------------------- | ----------------------- |
| `DATABASE_URL`   | PostgreSQL connection string       | Required                |
| `OPENAI_API_KEY` | OpenAI API key for AI descriptions | Required                |
| `CLIENT_ID`      | Google OAuth client ID             | Required                |
| `CLIENT_SECRET`  | Google OAuth client secret         | Required                |
| `FRONTEND_URL`   | Frontend application URL           | `http://localhost:5173` |
| `BACKEND_URL`    | Backend application URL            | `http://127.0.0.1:8000` |
| `SECRET_KEY`     | JWT signing secret                 | Required                |

## Security Considerations

- All API endpoints use proper authentication where required
- JWT tokens are stored in HTTP-only cookies
- CORS is configured for frontend integration
- OAuth state management prevents CSRF attacks
- Database queries use parameterized statements

## Testing

Run the development server and test endpoints using:

- **FastAPI Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Direct API calls**: Use tools like Postman or curl

## Troubleshooting

### Common Issues

1. **Database connection errors**

   - Verify PostgreSQL is running
   - Check DATABASE_URL format
   - Ensure database exists

2. **Google OAuth not working**

   - Verify CLIENT_ID and CLIENT_SECRET
   - Check OAuth redirect URLs in Google Console
   - Ensure CORS settings allow frontend domain

3. **AI descriptions failing**

   - Verify OPENAI_API_KEY is valid
   - Check OpenAI API quota and billing
   - Review API rate limits

4. **Import errors**
   - Ensure virtual environment is activated
   - Install all requirements: `pip install -r requirements.txt`
   - Check Python version compatibility

## License

Free to use for personal and educational purposes.

## Author

Made with ❤️ by **RB Rithanya**
