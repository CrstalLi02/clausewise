"""Seed demo data: merge departments, migrate misfiled documents, and create mock documents / pending review orders / badcases / initial Skills per department.

Usage: python -m scripts.seed_demo_data

What it does:
1. Merges the "Logistics Office" and the "Logistics and Security Department" into one department (keeping dept_hqaq).
2. Moves files misfiled under Academic Affairs (dept_jwc) to the Logistics and Security Department (dept_hqaq).
3. Generates 3 mock documents per department, in active / review / draft states, and ingests them.
4. Generates 1 pending review order per department (the starting point of the human review Loop).
5. Generates several badcases per department (feedback + traces); the rubric rules reflected from them are written into the department's initial Skill.
6. Generates 1 initial Skill per department based on its unique rules (with unique_rules + rubric_rules).

Idempotent: re-running skips data that already exists.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.deps import build_container


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Department merge mapping: from_dept -> to_dept (idempotent; once the merged department is deleted, this migration has no side effects)
# Note: Academic Affairs (dept_jwc) is no longer migrated wholesale — its regular academic documents must stay there;
#       the misfiled files such as "rainstorm weather" were cleaned up once and no longer take part in automatic migration, to avoid collateral damage.
MIGRATE_MAP = {
    "dept_hqc": "dept_hqaq",  # Logistics Office merged into the Logistics and Security Department
}
DELETE_DEPTS = ["dept_hqc"]


# =====================================================================
# Mock data per department: skill / docs / badcases / review_qa
# =====================================================================
DEPT_DATA: list[dict[str, Any]] = [
    {
        "dept_id": "dept_jwc",
        "skill": {
            "name": "Course Registration, Withdrawal, and Student Status Inquiries",
            "keywords": ["course registration", "withdraw", "refund", "student status", "credit", "leave of absence", "change major", "minor"],
            "unique_rules": [
                "Academic Affairs policies follow the week numbers of the semester calendar: the course withdrawal deadline is week 8, and refunds are proportional to the remaining teaching weeks",
                "Answers must cite specific article numbers and be checked against the current semester calendar",
            ],
        },
        "docs": [
            {
                "title": "Undergraduate Course Registration Regulations",
                "status": "active",
                "content": "# Undergraduate Course Registration Regulations\n\n## Chapter 1 General Provisions\n\nArticle 1 These regulations are formulated to standardize undergraduate course registration and safeguard the teaching order.\n\nArticle 2 Students shall complete course registration for the next semester through the academic affairs system during weeks 16 to 18 of each semester.\n\n## Chapter 2 Withdrawal and Course Changes\n\nArticle 3 Students may apply to withdraw from a course during weeks 1 to 8 after the semester begins; late applications will not be accepted.\n\nArticle 4 After withdrawal, tuition is refunded in proportion to the remaining teaching weeks; the exact proportion is determined by the Finance Office.",
            },
            {
                "title": "Implementation Rules for Undergraduate Course Withdrawal and Refunds",
                "status": "review",
                "content": "# Implementation Rules for Undergraduate Course Withdrawal and Refunds\n\nArticle 1 Withdrawal is based on the submission time in the academic affairs system and takes effect immediately upon approval.\n\nArticle 2 For withdrawals in weeks 1 to 4 the refund rate is 100%; weeks 5 to 6, 60%; weeks 7 to 8, 30%.\n\nArticle 3 Refunds are returned to the original payment method within 15 working days after the withdrawal is approved.",
            },
            {
                "title": "Procedures for Undergraduate Student Status Changes",
                "status": "draft",
                "content": "# Procedures for Undergraduate Student Status Changes\n\nArticle 1 A leave of absence must be requested by the student, signed by a parent, reviewed by the counselor, and then approved by Academic Affairs.\n\nArticle 2 Requests to resume studies must be submitted within two weeks before the semester begins, together with the relevant supporting documents.\n\nArticle 3 Requests to change majors are accepted once a year in the spring semester, and admission is merit-based according to the receiving school's assessment.",
            },
        ],
        "badcases": [
            {"query": "Up to which week can I withdraw from a course?", "bad_answer": "The withdrawal deadline is week 10.", "signal": "correction",
             "rule": "The course withdrawal deadline must be checked against the current semester calendar; the answer is week 8, not week 10"},
            {"query": "Can I get a tuition refund if I withdraw from a course?", "bad_answer": "No refunds.", "signal": "down",
             "rule": "Answers about course withdrawal must also state the refund rates (100%/60%/30% by remaining teaching weeks)"},
            {"query": "What is the course withdrawal deadline for graduate students?", "bad_answer": "The undergraduate deadline is week 8.", "signal": "correction",
             "rule": "Undergraduate and graduate rules must not be mixed; answer according to the Graduate School's articles"},
        ],
        "review_qa": [
            {"question": "What is the latest week undergraduates can withdraw from a course?", "expected": "Week 8 after the semester begins", "answer": "Students may apply to withdraw from a course during weeks 1 to 8 after the semester begins; late applications will not be accepted."},
            {"question": "How much tuition is refunded for a withdrawal in week 6?", "expected": "60%", "answer": "For withdrawals in weeks 5 to 6, the refund rate is 60%."},
            {"question": "When are requests to change majors accepted each year?", "expected": "Once a year in the spring semester", "answer": "Requests to change majors are accepted once a year in the spring semester, and admission is merit-based according to the receiving school's assessment."},
        ],
    },
    {
        "dept_id": "dept_xsc",
        "skill": {
            "name": "Scholarship, Financial Aid, Dormitory, and Leave Inquiries",
            "keywords": ["scholarship", "financial aid", "dormitory", "room change", "leave request", "disciplinary", "comprehensive evaluation", "work-study"],
            "unique_rules": [
                "Student Affairs handles scholarships, grants, loans, dormitories, leave, and discipline; application materials and deadlines follow Student Affairs notices",
                "Leave durations map to different approval levels (counselor / school / Student Affairs)",
            ],
        },
        "docs": [
            {
                "title": "Undergraduate Scholarship Evaluation Regulations",
                "status": "active",
                "content": "# Undergraduate Scholarship Evaluation Regulations\n\nArticle 1 Scholarships are evaluated based on a combined ranking of academic performance and the comprehensive quality evaluation.\n\nArticle 2 Application materials include a transcript, the comprehensive evaluation certificate, and copies of award certificates; all are required.\n\nArticle 3 Evaluation results are publicized for 5 working days and awarded if there are no objections.",
            },
            {
                "title": "Student Dormitory Management and Room Change Rules",
                "status": "review",
                "content": "# Student Dormitory Management and Room Change Rules\n\nArticle 1 Room changes require a written application reviewed by the counselor and the dormitory management center.\n\nArticle 2 Room change applications are processed together within two weeks after each semester begins.\n\nArticle 3 Violations such as unauthorized electricity use will result in a warning or more severe disciplinary action.",
            },
            {
                "title": "Student Leave and Attendance Management Rules",
                "status": "draft",
                "content": "# Student Leave and Attendance Management Rules\n\nArticle 1 Leave of 1 day is approved by the counselor, 2 to 7 days by the school, and more than 7 days by Student Affairs.\n\nArticle 2 Sick leave requires a hospital diagnosis certificate; personal leave requires a stated reason.\n\nArticle 3 Leaving campus without approval is treated as absence without leave.",
            },
        ],
        "badcases": [
            {"query": "What materials do I need to apply for a scholarship?", "bad_answer": "Just fill out a form.", "signal": "down",
             "rule": "Answers about scholarship applications must list the complete set of materials (transcript / comprehensive evaluation certificate / award certificates)"},
            {"query": "How do I change dormitory rooms?", "bad_answer": "Just move over.", "signal": "correction",
             "rule": "Answers about room changes must state the application channel (counselor + dormitory management center) and the processing window (two weeks after the semester begins)"},
            {"query": "Who approves a 5-day leave request?", "bad_answer": "The counselor can approve it.", "signal": "correction",
             "rule": "Leave durations map to approval levels; a 5-day leave must be approved by the school"},
        ],
        "review_qa": [
            {"question": "What is the main basis for scholarship evaluation?", "expected": "Academic performance and the comprehensive evaluation ranking", "answer": "Scholarships are evaluated based on a combined ranking of academic performance and the comprehensive quality evaluation."},
            {"question": "Who approves leave of 2 to 7 days?", "expected": "The school", "answer": "Leave of 1 day is approved by the counselor, 2 to 7 days by the school, and more than 7 days by Student Affairs."},
            {"question": "When are room change applications processed?", "expected": "Within two weeks after the semester begins", "answer": "Room change applications are processed together within two weeks after each semester begins."},
        ],
    },
    {
        "dept_id": "dept_cwc",
        "skill": {
            "name": "Payment, Refund, and Reimbursement Inquiries",
            "keywords": ["payment", "refund", "tuition", "reimbursement", "invoice", "fee standard", "receipt of funds"],
            "unique_rules": [
                "Fee amounts, refund rates, and reimbursement deadlines must follow Finance Office standards, with amounts accurate to the cent",
                "Reimbursement answers must state the required receipts, approval process, and deadline",
            ],
        },
        "docs": [
            {
                "title": "Student Fee Management Regulations",
                "status": "active",
                "content": "# Student Fee Management Regulations\n\nArticle 1 Tuition is charged per academic year, according to the standards published by the university.\n\nArticle 2 Students may pay through the unified payment platform or by bank direct debit.\n\nArticle 3 Overdue payments without an approved deferral are handled according to university regulations.",
            },
            {
                "title": "Expense Reimbursement and Receipt Management Rules",
                "status": "review",
                "content": "# Expense Reimbursement and Receipt Management Rules\n\nArticle 1 Reimbursement requires a lawful, compliant invoice made out to the full name of the institution.\n\nArticle 2 Reimbursement requests shall be submitted within 30 days after the matter is completed.\n\nArticle 3 Travel reimbursement requires an approval form and proof of the itinerary.",
            },
            {
                "title": "Student Refund Procedures",
                "status": "draft",
                "content": "# Student Refund Procedures\n\nArticle 1 After the relevant departments review a refund request, the Finance Office processes it centrally.\n\nArticle 2 Refunds are returned to the original payment method within 15 working days after approval.\n\nArticle 3 Refund progress can be checked in the finance system.",
            },
        ],
        "badcases": [
            {"query": "How much is tuition per year?", "bad_answer": "Probably over ten thousand.", "signal": "down",
             "rule": "Answers involving amounts must give specific figures and the supporting article; vague wording is not allowed"},
            {"query": "What kind of invoice do I need for reimbursement?", "bad_answer": "Any invoice will do.", "signal": "correction",
             "rule": "Reimbursement answers must state the lawful, compliant invoice requirement, the payee title requirement, and the 30-day deadline"},
            {"query": "How long does a refund take to arrive?", "bad_answer": "It arrives immediately.", "signal": "correction",
             "rule": "Refund answers must state that refunds are returned to the original payment method within 15 working days"},
        ],
        "review_qa": [
            {"question": "Within how long after the matter is completed must a reimbursement request be submitted?", "expected": "Within 30 days", "answer": "Reimbursement requests shall be submitted within 30 days after the matter is completed."},
            {"question": "How long does it take for refunds to be returned?", "expected": "Within 15 working days", "answer": "Refunds are returned to the original payment method within 15 working days after approval."},
            {"question": "How can tuition be paid?", "expected": "Unified payment platform or bank direct debit", "answer": "Students may pay through the unified payment platform or by bank direct debit."},
        ],
    },
    {
        "dept_id": "dept_rsc",
        "skill": {
            "name": "Professional Title Appointment and HR Procedure Inquiries",
            "keywords": ["professional title", "appointment", "talent recruitment", "contract", "attendance", "leave request", "social insurance", "onboarding", "resignation"],
            "unique_rules": [
                "Human Resources handles faculty and staff title appointments, onboarding and resignation, contracts, and social insurance; applicable articles depend on the employee's status",
                "Faculty and staff leave/attendance rules differ from student rules and must not be confused",
            ],
        },
        "docs": [
            {
                "title": "Faculty and Staff Professional Title Appointment Regulations",
                "status": "active",
                "content": "# Faculty and Staff Professional Title Appointment Regulations\n\nArticle 1 Professional title applications are graded as assistant, intermediate, associate senior, and full senior levels.\n\nArticle 2 Applicants must meet basic requirements for education, years of service, and performance.\n\nArticle 3 Appointment results are publicized after a vote by the review committee.",
            },
            {
                "title": "Faculty and Staff Onboarding and Resignation Procedures",
                "status": "review",
                "content": "# Faculty and Staff Onboarding and Resignation Procedures\n\nArticle 1 Onboarding requires proof of academic degrees, a medical examination report, and other materials.\n\nArticle 2 Resignation requires a written application submitted 30 days in advance and a work handover.\n\nArticle 3 Social insurance is transferred according to regulations after resignation.",
            },
            {
                "title": "Faculty and Staff Attendance and Leave Rules",
                "status": "draft",
                "content": "# Faculty and Staff Attendance and Leave Rules\n\nArticle 1 Faculty and staff leave must be approved by the head of their department.\n\nArticle 2 Sick leave requires a hospital certificate; personal leave requires a stated reason.\n\nArticle 3 Consecutive unexcused absences are handled according to the university's personnel policies.",
            },
        ],
        "badcases": [
            {"query": "What are the requirements for an associate senior title?", "bad_answer": "Just enough years of service.", "signal": "down",
             "rule": "Title appointment answers must distinguish application levels and list the education / years of service / performance requirements"},
            {"query": "How far in advance must I apply to resign?", "bad_answer": "You can leave anytime.", "signal": "correction",
             "rule": "Resignation answers must state the 30-day advance written application and the work handover"},
            {"query": "Who approves a 5-day leave for faculty?", "bad_answer": "The counselor approves it.", "signal": "correction",
             "rule": "Faculty and staff leave is approved by the department head, which differs from student leave approval"},
        ],
        "review_qa": [
            {"question": "What levels are there for professional title appointments?", "expected": "Assistant / intermediate / associate senior / full senior", "answer": "Professional title applications are graded as assistant, intermediate, associate senior, and full senior levels."},
            {"question": "How far in advance must a resignation application be submitted?", "expected": "30 days", "answer": "Resignation requires a written application submitted 30 days in advance and a work handover."},
            {"question": "What materials are required for onboarding?", "expected": "Proof of academic degrees, a medical examination report, etc.", "answer": "Onboarding requires proof of academic degrees, a medical examination report, and other materials."},
        ],
    },
    {
        "dept_id": "dept_yjsy",
        "skill": {
            "name": "Graduate Training and Degree Inquiries",
            "keywords": ["graduate", "degree", "thesis", "defense", "proposal", "mid-term", "blind review", "supervisor", "training plan"],
            "unique_rules": [
                "Graduate School policies apply to master's and doctoral students; each thesis stage (proposal / mid-term / pre-defense / defense) has its own deadline",
                "Graduate training and degree rules must not be mixed with undergraduate rules",
            ],
        },
        "docs": [
            {
                "title": "Graduate Training Plan and Credit Regulations",
                "status": "active",
                "content": "# Graduate Training Plan and Credit Regulations\n\nArticle 1 Master's students need at least 28 credits in total, and doctoral students at least 20 credits.\n\nArticle 2 Failed degree courses must be retaken; failing a retake disqualifies the student from applying for the degree.\n\nArticle 3 Graduate students shall draw up an individual training plan under their supervisor's guidance.",
            },
            {
                "title": "Implementation Rules for Graduate Thesis Work",
                "status": "review",
                "content": "# Implementation Rules for Graduate Thesis Work\n\nArticle 1 A thesis must go through the proposal, mid-term review, pre-defense, blind review, and formal defense in order.\n\nArticle 2 The proposal shall be completed before the end of the second semester, and the mid-term review in the third semester.\n\nArticle 3 Students who fail the blind review may not proceed to the defense.",
            },
            {
                "title": "Graduate Proposal and Mid-Term Assessment Regulations",
                "status": "draft",
                "content": "# Graduate Proposal and Mid-Term Assessment Regulations\n\nArticle 1 The proposal report is submitted to the school for review after the supervisor approves it.\n\nArticle 2 The mid-term assessment focuses on thesis progress and the completeness of experimental data.\n\nArticle 3 Students who fail the assessment must make corrections within a set period and be reassessed.",
            },
        ],
        "badcases": [
            {"query": "How many credits do graduate students need to graduate?", "bad_answer": "20 credits, same as undergraduates.", "signal": "correction",
             "rule": "Graduate credit requirements (28 for master's / 20 for doctoral) must not be confused with undergraduate ones"},
            {"query": "When must the thesis proposal be completed?", "bad_answer": "In the third semester.", "signal": "correction",
             "rule": "The proposal must be completed before the end of the second semester, and the mid-term review in the third semester"},
            {"query": "Can I defend if I fail the blind review?", "bad_answer": "Yes.", "signal": "down",
             "rule": "Students who fail the blind review may not proceed to the defense"},
        ],
        "review_qa": [
            {"question": "What stages does a master's thesis go through?", "expected": "Proposal / mid-term / pre-defense / blind review / defense", "answer": "A thesis must go through the proposal, mid-term review, pre-defense, blind review, and formal defense in order."},
            {"question": "What is the total credit requirement for master's students?", "expected": "At least 28 credits", "answer": "Master's students need at least 28 credits in total, and doctoral students at least 20 credits."},
            {"question": "When must the proposal report be completed?", "expected": "Before the end of the second semester", "answer": "The proposal shall be completed before the end of the second semester."},
        ],
    },
    {
        "dept_id": "dept_zfxy",
        "skill": {
            "name": "Sino-French Joint Program Inquiries",
            "keywords": ["sino-french", "french", "study abroad", "exchange", "dual degree", "france", "luggage storage", "proposal", "psychological assessment"],
            "unique_rules": [
                "The Sino-French Institute is a joint Chinese-foreign program with special rules on French-taught courses, exchanges in France, and dual degrees",
                "Sino-French Institute courses and main-campus courses are not interchangeable",
            ],
        },
        "docs": [
            {
                "title": "Sino-French Institute Student Management Regulations",
                "status": "active",
                "content": "# Sino-French Institute Student Management Regulations\n\nArticle 1 The institute runs joint Chinese-foreign training, with core courses taught in French.\n\nArticle 2 Students must earn the credits recognized by both parties to obtain the dual degree.\n\nArticle 3 Exchanges in France require the specified language level and credits.",
            },
            {
                "title": "Selection Regulations for the France Exchange Program",
                "status": "review",
                "content": "# Selection Regulations for the France Exchange Program\n\nArticle 1 Selection is merit-based on academic performance, French proficiency, and overall performance.\n\nArticle 2 Credits earned during the exchange are mutually recognized per the agreement, and students must complete the courses required by the partner institution.\n\nArticle 3 Exchange costs follow the program agreement and are partly subsidized by the university.",
            },
            {
                "title": "Sino-French Institute Dormitory and Luggage Storage Rules",
                "status": "draft",
                "content": "# Sino-French Institute Dormitory and Luggage Storage Rules\n\nArticle 1 Students leaving campus for winter or summer vacation may apply for luggage storage, which requires registration and labeling.\n\nArticle 2 Stored luggage must be packed by the students themselves, and valuables must be kept on their person.\n\nArticle 3 Luggage not collected on time is handled according to institute rules.",
            },
        ],
        "badcases": [
            {"query": "Do I have to learn French at the Sino-French Institute?", "bad_answer": "No.", "signal": "down",
             "rule": "Core courses at the Sino-French Institute are taught in French; the answer must reflect the French requirement"},
            {"query": "What are the requirements for the France exchange?", "bad_answer": "Just pay and you can go.", "signal": "correction",
             "rule": "Answers about the France exchange must state the language level, credit, and overall performance requirements"},
            {"query": "Are the Sino-French Institute dorm rules the same as the main campus?", "bad_answer": "Yes, the same.", "signal": "correction",
             "rule": "Logistics matters at the Sino-French Institute such as dormitories and luggage storage follow institute notices and are not interchangeable with the main campus"},
        ],
        "review_qa": [
            {"question": "What training model does the Sino-French Institute use?", "expected": "Joint Chinese-foreign training with core courses taught in French", "answer": "The institute runs joint Chinese-foreign training, with core courses taught in French."},
            {"question": "How can a student obtain the dual degree?", "expected": "Earn the credits recognized by both parties", "answer": "Students must earn the credits recognized by both parties to obtain the dual degree."},
            {"question": "What should students do with their luggage when leaving for winter or summer vacation?", "expected": "Apply for storage, register, and label it", "answer": "Students leaving campus for winter or summer vacation may apply for luggage storage, which requires registration and labeling."},
        ],
    },
    {
        "dept_id": "dept_hqaq",
        "skill": {
            "name": "Logistics Services and Safety Emergency Inquiries",
            "keywords": ["logistics", "cafeteria", "dorm repair", "repair", "typhoon", "rainstorm", "flood", "emergency", "safety", "power outage"],
            "unique_rules": [
                "The Logistics and Security Department handles campus logistics and safety emergencies; emergency phone numbers and response procedures must be accurate",
                "Weather warnings such as typhoons/rainstorms must come with specific tiered response measures",
            ],
        },
        "docs": [
            {
                "title": "Campus Flood Emergency Response Plan",
                "status": "active",
                "content": "# Campus Flood Emergency Response Plan\n\nArticle 1 An emergency response is activated at orange-level rainstorm warnings or above, and safety notices are issued promptly.\n\nArticle 2 Faculty and students should follow rainfall warnings, avoid going out unless necessary, and stay away from low-lying flooded areas.\n\nArticle 3 In case of hazards such as apartment leaks, flooding, damaged facilities, or electrical faults, do not handle them yourself; call the campus emergency number 0571-28881110 immediately.",
            },
            {
                "title": "Student Apartment Management and Repair Request Regulations",
                "status": "review",
                "content": "# Student Apartment Management and Repair Request Regulations\n\nArticle 1 Apartment facility faults can be reported through the online repair platform or by phone.\n\nArticle 2 Maintenance staff will respond within 1 working day after a repair request.\n\nArticle 3 Repair costs for damage caused by people are borne by those responsible.",
            },
            {
                "title": "Campus Safety Emergency Response Guidelines",
                "status": "draft",
                "content": "# Campus Safety Emergency Response Guidelines\n\nArticle 1 In emergencies such as fires, typhoons, or earthquakes, follow unified command and evacuate in an orderly manner.\n\nArticle 2 Safety hazards should be reported promptly to the Security Department.\n\nArticle 3 For emergencies at night, call the campus 24-hour duty line.",
            },
        ],
        "badcases": [
            {"query": "What should I do during a red rainstorm warning?", "bad_answer": "Carry on as usual.", "signal": "down",
             "rule": "Weather warning answers must give specific response measures: avoid going out unless necessary and stay away from flooded areas"},
            {"query": "What number do I call if my apartment is leaking?", "bad_answer": "Ask the dorm supervisor.", "signal": "correction",
             "rule": "Safety emergency answers must give the campus emergency number 0571-28881110"},
            {"query": "How do I report a broken dorm light?", "bad_answer": "Fix it yourself.", "signal": "correction",
             "rule": "Repair answers must state the online repair platform / phone channels and the 1-working-day response time"},
        ],
        "review_qa": [
            {"question": "What does the university activate during an orange rainstorm warning?", "expected": "An emergency response and safety notices", "answer": "An emergency response is activated at orange-level rainstorm warnings or above, and safety notices are issued promptly."},
            {"question": "What should be done about an apartment leak?", "expected": "Do not handle it yourself; call 0571-28881110", "answer": "In case of hazards such as apartment leaks, flooding, damaged facilities, or electrical faults, do not handle them yourself; call the campus emergency number 0571-28881110 immediately."},
            {"question": "How soon is a repair request answered?", "expected": "Within 1 working day", "answer": "Maintenance staff will respond within 1 working day after a repair request."},
        ],
    },
]


# =====================================================================
async def migrate_departments(container) -> None:
    store = container.store
    for from_dept, to_dept in MIGRATE_MAP.items():
        moved = 0
        # documents
        for d in await store.list_documents(dept_id=from_dept):
            d["dept_id"] = to_dept
            await store.upsert("documents", d)
            moved += 1
        # chunks
        for c in await store.list_all_chunks(dept_id=from_dept):
            c["dept_id"] = to_dept
            await store.upsert("chunks", c)
        # doc_relations
        for r in await store.list_relations():
            changed = False
            if r.get("from_dept") == from_dept:
                r["from_dept"] = to_dept
                changed = True
            if r.get("to_dept") == from_dept:
                r["to_dept"] = to_dept
                changed = True
            if changed:
                await store.upsert("doc_relations", r)
        # review orders
        for o in await store.list_review_orders(dept_id=from_dept):
            o["dept_id"] = to_dept
            await store.upsert("review_orders", o)
        # test questions
        for q in await store.list_test_questions(dept_id=from_dept):
            q["dept_id"] = to_dept
            await store.upsert("test_questions", q)
        print(f"[migrate] {from_dept} -> {to_dept}: {moved} documents (including chunks/relations/review orders/question bank)")

    for dept_id in DELETE_DEPTS:
        if await store.get_department(dept_id) is not None:
            await store.delete("departments", dept_id)
            await store.delete("dept_memory", dept_id)
            print(f"[merge] Deleted redundant department {dept_id}")


async def seed_docs(container) -> None:
    store = container.store
    tmp_dir = Path(tempfile.mkdtemp(prefix="clausewise_seed_"))
    try:
        for item in DEPT_DATA:
            dept_id = item["dept_id"]
            existing = {d.get("title") for d in await store.list_documents(dept_id=dept_id)}
            for spec in item["docs"]:
                title = spec["title"]
                if title in existing:
                    print(f"[skip] Already exists {dept_id} \"{title}\"")
                    continue
                fp = tmp_dir / f"{title}.md"
                fp.write_text(spec["content"], encoding="utf-8")
                try:
                    doc = await container.indexer.ingest(str(fp), dept_id=dept_id, uploaded_by="seed_demo")
                    # Set different statuses + record pipeline stages
                    await store.update_document(doc["_id"], {
                        "status": spec["status"],
                        "pipeline_stages": [
                            {"key": "upload", "name": "Upload", "done": True},
                            {"key": "parse", "name": "Format parsing", "done": True},
                            {"key": "clean", "name": "Cleaning", "done": True},
                            {"key": "chunk", "name": "Semantic chunking", "done": True, "detail": f"{doc.get('chunk_count', 0)} chunks"},
                            {"key": "metadata", "name": "Metadata extraction", "done": True, "detail": doc.get("doc_type", "other")},
                            {"key": "vectorize", "name": "Vectorization", "done": doc.get("vector_status") == "ready"},
                            {"key": "index", "name": "Index building", "done": doc.get("vector_status") == "ready"},
                            {"key": "relations", "name": "Cross-department relation mining", "done": True, "detail": "0 relations"},
                        ],
                    })
                    print(f"[doc] {dept_id} \"{title}\" (status={spec['status']}, {doc.get('chunk_count', 0)} chunks)")
                except Exception as exc:  # noqa: BLE001
                    print(f"[fail] {dept_id} \"{title}\": {exc}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def seed_review_orders(container) -> None:
    store = container.store
    for item in DEPT_DATA:
        dept_id = item["dept_id"]
        order_id = f"review_{dept_id}_seed"
        if await store.get_review_order(order_id) is not None:
            print(f"[skip] Review order already exists {order_id}")
            continue
        qa_pairs = [
            {
                "question": q["question"],
                "expected": q["expected"],
                "answer": q["answer"],
                "citations": [],
                "confidence": 0.8,
                "verdict": None,
                "correct": None,
                "correction": "",
            }
            for q in item["review_qa"]
        ]
        order = {
            "_id": order_id,
            "dept_id": dept_id,
            "doc_id": "",
            "doc_title": item["skill"]["name"] + " (mock review order)",
            "status": "pending",
            "qa_pairs": qa_pairs,
            "total": len(qa_pairs),
            "correct": 0,
            "accuracy": None,
            "created_at": _now(),
            "reviewed_at": None,
            "reviewed_by": None,
        }
        await store.insert_review_order(order)
        print(f"[review] {dept_id} created pending review order {order_id} ({len(qa_pairs)} questions)")


async def seed_badcases_and_skills(container) -> None:
    store = container.store
    for item in DEPT_DATA:
        dept_id = item["dept_id"]
        skill_spec = item["skill"]

        # 1) badcases: write feedback + traces (for Loop Reflect)
        #    Demo badcases are reset to "unconsumed" on every re-run, so "Manually trigger a Loop" always has feedback to observe
        for i, bc in enumerate(item["badcases"]):
            fb_id = f"fb_{dept_id}_{i}"
            await store.upsert("feedback", {
                "_id": fb_id,
                "session_id": "",
                "user_id": "student",
                "query": bc["query"],
                "answer": bc["bad_answer"],
                "kind": "explicit",
                "signal": bc["signal"],
                "detail": {"root_cause": "retrieval" if bc["signal"] == "down" else "generation", "rule": bc["rule"], "dept_id": dept_id},
                "consumed": False,
                "created_at": _now(),
            })
            trace_id = f"trace_{dept_id}_bad_{i}"
            if await store.get("traces", trace_id) is None:
                await store.upsert("traces", {
                    "_id": trace_id,
                    "session_id": "",
                    "user_id": "student",
                    "query": bc["query"],
                    "answer": bc["bad_answer"],
                    "intent": {"type": "regulation_consult", "depts": [dept_id]},
                    "verification": {"passed": False, "score": 0.4, "issues": [bc["rule"]]},
                    "latency_ms": 1200,
                    "success": False,
                    "created_at": _now(),
                })

        # 1.5) good case: 👍 feedback on a correct answer (used to compute the adoption rate; marked consumed so it never enters the Loop queue)
        for g_i, gq in enumerate(item["review_qa"][:1]):
            await store.upsert("feedback", {
                "_id": f"fb_{dept_id}_up_{g_i}",
                "session_id": "",
                "user_id": "student",
                "query": gq["question"],
                "answer": gq["answer"],
                "kind": "explicit",
                "signal": "up",
                "detail": {},
                "consumed": True,
                "created_at": _now(),
            })

        # 2) Initial skill: unique_rules (department-specific rules) + rubric_rules (initially empty; accumulated by Reflect after running the Loop)
        skill_id = f"skill_{dept_id}_seed"
        skill = {
            "_id": skill_id,
            "name": skill_spec["name"],
            "dept_id": dept_id,
            "scope": "department",
            "trigger": {
                "intent_patterns": skill_spec["keywords"],
                "entities_required": ["matter"],
                "confidence_threshold": 0.75,
            },
            "action": {
                "type": "workflow",
                "steps": [
                    {"step": 1, "action": "extract_entity", "params": {"entity": "matter"}},
                    {"step": 2, "action": "retrieve", "params": {"query": "{matter} related policies", "top_k": 5}},
                    {"step": 3, "action": "generate", "params": {"template": "department"}},
                ],
            },
            "unique_rules": skill_spec["unique_rules"],
            "rubric_rules": [],
            "metrics": {"trigger_count": 0, "success_rate": 0.0, "avg_latency_ms": 0, "last_triggered": ""},
            "version": 1,
            "status": "active",
            "auto_generated": False,
            "created_by": "seed",
            "created_at": _now(),
        }
        await store.upsert_skill(skill)
        print(f"[badcase] {dept_id} prepared {len(item['badcases'])} unconsumed feedback items + {len(item['badcases'])} failed traces + 1 👍 feedback")
        print(f"[Skill] {dept_id} initial skill \"{skill_spec['name']}\": {len(skill_spec['unique_rules'])} unique rules (rubric rules accumulate after running the Loop)")


async def main() -> None:
    settings = get_settings()
    container = build_container(settings)
    if container.mongo is not None:
        await container.mongo.connect()
    if hasattr(container.session_store, "connect"):
        try:
            await container.session_store.connect()
        except Exception:
            pass

    print("== 1/4 Merge departments + migrate misfiled documents ==")
    await migrate_departments(container)

    print("\n== 2/4 Generate 3 mock documents per department (active/review/draft) ==")
    await seed_docs(container)

    print("\n== 3/4 Generate pending review orders per department ==")
    await seed_review_orders(container)

    print("\n== 4/4 Generate badcases and write the reflected rubric rules into the initial Skills ==")
    await seed_badcases_and_skills(container)

    print("\nDone.")
    if container.mongo is not None:
        await container.mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
