# Landlord Tracker — Delivery & Distribution Plan

**Goal:** take Landlord Tracker from "working tarball on Rodrigo's desk" to a
publicly installable app (Flathub + Snap Store) and a first wave of real users,
without spending money and without changing the product's identity
(Linux-first, privacy-first, offline, free forever, donations only).

**Version this plan targets:** 0.2.0 (first public release; 0.1.x stays internal)

**Status:** plan only. No distribution work has been started.

---

## 1. Where we actually are

| Thing | State |
|---|---|
| App works, 111 tests pass | ✅ |
| One-step tarball installer, verified in a sandbox HOME | ✅ |
| Screenshots rendered from real code (`artifacts/screenshots/`) | ✅ |
| README + GPL-3.0 LICENSE | ✅ exists |
| Git repository | ❌ none (`fatal: not a git repository`) |
| `gh`, `snapcraft`, `flatpak`, `flatpak-builder` | ❌ not installed |
| AppStream metainfo XML (required by both stores) | ❌ missing |
| Flathub manifest / snapcraft.yaml | ❌ missing |
| Public repo, issue tracker, release page | ❌ none |

**Blocker that is not technical:** every store path needs an account that only
Rodrigo can create. I will not register accounts, claim an app name, or invent a
contact address on his behalf. Plan assumes he does those steps when asked.

---

## 2. Decisions needed from Rodrigo first

1. ~~**App ID / reverse-DNS name.**~~ **DECIDED 2026-09-26 —
   `io.github.snatner.LandlordTracker`.** GitHub route, *not* the `sipsats.com`
   domain: Flathub accepts `io.github.*` for small apps, it is free, and it needs
   no domain he has to keep renewing. Verified with him that `github.com/snatner`
   is his (created Aug 2018, empty). One-way door: the ID is permanent once
   published.
2. ~~**GitHub account + repo name.**~~ **DECIDED — `snatner/landlord-tracker`**,
   public, GPL-3.0. The account already exists, so **no new account and no new
   email are needed for GitHub**; whatever address is on that account stands.
3. **Donations:** Ko-fi URL exists in `context.py` as a placeholder. Register
   the real page (or drop the buttons) before launch, or the UI advertises a
   dead link.
4. ~~**Feature-request email.**~~ **DECIDED 2026-09-26 — `landlordtracker@posteo.us`**,
   a dedicated Posteo alias created for this app (Posteo allows 3 free aliases,
   25 total). Shipped in `context.py` and verified in the rendered screenshot.
   Do **not** plan to rotate it: a deleted alias stays blocked for 6 years and
   the owner can re-add it, but post to a deleted alias **bounces** and shipped
   copies cannot be recalled. Still outstanding on this front: the Ko-fi and
   Buy Me a Coffee URLs are unconfirmed, and `README.md` advertises a *different*
   Ko-fi slug (`/landlordtracker`) than `context.py` (`/snatner1337`).
5. **Launch shape:** quiet (Flathub listing only) vs public push (Reddit/HN
   wave). Recommend quiet first, then one push once a few real users have
   confirmed it works on their machines.

---

## 3. Phase 0 — Finish and freeze the app

Do not submit a moving target: both stores review a specific build, and Flathub
re-checks nothing on updates but reviewers do judge a "not fully functional"
first impression.

- [ ] Finish the pending friction work (create-the-repeat from the add-expense
      form, one-click catch-up, sidebar pending badge).
- [ ] Add the AppStream metainfo file **upstream** (Phase 2) so listing text
      lives with the code.
- [ ] Freeze features; only bug fixes until the first store build passes.
- [ ] Bump to `0.2.0` and cut a tarball as the "known good" fallback.

**Verification:** `106 + N tests pass`, sandbox install launches, screenshots
re-rendered (the harness now uses a fresh data dir per run).

---

## 4. Phase 1 — Git + GitHub (needs his account)

