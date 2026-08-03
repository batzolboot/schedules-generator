# WebTMS HTML Fixtures

These fixtures were collected during the 2026-08-02 WebTMS source investigation.

## Access boundary

The official application still redirects unauthenticated clients to Drexel Connect. The Phase 3B fixtures below were collected after one maintainer authenticated directly in a visible Playwright browser and were sanitized before being written here.

## Included fixtures

### `official_webtms_link_page.html`

A reduced fixture derived from the publicly accessible Drexel Registrar information page:

```text
https://drexel.edu/registrar/scheduling/scheduling-policies-and-procedures/webtms
```

It preserves only the page title, description, official WebTMS link, and public warning relevant to source discovery.

### `webtms_authentication_gate.html`

A synthetic reduction of the observed final browser state after navigating to:

```text
https://drexel.edu/webtms
```

It records that the navigation ended at Drexel Connect. It is not a copy of the CAS response.

## Sanitization

- Full downloaded pages are not stored.
- Cookies, session IDs, CSRF tokens, and execution parameters were removed.
- No credentials were entered or captured.
- No instructor or student information is present.
- The authentication fixture is deliberately synthetic and contains only the structural signal needed for an access-boundary test.

## Missing fixture coverage

The fixtures now cover term/college/subject navigation, a course list, an ordinary lecture, a lab component, a two-row lecture/final-exam schedule, and an asynchronous section. A true arranged/TBA section, recitation detail, cancellation/closed indicator, team-taught section, and authoritative component compatibility set remain unobserved.

### Authenticated sanitized fixtures

- `term_colleges_subjects_summer_quarter_2025_26.html`
- `computer_science_course_list_summer_quarter_2025_26.html`
- `cs_172_lecture_with_final_exam.html`
- `cs_172_lab.html`
- `cs_504_online_asynchronous.html`

## Authenticated fixture policy

Any fixture collected with the maintainer session must be sanitized before it
is written here. It must contain no cookies, tokens, CSRF values,
authentication headers, email addresses, or identifiable instructor names.
All meeting rows must remain present so multi-row sections are testable.
