# Paradox Sports OMS - Testing Guide

A step-by-step, simple guide for test the Paradox Sports OMS application together in **45 to 60 minutes**.

No technical knowledge is required! Every person gets a specific role, clear instructions on what buttons to click, what words to type, what to say out loud to teammates, and what to watch out for on their screen.

---

## 1. What Are We Doing Today?

We are testing the system as a team to make sure everything works smoothly before real users start using it.

### Two Types of Tests We Will Do:
- **🟢 Positive Test (The "Happy Path")**:
  Testing if the system works normally when people do their job correctly.
  *Example: A manager assigns a task $\rightarrow$ the volunteer receives it $\rightarrow$ the volunteer finishes it $\rightarrow$ the manager approves it.*
- **🔴 Negative Test (The "Safety & Error Check")**:
  Testing if the system protects itself when someone makes a mistake, tries to view pages they are not allowed to see, or loses internet connection.
  *Example: A volunteer tries to access the Admin settings page $\rightarrow$ the system must show a clean "Access Restricted" screen instead of crashing.*

---

## 2. Who Sits Where? (Choose Your Seat)

Before opening your laptops, decide who will take each seat:

```
┌─────────────────────────────────────────────────────────────┐
│                      THE TESTING TABLE                      │
├──────────────────────────────┬──────────────────────────────┤
│ 👑 Seat 1: The Executive Boss│ ⚽ Seat 2: Football Manager   │
│    (Admin & Core Leader)     │    (Vertical Coordinator)    │
├──────────────────────────────┼──────────────────────────────┤
│ 📦 Seat 3: Logistics Manager │ 🏃 Seat 4: Football Volunteer │
│    (Equipment Coordinator)   │    (Frontline Team Member)   │
├──────────────────────────────┼──────────────────────────────┤
│ 🚚 Seat 5: Logistics Worker  │ 🕵️ Seat 6: The Rule Tester   │
│    (Delivers Gear)           │    (Public Guest / Quality)  │
└──────────────────────────────┴──────────────────────────────┘
```

| Seat | Persona Name | Role in System | Department / Vertical | What You Will Do |
| :---: | :--- | :--- | :--- | :--- |
| **Seat 1** | **The Executive Boss** | `ADMIN` / `SPORTS_CORE` | Executive Management | Creates accounts, issues organization-wide rules, checks compliance. |
| **Seat 2** | **Football Manager** | `COORDINATOR` | Football Operations | Gives tasks to volunteers, approves daily reports, requests gear from Logistics. |
| **Seat 3** | **Logistics Manager** | `COORDINATOR` | Logistics & Inventory | Reviews equipment requests, manages inventory, assigns gear delivery. |
| **Seat 4** | **Football Volunteer** | `VOLUNTEER` | Football Operations | Does tasks, reports roadblocks when things go wrong, writes daily reports. |
| **Seat 5** | **Logistics Worker** | `VOLUNTEER` | Logistics & Inventory | Packs and delivers equipment, chats with other teams in request threads. |
| **Seat 6** | **The Rule Tester** | `EVENT_TEAM` / Public | Multi-role & Guest | Tests public forms (no login), tests locked pages, tests disconnecting Wi-Fi. |

---

## 3. Preparation: Getting Logged In (5 Minutes)

1. **Open the Website**:
   Every tester opens the website in their browser:
   - If running locally: `http://localhost:3000`
   - If running on VM: `https://oms.x.me` (or your server domain/IP).
2. **Create or Check User Accounts (Seat 1 does this)**:
   - **Seat 1 (The Boss)** logs in as Admin.
   - Go to **Admin $\rightarrow$ Users** (`/admin/users`).
   - Ensure accounts exist for Seat 2, 3, 4, 5, and 6 with their respective roles.
3. **Everyone Log In**:
   - Seat 1 logs in as Admin.
   - Seat 2 logs in as Football Coordinator.
   - Seat 3 logs in as Logistics Coordinator.
   - Seat 4 logs in as Football Volunteer.
   - Seat 5 logs in as Logistics Volunteer.
   - Seat 6 opens an **Incognito / Private browser window** (ready to act as a public guest).

