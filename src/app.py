"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import logging
import os
import secrets
import time
from pathlib import Path

import teacher_auth

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

logger = logging.getLogger(__name__)
sessions = {}
SESSION_SECONDS = 8 * 60 * 60


class Login(BaseModel):
    username: str
    password: str


def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="Invalid request origin")


def require_teacher(request: Request):
    check_origin(request)
    token = request.cookies.get("teacher_session")
    session = sessions.get(token)
    if not session or session[1] <= time.time():
        if token:
            sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Teacher login required")
    return session[0]


@app.post("/auth/login")
def login(credentials: Login, request: Request, response: Response):
    check_origin(request)
    try:
        valid = teacher_auth.authenticate(credentials.username, credentials.password)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.exception("Unable to read teacher credentials")
        raise HTTPException(status_code=503, detail="Teacher login is not configured correctly") from exc
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    old_token = request.cookies.get("teacher_session")
    if old_token:
        sessions.pop(old_token, None)
    now = time.time()
    for token, (_, expiry) in list(sessions.items()):
        if expiry <= now:
            sessions.pop(token, None)
    token = secrets.token_urlsafe(32)
    sessions[token] = (credentials.username, now + SESSION_SECONDS)
    response.set_cookie(
        "teacher_session", token, max_age=SESSION_SECONDS, httponly=True,
        samesite="strict", secure=request.url.scheme == "https",
    )
    return {"username": credentials.username}


@app.get("/auth/session")
def get_session(username: str = Depends(require_teacher)):
    return {"username": username}


@app.post("/auth/logout")
def logout(request: Request, response: Response, username: str = Depends(require_teacher)):
    sessions.pop(request.cookies.get("teacher_session"), None)
    response.delete_cookie("teacher_session")
    return {"message": "Logged out"}


# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, username: str = Depends(require_teacher)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, username: str = Depends(require_teacher)):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
