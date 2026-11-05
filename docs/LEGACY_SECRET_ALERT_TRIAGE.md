# GoreeCloud Search — Historical credential alert triage

**Incident status:** Owner/security verification required; **not resolved** by this document.  
**Observed evidence:** GitHub email dated 2026-11-01, subject `[GoreeCloud/search] Possible valid secrets detected`, pointing to [secret scanning alert #1](https://github.com/GoreeCloud/search/security/secret-scanning/1).

The notification identifies a match in a historical recovery-era Search source path (`searx/engines/youtube_noapi.py`, line 32). It is **not evidence that the new original implementation contains this code**, and it must not trigger reuse, checkout or import of the old recovery tree. The previously rejected recovery PR #1 remains closed/unmerged.

The alert status, credential validity, provider owner, historical access, and actual revocation/rotation are **not independently confirmed**. Closing a pull request or deleting a branch does not by itself invalidate an exposed token or remove publicly reachable Git history.

## P1 owner/security remediation procedure

1. An authorized repository security administrator should open the GitHub alert in the authenticated security UI, determine the credential type, scope, owner and exposure window **without pasting or reproducing the value** into tickets, chats, logs or source.
2. The credential owner should revoke/rotate any valid exposure using the source provider's account interface; review last-used/abuse/audit logs and ensure no downstream configurations still rely on the revoked value.
3. Assess public repository history retention and security implications through approved non-destructive processes. Any public history rewrite, credential change or production configuration update requires explicit risk review and appropriate approval.
4. Only then verify remediation and update alert disposition, documentation and Todoist evidence. Do **not** mark the alert resolved based on this email alone.

This security item is independently tracked as a high-priority Todoist task. Draft [greenfield PR #2](https://github.com/GoreeCloud/search/pull/2) excludes legacy recovered code and remains unmerged. Never use this document as evidence of credential rotation.