---

## 4. The Live Testing Script (Step-by-Step)

Follow these phases together. Do not skip ahead. When you finish an action, speak out loud to your team!

---

### Phase 1: Checking Logins, Menus & Security (10 Minutes)

#### 🟢 Test 1.1: Checking What Each Person Can See
- **Goal**: Make sure volunteers cannot see manager menus, and managers cannot see admin settings.
- **What to do**:
  - Everyone look at your left sidebar navigation.
- **What each person should see**:
  - **Seat 1 (Boss)**: Sees **Admin**, **System Config**, **Audit Logs**, **All Departments**.
  - **Seat 2 & 3 (Managers)**: See **Team Workload**, **Review Queue**, **Requirements**, **Meetings**, **Department Tasks**.
  - **Seat 4 & 5 (Volunteers)**: See **My Work**, **My Reports**, **Announcements**, **Calendar**. (You should **NOT** see Admin or Review Queue).
- **Did it pass?**: If Seat 4 sees the Admin button, that is a bug! If menus match your role, mark **PASS**.

---

#### 🔴 Test 1.2: Trying to Sneak Into the Admin Page (Negative Test)
- **Goal**: Make sure a regular volunteer cannot access the Admin settings by typing the link directly.
- **Who acts**: **Seat 4 (Football Volunteer)**.
- **Exact steps**:
  1. Click your browser address bar at the top.
  2. Type: `http://localhost:3000/admin/users` (or your domain `/admin/users`) and press **Enter**.
- **What you should see on screen**:
  - You should **NOT** see user lists.
  - You should see a clean, friendly screen that says:
    🛡️ **Access Restricted (403)**
    *"You do not have permission to access this area."*
  - Click the blue **Return to Workspace** button. It should take you safely back home.
- **Did it pass?**: If you saw the 403 screen without any raw code or crash, mark **PASS**.

---

#### 🔴 Test 1.3: What Happens If Internet Disconnects? (Negative $\rightarrow$ Positive)
- **Goal**: Check if the system warns the user when their Wi-Fi drops and recovers cleanly when restored.
- **Who acts**: **Seat 6 (The Rule Tester)**.
- **Exact steps**:
  1. Turn off your laptop Wi-Fi (or open browser DevTools $\rightarrow$ Network tab $\rightarrow$ select **Offline**).
  2. Try clicking any button or link on the page.
  3. Turn your Wi-Fi back on (or set back to **Online**).
- **What you should see on screen**:
  - While offline: A floating **amber bar** appears at the top:
    ⚠️ *"You are currently offline. Check your internet connection."*
  - While offline, clicking a button should show a friendly retry prompt, **not a blank white screen**.
  - When reconnected: The bar turns **emerald green**:
    ✅ *"Internet connection restored"* and smoothly disappears after 3 seconds.
- **Did it pass?**: If the banner appeared and vanished cleanly, mark **PASS**.

---

### Phase 2: Assigning a Task & Handling a Problem (15 Minutes)

In this test, a manager gives work to a volunteer, the volunteer hits a roadblock, the manager helps, and the work gets finished.

```
[Seat 2: Football Manager]                 [Seat 4: Football Volunteer]
         │                                               │
         ├── 1. Creates Task & Assigns ─────────────────►│
         │                                               │ (Sees task in 'My Work')
         │                                               │
         │                                               ├── 2. Clicks 'Start Task'
         │                                               │
         │◄─ 3. Gets RED ALERT (Gate Locked!) ───────────┤ (Marks task as BLOCKED)
         │                                               │
         ├── 4. Helps & Clears Blocker ─────────────────►│
         │                                               │
         │                                               ├── 5. Finishes checklist
         │◄─ 6. Receives in Review Queue ────────────────┤ (Submits for review)
         │                                               │
         ├── 7. Approves Task (COMPLETED) ──────────────►│ (Work done!)
```

