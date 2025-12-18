# Google Cloud Platform Setup Guide

This guide walks you through setting up Google Cloud Platform (GCP) and obtaining the OAuth 2.0 credentials needed for the Flask Google Drive API application.

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)

## Step 1: Create a Google Cloud Project

1. **Navigate to Google Cloud Console**
   - Go to https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create a New Project**
   - Click on the project dropdown at the top of the page
   - Click "New Project"
   - Enter a project name (e.g., "Flask Drive App")
   - Click "Create"
   - Wait for the project to be created (this may take a few seconds)

3. **Select Your Project**
   - Click on the project dropdown again
   - Select your newly created project

## Step 2: Enable Google Drive API

1. **Navigate to APIs & Services**
   - In the left sidebar, click on "APIs & Services" > "Library"
   - Or visit: https://console.cloud.google.com/apis/library

2. **Search for Google Drive API**
   - In the search bar, type "Google Drive API"
   - Click on "Google Drive API" from the results

3. **Enable the API**
   - Click the "Enable" button
   - Wait for the API to be enabled

## Step 3: Configure OAuth Consent Screen

1. **Navigate to OAuth Consent Screen**
   - In the left sidebar, click "APIs & Services" > "OAuth consent screen"
   - Or visit: https://console.cloud.google.com/apis/credentials/consent

2. **Select User Type**
   - Choose "External" (unless you have a Google Workspace account)
   - Click "Create"

3. **Fill in App Information**
   - **App name**: Enter your application name (e.g., "Flask Drive App")
   - **User support email**: Select your email address
   - **Developer contact information**: Enter your email address
   - Leave other fields as default
   - Click "Save and Continue"

4. **Configure Scopes**
   - Click "Add or Remove Scopes"
   - In the filter box, search for "Google Drive API"
   - Select the following scope:
     - `https://www.googleapis.com/auth/drive` (Full Drive access)
     - Or `https://www.googleapis.com/auth/drive.readonly` (Read-only access)
   - Click "Update"
   - Click "Save and Continue"

5. **Add Test Users** (for External apps)
   - Click "Add Users"
   - Enter your email address (and any other testers)
   - Click "Add"
   - Click "Save and Continue"

6. **Review and Finish**
   - Review your settings
   - Click "Back to Dashboard"

## Step 4: Create OAuth 2.0 Credentials

1. **Navigate to Credentials**
   - In the left sidebar, click "APIs & Services" > "Credentials"
   - Or visit: https://console.cloud.google.com/apis/credentials

2. **Create OAuth Client ID**
   - Click "Create Credentials" > "OAuth client ID"

3. **Configure OAuth Client**
   - **Application type**: Select "Web application"
   - **Name**: Enter a name (e.g., "Flask Drive Client")
   
4. **Add Authorized Redirect URIs**
   - Under "Authorized redirect URIs", click "Add URI"
   - Enter: `http://localhost:5000/auth/callback`
   - For production, add your production redirect URI (e.g., `https://yourdomain.com/auth/callback`)
   - Click "Create"

5. **Download Credentials**
   - A popup will appear with your Client ID and Client Secret
   - Click "Download JSON"
   - Save the file as `credentials.json`

## Step 5: Place Credentials File

1. **Move the Downloaded File**
   - Rename the downloaded file to `credentials.json` (if it has a different name)
   - Move it to your Flask project directory:
     ```bash
     mv ~/Downloads/client_secret_*.json /Users/nasim/pythonProjects/flask_drive_app/credentials.json
     ```

2. **Verify File Location**   
   ```bash
   ls -la /Users/nasim/pythonProjects/flask_drive_app/credentials.json
   ```

## Step 6: Test the Setup

1. **Start the Flask Application**
   ```bash
   cd /Users/nasim/pythonProjects/flask_drive_app
   source venv/bin/activate
   python app.py
   ```

2. **Authenticate**
   - Open your browser and visit: http://localhost:5000/auth
   - You should be redirected to Google's sign-in page
   - Sign in and grant permissions
   - You should be redirected back with a success message

3. **Verify Token Creation**
   - Check that `token.json` was created in your project directory
   ```bash
   ls -la /Users/nasim/pythonProjects/flask_drive_app/token.json
   ```

## Common Issues and Solutions

### Issue: "Access blocked: This app's request is invalid"

**Solution:**
- Ensure you've configured the OAuth consent screen
- Verify the redirect URI in Google Cloud Console matches exactly: `http://localhost:5000/auth/callback`
- Check that your email is added as a test user (for External apps)

### Issue: "redirect_uri_mismatch"

**Solution:**
- The redirect URI in your request doesn't match what's configured in Google Cloud Console
- Go to Credentials > Edit your OAuth client
- Ensure `http://localhost:5000/auth/callback` is listed under "Authorized redirect URIs"
- For production, add your production URL

### Issue: "invalid_client"

**Solution:**
- Your `credentials.json` file may be corrupted or from a different project
- Download the credentials file again from Google Cloud Console
- Ensure it's named exactly `credentials.json`

### Issue: "Access denied: You don't have permission to access this app"

**Solution:**
- Add your email as a test user in the OAuth consent screen
- If the app is in "Testing" mode, only test users can access it
- To make it public, publish the app (not recommended for personal use)

### Issue: "invalid_grant" or "Token has been expired or revoked"

**Solution:**
- Delete `token.json` and re-authenticate
- Visit http://localhost:5000/auth again

### Issue: "The API is not enabled for your project"

**Solution:**
- Ensure Google Drive API is enabled
- Go to APIs & Services > Library
- Search for "Google Drive API" and click "Enable"

## Security Best Practices

### For Development

1. **Never commit credentials**
   - Ensure `credentials.json` and `token.json` are in `.gitignore`
   - Don't share these files publicly

2. **Use test accounts**
   - Use a separate Google account for testing
   - Don't use your primary Google account with production data

### For Production

1. **Use HTTPS**
   - Always use HTTPS in production
   - Update redirect URI to use `https://`

2. **Restrict API Keys**
   - In Google Cloud Console, restrict your API keys
   - Limit access to specific IP addresses or referrers

3. **Publish OAuth App** (if needed)
   - If the app needs to be used by others, submit for verification
   - Go through Google's app verification process

4. **Monitor Usage**
   - Set up billing alerts in Google Cloud
   - Monitor API usage in the console

5. **Secure Token Storage**
   - In production, use a database to store tokens
   - Encrypt tokens at rest
   - Implement token rotation

## Additional Resources

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 for Web Apps](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Drive API Scopes](https://developers.google.com/drive/api/v3/about-auth)

## API Quota Information

Google Drive API has the following quotas:

- **Queries per day**: 1,000,000,000
- **Queries per 100 seconds per user**: 1,000
- **Queries per 100 seconds**: 10,000

For most applications, these limits are more than sufficient. If you need higher quotas, you can request an increase in the Google Cloud Console.

## Next Steps

Once you've completed this setup:

1. ✅ You have a Google Cloud Project
2. ✅ Google Drive API is enabled
3. ✅ OAuth consent screen is configured
4. ✅ OAuth 2.0 credentials are created
5. ✅ `credentials.json` is in your project directory

You're ready to run the Flask application! See [README.md](README.md) for usage instructions.
