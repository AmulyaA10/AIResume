from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
import urllib.parse

from app.models import LoginRequest
from app.config import FRONTEND_URL, BACKEND_URL, get_oauth_creds
from services.db.lancedb_client import get_or_create_table

router = APIRouter()


@router.post("/login")
async def login(request: LoginRequest):
    # Mock authentication
    if request.username == "recruit" and request.password == "admin123":
        return {"success": True, "token": "mock-recruiter-token-123", "user": {"name": "Senior Recruiter", "id": "user_recruiter_456"}}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/google")
async def auth_google():
    creds = get_oauth_creds()
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={creds['google_client_id']}&redirect_uri={BACKEND_URL}/api/auth/google/callback&scope=openid%20email%20profile"
    )


@router.get("/google/callback")
async def auth_google_callback(code: str):
    import requests as req
    creds = get_oauth_creds()
    display_name = "Google User"
    email = "user@example.com"

    if creds["google_client_id"] != "placeholder_id" and creds["google_client_secret"] != "placeholder_secret":
        try:
            token_res = req.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{BACKEND_URL}/api/auth/google/callback",
                "client_id": creds["google_client_id"],
                "client_secret": creds["google_client_secret"],
            })
            token_data = token_res.json()
            if "access_token" in token_data:
                userinfo_res = req.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {token_data['access_token']}"}
                )
                if userinfo_res.status_code == 200:
                    user_data = userinfo_res.json()
                    display_name = user_data.get("name", display_name)
                    email = user_data.get("email", email)
        except Exception as e:
            print(f"--- Google Auth Exception: {e} ---")

    encoded_name = urllib.parse.quote(display_name)
    encoded_email = urllib.parse.quote(email)
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?token=mock-google-token&name={encoded_name}&email={encoded_email}")


@router.get("/linkedin")
async def auth_linkedin():
    creds = get_oauth_creds()
    print("--- [Auth] Redirecting to LinkedIn OAuth ---")
    return RedirectResponse(
        url=f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={creds['linkedin_client_id']}&redirect_uri={BACKEND_URL}/api/auth/linkedin/callback&scope=openid%20profile%20email"
    )


