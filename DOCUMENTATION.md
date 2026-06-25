### 🖥️ Custom CTFd Computer Lab Extensions: Technical Roadmap

Welcome to the technical deployment documentation for the custom university computer range laboratory extensions. All custom features, telemetry monitoring pipelines, and automation tools are fully active and synchronized under the core version control branch track: **`hamza`**.

* * *

### 📂 Custom Subsystems & File Layout Directory

This project isolates custom features cleanly inside independent framework plugin modules, ensuring zero bloat or stability degradation across core platform database schemas.

### ⏳ 1. Challenge Focus Session Time Tracker
* **What it does**: Automatically tracks the exact amount of time a student spends actively working on a challenge by monitoring when they open it and keeping track of their focus windows.
* **Key feature**: Includes a smart 15-minute idle timeout cap. If a student leaves their desk or walks away from their computer, the system automatically stops the clock to keep the lab time data completely accurate.

### 🚨 2. Classroom Threat Detection & Security Monitor
* **What it does**: Acts as an automated security guard for the lab by continuously watching flag submissions for suspicious behavior.
* **Key feature**: Instantly locks a player out for 3 minutes if they try to brute-force a puzzle (5 wrong guesses in 2 minutes), and automatically logs flag-sharing collusion leaks if a student magically solves a puzzle in under 15 seconds from opening it.

### 💡 3. Pedagogical Clue & Hint Usage Analytics
* **What it does**: Gives instructors a clear window into where students are getting stuck by aggregating and analyzing how hints are being unlocked across the classroom.
* **Key feature**: Identifies exactly which challenges are causing massive roadblocks and maps out student reliance on help files, showing the exact costs spent and task indexes reviewed.

### ⭐ 4. Challenge Peer Review Feedback
* **What it does**: Allows students to submit crowdsourced feedback on laboratory exercises by standardizing challenge ratings into clear metrics.
* **Key feature**: Displays binary Upvote/Downvote approval percentage ratios natively on the dashboard with built-in text-wrapping layout safeties to prevent long comments from breaking the screen.

### 📊 5. Student Performance Analytics Matrix
* **What it does**: Computes individual student laboratory rankings, final scores, error logs, and achievements on a centralized grading sheet.
* **Key feature**: Features custom, zero-dependency SVG donut charts that render instantly without slowing down browsers, alongside an isolated `/performance/team` student scorecard route that lets teams review their own metrics while keeping peers completely hidden.

### 📝 6. Administration Audit Log Ledger
* **What it does**: Provides complete accountability across the platform by maintaining a real-time historical logging table of all modifications executed by admins.
* **Key feature**: Intercepts server changes (POST/PATCH/PUT/DELETE) across challenges, users, teams, and hints—logging exact timestamps, admin names, workstation IP locations, and form payload data sizes at a single glance.

### ⚙️ 7. Challenge Autofill & Bulk Modifier Hub
* **What it does**: Eliminates boring data entry by automating the challenge creation process and giving organizers a tool to edit multiple puzzles at once.
* **Key feature**: Autofills template categories ("Lab-Session"), point values ("100"), hidden publishing states, and markdown descriptions on fresh wizard popups. It also lets admins select an entire category folder to change the points or states of multiple existing challenges simultaneously.

### ⏰ 8. Automated Scoreboard Freeze Scheduler
* **What it does**: Builds competition suspense automatically by allowing organizers to schedule an exact date and time in advance for the public scoreboard to freeze.
* **Key feature**: Works seamlessly with your local PC clock. Once the deadline hits, a background clock checker automatically updates CTFd's internal settings to freeze public leaderboards, ensuring standard users can still earn points privately while removing the risk of an admin forgetting to toggle it manually.


### 9\. 🤝 Dynamic Sponsor Management Engine

This feature gives administrators a complete settings page to manage event sponsors without touching any code. It replaces static placeholders with a fully automated management dashboard.

* * *

### 📊 Shared Core Integrations Strategy

Every analytics extension listed above has been built to use a uniform reporting design framework:

1.  **Single-Click Data Exporters:** Embedded native backend streaming endpoints that package SQL tables into clean **Excel CSV spreadsheet** attachments.
2.  **Zero-Dependency Vector Visuals:** Pure **SVG Donut Charts** are drawn inline natively on the frontend layer, ensuring high-speed processing without breaking Content Security Policies (CSP) or loading untrusted external CDNs.
3.  **Grading Sheet Print Optimization:** Outfitted templates with custom media responsive print styling layouts (`@media print`). Clicking **Save PDF Report** strips out navbars, headers, and footers, isolating clean data sheets perfectly for student evaluations or internship logs.

* * *

### 📋 Database Relational Architecture Maps

### Framework Tables Hooked Into

*   `users` / `teams` / `challenges`
*   `solves` / `submissions`
*   `hints` / `unlocks` / `config`

### Custom Extension Tables Created on Disk

*   `sponsors` (Priority sequence maps)
*   `challenge_time_track` & `challenge_clicks` (Focus intervals)
*   `security_alerts` & `classroom_open_logs` (Intrusion metrics)
*   `admin_activity_logs` (Audit trails data)

* * *

### 🛠️ Global Environment Operational Checklist

To spin up, verify, or update the complete multi-module repository framework layout locally, execute these production terminal lines:

bash

    # 1. Pull down active branch source tracking alignments
    git checkout hamza
    git pull origin hamza
    
    # 2. Recompile and launch complete isolated system dependencies container loops
    docker compose down && docker compose up -d
    
    # 3. Verify server initialization script logs
    docker compose logs -f ctfd
    ```
    

Use code with caution.