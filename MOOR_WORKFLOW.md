# Moor Development Workflow

This document explains the workflow for maintaining **Moor**, including how to keep the project up to date with the original upstream project (`Moor inc./hermes-agent`), manage your own features, and ensure the Moor rebranding is preserved.

## 1. Project Setup (Already Completed)
You have already:
- Initialized the Git repository.
- Linked your own GitHub as the `origin` remote.
- Linked the original project as the `upstream` remote (`https://github.com/Moor inc./hermes-agent.git`).
- Ran the `rebrand.py` script to change user-facing text from Moor to Moor.

---

## 2. The Routine Workflow: Pulling Updates from Upstream

Whenever you want to pull the latest features and bug fixes from the original creators of the project, follow these exact steps:

### Step A: Download the Latest Upstream Changes
Fetch the newest updates from the original repository and merge them into your branch:
```powershell
git fetch upstream
git merge upstream/main
```
> **Note:** If you are using `master` instead of `main`, the command is still `git merge upstream/main` because the original repo uses `main`.

### Step B: Resolve Any Merge Conflicts (If they happen)
If the original developers modified the exact same line of code that you modified (or rebranded), Git will pause and tell you there is a **Merge Conflict**.
1. Open the conflicting files in your code editor.
2. Choose which changes to keep (usually you want to keep their new features).
3. Once all conflicts are resolved, mark them as resolved:
```powershell
git add .
```

### Step C: Run the Rebrand Script
Because the new code you just downloaded will contain the word "Moor", you must run your rebrand script again to enforce the Moor branding on the new files:
```powershell
python rebrand.py
```

### Step D: Save and Push
Finally, commit the merged and rebranded update, and push it to your GitHub:
```powershell
git add .
git commit -m "Merged upstream updates and applied Moor rebranding"
git push origin master
```

---

## 3. Adding Your Own Features

You can write custom code, add new skills, and modify existing files at any time. 
To save your custom work:
```powershell
git add .
git commit -m "Add my new awesome feature"
git push origin master
```

### Best Practices for Custom Features
- **Try to keep the core structure intact:** It's completely fine to add new files (like new tools in the `tools/` folder or new skills). Adding new files almost never causes merge conflicts when pulling upstream.
- **Modifying core files:** If you heavily modify the core files (like `run_agent.py` or `cli.py`), be prepared to manually resolve merge conflicts when you pull updates, since the original developers will likely be modifying those files as well.

---

## 4. Summary Checklist for Updates
Whenever you hear there's a cool new update from Moor inc., just run this sequence:

1. `git fetch upstream`
2. `git merge upstream/main`
3. *(Resolve conflicts if any)*
4. `python rebrand.py`
5. `git add .`
6. `git commit -m "Update from upstream"`
7. `git push origin master`