#### 🟢 Step 2.1: Assigning the Task
- **Who acts**: **Seat 2 (Football Manager)**.
- **Exact steps**:
  1. Click **Tasks** $\rightarrow$ Click **New Task** button.
  2. Fill in the form:
     - **Title**: `Inspect Goal Nets & Paint Penalty Dot`
     - **Department**: `Football Operations`
     - **Priority**: `HIGH`
     - **Assignee**: Select **Seat 4 (Football Volunteer)** from the dropdown.
     - **Checklist Items**: Click *Add Item*:
       - Item 1: `Check goal nets for holes`
       - Item 2: `Paint white penalty mark on pitch`
  3. Click **Create Task**.
  4. **Say out loud to Seat 4**: *"Hey Seat 4, I just assigned you a task!"*

---

#### 🟢 Step 2.2: Volunteer Starts the Work
- **Who acts**: **Seat 4 (Football Volunteer)**.
- **Exact steps**:
  1. Go to **My Work** (or refresh the page).
  2. You should see the task: `Inspect Goal Nets & Paint Penalty Dot` with a red/orange `HIGH` badge.
  3. Click on the task to open its details.
  4. Click the button **Start Task**. (Status becomes `IN_PROGRESS`).
  5. Check off the first box: `[✓] Check goal nets for holes`.

---

#### 🔴 Step 2.3: Something Goes Wrong! (Roadblock / Blocker Test)
- **Who acts**: **Seat 4 (Football Volunteer)**.
- **Situation**: You are on the field, but the paint shed is locked and paint is missing.
- **Exact steps**:
  1. Inside the task, click the button **Mark as Blocked**.
  2. A popup asks for a reason. Type:
     `The equipment shed is padlocked and we have no white paint.`
  3. Click **Confirm Blocker**.
  4. **Say out loud to Seat 2**: *"Manager, I am blocked! The shed is locked."*

---

#### 🟢 Step 2.4: Manager Sees the Alert and Helps
- **Who acts**: **Seat 2 (Football Manager)**.
- **Exact steps**:
  1. Look at your **Team Tasks** dashboard.
  2. The task status should now show a bright red **BLOCKED** badge.
  3. Click the blocked task to read Seat 4's reason.
  4. In the task comments, type:
     `I called the groundskeeper. Keys are at Security Gate 1. Proceed.`
  5. Click **Resume / Clear Blocker**.
  6. **Say out loud to Seat 4**: *"Shed is unlocked now, go ahead!"*

---

#### 🟢 Step 2.5: Finishing the Task & Manager Approval
- **Who acts**: **Seat 4** then **Seat 2**.
- **Exact steps**:
  1. **Seat 4**: Your task is back to `IN_PROGRESS`.
  2. Check off the second box: `[✓] Paint white penalty mark on pitch`.
  3. Both checklist items are now checked (100%).
  4. In the completion notes, type: `All nets checked and pitch painted.`
  5. Click **Submit for Review**.
  6. **Seat 2**: Open your **Review Queue**.
  7. You will see Seat 4's submitted task. Inspect the checklist.
  8. Click **Approve Task**.
- **What everyone should see**:
  - The task status turns green: **COMPLETED**.
  - It clears from pending work and is saved in history.
- **Did it pass?**: If the whole flow worked from start to finish, mark **PASS**.

---

### Phase 3: Asking Another Department for Equipment (10 Minutes)

In this test, the Football team needs equipment from the Logistics department.

```
[Seat 2: Football Manager]                 [Seat 3 & 5: Logistics Team]
         │                                               │
         ├── 1. Requests 50 Footballs ──────────────────►│ (Too many!)
         │                                               │
         │◄─ 2. REJECTED with Reason ────────────────────┤ [Negative Check]
         │                                               │
         ├── 3. Requests 10 Cones & 2 Whistles ─────────►│ (Reasonable)
         │                                               │
         │◄─ 4. ACCEPTED & Assigned to Seat 5 ───────────┤ [Positive Check]
         │                                               │
         │◄══ 5. Chat in Thread ("Gear ready at Shed") ══►│
         │                                               │
         │◄─ 6. Gear Delivered (FULFILLED) ──────────────┤ (Seat 5)
         │                                               │
         ├── 7. Football Confirms Receipt (CLOSED) ──────►│ (Done!)
```

