"""Browser-facing login: an email-OTP page plus its two JSON endpoints, mounted on the
same ASGI app as /mcp (via FastMCP custom routes).

Flow:
  1. GET  /login            → the page (enter email, then the emailed code).
  2. POST /login/send-otp   → {email}       → Gupshup emails a code; the user row is ensured.
  3. POST /login/verify-otp → {email, otp}  → on success the user is marked verified and
     the STABLE token (their Mongo id) is returned with a ready-to-paste MCP config.

The client then sends that token in the config.USER_ID_HEADER header on every MCP
request. Requires Mongo (to mint/persist the stable token); when Mongo is not configured
the endpoints return 503 — a Mongo-less deployment uses opaque dev tokens without a page.
"""

from __future__ import annotations

import os
import re

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from . import config, db, oauth, otp

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _public_base(request: Request) -> str:
    """Public origin for the copy-paste config. PUBLIC_BASE_URL wins (set it behind a
    proxy so the snippet shows mcp.likeminds.io, not the internal bind); else derive it
    from the request."""
    base = os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)
    return base.rstrip("/")


def _json_body(coro_result) -> dict:
    return coro_result if isinstance(coro_result, dict) else {}


async def _send_otp(request: Request) -> JSONResponse:
    if not config.USE_MONGO:
        return JSONResponse({"ok": False, "error": "Login is not configured on this server."}, status_code=503)
    try:
        body = _json_body(await request.json())
    except Exception:  # noqa: BLE001 — malformed JSON
        return JSONResponse({"ok": False, "error": "Invalid request."}, status_code=400)
    email = str(body.get("email", "")).strip().lower()
    if not _EMAIL_RE.match(email):
        return JSONResponse({"ok": False, "error": "Enter a valid email address."}, status_code=400)
    try:
        await otp.send_otp(email)
        await db.get_or_create_user(email)
    except otp.OTPError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)
    except Exception:  # noqa: BLE001 — DB/other failure
        return JSONResponse({"ok": False, "error": "Could not start login. Please try again."}, status_code=500)
    return JSONResponse({"ok": True})


async def _verify_otp(request: Request) -> JSONResponse:
    if not config.USE_MONGO:
        return JSONResponse({"ok": False, "error": "Login is not configured on this server."}, status_code=503)
    try:
        body = _json_body(await request.json())
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Invalid request."}, status_code=400)
    email = str(body.get("email", "")).strip().lower()
    code = str(body.get("otp", "")).strip()
    if not _EMAIL_RE.match(email) or not code:
        return JSONResponse({"ok": False, "error": "Email and code are required."}, status_code=400)
    try:
        ok = await otp.verify_otp(email, code)
    except otp.OTPError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)
    if not ok:
        return JSONResponse({"ok": False, "error": "That code isn't valid. Please try again."}, status_code=400)
    try:
        token = await db.mark_verified(email)
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Could not issue your token. Please try again."}, status_code=500)
    if not token:
        return JSONResponse({"ok": False, "error": "Could not issue your token. Please try again."}, status_code=500)

    # OAuth login: an `lg` (the pending /authorize request id) means this page is the
    # OAuth authorization UI. Finish the handshake — mint the auth code bound to the
    # verified user and hand the client its redirect back. The page then navigates there.
    login_id = str(body.get("lg", "")).strip()
    if login_id:
        redirect = await oauth.complete_authorization(login_id, token)
        if not redirect:
            return JSONResponse(
                {"ok": False, "error": "This sign-in link expired. Restart the connection from your MCP client."},
                status_code=400,
            )
        return JSONResponse({"ok": True, "redirect": redirect})

    # Standalone login (manual header / fallback): hand back the stable token + config.
    return JSONResponse({
        "ok": True,
        "token": token,
        "header": config.USER_ID_HEADER,
        "mcp_url": _public_base(request) + "/mcp",
    })


async def _login_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_PAGE.replace("__HEADER__", config.USER_ID_HEADER))


