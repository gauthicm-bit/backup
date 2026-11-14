# Handoffs log (append-only)

Every role appends here when something another role can use is ready, when a stub is replaced, and at every gate. Newest at the bottom. Never edit old entries.

Format:

```
## YYYY-MM-DD HH:MM · <from> → <to> · contract <version>
Ready: <what works, with contract §>
Stubbed: <what is still fake, and until when>
Gate: <Gate N PASS/FAIL — only for gate entries>
```

---

## 2026-11-14 · all · contract 1.0.0
Ready: AGENTS.md, docs/API_CONTRACT.md, docs/lifecycle/PERSON_{A,B,C}.md committed. Review contract §10 decisions at kickoff.
