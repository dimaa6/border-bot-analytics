from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import redis
import secrets
from datetime import datetime
from collections import defaultdict

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

security = HTTPBasic()
_REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
_REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
r = redis.Redis(host=_REDIS_HOST, port=_REDIS_PORT, db=0, decode_responses=True)

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    correct_user = secrets.compare_digest(credentials.username, "admin")
    correct_pass = secrets.compare_digest(credentials.password, "change_this_password")
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic"},
        )
    return True

@app.get("/api/today")
def get_today_stats(auth: bool = Depends(authenticate)):
    """Fetches all metrics specifically recorded for today's date."""
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    
    return {
        "date": today_str,
        "main_menu": r.hgetall(f"analytics:daily:{today_str}:main_menu"),
        "countries": r.hgetall(f"analytics:crossing_countries:{today_str}"),
        "checkpoints": r.hgetall(f"analytics:checkpoints:{today_str}"),
        "directions": r.hgetall(f"analytics:direction:{today_str}"),
        "crossing_events": r.hgetall(f"analytics:crossing_events:{today_str}"),
        "funnel_crossing": r.hgetall(f"analytics:funnel:crossing:{today_str}"),
        "funnel_cancels": r.hgetall(f"analytics:funnel:cancels:{today_str}")
    }

@app.get("/api/all")
def get_all_categories(auth: bool = Depends(authenticate)):
    """Returns lifetime metrics categorized cleanly for the tab views."""
    return {
        "main_menu": r.hgetall("analytics:main_menu"),
        "crossing": {
            "countries": r.hgetall("analytics:crossing_countries"),
            "checkpoints": r.hgetall("analytics:checkpoints"),
            "directions": r.hgetall("analytics:direction"),
            "events": r.hgetall("analytics:crossing_events")
        },
        "route_planner": {
            "funnel": r.hgetall("analytics:funnel:plan_route"),
            "origins": r.hgetall("analytics:plan_route_origin"),
            "destinations": r.hgetall("analytics:plan_route_destination"),
            "countries": r.hgetall("analytics:plan_route_countries"),
            "directions": r.hgetall("analytics:plan_route_direction")
        },
        "funnels": {
            "crossing": r.hgetall("analytics:funnel:crossing"),
            "stats": r.hgetall("analytics:funnel:stats"),
            "cancels": r.hgetall("analytics:funnel:cancels"),
            "info": r.hgetall("analytics:info")
        }
    }

@app.get("/api/timeseries")
def get_timeseries(auth: bool = Depends(authenticate)):
    """Daily, Monthly, and Yearly aggregates for historical trends."""
    keys = r.keys("analytics:daily:*:main_menu")
    daily_data = defaultdict(lambda: defaultdict(int))
    monthly_data = defaultdict(lambda: defaultdict(int))
    yearly_data = defaultdict(lambda: defaultdict(int))

    for key in keys:
        date_str = key.split(":")[2]
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
            
        month_str = dt.strftime("%Y-%m")
        year_str = dt.strftime("%Y")
        
        counts = r.hgetall(key)
        for action, val in counts.items():
            val_int = int(val)
            daily_data[date_str][action] += val_int
            monthly_data[month_str][action] += val_int
            yearly_data[year_str][action] += val_int

    return {
        "daily": dict(sorted(daily_data.items())),
        "monthly": dict(sorted(monthly_data.items())),
        "yearly": dict(sorted(yearly_data.items()))
    }

@app.get("/", response_class=HTMLResponse)
def root(auth: bool = Depends(authenticate)):
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()
