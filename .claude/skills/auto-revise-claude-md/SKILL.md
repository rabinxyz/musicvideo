---
name: auto-revise-claude-md
description: Auto-apply version of revise-claude-md for headless/autonomous mode
---

!`cat ~/.claude/plugins/marketplaces/claude-plugins-official/plugins/claude-md-management/commands/revise-claude-md.md | tail -n +6 | sed 's/Ask if the user wants to apply the changes\. Only edit files they approve\./Apply all proposed changes directly without asking for confirmation./' | sed 's/## Step 5: Apply with Approval/## Step 5: Auto-Apply Changes/'`