#### 🔴 Step 3.1: Rejecting an Unrealistic Request (Negative Test)
- **Goal**: Make sure a department can decline a request they cannot fulfill and provide a clear reason.
- **Who acts**: **Seat 2 (Football)** $\rightarrow$ **Seat 3 (Logistics Manager)**.
- **Exact steps**:
  1. **Seat 2**: Click **Requirements** $\rightarrow$ Click **New Requirement**.
     - Item Needed: `50 Official Match Footballs`
     - Target Department: `Logistics & Inventory`
     - Needed By: Tomorrow
     - Urgency: `CRITICAL`
     - Click **Submit Request**.
  2. **Seat 3**: Look at your incoming **Requirements Queue**.
  3. Click on the 50 Footballs request.
  4. Click **Reject Request**. Type reason:
     `We only have 12 footballs in stock. Cannot provide 50.`
  5. Click **Confirm Rejection**.
  6. **Seat 2**: Check your screen. You should see the request marked **REJECTED** with Seat 3's explanation.
- **Did it pass?**: If rejection was clear and recorded, mark **PASS**.

---

#### 🟢 Step 3.2: Successful Equipment Request & Delivery (Positive Test)
- **Goal**: Request reasonable gear, assign a worker to deliver it, chat in the thread, and close the request.
- **Who acts**: **Seat 2** $\rightarrow$ **Seat 3** $\rightarrow$ **Seat 5 (Logistics Worker)**.
- **Exact steps**:
  1. **Seat 2**: Click **New Requirement** again:
     - Item Needed: `10 Training Cones & 2 Whistles`
     - Target Department: `Logistics & Inventory`
     - Click **Submit Request**.
  2. **Seat 3 (Logistics Manager)**: Open your queue $\rightarrow$ Click the request $\rightarrow$ Click **Accept & Assign** $\rightarrow$ Select **Seat 5 (Logistics Worker)**.
  3. **Seat 5 (Logistics Worker)**: Open the requirement from your tasks.
  4. Scroll down to the message thread. Type:
     `I packed 10 orange cones and 2 Fox40 whistles at Locker 2. Come pick them up.`
     Click **Send Message**.
  5. **Seat 4 (Football Volunteer)**: Open the same requirement, look at the chat, and type:
     `Got them! Thanks Seat 5.`
     Click **Send Message**.
  6. **Seat 5**: Click the button **Mark as Fulfilled**.
  7. **Seat 2 (Football Manager)**: Inspect the cones, click **Confirm & Close**.
- **What everyone should see**:
  - The requirement status moves to **CLOSED**.
  - All messages, delivery timestamps, and who approved are saved cleanly.
- **Did it pass?**: Mark **PASS**.

---

### Phase 4: Daily Shift Work Reporting & Anti-Cheating Check (10 Minutes)

Every working member submits a report at the end of their shift.

#### 🟢 Step 4.1: Submitting and Approving a Daily Report
- **Who acts**: **Seat 4 (Volunteer)** $\rightarrow$ **Seat 2 (Football Manager)**.
- **Exact steps**:
  1. **Seat 4**: Click **Daily Reports** in your sidebar.
  2. Click **Submit Daily Report**.
  3. Fill in the fields:
     - **Hours Worked**: `4`
     - **Work Summary**: `Inspected goal nets, resolved paint issue, and marked pitch dots.`
     - **Blockers / Roadblocks**: `None remaining.`
     - **Plan for Tomorrow**: `Help organize matchday warm-up bibs.`
  4. Click **Submit Report**.
  5. **Seat 2 (Football Manager)**: Open your **Reports Review Queue**.
  6. Click on Seat 4's report.
  7. Read the summary. Type a comment: `Good job handling the paint issue.`
  8. Click **Approve Report**.
- **What happens**:
  - Status becomes **APPROVED**. Seat 4 officially gets credit for 4 hours of work.
- **Did it pass?**: Mark **PASS**.

---

