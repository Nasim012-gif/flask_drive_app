# Flask Google Drive API

A Flask backend application with Google Drive API integration, providing RESTful endpoints for file operations (list, upload, download, delete, search).

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure Google Drive access
- 📁 **File Management** - List, upload, download, and delete files
- 🔍 **Search Functionality** - Search files with custom queries
- 🌐 **RESTful API** - Clean, well-documented endpoints
- 🔒 **Secure** - Token-based authentication with automatic refresh

## Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account
- Google Drive API enabled

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/nasim/pythonProjects/flask_drive_app
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your `FLASK_SECRET_KEY`:

```env
FLASK_SECRET_KEY=your-random-secret-key-here
```

### 3. Google Cloud Setup

**⚠️ Important:** You must complete this step before running the application.

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions on:
- Creating a Google Cloud Platform project
- Enabling Google Drive API
- Creating OAuth 2.0 credentials
- Downloading `credentials.json`

Place the downloaded `credentials.json` file in the project root directory.

### 4. Run the Application

```bash
python app.py
```

The server will start at `http://localhost:5000`

### 5. Authenticate

1. Visit `http://localhost:5000/auth` in your browser
2. Sign in with your Google account
3. Grant the requested permissions
4. You'll be redirected back with a success message

## API Endpoints

### Health Check
```http
GET /
```
Returns server status and authentication state.

**Response:**
```json
{
  "status": "ok",
  "message": "Flask Google Drive API is running",
  "authenticated": true
}
```

---

### Authenticate
```http
GET /auth
```
Initiates OAuth 2.0 flow. Redirects to Google sign-in page.

---

### List Files
```http
GET /files?page_size=10&query=name contains 'report'
```

**Query Parameters:**
- `page_size` (optional): Number of files to return (default: 10)
- `query` (optional): Search query in Drive API format

**Response:**
```json
{
  "status": "success",
  "count": 5,
  "files": [
    {
      "id": "file-id-here",
      "name": "example.pdf",
      "mimeType": "application/pdf",
      "size": "1024000",
      "createdTime": "2025-12-12T10:00:00.000Z",
      "modifiedTime": "2025-12-12T12:00:00.000Z",
      "webViewLink": "https://drive.google.com/..."
    }
  ]
}
```

---

### Upload File
```http
POST /upload
Content-Type: multipart/form-data
```

**Form Data:**
- `file` (required): File to upload
- `name` (optional): Custom name for the file
- `folder_id` (optional): Parent folder ID

**Example with curl:**
```bash
curl -X POST -F "file=@document.pdf" http://localhost:5000/upload
```

**Response:**
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "file": {
    "id": "new-file-id",
    "name": "document.pdf",
    "mimeType": "application/pdf",
    "size": "524288",
    "webViewLink": "https://drive.google.com/..."
  }
}
```

---

### Download File
```http
GET /download/<file_id>
```

**Path Parameters:**
- `file_id`: ID of the file to download

Downloads the file to your browser/client.

**Example:**
```bash
curl -O http://localhost:5000/download/abc123xyz
```

---

### Delete File
```http
DELETE /delete/<file_id>
```

**Path Parameters:**
- `file_id`: ID of the file to delete

**Example:**
```bash
curl -X DELETE http://localhost:5000/delete/abc123xyz
```

**Response:**
```json
{
  "status": "success",
  "message": "File abc123xyz deleted successfully"
}
```

---

### Search Files
```http
GET /search?q=name contains 'report'
```

**Query Parameters:**
- `q` (required): Search query

**Example Queries:**
- `name contains 'report'` - Files with "report" in the name
- `mimeType='application/pdf'` - All PDF files
- `modifiedTime > '2023-01-01T00:00:00'` - Files modified after Jan 1, 2023

**Response:**
```json
{
  "status": "success",
  "count": 3,
  "files": [...]
}
```

## Authentication Flow

1. User visits `/auth` endpoint
2. Application redirects to Google OAuth consent page
3. User signs in and grants permissions
4. Google redirects back to `/auth/callback` with authorization code
5. Application exchanges code for access token
6. Token is saved to `token.json` for future requests
7. Token automatically refreshes when expired

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200` - Success
- `400` - Bad request (missing parameters, invalid input)
- `401` - Unauthorized (not authenticated)
- `404` - Not found (file or endpoint doesn't exist)
- `500` - Internal server error

**Error Response Format:**
```json
{
  "error": "Error message describing what went wrong"
}
```

## Security Considerations

### Production Deployment

1. **Use HTTPS**: Always use HTTPS in production
2. **Secret Key**: Generate a strong random secret key
3. **Environment Variables**: Never commit `.env` or `credentials.json` to version control
4. **Token Storage**: Consider using a database for token storage in production
5. **CORS**: Configure CORS to allow only trusted origins

### Generate a Secure Secret Key

```python
import secrets
print(secrets.token_hex(32))
```

### Restricted Scopes

If you only need read access, change the scope in `config.py`:

```python
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
```

## Troubleshooting

### "credentials.json not found"
- Complete the Google Cloud setup (see SETUP_GUIDE.md)
- Ensure `credentials.json` is in the project root directory

### "Not authenticated" error
- Visit `/auth` endpoint to authenticate
- Check if `token.json` exists and is valid

### "Invalid grant" error
- Delete `token.json` and re-authenticate
- Ensure OAuth consent screen is properly configured

### "Access denied" error
- Check that you've granted all requested permissions
- Verify the OAuth scope in `config.py` matches your consent screen

## Project Structure

```
flask_drive_app/
├── app.py                 # Main Flask application
├── drive_service.py       # Google Drive API wrapper
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── SETUP_GUIDE.md        # Google Cloud setup instructions
├── credentials.json      # OAuth credentials (you create this)
└── token.json            # Access token (auto-generated)
```

## Development

### Running in Debug Mode

Debug mode is enabled by default in development. To disable:

```env
FLASK_DEBUG=False
```

### Testing with curl

```bash
# List files
curl http://localhost:5000/files

# Upload file
curl -X POST -F "file=@test.txt" http://localhost:5000/upload

# Download file
curl -O http://localhost:5000/download/FILE_ID

# Delete file
curl -X DELETE http://localhost:5000/delete/FILE_ID

# Search files
curl "http://localhost:5000/search?q=name%20contains%20'test'"
```

## License

This project is provided as-is for educational and development purposes.

## Support

For issues related to:
- **Google Cloud Platform**: See [Google Cloud Documentation](https://cloud.google.com/docs)
- **Google Drive API**: See [Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- **Flask**: See [Flask Documentation](https://flask.palletsprojects.com/)
