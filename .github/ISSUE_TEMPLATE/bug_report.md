---
name: Bug Report
about: Create a report to help us improve Telex
title: "[BUG] "
labels: ["bug"]
assignees: ""
---

<!-- Want to submit a fix? Small bug fixes are welcome as direct pull requests! For larger refactors, feel free to leave a comment to coordinate. -->

**Did you run the bootstrap script?**
- [ ] Yes, I ran `./scripts/bootstrap.sh` (macOS/Linux) or `.\scripts\bootstrap.ps1` (Windows)
- [ ] No (if you skipped this, please try it first — it auto-configures the local environment)

**Telex version / commit SHA**
<!-- Run `git rev-parse --short HEAD` in the repo and paste the result here -->
Commit:

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots / Screen Recordings**
If applicable, add screenshots or a video recording to help explain your problem.

**Environment (please complete the following information):**
- OS: [e.g. Ubuntu 22.04, Windows 11, macOS Sonoma]
- Browser (if UI related): [e.g. Chrome 124, Firefox 125]
- Python Version: [e.g. 3.11.8]
- Node.js Version: [e.g. 20.12.0]

**Backend logs**

<details>
<summary>Click to expand backend logs</summary>

```
Paste the output from your terminal running uvicorn here.
You can also find logs in the console where you ran: uvicorn main:app --reload --port 8000
```

</details>

**Additional context**
Add any other context about the problem here (e.g. browser console errors, network tab screenshots).
