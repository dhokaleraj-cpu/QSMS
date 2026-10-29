"""R33 · About STAWN QCMS: product, developer, copyright and licence text (same wording as the Android app)."""
from __future__ import annotations

PRODUCT = "STAWN QCMS"
TAGLINE = "Quality Control Monitoring System"
COMPANY = "STAWN PRECISION PRIVATE LIMITED"
EMAIL = "business@stawnprecision.com"
ANDROID_VERSION = "3.7.0"
IOS_VERSION = "1.3.0"
COPYRIGHT = f"© 2026 {COMPANY}. All rights reserved."
DEVELOPER = (
    ("Developed by", COMPANY),
    ("Location", "Thane, Maharashtra, India"),
    ("Product", f"{PRODUCT} – {TAGLINE}"),
    ("Platforms", "Web application · Android app · iPhone and iPad app"),
    ("Licensing", "Company licence with online key validation and licensed user seats"),
    ("Contact", EMAIL),
)
LICENSEE = (
    ("Licensed user", "Four Star Industries Pvt. Ltd."),
    ("Use", "Internal quality, supply chain and traceability records"),
)
NOTICE = (
    f"STAWN QCMS, the STAWN name and logo, the software, its source code, screen designs, report and print layouts, "
    f"database design and documentation are the intellectual property of {COMPANY} and are protected by the "
    "Copyright Act, 1957 (India) and international copyright laws.",
    f"The software is licensed, not sold. Copying, modifying, reverse engineering, redistributing, sub-licensing or reselling "
    f"the software or any part of it without the prior written permission of {COMPANY} is prohibited.",
    "All business data entered in QCMS (parts, orders, inspection results, reports and documents) belongs to the licensed user.",
    "Other product and company names shown in the records belong to their respective owners.",
)
SECURITY = (
    "Data is stored in the licensed user's own Supabase database with row-level security for every company (tenant).",
    "Passwords are never stored on the phone; the session key is kept in the Android Keystore and the app locks after 15 minutes in the background.",
    "Personal e-mail credentials are visible only to their own user – not to other users or administrators.",
    "Every create, change and deletion is recorded in the record history and user activity log.",
)
SUPPORT = f"For licences, new features, training or support contact {COMPANY} at {EMAIL}."