@router.get("/linkedin/callback")
async def auth_linkedin_callback(code: str, background_tasks: BackgroundTasks):
    import requests
    creds = get_oauth_creds()

    user_id = "user_alex_chen_123"  # LinkedIn OAuth users are jobseekers
    profile_data = None
    real_profile_url = None
    display_name = "LinkedIn User"
    email = "user@example.com"
    auth_debug_msg = ""

    # 1. Attempt Real Token Exchange if secrets are present
    if creds["linkedin_client_id"] != "placeholder_id" and creds["linkedin_client_secret"] != "placeholder_secret":
        try:
            print("--- Attempting Real LinkedIn Token Exchange ---")
            token_url = "https://www.linkedin.com/oauth/v2/accessToken"
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{BACKEND_URL}/api/auth/linkedin/callback",
                "client_id": creds["linkedin_client_id"],
                "client_secret": creds["linkedin_client_secret"]
            }
            token_res = requests.post(token_url, data=payload)
            token_data = token_res.json()

            if "access_token" in token_data:
                access_token = token_data["access_token"]
                headers = {"Authorization": f"Bearer {access_token}"}

                # A. Try OIDC UserInfo (Standard)
                try:
                    userinfo_res = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
                    if userinfo_res.status_code == 200:
                        user_data = userinfo_res.json()
                        first_name = user_data.get("given_name", "")
                        last_name = user_data.get("family_name", "")
                        email = user_data.get("email", "")
                        display_name = user_data.get("name", f"{first_name} {last_name}")
                        picture = user_data.get("picture", "")

                        def sanitize_slug(name):
                            import re
                            s = name.lower()
                            s = re.sub(r'[^a-z0-9]', '-', s)
                            s = re.sub(r'-+', '-', s)
                            return s.strip('-')

                        real_profile_url = f"https://www.linkedin.com/in/{sanitize_slug(display_name)}" if first_name else None

                        profile_data = f"Name: {display_name}\nEmail: {email}\nProfile URL: {real_profile_url or 'N/A'}\nAvatar: {picture}\nSource: LinkedIn OIDC"
                        print(f"--- Real LinkedIn Auth Success (OIDC) for {display_name} ---")
                    else:
                        auth_debug_msg += f"OIDC Failed ({userinfo_res.status_code}); "
                        raise Exception("OIDC endpoint failed")
                except Exception as oidce:
                    # B. Fallback to Legacy API (v2/me)
                    print(f"--- OIDC Failed, trying Legacy v2/me: {oidce} ---")
                    try:
                        me_res = requests.get("https://api.linkedin.com/v2/me", headers=headers)
                        if me_res.status_code == 200:
                            me_data = me_res.json()
                            first_name = me_data.get("localizedFirstName", "LinkedIn User")
                            last_name = me_data.get("localizedLastName", "")
                            profile_id = me_data.get("id", "unknown")
                            display_name = f"{first_name} {last_name}"

                            email_res = requests.get("https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))", headers=headers)
                            email = "private@linkedin.com"
                            if email_res.status_code == 200:
                                email_data = email_res.json()
                                try:
                                    email = email_data["elements"][0]["handle~"]["emailAddress"]
                                except:
                                    pass

                            real_profile_url = f"https://www.linkedin.com/in/{profile_id}"
                            profile_data = f"Name: {display_name}\nLinkedIn ID: {profile_id}\nEmail: {email}\nSource: LinkedIn Legacy v2"
                            print(f"--- Real LinkedIn Auth Success (Legacy) for {display_name} ---")
                        else:
                            auth_debug_msg += f"Legacy Failed ({me_res.status_code}: {me_res.text}); "
                            print(f"--- Legacy Auth Failed: {me_res.text} ---")
                    except Exception as legacy_e:
                        auth_debug_msg += f"Legacy Error ({str(legacy_e)}); "
                        print(f"--- Legacy Auth Exception: {legacy_e} ---")

            else:
                auth_debug_msg += f"Token Exchange Failed ({str(token_data)}); "
                print(f"--- Real LinkedIn Token Exchange Failed: {token_data} ---")
        except Exception as e:
            auth_debug_msg += f"Auth Exception ({str(e)}); "
            print(f"--- Real LinkedIn Auth Exception: {e} ---")
    else:
        auth_debug_msg += "Missing Client ID/Secret; "

    # 2. Fallback to Mock Data if Real Auth failed
    if not profile_data:
        print("--- Using Mock LinkedIn Profile Data ---")
        real_profile_url = "https://www.linkedin.com/in/alex-chen-demo"
        display_name = "LinkedIn User"
        email = "user@example.com"
        profile_data = """
        Name: LinkedIn User
        Role: Senior Technical Recruiter
        Summary: Experienced recruiter with a passion for AI and automation.
        """

    # NUCLEAR WIPE: Delete any old LinkedIn profiles for this user to force a fresh sync
    print(f"--- [Wipe] Clearing stale LinkedIn records for {user_id} ---")
    try:
        table = get_or_create_table()
        table.delete(f"user_id = '{user_id}' AND filename = 'LinkedIn_Profile.pdf'")
    except Exception as e:
        print(f"DEBUG: Wipe failed (might be first time): {e}")

    print(f"--- Processed LinkedIn OAuth for {user_id} ---")

    # Redirect with results AND debug info
    final_profile_url = real_profile_url if real_profile_url else ""
    redirect_url = f"{FRONTEND_URL}/auth/callback?token=mock-linkedin-token&name={display_name}&email={email}&linkedin_connected=true&profile_url={final_profile_url}"
    if auth_debug_msg:
        redirect_url += f"&auth_error={urllib.parse.quote(auth_debug_msg)}"

    return RedirectResponse(url=redirect_url)