```bash
cd ~/landlord-tracker
git init
git add -A
git commit -m "feat: initial public release of Landlord Tracker"
git branch -M main
git remote add origin git@github.com:<his-user>/landlord-tracker.git
git push -u origin main
```

Prep I can do without his account:

- [ ] `.gitignore` — must exclude `.venv/`, `dist/releases/`, `__pycache__/`,
      `.pytest_cache/`, and **any local database or real tenant data**.
      *This is the single highest-risk file in the whole plan: a committed
      `landlord.db` would publish real tenant names and rents permanently.*
- [ ] `README.md` — already strong; add install-from-Flathub section once live,
      plus a screenshot table and the privacy statement.
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant),
      `.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml`
- [ ] Release checklist in `docs/releasing.md`
- [ ] Tag the release: `git tag -a v0.2.0 -m "Landlord Tracker 0.2.0"`
- [ ] Optional: GitHub Actions running `pytest` on push (free for public repos)

**Security check before first push:**

```bash
git log --all -p | grep -iE 'api[_-]?key|secret|password|token' | head
git ls-files | grep -iE '\.db$|\.env$|credential' || echo "clean"
```

---

## 5. Phase 2 — AppStream metainfo (required by both stores)

Without this file neither GNOME Software nor KDE Discover can show the app, and
Flathub will not accept the submission. It also drives curation and promotion
decisions, so quality here buys visibility later.

Deliverable: `src/landlord_tracker/resources/io.github.snatner.LandlordTracker.metainfo.xml`

Required content:

- `<id>`, `<name>`, `<summary>` (short), `<description>` (long, `<p>` blocks)
- `<developer id="io.github.snatner">` with a name
- `<metadata_license>CC0-1.0</metadata_license>` and
  `<project_license>GPL-3.0-or-later</project_license>`
- `<launchable type="desktop-id">io.github.snatner.LandlordTracker.desktop</launchable>`
- `<screenshots>` — Flathub wants real, current screenshots. We already generate
  them from real code; host them in the repo so they cannot go stale.
- `<url type="homepage|bugtracker">`
- `<releases>` with at least the current version + date
- `<content_rating type="oars-1.1"/>` (expect `none` on every category)
- `<categories><category>Office</category><category>Finance</category></categories>`
- `<keywords>`, `<branding>` (icon colours, optional)
- PT translations via `xml:lang="pt"` — the app already ships EN + PT-PT, so do it.

Also needed: rename the `.desktop` entry to `io.github.snatner.LandlordTracker.desktop`
and add `X-AppStream-ID` consistency, then update `StartupWMClass` to the new stem
(the dock-association invariant from v0.1.8 — the regression test will catch a
mismatch).

**Verification:**

```bash
appstreamcli validate --explain <file>.metainfo.xml
```
Expected: passes with no errors (warnings about missing optional fields are OK).

---

## 6. Phase 3 — Flathub

**The PySide6 path is solved, do not invent it:** the Qt Company publishes
`io.qt.PySide.BaseApp` on Flathub, built on `org.kde.Platform` 6.x, which exists
precisely so PySide6 apps can be packaged without downloading wheels at build
time. Manifest targets that BaseApp.

Constraints learned from the docs and packaging threads:

- **Builds must be offline.** Granting network access so the build can `pip
  install PySide6` gets the submission sent back. Use the BaseApp's PySide6.
- `openpyxl` must be vendored as a module (pre-built locally, no network) or the
  JSON export path trimmed on Flatpak. Decide during the manifest spike.
- No `flatpak-builder` on this box yet; Flathub's own guidance is to build with
  `org.flatpak.Builder`.
- **Read Flathub's Generative AI policy before submitting.** The submission page
  links it as an explicit prerequisite, and this app was built with AI
  assistance. Read it, follow it, and disclose accurately if it asks for that.
  Do not guess at its contents.