def register(mcp) -> None:
    """Attach the login routes to the FastMCP app (served alongside /mcp)."""
    mcp.custom_route("/login", methods=["GET"])(_login_page)
    mcp.custom_route("/login/send-otp", methods=["POST"])(_send_otp)
    mcp.custom_route("/login/verify-otp", methods=["POST"])(_verify_otp)


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LikeMinds MCP — Sign in</title>
<style>
  :root{
    --bg:#0b0d12; --card:#141821; --edge:#242a37; --ink:#eef1f6; --mut:#9aa4b6;
    --brand:#6d5efc; --brand2:#4a8cff; --ok:#1f8a5b; --err:#e5534b; --code:#0e1118;
  }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f5f7fb; --card:#ffffff; --edge:#e4e8f0; --ink:#131722; --mut:#5a6474; --code:#f1f3f9; }
  }
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    background:radial-gradient(1200px 600px at 50% -10%, rgba(109,94,252,.18), transparent 60%),var(--bg);
    color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;padding:24px}
  .card{width:100%;max-width:460px;background:var(--card);border:1px solid var(--edge);
    border-radius:16px;padding:30px 30px 26px;box-shadow:0 20px 60px rgba(0,0,0,.28)}
  .brand{display:flex;align-items:center;gap:10px;margin-bottom:18px}
  .dot{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,var(--brand),var(--brand2))}
  .brand b{font-size:15px;letter-spacing:.2px}
  h1{font-size:20px;margin:2px 0 4px}
  p.sub{color:var(--mut);margin:0 0 20px;font-size:14px}
  label{display:block;font-size:13px;color:var(--mut);margin:14px 0 6px}
  input{width:100%;padding:11px 12px;border:1px solid var(--edge);border-radius:10px;background:transparent;
    color:var(--ink);font-size:15px;outline:none;transition:border-color .15s}
  input:focus{border-color:var(--brand)}
  button{width:100%;margin-top:16px;padding:11px 14px;border:0;border-radius:10px;cursor:pointer;
    font-size:15px;font-weight:600;color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand2))}
  button:disabled{opacity:.6;cursor:default}
  button.ghost{background:transparent;color:var(--mut);border:1px solid var(--edge);font-weight:500;margin-top:10px}
  .err{display:none;margin-top:14px;padding:10px 12px;border-radius:10px;background:rgba(229,83,75,.12);
    color:var(--err);font-size:13.5px;border:1px solid rgba(229,83,75,.3)}
  #step2{display:none}
  #result{display:none}
  .tokrow{display:flex;gap:8px;margin-top:6px}
  .tokrow input{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
  .copy{width:auto;margin:0;padding:0 14px;font-weight:500;background:var(--edge);color:var(--ink)}
  .snip{margin-top:16px}
  .snip .hd{display:flex;justify-content:space-between;align-items:center;margin:0 0 6px}
  .snip .hd span{font-size:12.5px;color:var(--mut)}
  .snip .hd button{width:auto;margin:0;padding:3px 10px;font-size:12px;font-weight:500;background:var(--edge);color:var(--ink)}
  pre{margin:0;padding:12px;background:var(--code);border:1px solid var(--edge);border-radius:10px;
    overflow:auto;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;line-height:1.45;color:var(--ink)}
  .done{display:flex;align-items:center;gap:8px;color:var(--ok);font-weight:600;font-size:14px;margin-bottom:4px}
  .hint{color:var(--mut);font-size:13px;margin:16px 0 0}
</style>
</head>
<body>
  <div class="card">
    <div class="brand"><div class="dot"></div><b>LikeMinds MCP</b></div>

    <div id="forms">
      <h1>Sign in</h1>
      <p class="sub">Verify your email to get your personal access token. Your custom skills are private to you.</p>

      <label for="email">Work email</label>
      <input id="email" type="email" autocomplete="email" placeholder="you@company.com"/>
      <button id="send">Send code</button>

      <div id="step2">
        <label for="otp">Verification code</label>
        <input id="otp" inputmode="numeric" autocomplete="one-time-code" placeholder="Enter the code we emailed you"/>
        <button id="verify">Verify &amp; get token</button>
      </div>

      <div id="err" class="err"></div>
    </div>

    <div id="result">
      <div class="done">✓ Verified</div>
      <h1>Your access token</h1>
      <p class="sub">Keep this private. Paste it into your MCP client config; it's stable, so you can reuse it.</p>

      <label>Token</label>
      <div class="tokrow">
        <input id="token" readonly/>
        <button class="copy" data-copy="#token">Copy</button>
      </div>

      <div class="snip">
        <div class="hd"><span>MCP client config (.mcp.json)</span><button data-copy="#json">Copy</button></div>
        <pre id="json"></pre>
      </div>

      <div class="snip">
        <div class="hd"><span>Or add it with the Claude Code CLI</span><button data-copy="#cli">Copy</button></div>
        <pre id="cli"></pre>
      </div>

      <p class="hint">Sends header <code>__HEADER__</code> on every request. Run <b>list_skills</b> to confirm you're signed in.</p>
    </div>
  </div>

<script>
  const $ = s => document.querySelector(s);
  let currentEmail = "";
  const LG = new URLSearchParams(location.search).get('lg') || '';  // OAuth pending-login id
  if (LG) { const s = document.querySelector('.sub'); if (s) s.textContent = 'Verify your email to connect your MCP client.'; }
  function showErr(m){ const e=$('#err'); e.textContent=m||''; e.style.display=m?'block':'none'; }
  function setBusy(sel,busy){ const b=$(sel);
    if(busy){ b.dataset.prev=b.textContent; b.disabled=true; b.textContent='…'; }
    else { b.disabled=false; b.textContent=b.dataset.prev||b.textContent; } }
  async function post(url,data){
    const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    let j={}; try{ j=await r.json(); }catch(e){}
    return { ok: r.ok && j.ok, data: j };
  }
  $('#send').addEventListener('click', async () => {
    showErr('');
    const email = $('#email').value.trim();
    if(!email){ showErr('Enter your email.'); return; }
    setBusy('#send',true);
    const {ok,data} = await post('/login/send-otp',{email});
    setBusy('#send',false);
    if(!ok){ showErr(data.error||'Could not send the code.'); return; }
    currentEmail = email;
    $('#step2').style.display='block';
    $('#send').textContent='Resend code';
    $('#otp').focus();
  });
  $('#verify').addEventListener('click', async () => {
    showErr('');
    const otp = $('#otp').value.trim();
    if(!otp){ showErr('Enter the code.'); return; }
    setBusy('#verify',true);
    const {ok,data} = await post('/login/verify-otp',{email:currentEmail,otp,lg:LG});
    setBusy('#verify',false);
    if(!ok){ showErr(data.error||'Invalid code.'); return; }
    if(data.redirect){ window.location.href = data.redirect; return; }  // OAuth: hand control back to the client
    render(data);
  });
  $('#otp').addEventListener('keydown', e => { if(e.key==='Enter') $('#verify').click(); });
  $('#email').addEventListener('keydown', e => { if(e.key==='Enter') $('#send').click(); });
  function render(d){
    const header = d.header || '__HEADER__';
    const url = d.mcp_url;
    $('#token').value = d.token;
    const cfg = {mcpServers:{likeminds:{type:'http',url:url,headers:{}}}};
    cfg.mcpServers.likeminds.headers[header] = d.token;
    $('#json').textContent = JSON.stringify(cfg,null,2);
    $('#cli').textContent = 'claude mcp add --transport http --scope user likeminds '+url+' --header "'+header+': '+d.token+'"';
    $('#forms').style.display='none';
    $('#result').style.display='block';
  }
  document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => {
    const el = document.querySelector(b.getAttribute('data-copy'));
    const text = (el.value!==undefined && el.tagName==='INPUT') ? el.value : el.textContent;
    navigator.clipboard.writeText(text).then(()=>{ const p=b.textContent; b.textContent='Copied'; setTimeout(()=>b.textContent=p,1200); });
  }));
</script>
</body>
</html>
"""
