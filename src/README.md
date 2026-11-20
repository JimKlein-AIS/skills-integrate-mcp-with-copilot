# Mergington High School Activities API

A simple FastAPI application for viewing extracurricular activities and managing registrations.

## Features

- View all available extracurricular activities
- Teachers can sign in to register and unregister students.
- Students can view activities and their participants without logging in.

## Getting Started

1. Install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Create a teacher account. The password is prompted for interactively and stored
   as a salted hash in `src/teachers.json`, which is ignored by Git. Repeat this
   command to add a teacher or replace an existing teacher's password.

   ```
   python src/teacher_auth.py USERNAME
   ```

3. Run the application from the repository root:

   ```
   uvicorn app:app --app-dir src --reload
   ```

4. Open your browser and go to:
   - Application: http://localhost:8000/
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

Keep `teachers.json` private and back it up separately. Login is unavailable until
the file exists. Teacher sessions are stored in the server process, expire after
eight hours, and are cleared on restart; restart after changing credentials to
revoke existing sessions. Use HTTPS for deployments: the session cookie is marked
Secure on HTTPS requests. If using a reverse proxy, configure Uvicorn to trust
forwarded headers only from that proxy and preserve the original host and scheme.
Sessions are process-local, so run a single worker. This simple login has no
rate limiting; add appropriate protection before deploying it publicly.

Run the authentication tests from the repository root with
`python -m unittest discover -s tests`.

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Log in with a JSON username and password |
| GET    | `/auth/session`                                                   | Check the current teacher session |
| POST   | `/auth/logout`                                                    | End the current teacher session |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student (teacher only) |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher only) |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier.

All data is stored in memory, which means data will be reset when the server restarts.
