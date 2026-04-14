---
description: Apply all approved fixes from the approval sheet
---

# Apply Approved Fixes

You are applying approved bug fixes from `approval_sheet.md`. Follow this exact process:

## Step 1: Read the Approval Sheet
Read `approval_sheet.md` from the repository root. Parse the table rows.

## Step 2: Find APPROVED Entries
Find all rows with Status = `APPROVED`. If none found, inform the user and stop.

## Step 3: For Each APPROVED Row (in order)
For each approved fix:

1. **Announce**: Print the Bug ID and summary you are about to apply
2. **Read affected files**: Use the "Affected Files" column to find exactly which files and line ranges to read
3. **Verify current state**: Confirm the code at those lines matches what the root cause describes. If the code has already changed, SKIP this entry.
4. **Apply the fix**: Make the changes described in "Fix Description" at the locations specified in "Affected Files"
5. **Verify**: Re-read the modified lines to confirm correctness
6. **Update the sheet**: Change the row's Status from `APPROVED` to `APPLIED` and add the date

## Step 4: Create a Git Commit
Stage all modified files (both code changes and the updated `approval_sheet.md`).
Create a single commit with the message format:
```
fix: apply approved bug fixes {BUG-IDs}

Applied fixes:
- BUG-YYYY-MM-DD-N: {summary}
- BUG-YYYY-MM-DD-N: {summary}
```

## Step 5: Summary Report
Print:
- Number of fixes applied
- Number of fixes skipped (with reasons)
- List of files modified
- The git commit hash

## Important Rules
- NEVER apply a fix with Status other than APPROVED
- Before applying any fix, read the `## Constraints` section of CLAUDE.md and follow all rules listed there
- If a fix conflicts with current code state, SKIP it and mark Status as `CONFLICT`
- Create ONE commit for all applied fixes, not separate commits per fix
