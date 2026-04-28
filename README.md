<h1 align="center">- ZhiXue Lite Backend -</h1>

<p align="center">
<img src="https://img.shields.io/github/license/amakerlife/ZhiXue-Lite-backend" alt="License" />
<img src="https://img.shields.io/github/last-commit/amakerlife/ZhiXue-Lite-backend">
</p>
<p align="center">
    <img src="https://socialify.git.ci/amakerlife/ZhiXue-Lite-backend/image?description=1&forks=1&issues=1&language=1&name=1&owner=1&pulls=1&stargazers=1&theme=Light">
</p>

Lightweight Web App for Integrating with zhixue.com’s Official API, built using the frontend stack Vite + React + Tailwind CSS and the backend stack Python Flask + PostgreSQL.

---

## Quick Start

```bash
git clone https://github.com/amakerlife/ZhiXue-Lite-backend
cd ZhiXue-Lite-backend
mv ./example.env ./.env
vim ./.env
pip install .
flask run
```

## To-Do List

- [ ] Create a mapping from `login_name` to `student_id` using the student ID as the unique identifier, allowing users to log in with different usernames
- [ ] Randomly select answer sheets from exams
- [ ] Use a separate API to retrieve total score data to avoid certain issues (which may include those related to grading)
- [ ] Add task priorities (e.g., sending verification emails has the highest priority) and execute tasks in order
- [ ] Support school selection (backend returns a list of schools)
- [ ] Add “Forgot Password” feature
- [ ] Store detailed information such as exam grade and level in the exam database
- [ ] After fetching grades following an overwrite update, perform an additional comparison to mark records present locally but missing remotely for deletion or soft deletion
- [ ] Rewrite using Go
- [x] Automatically select the appropriate login method for students and teachers, and save the selection
- [x] Allow parent login
- [x] [To be implemented after Go rewrite] Asynchronous polling for background tasks; return immediately after starting child processes and check process status on each poll
- [x] [To be implemented after Go rewrite] Display detailed information in the task list for authorized users


## Note

Before using this project, please ensure you have a teacher account for the target school with permissions to view at least school-level reports. To access all features, please add a principal or administrator account. This project does not provide an API for verification codes; please handle this on your own.