#### 🔴 Step 4.2: The Anti-Cheating Check (Can you approve your own report?)
- **Goal**: Make sure managers cannot approve their own daily reports to inflate their hours.
- **Who acts**: **Seat 2 (Football Manager)**.
- **Exact steps**:
  1. **Seat 2**: Go to **Daily Reports** $\rightarrow$ Click **Submit Daily Report**.
  2. Fill in 3 hours of coordinator work for yourself $\rightarrow$ Click **Submit Report**.
  3. Now go to your **Review Queue**. You will see your own report listed.
  4. Try to click **Approve** on your own report.
- **What you MUST see on screen**:
  - The system must **REFUSE** to approve it!
  - It should display:
    🚫 *"Self-review violation: You cannot approve your own report."*
  - **The rule**: Only **Seat 1 (The Executive Boss)** is allowed to review and approve Seat 2's daily report!
- **Did it pass?**: If the system stopped you from self-approving, mark **PASS**. If it let you approve yourself, that is a **CRITICAL BUG**!

---

### Phase 5: The Boss Issues an Urgent Rule (Directives) (5 Minutes)

When executive leaders issue a safety mandate, everyone in the organization must acknowledge it.

#### 🟢 Step 5.1: Issuing a Rule and Watching Compliance Go Up
- **Who acts**: **Seat 1 (The Boss)** $\rightarrow$ **Seats 2, 3, 4, 5**.
- **Exact steps**:
  1. **Seat 1 (Boss)**: Go to **Directives** $\rightarrow$ Click **New Directive**.
     - **Title**: `Urgent Lightning Safety: Immediate Field Evacuation`
     - **Audience**: `All Organization`
     - **Rule**: `If thunder is heard, all matches stop immediately for 30 minutes.`
     - Click **Issue Directive**.
  2. **Look at your screens (Seats 2, 3, 4, 5)**:
     - A high-priority banner appears at the top of your screen.
  3. **Seat 4 & Seat 5**: Click the banner $\rightarrow$ Read the rule $\rightarrow$ Click the button:
     **"I Acknowledge & Understand"**.
  4. **Seat 1 (Boss)**: Look at your **Compliance Dashboard**:
     - The live compliance bar moves from `0%` $\rightarrow$ `50%`.
     - It shows exactly who has acknowledged and who has not.
- **Did it pass?**: If the banner appeared and compliance updated live, mark **PASS**.

---

### Phase 6: Outside Public Form Submission (5 Minutes)

Testing how someone from the public applies without having an account.

#### 🟢 Step 6.1: An Outside Guest Submits an Application
- **Who acts**: **Seat 6 (Acting as a public athlete)**.
- **Exact steps**:
  1. Open a **Private / Incognito window** where you are **NOT logged in**.
  2. Go to the public application page:
     `http://localhost:3000/forms/public/summer-trials` (or your active public form link).
  3. Fill out the application:
     - Full Name: `Alex Rivers`
     - Sport: `Football`
     - Age: `19`
     - Phone: `555-0199`
  4. Click **Submit Application**.
- **What you should see**:
  - A clean green confirmation: *"Thank you! Your application has been received."*
  - You did not need a password or login.
- **Seat 2 (Football Manager)**:
  - Check your **Form Submissions Queue**.
  - You should see Alex Rivers' application waiting for review!
  - Click **Approve Application**.
- **Did it pass?**: Mark **PASS**.

---

## 5. Cheat Sheet: What Should I Be Doing? (By Seat)

If you get lost during the test, look at your seat's cheat sheet below:

### 👑 Seat 1 (The Boss / Admin)
- Your job is to oversee everything.
- You make sure user accounts exist in **Admin $\rightarrow$ Users**.
- In Phase 5, you issue the urgent Lightning Directive and watch the compliance bar.
- If someone gets stuck with permissions, you check their role.

### ⚽ Seat 2 (Football Manager)
- In Phase 2: You create the pitch inspection task and assign it to Seat 4. When Seat 4 reports a blocker, you help unblock it, then approve the finished task.
- In Phase 3: You request 50 footballs (get rejected), then request 10 cones (get fulfilled).
- In Phase 4: You approve Seat 4's daily report. Then you submit your own report and verify that you cannot approve yourself!

