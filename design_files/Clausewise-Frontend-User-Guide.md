# Clausewise Frontend User Guide

> Applicable version: Python control plane + pi Agent execution engine  
> Default URL: <http://localhost:8080>

## 1. Page Roles and Demo Accounts

Clausewise automatically opens the right workspace based on the account you sign in with; there is no need to pick a role manually.

| Role | Demo Account | Default Password | Workspace Capabilities |
|---|---|---|---|
| Student | `student` | `student123` | Policy Q&A, citation viewing, session history, feedback, personal long-term memory |
| Department Admin | `jwc_admin` | `admin123` | Own department's documents, reviews, feedback, traces, Skills, memory, and agent status |
| Super Admin | `admin` | `admin123` | Global departments, Loop, policies, experiments, memory, reviews, and the agent network |

The local demo also provides a Finance Office admin: `cwc_admin / admin123`.

## 2. Signing In and Out

### 2.1 Signing In

1. Open <http://localhost:8080>.
2. Enter the username and password; in the local demo you can also click an identity card to fill them in automatically.
3. Click "Secure sign-in".
4. The system opens the workspace that matches the role and department scope in the token.

### 2.2 Signing Out

- Student side: click the sign-out icon to the right of the user area in the bottom-left corner.
- Admin side: click "Sign out" at the bottom of the left navigation.

Signing out clears the browser's login token; it does not delete sessions, documents, or memory.

## 3. Student Policy Q&A Workspace

### 3.1 Asking a Trusted Question

1. Sign in with the student account.
2. Click a sample question, or type a question at the bottom.
3. Press Enter or click send; Shift + Enter inserts a new line.
4. The system runs intent recognition, department routing, active-policy retrieval, pi Agent generation, and Verifier checks in turn.
5. The answer card shows the number of retrieved evidence items, the intent, the answer confidence, and the verification score.

### 3.2 Viewing Policy Citations

1. Click "View N policy sources" at the bottom of the answer.
2. Review the document title, section path or chunk number, and the source text supporting the answer.
3. When the policies contain no explicit answer, the system should clearly state that no provision was found and must not make one up.

### 3.3 Viewing Department Routing

The "Smart routing" section of the answer card shows the matched departments and the main reason. Cross-department questions may match multiple departments at once.

### 3.4 Submitting Feedback

- "Helpful": records an adoption signal.
- "Copy": copies the answer and also records a copy-usage signal.
- "Needs improvement": records negative feedback for Observe and Reflect to analyze.

Asking follow-up questions or leaving without rating also produces implicit signals such as follow-ups or abandoned sessions. Feedback never modifies policy facts directly; it enters the governed Loop.

### 3.5 Managing Session History

1. "Recent conversations" on the left shows your own history.
2. Click a title to restore its messages and citations.
3. Click "New conversation" to start an independent context.
4. Hover over a history item and click the delete icon to delete your session and its associated episodic memory.

Users cannot read or delete other people's sessions.

### 3.6 Using Personal Long-Term Memory

1. Click "My long-term memory".
2. Enter a preference name, e.g. `answer_style`.
3. Enter the preference value, e.g. "Concise answers with bullet points".
4. Click "Remember this preference".
5. Later Q&A sessions will selectively recall this preference.
6. Click the delete icon when you no longer need it.

Long-term memory requires the user's explicit consent. Sensitive information such as ID numbers, passwords, and contact details is rejected by the backend.

## 4. Department Admin Workspace

Department admins can only view and operate on data from their bound department. For example, `jwc_admin` can only access `dept_jwc`.

### 4.1 Overview

1. Click "Overview".
2. Review the department's documents, chunks, Skills, conflicts, traces, review orders, and question bank size.
3. Check whether the department is in the human-in-the-loop, human-on-the-loop, or human-out-of-the-loop phase.
4. Use accuracy and sample progress to judge how far the department is from a progressive exit.

Department phases advance automatically based on real review quality and cannot be skipped manually.

### 4.2 Uploading Department Documents

1. Click "Knowledge Assets".
2. Confirm your department and click "Choose policy file".
3. Select a PDF, DOCX, Markdown, TXT, or HTML file.
4. Wait for the status to go from `queued` to `running`, then to `completed`.
5. The page shows the upload, parsing, cleaning, chunking, metadata, vectorization, indexing, and relation discovery Pipeline.
6. After ingestion completes, the system automatically generates a review order.

### 4.3 Document Status Governance

- You can archive a current policy, or restore an archived/draft document to active.
- You can view the version, chunk count, vector status, and Pipeline.
- Only `active` documents take part in student retrieval; old versions should be archived.

### 4.4 Trusted Review

1. Click "Trusted Review" and select "Pending".
2. Click "View details" on a review order.
3. Mark each question "Correct" or "Incorrect".
4. Enter a correction for incorrect questions.
5. Submit once every question is handled; unmarked questions never pass by default.
6. Results are written to the question bank and feedback, and added to the department's cumulative accuracy.

### 4.5 Viewing the Department Loop

1. Click "Evolution Loop".
2. Review Execute → Observe → Reflect → Adapt → Deploy.
3. Load pending feedback and recent traces.
4. Check the status and metrics of the department's Skills, Hooks, and Rules.

Department admins cannot trigger the global Loop or switch the global phase; the page does not show those actions, and the backend rejects unauthorized requests.

### 4.6 Viewing Department Memory and Experiments

