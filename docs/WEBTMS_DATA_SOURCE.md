# WebTMS Data Source Investigation

## Status

Investigation date: 2026-08-02

Phase 3B update: the maintainer subsequently authorized one interactive
Drexel login and MFA session. Playwright storage state is local and ignored;
the repository contains only sanitized course-data fixtures. The original
unauthenticated Phase 3A findings below remain useful evidence for why the
browser boundary is required. Confirmed authenticated routes and HTML details
are documented in `WEBTMS_AUTHENTICATED_CLIENT.md` and
`WEBTMS_FIELD_MAPPING.md`.

The official Drexel WebTMS link currently leads to a Drexel Connect (CAS) authentication boundary. Normal HTTP requests and an ordinary browser session both reach the same sign-in page. No authentication was attempted, and no protected course-schedule pages were collected.

This stage therefore confirms the current entry and access flow, but it cannot yet confirm the term, department, course, section, or meeting HTML structure. Importer implementation should remain blocked until Drexel provides a public endpoint, permits authenticated access for this use, or the project receives permitted sanitized fixtures.

## Confirmed URLs and navigation

The official information page is:

```text
https://drexel.edu/registrar/scheduling/scheduling-policies-and-procedures/webtms
```

It describes WebTMS and links to:

```text
https://drexel.edu/webtms
```

The short link currently follows this redirect flow:

```text
https://drexel.edu/webtms
  → https://termmasterschedule.drexel.edu
  → https://termmasterschedule.drexel.edu/webtms_du/
  → https://connect.drexel.edu/cas/login?service=...
  → https://connect.drexel.edu/idp/profile/cas/login?execution=...
```

The historically documented application URL does not bypass the boundary:

```text
https://termmasterschedule.drexel.edu/webtms_du/app
  → https://termmasterschedule.drexel.edu/webtms_du/
  → Drexel Connect
```

The direct `/app` attempt ended on a Drexel Connect error page after redirection. This does not expose any WebTMS application HTML.

## HTTP behavior

- Plain HTTPS requests are sufficient for the public Drexel information page.
- Plain HTTPS requests are not currently sufficient for term or course data because CAS intercepts the WebTMS application.
- The WebTMS host sets a `JSESSIONID` cookie before redirecting to CAS.
- Drexel Connect sets its own `JSESSIONID` and presents a form with an execution-specific URL and CSRF token.
- These are authentication parameters, not WebTMS navigation parameters, and must not be replayed or automated by this project.
- No CAPTCHA, rate-limit response, or robots denial was encountered.
- Browser automation was used once, only after HTTP demonstrated the barrier. It confirmed the same sign-in page. No button was clicked and no credentials were entered.

## Request discipline

All scripted requests used this descriptive user agent:

```text
DrexelScheduleGenerator-Portfolio/0.1 (WebTMS source investigation; contact via repository maintainer)
```

Requests were separated by three-second delays. No term, college, department, or course crawl was attempted. No URL was repeatedly downloaded except one retry of the public information page after PowerShell's HTTP client failed before returning a response.

## Investigation checklist

| Topic | Result |
| --- | --- |
| Current WebTMS base URL | Confirmed official short link and WebTMS host; application is CAS-protected |
| Quarter and semester term lists | Not observable without authentication |
| Term codes and names | Not observable |
| Colleges and departments | Not observable |
| Course-page navigation | Not observable |
| Section HTML | Not observable |
| Separate section-detail requests | Not observable |
| CRN availability and term uniqueness | Not observable from current public pages |
| Course subject, number, title, credits | Not observable |
| Section number and component | Not observable |
| Instructor information | Not collected |
| Meeting days, times, dates, building, room | Not observable |
| Instructional method and campus | Not observable |
| Asynchronous/arranged representation | Not observable |
| Lecture/lab/recitation relationships | Not observable |
| Cross-listed sections | Not observable |
| Cancellation/closed indicators | Not observable |
| Data last-updated value | The public information page tells users to check it, but does not expose the schedule's value |
| Pagination | Not observable |
| WebTMS forms/hidden parameters | Not observable; only CAS authentication parameters were seen |
| Cookies | WebTMS and CAS session cookies observed during redirects |
| HTML consistency | Cannot be assessed without representative course pages |

## Stable identifiers

No course-data identifier was confirmed in the accessible HTML. In particular, this investigation cannot yet establish:

- whether CRN is present;
- whether CRN is unique within a term;
- whether term, college, department, course, section, instructor, or meeting records have separate source IDs;
- whether identifiers are encoded in URLs, forms, hidden inputs, or table cells.

The database should continue to preserve source identifiers when available and use documented composite fallbacks only after permitted fixtures establish their semantics.

## Fixture outcome

Only two reduced, non-sensitive fixtures were added:

- `official_webtms_link_page.html` captures the public official link contract.
- `webtms_authentication_gate.html` captures the fact that protected application access ends at Drexel Connect.

No raw CAS page, cookies, CSRF value, execution token, instructor name, or protected schedule content is stored. Course, multi-component, asynchronous, and multiple-meeting fixtures remain unavailable.

## Live request ledger

Top-level live source attempts:

1. `https://drexel.edu/registrar/scheduling/scheduling-policies-and-procedures/webtms` — PowerShell client failed internally before returning status or content.
2. `https://drexel.edu/registrar/scheduling/scheduling-policies-and-procedures/webtms` — retry with curl; HTTP 200.
3. `https://drexel.edu/webtms` — HTTP redirect chain ending at Drexel Connect; final HTTP 200.
4. `https://termmasterschedule.drexel.edu/webtms_du/app` — HTTP redirect chain ending at Drexel Connect error; final HTTP 500.
5. `https://drexel.edu/webtms` — one browser navigation to verify the access boundary; ended at Drexel Connect.

One separate search-engine query restricted to `drexel.edu` was used to discover the official information page. It was not a WebTMS course-data request.

Count summary:

- 5 top-level direct/browser source attempts, including the failed client attempt and one justified retry.
- 1 discovery search query.
- Redirects caused additional HTTP transactions within attempts 3–5; their destinations are described above, but execution-specific CAS URLs are intentionally not preserved.

## Required next decision

Before further source work, choose one of these paths:

1. Ask Drexel whether WebTMS has an approved public feed or supported integration endpoint.
2. Provide permitted, sanitized WebTMS term/course HTML captured by an authorized user for offline parser development.
3. Explicitly authorize investigation using an authenticated session and define what protected data may be retained. Even with authorization, credentials, cookies, CSRF tokens, and unsanitized personal data must never enter the repository.

The recommended path is an approved public feed or permitted sanitized fixtures.