- Submissions are judged on completeness: "not fully functional or easily visible
  issues at submission" is a rejection reason.

Task list:

- [ ] `packaging/flatpak/io.github.snatner.LandlordTracker.yml` (manifest, offline build)
- [ ] Spike: build it locally with `org.flatpak.Builder`, confirm the window
      opens and the SQLite file is written inside the sandbox home
- [ ] `flatpak run` smoke test incl. a file-import and a backup round trip
- [ ] `flatpak-builder-lint` clean
- [ ] Fork `flathub/flathub`, branch, PR with the manifest
- [ ] Respond to reviewer feedback

**Expect:** days-to-weeks of human review, possible change requests. The tarball
remains the primary channel until this lands, so nothing is blocked on it.

---

## 7. Phase 4 — Snap Store (needs Ubuntu One account)

Snaps are the natural second target because the app is aimed at Ubuntu.

- [ ] `snapcraft login` (his Ubuntu One account) then
      `snapcraft register landlord-tracker` — the name is first-come, register
      early, it is free. Note: `landlord-tracker` may be taken; have a fallback.
- [ ] `snap/snapcraft.yaml`: `base: core24`, `confinement: strict`,
      `grade: stable`, `adopt-info`, and the **`kde-neon-6` extension** for
      Qt6/PySide6, with the `desktop-launch6` command chain — this is the
      documented KDE/Snapcraft pattern for Qt6 desktop apps. Requires
      `build-base`/`build-packages` for the venv build and bundle PySide6 into
      the snap payload.
- [ ] Plugs: `home` (user documents), and nothing else. No `network` needed —
      the app makes zero network calls, which is worth stating in the listing.
- [ ] `desktop:` entry + icon from the same SVG.
- [ ] Build locally (`snapcraft` — not installed yet) and test with
      `snap install --dangerous` before uploading.
- [ ] `snapcraft upload --release=stable`.

**Confirmation nuance:** strict-confinement file access to arbitrary user paths
needs the `home` interface, which auto-connects. Verify the document vault and
export dialogs actually work inside the confined snap — sandbox surprises here
are common, and this is where "it worked as a tarball" stops being evidence.

---

## 8. Phase 5 — Spreading the word, for free

Sequence matters more than volume. A store listing with no context converts
badly; a link drop into a dozen subreddits gets you banned and no users.

### 5a. Get the boring foundations right (free, high leverage)

- [ ] Flathub listing complete: good summary, real screenshots, PT translation,
      OARS rating, releases populated. This is the page most people will land on.
- [ ] GitHub repo with a README that answers, in the first screen: what it does,
      who it is for, that it is offline/no-account, and how to install.
