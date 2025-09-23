# Gmail Unsubscriber - API Documentation

This document provides detailed information about the backend API endpoints for the Gmail Unsubscriber application.

## Base URL

All API endpoints are relative to the base URL of your deployed backend:
- Development: `http://localhost:5000`
- Production: Your deployed backend URL

## Authentication

Most endpoints require authentication. The application uses cookie-based authentication with sessions.

### Authentication Endpoints

#### GET /api/auth/login

Initiates the OAuth2 authorization flow with Google.

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?..."
}
```

#### GET /oauth2callback

Handles the OAuth2 callback from Google. This endpoint is called by Google after the user authorizes the application.

**Query Parameters:**
- `code`: Authorization code from Google
- `state`: State parameter for security verification

**Response:**
- Redirects to the frontend with authentication status

#### POST /api/auth/logout

Logs out the user by clearing their session.

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

#### GET /api/auth/status

Checks if the user is authenticated.

**Response:**
```json
{
  "authenticated": true,
  "email": "user@gmail.com"
}
```

Or if not authenticated:
```json
{
  "authenticated": false
}
```

## Data Endpoints

### GET /api/stats

Gets the user's unsubscription statistics.

**Authentication Required:** Yes

**Response:**
```json
{
  "total_scanned": 42,
  "total_unsubscribed": 35,
  "time_saved": 70
}
```

### GET /api/unsubscribed-services

Gets the list of unsubscribed services/domains.

**Authentication Required:** Yes

**Response:**
```json
[
  {
    "domain": "example.com",
    "sender_name": "Example Newsletter",
    "emails": ["newsletter@example.com"],
    "count": 5,
    "last_unsubscribed": "2025-04-08T12:34:56.789Z"
  }
]
```

### GET /api/activities

Gets the user's recent activities.

**Authentication Required:** Yes

**Response:**
```json
[
  {
    "type": "success",
    "message": "Successfully unsubscribed from email 1/10",
    "time": "2025-04-08T12:34:56.789Z"
  },
  {
    "type": "error",
    "message": "Failed to unsubscribe from email 2/10",
    "time": "2025-04-08T12:35:56.789Z"
  }
]
```

## Process Endpoints

### POST /api/unsubscribe/start

Starts the unsubscription process.

**Authentication Required:** Yes

**Request Body:**
```json
{
  "search_query": "\"unsubscribe\" OR \"email preferences\" OR \"opt-out\" OR \"subscription preferences\"",
  "max_emails": 50
}
```

**Response:**
```json
{
  "success": true,
  "message": "Unsubscription process started"
}
```

### GET /api/unsubscribe/status

Gets the status of the unsubscription process.

**Authentication Required:** Yes

**Response:**
```json
{
  "stats": {
    "total_scanned": 42,
    "total_unsubscribed": 35,
    "time_saved": 70
  },
  "activities": [
    {
      "type": "success",
      "message": "Successfully unsubscribed from email 1/10",
      "time": "2025-04-08T12:34:56.789Z"
    }
  ],
  "status": "in_progress"
}
```

### POST /api/unsubscribe/preview

Preview emails for unsubscription without making changes. This endpoint scans emails and detects RFC 8058 one-click unsubscribe support.

**Authentication Required:** Yes

**Request Body:**
```json
{
  "search_query": "\"unsubscribe\" OR \"opt-out\"",
  "max_emails": 50
}
```

**Response:**
```json
{
  "candidates": [
    {
      "id": "msg123",
      "subject": "Weekly Newsletter",
      "sender_name": "Example News",
      "sender_email": "news@example.com",
      "domain": "example.com",
      "has_rfc8058_one_click": true,
      "rfc8058_unsub_url": "https://example.com/unsub/123",
      "recommended_action": "one_click_unsub"
    },
    {
      "id": "msg124",
      "subject": "Marketing Email",
      "sender_name": "Store",
      "sender_email": "store@shop.com",
      "domain": "shop.com",
      "has_rfc8058_one_click": false,
      "rfc8058_unsub_url": "",
      "recommended_action": "label_archive"
    }
  ],
  "message": "Found 2 email candidates"
}
```

### POST /api/unsubscribe/apply

Apply unsubscribe actions to selected emails. Supports RFC 8058 one-click unsubscribe and label+archive fallback.

**Authentication Required:** Yes

**Request Body:**
```json
{
  "items": [
    {
      "id": "msg123",
      "action": "one_click_unsub"
    },
    {
      "id": "msg124",
      "action": "label_archive"
    }
  ],
  "create_auto_archive_filter": true
}
```

**Response:**
```json
{
  "success": true,
  "operation_id": "550e8400-e29b-41d4-a716-446655440000",
  "summary": {
    "processed": 2,
    "successful": 2,
    "failed": 0,
    "filters_created": 2
  }
}
```

### POST /api/unsubscribe/undo

Undo a previous unsubscribe operation. Reverts label changes and deletes created filters. Note: RFC 8058 one-click unsubscribes cannot be undone.

**Authentication Required:** Yes

**Request Body:**
```json
{
  "operation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "success": true,
  "summary": {
    "reverted": 1,
    "filters_deleted": 2
  },
  "warning": "1 one-click unsubscribes cannot be undone"
}
```

### DELETE /api/user/data

Delete all app-stored data for the authenticated user. This includes statistics, activities, operations history, and domain data. Note: This does NOT delete any Gmail content, only data stored by the application.

**Authentication Required:** Yes

**Response:**
```json
{
  "success": true,
  "message": "All user data has been deleted"
}
```

## Error Handling

All API endpoints return appropriate HTTP status codes:

- 200: Success
- 400: Bad Request (invalid parameters)
- 401: Unauthorized (authentication required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 500: Internal Server Error

Error responses include a JSON object with an error message:

```json
{
  "error": "Authentication required"
}
```

## Rate Limiting

The API implements basic rate limiting to prevent abuse:

- Authentication endpoints: 10 requests per minute
- Data endpoints: 60 requests per minute
- Process endpoints: 10 requests per minute

## CORS

The API supports Cross-Origin Resource Sharing (CORS) for the frontend domain. Make sure to update the CORS configuration in the backend when deploying to production.

## Websockets

The current version of the API uses polling for real-time updates. Future versions may implement websockets for more efficient real-time communication.
