"""
Seed Script for Initial Operational FAQs in PostgreSQL
Paradox Sports OMS - Phase 13
"""

import os
import sys
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.faq import FAQ, FAQStatus
from app.models.user import User

DEFAULT_FAQS = [
    {
        "question": "How do I submit my Daily Work Report?",
        "category": "Daily Operations",
        "answer": "Navigate to 'Work Reports' from the sidebar. Click 'Submit Daily Report'. Your author identity, role, vertical, and today's date are locked and automatically derived from your authenticated session. Select any active tasks you worked on today, describe your progress, list any blockers, and click 'Submit Report'.",
        "related_route": "/reports",
        "route_label": "Go to Work Reports",
        "display_order": 1,
    },
    {
        "question": "How do I update my operational profile or contact details?",
        "category": "Account & Identity",
        "answer": "Click your profile icon in the header or visit 'Profile'. Click 'Edit Profile' to update your contact phone number, operational specialization, duties, certifications, and availability status. Click 'Change Password' to update your security credentials.",
        "related_route": "/profile",
        "route_label": "Go to Profile",
        "display_order": 2,
    },
    {
        "question": "How do I acknowledge an Operational Directive?",
        "category": "Governance & Compliance",
        "answer": "Operational Directives issued by executive leadership appear in the 'Directives' workspace and on your Workspace Home overview. Open 'Directives', inspect the binding instructions, and click 'Acknowledge' to record your compliance timestamp.",
        "related_route": "/directives",
        "route_label": "Go to Directives",
        "display_order": 3,
    },
    {
        "question": "How are Master Tasks assigned and transitioned?",
        "category": "Work Management",
        "answer": "Tasks are created in 'Master Tasks' within your vertical division. Coordinators and Supervisors assign tasks to operators. Once assigned, tasks automatically appear in your 'My Work' projection. You can transition a task from OPEN to IN_PROGRESS, BLOCKED, or COMPLETED as deliverables are completed.",
        "related_route": "/my-work",
        "route_label": "Go to My Work",
        "display_order": 4,
    },
    {
        "question": "How do I raise an Issue or Blocker?",
        "category": "Risk & Escalation",
        "answer": "Navigate to 'Issues & Escalations' and click 'Report Issue'. Provide a title, description, priority, and sensitivity level (PUBLIC, INTERNAL, or CONFIDENTIAL). If a critical blocker arises on a matchday or tournament, use the 'Escalate' action to notify leadership immediately.",
        "related_route": "/issues",
        "route_label": "Go to Issues",
        "display_order": 5,
    },
    {
        "question": "How do I request resources from another division?",
        "category": "Events & Operations",
        "answer": "Use the 'Requirements' workspace to raise cross-vertical operational requests (e.g. equipment setups, medical staffing, pitch preparation). Specify your requesting division, the target division, priority, and deadline. Both divisions can communicate via the interactive message stream.",
        "related_route": "/requirements",
        "route_label": "Go to Requirements",
        "display_order": 6,
    },
    {
        "question": "How do I RSVP and convert Meeting action items to tasks?",
        "category": "Coordination",
        "answer": "In the 'Meetings' workspace, open any scheduled meeting to submit your RSVP (Accept, Tentative, Decline). Supervisors and organizers can log action items during or after the meeting and click 'Convert to Task' with 1 click to create an authoritative Master Task.",
        "related_route": "/meetings",
        "route_label": "Go to Meetings",
        "display_order": 7,
    },
]


def seed_faqs():
    print("Creating tables if not present...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin_user = db.scalar(select(User).limit(1))
        actor_id = admin_user.id if admin_user else None

        for item in DEFAULT_FAQS:
            existing = db.scalar(select(FAQ).where(FAQ.question == item["question"]))
            if not existing:
                faq = FAQ(
                    question=item["question"],
                    answer=item["answer"],
                    category=item["category"],
                    display_order=item["display_order"],
                    status=FAQStatus.PUBLISHED,
                    target_audience="ALL",
                    related_route=item.get("related_route"),
                    route_label=item.get("route_label"),
                    created_by_id=actor_id,
                    updated_by_id=actor_id,
                )
                db.add(faq)
                print(f"  + Seeded FAQ: {faq.question[:35]}...")
            else:
                print(f"  ~ Existing FAQ: {existing.question[:35]}...")
        db.commit()
        print("FAQ seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_faqs()
