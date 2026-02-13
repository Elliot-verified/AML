# Launching the Streamlit app for other users

A practical path from "just me" to "multiple users" without overbuilding at the start.

---

## Where you are now

- One Streamlit app; one run at a time; no auth; fine for you and maybe a couple of colleagues on a shared VM or your laptop.

---

## Stage 1: Share with a few users (simplest)

**Goal:** Colleagues or a small group can open a URL and use the app.

**Options (pick one):**

| Option | Effort | Best for |
|--------|--------|----------|
| **Streamlit Community Cloud** | Low: push to GitHub, connect at share.streamlit.io | Demos, &lt;~10 users, light use. Free tier has RAM limits; heavy runs may fail or need paid. |
| **Single cloud VM** | Medium: rent a VM, run `streamlit run ... --server.address 0.0.0.0`, open port or use SSH tunnel | Full control, same heavy pipeline as local. One run at a time unless you add a queue. |
| **Hugging Face Spaces** | Low: deploy Streamlit app to a Space | Community-facing, free tier; same RAM/CPU limits as Streamlit Cloud. |

**Recommendation for Stage 1:** Use a **single VM** (e.g. GCP e2-standard-4 or similar) so you keep the exact same stack (PepMLM, MetaLATTE) and avoid rewriting for Hugging Face–only models. Put the app behind a **reverse proxy** (nginx or Caddy) with HTTPS; optionally add **HTTP basic auth** or a simple password so only your group has the URL. Details are in `CLOUD_RUN.md` (Option 2).

**Limitation:** One pipeline run at a time. If User B clicks "Run" while User A’s run is still going, they either wait or you see conflicts. For a handful of users that’s often acceptable.

---

## Stage 2: Auth + slightly more users

**Goal:** Only authorized people can use the app; maybe 10–30 users.

- **Auth:** Use Streamlit’s built-in [secrets](https://docs.streamlit.io/develop/concepts/configuration#secrets-management) and a simple password or list of allowed tokens in the sidebar; or put the app behind **OAuth** (e.g. nginx + oauth2-proxy, or a provider like Auth0) so users log in with Google/GitHub.
- **Hosting:** Still one VM (or one container on Cloud Run / Railway / Render). Give the app more RAM/CPU if needed.
- **Runs:** Still effectively one at a time unless you add a queue (Stage 3).

---

## Stage 3: Multiple users, many runs (queue + workers)

**Goal:** Many users can submit runs without blocking each other; each gets a "job" and results when ready.

**Architecture:**

1. **Front-end:** Keep Streamlit (or replace with a small React/Vue app) so users set parameters and click "Run."
2. **Back-end API:** e.g. **FastAPI** that accepts pipeline config (JSON), creates a **job** (e.g. in a DB or Redis), returns a `job_id`.
3. **Worker(s):** Separate process(es) that pull jobs from a **queue** (Celery + Redis, or RQ, or a simple DB-backed queue), run `run_pipeline(cfg)`, and write outputs to **object storage** (S3, GCS) or a shared filesystem.
4. **Front-end:** Polls "is job X done?" and shows a download link for the result (signed URL or stored path).

Then you can scale by adding more workers or bigger VMs; the app no longer blocks on the pipeline.

**When to do this:** When a single process and "one run at a time" becomes a real bottleneck (e.g. &gt;5–10 active users or long queues).

---

## Suggested path forward

1. **Now → next few months:** Deploy the **current Streamlit app on one cloud VM** (Stage 1). Use `CLOUD_RUN.md` Option 2. Add nginx + HTTPS and optional basic auth so only your team has the URL. No code changes to the pipeline.
2. **When you need access control:** Add simple auth (Streamlit secrets or OAuth in front of the app) — Stage 2.
3. **When one-run-at-a-time hurts:** Introduce an **API + job queue + worker** and point the Streamlit app at "submit job" and "poll + download" instead of calling `run_pipeline()` in the same process — Stage 3.

Keeping the **same Streamlit UI** and **same `pipeline_runner.run_pipeline()`** through Stage 1 and 2 keeps the path forward simple; only Stage 3 requires a separate backend and worker design.

---

## Summary

| Stage | What you do | Good for |
|-------|-------------|----------|
| **1** | One VM (or Streamlit Cloud), share URL, optional nginx + basic auth | Small team, few concurrent users |
| **2** | Add proper auth (OAuth / secrets) on the same deployment | 10–30 users, need to restrict access |
| **3** | API + job queue + workers + result storage | Many users, many concurrent runs |

**Best path forward for "launch for other users" right now:** Deploy the existing app to a **single cloud VM**, put it behind HTTPS (and optional auth), and share the URL. Evolve to Stage 2 or 3 only when you hit real limits.