### 📦 Seat 3 (Logistics Manager)
- In Phase 3: You reject the 50 footballs request because you don't have enough stock.
- In Phase 3: You accept the 10 cones request and assign Seat 5 to pack and deliver them.

### 🏃 Seat 4 (Football Volunteer)
- In Phase 1: You try to type `/admin/users` to verify the 403 Access Restricted screen.
- In Phase 2: You open your task in "My Work", start it, hit the blocker button ("Shed is locked!"), wait for Seat 2 to unblock, finish the checklist, and submit for review.
- In Phase 4: You submit your daily report with 4.5 hours of work.
- In Phase 5: You click "I Acknowledge" on the Boss's directive.

### 🚚 Seat 5 (Logistics Worker)
- In Phase 3: You receive the 10 cones task from Seat 3. You chat with Seat 4 in the message thread, mark the gear as fulfilled, and deliver it.
- In Phase 5: You click "I Acknowledge" on the Boss's directive.

### 🕵️ Seat 6 (The Rule Tester & Guest)
- In Phase 1: You turn off your Wi-Fi to test the floating amber offline banner, then turn it back on to see the green restored toast.
- In Phase 6: You open an Incognito window (no login) and fill out the public sports trial form.

---

## 6. Official Test Scorecard (Fill Out During Testing)

Copy this table or print it to keep score:

| Test ID | Test Name | Positive or Negative? | Who Tested? | Result (PASS / FAIL) | Notes or Bugs Found |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **T-01** | Role-Based Menus (Volunteers can't see Admin) | 🟢 Positive | Everyone | [ ] | |
| **T-02** | URL Tampering (`/admin` shows 403 screen) | 🔴 Negative | Seat 4 | [ ] | |
| **T-03** | Wi-Fi Drop (Shows amber offline banner) | 🔴 Negative | Seat 6 | [ ] | |
| **T-04** | Wi-Fi Restored (Shows green restored toast) | 🟢 Positive | Seat 6 | [ ] | |
| **T-05** | Task Created & Shows up in 'My Work' | 🟢 Positive | Seat 2 $\rightarrow$ 4 | [ ] | |
| **T-06** | Task Blocker Triggered (Red alert to manager) | 🔴 Negative | Seat 4 $\rightarrow$ 2 | [ ] | |
| **T-07** | Task Unblocked, Finished & Approved | 🟢 Positive | Seat 2 $\rightarrow$ 4 $\rightarrow$ 2 | [ ] | |
| **T-08** | Equipment Request Rejected (With explanation) | 🔴 Negative | Seat 2 $\rightarrow$ 3 | [ ] | |
| **T-09** | Equipment Request Fulfilled & Chatted | 🟢 Positive | Seat 2 $\rightarrow$ 3 $\rightarrow$ 5 | [ ] | |
| **T-10** | Daily Report Submitted & Approved | 🟢 Positive | Seat 4 $\rightarrow$ 2 | [ ] | |
| **T-11** | Self-Review Blocked (Cannot approve own report)| 🔴 Negative | Seat 2 | [ ] | Critical integrity test |
| **T-12** | Directive Issued (Banner appears for all) | 🟢 Positive | Seat 1 $\rightarrow$ All | [ ] | |
| **T-13** | Directive Acknowledged (Compliance % goes up)| 🟢 Positive | Seat 4, 5 $\rightarrow$ 1 | [ ] | |
| **T-14** | Public Form Submitted (No login required) | 🟢 Positive | Seat 6 (Guest) | [ ] | |
| **T-15** | Application Approved in Manager Queue | 🟢 Positive | Seat 2 | [ ] | |

---

### What to Do If You Find a Bug:
1. Write down the **Test ID** (e.g. `T-06`).
2. Note what happened: *"Button didn't respond"* or *"Page showed white screen"*.
3. Note what role you were logged in as.
4. Pass the scorecard to the developer!