"Memory & Experiments" shows working memory, episodic memory, organizational knowledge memory, procedural learning memory, the independent fact plane, and the department's policy experiments. The department view does not expose users' private long-term memory.

### 4.7 Viewing the Department Agent Network

"Agent Network" shows the Orchestrator, Intent, Retrieval, Answer, and Verifier execution chain, along with the model, temperature, replicas, documents, Skills, Hooks, review quality, and hot topics.

## 5. Super Admin Workspace

### 5.1 Global Overview

1. Click "Overview".
2. Review system-wide departments, traces, review orders, question bank, Skills, and adoption rate.
3. Compare documents, conflicts, accuracy, and Human Fade-out phase department by department.

### 5.2 Creating a Department

1. Click "Knowledge Assets".
2. Enter a unique ID, the department name, and a category.
3. Click "Create". The new department appears in the overview and the agent network.

Department admins cannot see this action.

### 5.3 Global Documents and Reviews

- The documents page lets you view policy assets by department.
- The review center can be filtered by department and status.
- Super admins can process review orders for any department, but business fact judgments are best left to department admins.

### 5.4 Manually Triggering the Loop

1. Click "Evolution Loop".
2. First load feedback and traces to confirm there are pending signals.
3. Click "Trigger a new Loop".
4. The job enters Redis Stream, and the page polls automatically; no manual refresh is needed.
5. The five-stage timeline shows the completed or running state of Execute, Observe, Reflect, Adapt, and Deploy in turn.
6. When finished, review the structured report: feedback count, bad cases, root-cause distribution, policy candidates, release count, before/after asset changes, and next-step suggestions.
7. "Recent Loop runs" lets you reopen past reports instead of just showing a `job_id`.

Do not trigger the Loop repeatedly when there are no feedback samples.

### 5.5 Switching the Global Loop Phase

- Human in the loop: automatic outputs must be reviewed.
- Human on the loop: high-confidence outputs apply automatically; low-confidence ones go to review.
- Human out of the loop: runs automatically within the defined scope; humans own the boundaries and supervision.

The global phase controls the auto-apply threshold for policies; it never forcibly skips each department's review conditions.

### 5.6 Skill Review and Lifecycle

1. The initial page ships with three real, executable baseline Skills that demonstrate the extreme-weather, procedure-steps, and academic-deadline workflows.
2. Expand a Skill card to see its trigger words, execution steps, canary ratio, counts, success rate, version, origin, and status.
3. After a student asks a question that matches the trigger words, the baseline Skill genuinely changes the retrieval query, top_k, and answer template, and accumulates hit/success metrics.
4. Pending Skills automatically mined by the Loop can be approved with "Approve and activate".
5. Review the unique rules and the rubric rules reflected from badcases.
6. In "Memory & Experiments", view policy snapshots, canary buckets, lifecycle proposals, and rollbacks.

### 5.7 Reading the Memory and Experiments Overview

1. The five memory planes show their counts, purposes, and storage media.
2. The fact plane shows active documents, chunks, relations, and conflicts.
3. Memory governance shows usage records, stale knowledge, and pending candidates.
4. Policy evolution shows versions, executions, experiments, and lifecycle proposals.
5. Canary traffic shows the treatment/control buckets.
6. The feedback signal radar aggregates adoption, thumbs-down, correction, copy, follow-up, abandonment, and Verifier signals.
7. Recent traces show traceable results and latency.

### 5.8 Agent Network and Elasticity

Compare each department's execution units, models, documents, Skills, Hooks, review quality, and hot topics. The 1–20 shown on the page is the target elastic range; local Compose usually has only one instance, and real scaling requires Kubernetes/HPA.

## 6. Core Concepts

### 6.1 Loop

The Loop is not the model rewriting code on its own; it is a governed policy cycle: Execute saves traces; Observe collects signals; Reflect analyzes root causes; Adapt generates policy candidates; Deploy applies them after review, replay, and canary release, with rollback on failure.

### 6.2 Skill

A Skill is an executable workflow for a recurring question pattern, not just a single prompt. Focus on its trigger words, workflow, version, success rate, experiments, and lifecycle.

### 6.3 The Five Memory Planes and the Fact Plane

| Plane | Meaning on the Page | Used as Policy Fact? |
|---|---|---|
| Working memory | Current session context, short TTL | No |
| Episodic memory | Past events and session summaries | No |
| User semantic memory | Stable preferences the user explicitly approved | No |
| Organizational knowledge memory | FAQs/tips with sources, versions, and review | Sources must be re-checked |
| Procedural learning memory | Skills, Hooks, Rules, and experiments | No |
| Independent fact plane | Active documents, full chunks, and relations | Yes |

Memory is for understanding and guidance; key conclusions must go back to the fact plane and include citations.

## 7. FAQ

### The page says the backend is unavailable

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker compose ps
docker compose logs --tail=100 backend web
```

### A document stays in queued or running for a long time

```bash
docker compose logs -f worker
```

Complex documents also go through vectorization, conflict detection, and review question generation, so the first run can take tens of seconds.

### Why can't department admins see "New Department" or the manual Loop?

This is by design. Department admins can only govern their own department; global organization and policy operations belong to the super admin.

### How do I stop the system safely?

```bash
docker compose down
```

Do not run `docker compose down -v` casually; it deletes the MongoDB, Redis, and uploaded-file data volumes.