- [ ] `AlternativeTo` entry ("alternative to Excel/Google Sheets for rental
      tracking", alternatives: Landlordy, Stessa, Rentec). Free, permanent, and
      it ranks in search for exactly the intent we want.
- [ ] A one-page site or a `sipsats.com` subpath with the same copy. He owns the
      domain; a static page is enough.
- [ ] Ask to be listed in "awesome" lists and Linux app directories
      (`awesome-linux`, `awesome-selfhosted` only if it genuinely fits, Flathub's
      own category pages).

### 5b. Communities — respect the rules or lose the account

Reality check from current rule surveys: self-promotion is banned outright in
roughly 39% of the subreddits founders target, and another ~22% allow it only
under the informal 9:1 rule (nine genuine contributions per promotional post).
So: **read each community's sidebar/rule page immediately before posting**, and
prefer showing up as a participant first.

Ordered by fit for a privacy-first, offline, small-landlord tool:

1. **Portuguese landlord/finance communities** — smallest reach, highest intent,
   and he can speak to it authentically in PT-PT. Start here.
2. **r/linuxapps, r/linux, r/Ubuntu, r/gnome** — only after the Flathub listing
   exists, and only if framed as "made this for Linux, free/offline". These
   dislike marketing tone and reward technical detail.
3. **r/selfhosted** — genuinely on-topic: "no server, no cloud, one SQLite file
   you own" is the community's whole ethos. High engagement, technical audience,
   ~36 posts/day so timing matters.
4. **r/privacy** — the offline/no-telemetry angle is the pitch. Must be framed
   as a privacy argument, not a product ad.
5. **r/SideProject, r/somethingimade, r/opensource** — explicitly built for
   promotion posts; lower quality traffic but zero rule risk.
6. **Hacker News "Show HN"** — one shot, high variance, needs a genuinely
   interesting technical angle (offline-first, single-file SQLite, local-first
   for a boring domain). Must be present in the thread all day to answer.
7. **Lemmy (selfhosted/linux communities) and Mastodon (#Linux, #FOSS)** — small
   but positive and durable; a post keeps being seen, unlike Reddit.
8. **Linux YouTube / newsletter coverage** — a short, honest email to 5–10
   small-to-mid Linux channels with a screenshot and a Flathub link. Do not
   mass-blast; pick people who actually cover open-source apps.
9. **Product Hunt** — optional, weak fit for a Linux-only utility.

**Rules of engagement (non-negotiable):**

- One community at a time, spaced out; never the same copy pasted twice.
- Lead with the problem and the constraint, not the feature list.
- Disclose it is his app. Every community's rule that exists, exists for that.
- Never argue with criticism; fix what is fair, thank people for the rest.
- Do not put the app behind an email capture or a "roadmap" tease. It is free.
- No fake accounts, no vote solicitation, no review farming.

### 5c. Templates

Draft posts, one per community, written in his own voice and in PT-PT where
relevant. I will write these on request — do not reuse one post across
communities.

---

## 9. Phase 6 — After launch

- [ ] Triage issues weekly; the in-app feature-request button should point at a
      live channel by then.
- [ ] Wire the real donation destination, or remove the buttons.
- [ ] Keep the tarball channel alive for people whose distro is not Flathub-enabled.
- [ ] Tag every release; Flathub updates are automatic from a tracked tag.
- [ ] Watch for the honest signal: repeat users and unsolicited "this replaced my
      spreadsheet" comments. Absence of that after a few weeks means the pitch,
      not the app, needs work.

---

## 10. Risks and honest caveats

| Risk | Impact | Mitigation |
|---|---|---|
| Committing a real `landlord.db` or tenant data to a public repo | **Severe, irreversible** | `.gitignore` first, then a secret/DB scan before the first push |
| Flathub Generative AI policy | Submission blocked | Read it before writing the manifest; comply; disclose accurately |
| Offline-build rule for PySide6 | Flathub rejection | Use `io.qt.PySide.BaseApp`; verify build with no network |
| Snap confinement breaks file dialogs | Snap unusable | Test `--dangerous` lokally before upload |
| App ID / snap name taken or wrong | Permanent ID mistake | App ID decided: `io.github.snatner.LandlordTracker`. Register the snap name early — `landlord-tracker` may be taken, have a fallback |
| Reddit rules differ per sub | Bans, wasted effort | Read rules immediately before each post; 9:1 norm |
| Store review delay | No user-visible progress | Tarball stays primary; launch nothing on store timing |
| Donation/email placeholders ship | Looks broken, breaks trust | Resolve both before the public build |

---

## 11. Sequencing summary

```
Phase 0  finish + freeze (me)
Phase 1  git + GitHub                    (needs his account)   ─┐
Phase 2  AppStream metainfo              (me)                   │ parallel
Phase 3  Flathub manifest + PR           (needs his GitHub)     │
Phase 4  Snap build + registration       (needs his Ubuntu One) ┘
Phase 5  launch wave, community by community (after Flathub is live)
Phase 6  maintain, donate, iterate
```

Nothing in Phases 1–4 needs to wait on the others except the GitHub account,
and the tarball keeps working throughout.
