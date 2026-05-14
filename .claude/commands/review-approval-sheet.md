---
description: Summarize the current state of the approval sheet
---

# Review Approval Sheet

Read `approval_sheet.md` from the repository root and provide a summary:

1. Count entries by status (PENDING, APPROVED, REJECTED, APPLIED, CONFLICT)
2. List all PENDING entries with their Bug ID, summary, risk level, and affected files
3. Highlight any HIGH risk entries that need careful review
4. Check for potential conflicts between PENDING/APPROVED entries that modify the same files
5. Recommend a review order (HIGH risk first, then by dependency)
