# LikeMinds MCP - How to Use

---

## Connect

**MCP server URL:** `https://mcp.likeminds.io/mcp`

**Claude Desktop** - add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "likeminds": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.likeminds.io/mcp"]
    }
  }
}
```
Restart Claude Desktop after saving.

**Claude Code** - run once:
```bash
claude mcp add --transport http --scope user likeminds https://mcp.likeminds.io/mcp
```

---

## Bring Your Own API Key (Optional)

By default, inference runs on the server's Anthropic account. If you want it to bill to your own Anthropic account instead, add your API key to the MCP config:

**Claude Desktop:**
```json
{
  "mcpServers": {
    "likeminds": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.likeminds.io/mcp",
               "--header", "x-api-key: YOUR_ANTHROPIC_API_KEY"]
    }
  }
}
```

**Claude Code** (`.mcp.json`):
```json
{
  "mcpServers": {
    "likeminds": {
      "type": "http",
      "url": "https://mcp.likeminds.io/mcp",
      "headers": {
        "x-api-key": "YOUR_ANTHROPIC_API_KEY"
      }
    }
  }
}
```

The key is sent per-request and never stored on the server.

---

## Sign In

The first time you use LikeMinds, Claude will open a browser window asking you to sign in. Enter your work email, verify the code sent to you, and you are done. Claude handles the token from that point - you never need to paste it anywhere.

---

## How to Use

**Always start your message with `@likeminds`.**

This tells Claude to use LikeMinds instead of answering the question itself. Without it, Claude will just respond on its own and nothing will run.

```
@likeminds build the KB for Acme Corp from these reference files
@likeminds generate a SOW for the new deal
@likeminds the document you generated was off-brand, fix it
```

Attach your files directly to the message. If your files are at a public URL, you can paste the links instead of uploading.

You can also add free-text instructions to guide the output:
```
@likeminds generate a SOW for TechCorp - 3 month engagement, 2 engineers, focus on the cloud migration scope
```

---

## What You Can Do

### Build a knowledge base
Extracts your format, rules, and product knowledge from your reference files into a reusable knowledge base. No document is generated - just the KB.

**Use this to onboard a client once, then generate as many documents or configs as you need from it later.**

```
@likeminds build the KB for Acme Corp from these reference SOWs and playbook
[attach: acme-sow-sample.pdf, acme-playbook.docx]
```
```
@likeminds create a knowledge base from these sample documents so we can generate SOWs for new deals later
[attach: sample-sow-1.pdf, sample-sow-2.pdf, brand-guide.pdf]
```

---

### Generate a document (end to end)
Learns your format from reference files and produces a finished document (PDF or DOCX) in one go.

**Use this when you have reference files and want the finished document right now.**

```
@likeminds generate a SOW for TechCorp. 3 month engagement, cloud migration. Reference files attached.
[attach: techcorp-brief.pdf, sample-sow-1.pdf, sample-sow-2.pdf]
```
```
@likeminds produce an HLD for the new payments microservice using these past HLDs as format reference
[attach: past-hld-1.pdf, past-hld-2.pdf, payments-requirements.pdf]
```

---

### Generate a document from an existing knowledge base
Generates a new document using a KB that was already built in a previous run - skips the learning step.

**Use this for every new deal after the KB is set up. Pass the session ID of the run that built the KB, plus the deal-specific brief.**

```
@likeminds generate a SOW for Acme Corp's mobile app phase. Use the KB from session abc-123.
[attach: acme-mobile-brief.pdf]
```
```
@likeminds write a BRD for the Acme Corp analytics module using the same KB, session abc-123
[attach: analytics-requirements.pdf]
```

---

### Generate a config (end to end)
Learns your config format and rules from reference files, then produces a validated config file (JSON, XML, YAML, etc.).

**Use this when you have reference config files and want the finished config right now.**

```
@likeminds generate a JSON config for the campaign automation flow using these reference configs
[attach: sample-config-1.json, sample-config-2.json, nodeflow-schema.pdf]
```
```
@likeminds create an XML configuration for the lead routing module using these existing configs as reference
[attach: lead-routing-sample.xml, routing-rules.pdf]
```

---

### Generate a config from an existing knowledge base
Same as above but skips the learning step - uses a KB that was already built.

**Pass the session ID of the run that built the KB, plus the brief for the new scenario.**

```
@likeminds generate the config for the re-engagement campaign. Use the KB from session xyz-456.
[attach: re-engagement-brief.pdf]
```
```
@likeminds create a YAML config for the onboarding flow using KB from session xyz-456
[attach: onboarding-spec.pdf]
```

---

### Fix a bad output
If a generated document or config was wrong, use this to describe the problem. LikeMinds analyses what went wrong in the knowledge base and fixes it so future generations are better.

**Pass the session ID of the run that produced the bad output. Optionally attach the bad output and/or a corrected version.**

```
@likeminds the SOW from session abc-123 used the wrong pricing format and missed the payment schedule section. Fix it so next time it gets it right.
```
```
@likeminds the document from session abc-123 is off-brand - wrong tone and header format. Here is a corrected version.
[attach: corrected-sow.pdf]
```

After this runs, **generate again using the same session ID** (`seed_session_id`) and the output will reflect the fixes.

---

## Important: Save Your Session ID

Every run produces a **session ID**. Claude will always tell you what it is when a run finishes.

**Save it.** It is the only thing you need to:
- Generate a document or config from a KB you already built
- Generate another document or config for a new deal from the same KB
- Fix a bad output
- Get fresh download links after they expire

You can refer to it naturally:
```
@likeminds generate a new SOW using the KB from last time - session abc-123
```

---

## A Few Things to Know

**Download links expire in 1 hour.** Ask Claude for the session ID again and it will give you fresh links.

**If Claude asks you a question mid-run**, answer it. The system has paused to clarify something. Do not skip it or say "continue" - just answer the question and it will carry on.

**If a run fails**, Claude will tell you which step went wrong. You can ask it to retry and it will pick up from where it failed - it will not redo the steps that already completed.

---

## Quick Reference

| What you want to do | Say |
|---|---|
| Build a knowledge base | `@likeminds build the KB from these files` |
| Generate a document (first time) | `@likeminds generate a SOW from these reference files` |
| Generate a document from existing KB | `@likeminds generate a SOW, use KB from session <id>` |
| Generate a config (first time) | `@likeminds generate a JSON config from these reference configs` |
| Generate a config from existing KB | `@likeminds generate the config, use KB from session <id>` |
| Fix a bad output | `@likeminds the output from session <id> was wrong - <describe issue>` |
| Get fresh download links | `@likeminds give me the download links for session <id>` |
| Retry a failed run | `@likeminds retry the run from session <id>` |
