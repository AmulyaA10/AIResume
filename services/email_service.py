import smtplib
from email.message import EmailMessage
import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_PROJECT_ROOT / "backend" / ".env")
load_dotenv(_PROJECT_ROOT / "backend" / "env") # fallback just in case depending on how you named it


def _smtp_config() -> dict:
    return {
        "server": os.getenv("SMTP_SERVER", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "sender": os.getenv("SMTP_SENDER", os.getenv("SMTP_USERNAME", "")),
    }


def _send(msg: EmailMessage) -> bool:
    cfg = _smtp_config()
    if not cfg["server"] or not cfg["user"] or not cfg["password"]:
        print("DEBUG: [email_service] SMTP not configured — skipping.")
        return False
    try:
        with smtplib.SMTP(cfg["server"], cfg["port"]) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        print(f"DEBUG: [email_service] Sent to {msg['To']}")
        return True
    except Exception as e:
        print(f"DEBUG: [email_service] Failed to send to {msg['To']}: {e}")
        return False


def send_candidate_shortlisted(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    employer_name: str,
    reason: str = "",
) -> bool:
    """Notify a candidate they were automatically shortlisted for a job."""
    cfg = _smtp_config()
    msg = EmailMessage()
    msg['Subject'] = f"You've been shortlisted — {job_title}"
    msg['From'] = cfg["sender"]
    msg['To'] = candidate_email
    display = candidate_name or "there"
    body_text = (
        f"Hi {display},\n\n"
        f"Great news! Our AI recruitment agent has reviewed your resume and shortlisted you "
        f"for the {job_title} position{' at ' + employer_name if employer_name else ''}.\n\n"
        f"{reason + chr(10) + chr(10) if reason else ''}"
        f"A recruiter will be in touch shortly to discuss next steps.\n\n"
        f"Best regards,\nThe Recruitment Team"
    )
    html = f"""
    <html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6">
      <div style="max-width:560px;margin:0 auto;padding:32px 24px">
        <h2 style="color:#7c3aed">You've been shortlisted!</h2>
        <p>Hi <strong>{display}</strong>,</p>
        <p>Our AI recruitment agent reviewed your resume and shortlisted you for
           <strong>{job_title}</strong>{' at <strong>' + employer_name + '</strong>' if employer_name else ''}.</p>
        {'<blockquote style="border-left:3px solid #7c3aed;margin:16px 0;padding:8px 16px;color:#475569">' + reason + '</blockquote>' if reason else ''}
        <p>A recruiter will be in touch shortly to discuss next steps.</p>
        <p style="margin-top:32px;color:#64748b;font-size:13px">This notification was sent automatically by the AI Recruitment Agent.</p>
      </div>
    </body></html>"""
    msg.set_content(body_text)
    msg.add_alternative(html, subtype='html')
    return _send(msg)


def send_candidate_decision(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    employer_name: str,
    selected: bool,
    score: int = 0,
    reason: str = "",
) -> bool:
    """Notify a candidate of an automatic select/reject decision after they applied."""
    cfg = _smtp_config()
    msg = EmailMessage()
    display = candidate_name or "there"
    if selected:
        subject = f"Congratulations — {job_title}"
        headline = "You've been selected!"
        color = "#059669"
        intro = (
            f"We're pleased to inform you that your application for <strong>{job_title}</strong>"
            f"{' at <strong>' + employer_name + '</strong>' if employer_name else ''} has been <strong>accepted</strong>."
        )
    else:
        subject = f"Application Update — {job_title}"
        headline = "Application Status Update"
        color = "#dc2626"
        intro = (
            f"Thank you for applying to <strong>{job_title}</strong>"
            f"{' at <strong>' + employer_name + '</strong>' if employer_name else ''}. "
            f"After reviewing your application, we will not be moving forward at this time."
        )
    msg['Subject'] = subject
    msg['From'] = cfg["sender"]
    msg['To'] = candidate_email
    body_text = (
        f"Hi {display},\n\n"
        + ("Congratulations! " if selected else "Thank you for your application. ")
        + f"Your application for {job_title} has been {'accepted' if selected else 'reviewed'}.\n\n"
        + (f"AI Match Score: {score}%\n\n" if score else "")
        + (reason + "\n\n" if reason else "")
        + ("A recruiter will reach out shortly with next steps.\n\n" if selected else
           "We encourage you to apply for future openings.\n\n")
        + "Best regards,\nThe Recruitment Team"
    )
    html = f"""
    <html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6">
      <div style="max-width:560px;margin:0 auto;padding:32px 24px">
        <h2 style="color:{color}">{headline}</h2>
        <p>Hi <strong>{display}</strong>,</p>
        <p>{intro}</p>
        {'<p style="font-size:15px">AI Match Score: <strong>' + str(score) + '%</strong></p>' if score else ''}
        {'<blockquote style="border-left:3px solid ' + color + ';margin:16px 0;padding:8px 16px;color:#475569">' + reason + '</blockquote>' if reason else ''}
        <p>{'A recruiter will reach out shortly with next steps.' if selected else 'We encourage you to apply for future openings that match your profile.'}</p>
        <p style="margin-top:32px;color:#64748b;font-size:13px">This notification was sent automatically by the AI Recruitment Agent.</p>
      </div>
    </body></html>"""
    msg.set_content(body_text)
    msg.add_alternative(html, subtype='html')
    return _send(msg)


def send_employer_notification(employer_email: str, job_title: str, user_id: str, resume_filename: str, resume_content: str):
    cfg = _smtp_config()
    msg = EmailMessage()
    msg['Subject'] = f"New Application: {job_title}"
    msg['From'] = cfg["sender"]
    msg['To'] = employer_email

    html_content = f"""
    <html>
        <body>
            <h2>New Job Application Received</h2>
            <p><strong>Job Title:</strong> {job_title}</p>
            <p><strong>Candidate Details:</strong> You have a new candidate (User ID: {user_id}) applying for this position.</p>
            <p><strong>Resume File Name:</strong> {resume_filename}</p>
            <hr />
            <h3>Candidate Resume Details</h3>
            <pre style="white-space: pre-wrap; font-family: sans-serif; background-color: #f9f9f9; padding: 10px; border-radius: 5px;">{resume_content}</pre>
            <hr />
            <p><small>This email was automatically generated by the AIResume Application.</small></p>
        </body>
    </html>
    """
    
    msg.set_content(f"New application received for {job_title}. Please view this email in an HTML compatible client.")
    msg.add_alternative(html_content, subtype='html')

    return _send(msg)
