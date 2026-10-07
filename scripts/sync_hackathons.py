import os
import json
import requests
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase using your GitHub secret
service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
cred = credentials.Certificate(service_account_info)
firebase_admin.initialize_app(cred)
db = firestore.client()

# High-tier / Trusted organizer keywords
TRUSTED_KEYWORDS = [
    "smart india hackathon", "sih", "adobe", "flipkart", 
    "microsoft", "imagine cup", "google", "amazon", 
    "mlh", "nasscom", "infosys", "hackwithinfy"
]

def run_sync():
    print("Fetching active hackathons...")
    
    events = []
    try:
        res = requests.get("https://mlh.io/api/v2/events.json", timeout=15)
        if res.status_code == 200:
            events = res.json()
    except Exception as e:
        print(f"Feed fetch notice: {e}")

    # Flagship National & Global Hackathons
    flagship_hackathons = [
        {
            "title": "Smart India Hackathon 2026",
            "organizer": "Govt of India / AICTE",
            "deadline": "2026-11-04",
            "mode": "National",
            "prize_pool": "₹1,00,000 / Problem",
            "tags": "GovTech / Hardware / AI",
            "is_tier1": True,
            "url": "https://sih.gov.in"
        },
        {
            "title": "Microsoft Imagine Cup 2026",
            "organizer": "Microsoft",
            "deadline": "2026-10-18",
            "mode": "INT",
            "prize_pool": "$100,000 USD",
            "tags": "AI & Azure",
            "is_tier1": True,
            "url": "https://imaginecup.microsoft.com"
        },
        {
            "title": "Adobe GenSolve Hackathon",
            "organizer": "Adobe",
            "deadline": "2026-11-15",
            "mode": "Online",
            "prize_pool": "₹3,00,000 + PPI",
            "tags": "Generative AI & CV",
            "is_tier1": True,
            "url": "https://adobe.com"
        },
        {
            "title": "Flipkart GRiD 7.0",
            "organizer": "Flipkart",
            "deadline": "2026-10-25",
            "mode": "Online",
            "prize_pool": "₹5,00,000",
            "tags": "Robotics & E-Com",
            "is_tier1": True,
            "url": "https://unstop.com"
        }
    ]

    all_hackathons = flagship_hackathons.copy()
    for e in events:
        title = e.get("title", "")
        all_hackathons.append({
            "title": title,
            "organizer": "MLH Partner",
            "deadline": e.get("end_date", ""),
            "mode": "Online" if e.get("is_digital", True) else "Offline",
            "prize_pool": "Swag & Grants",
            "tags": "Open Source",
            "is_tier1": any(k in title.lower() for k in TRUSTED_KEYWORDS),
            "url": e.get("url", "")
        })

    # Save to Firestore 'hackathons' collection
    for h in all_hackathons:
        doc_id = "".join(filter(str.isalnum, h["title"].lower()))[:30]
        db.collection("hackathons").document(doc_id).set({
            **h,
            "last_updated": firestore.SERVER_TIMESTAMP
        }, merge=True)

    # Check for deadlines within 12 days to generate teacher reminders
    now = datetime.now(timezone.utc)
    for h in all_hackathons:
        try:
            deadline_date = datetime.strptime(h["deadline"][:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_left = (deadline_date - now).days

            if 0 <= days_left <= 12 and h["is_tier1"]:
                doc_id = "".join(filter(str.isalnum, h["title"].lower()))[:30]
                reminder_text = (
                    f"📢 *URGENT HACKATHON REMINDER — CSE DEPT*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 *{h['title']}* ({h['organizer']})\n"
                    f"⏳ *Registration Closes in {days_left} Days!*\n"
                    f"💰 Prize: {h['prize_pool']} | Mode: {h['mode']}\n"
                    f"👉 Apply: {h['url']}\n"
                    f"📌 Mentor Action: Check student draft applications in HackFi."
                )

                db.collection("staff_alerts").document(f"{doc_id}_alert").set({
                    "hackathon_title": h["title"],
                    "days_left": days_left,
                    "deadline": h["deadline"],
                    "formatted_message": reminder_text,
                    "target_group": "CSE (2nd & 3rd Yr)",
                    "updated_at": firestore.SERVER_TIMESTAMP
                }, merge=True)
        except Exception:
            continue

    print("Synced hackathons and teacher alerts to Firestore successfully!")

if __name__ == "__main__":
    run_sync()
