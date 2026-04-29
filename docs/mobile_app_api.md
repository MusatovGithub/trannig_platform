# Mobile app API

This project is currently a Django web application with server-rendered pages
and several JSON endpoints used by the browser UI. The first mobile-friendly
API layer lives under `/api/v1/`.

## Initial endpoints

- `GET /api/v1/auth/csrf/` - set CSRF cookie for session login.
- `POST /api/v1/auth/login/` - login with JSON body:
  `{"username": "...", "password": "...", "device_name": "iPhone"}`. Returns
  both the user and a Bearer token.
- `POST /api/v1/auth/logout/` - logout current session or revoke the current
  Bearer token.
- `GET /api/v1/me/` - current authenticated user.
- `GET /api/v1/client/dashboard/` - mobile home data for an athlete/client:
  trainings, subscriptions, group ratings, team, news and distances.
- `GET /api/v1/coach/dashboard/` - mobile home data for staff: CRM summary and
  recent competition results.
- `GET /api/v1/coach/classes/?date=YYYY-MM-DD` - classes for a coach/admin day
  with athletes and their grade/absence cells.
- `POST /api/v1/coach/attendance/<id>/mark/` - set a grade or absence status.
  Body: `{"status": "attended_5", "comment": "..."}`. Supported statuses:
  `attended_2`, `attended_3`, `attended_4`, `attended_5`, `attended_10`,
  `not_attended`, `none`.
- `GET /api/v1/customers/?search=&limit=50` - customers for the current user's
  company.
- `GET /api/v1/sport-categories/` - sport ranks/categories.
- `GET /api/v1/competitions/?limit=50` - competitions for the current user's
  company.
- `GET /api/v1/competitions/<id>/` - competition details and participants.
- `GET /api/v1/competitions/<id>/results/` - competition results.
- `POST /api/v1/competitions/<id>/participants/` - add participants to a
  competition. Body: `{"customer_ids": [1, 2]}`.
- `POST /api/v1/competitions/<id>/results/create/` - create a competition
  result.
- `GET /api/v1/results/<id>/` - get one result.
- `PUT /api/v1/results/<id>/` - update one result.
- `DELETE /api/v1/results/<id>/` - delete one result.

## Result body

```json
{
  "customer_id": 1,
  "discipline": "Комплекс",
  "distance": 100,
  "style": "25m",
  "result_time": "01:15:380",
  "place": 1,
  "assign_rank": 4,
  "is_disqualified": false,
  "disqualification_comment": ""
}
```

## Authentication

The API supports the existing Django session authentication for browser-like
clients and Bearer tokens for mobile clients. iPhone clients should call
`POST /api/v1/auth/login/`, store the returned token securely, then send it as:

```text
Authorization: Bearer <token>
```

Session clients should request `GET /api/v1/auth/csrf/` first, then send the
CSRF token with write requests. Mobile write endpoints require Bearer tokens.
Unauthenticated API requests return HTTP 401 with a JSON body instead of
redirecting to an HTML login page.

## Next mobile priorities

1. Add API login/logout/current session refresh.
2. Add write endpoints for adding competition participants.
3. Add write endpoints for creating/updating/deleting competition results.
4. Add LENEX `.lxf` import/export endpoints for Entry Editor workflows.
5. Add automated tests for API permissions and competition data contracts.
