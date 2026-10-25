# Manual browser and responsive checks

Use this checklist before changing the templates, CSS, browser scripts or form
behavior. It covers the home page and a saved paste, using free browser tools.
It is a focused smoke check, not a claim of full WCAG compliance or support for
every browser/device.

## Prepare a disposable session

Use a fresh checkout and its Python environment (`pip install -r requirements-dev.txt`).
Keep test data separate from your real Docker volume. For example, in PowerShell:

```powershell
$env:DATA_DIR = Join-Path $env:TEMP ('lan-paste-review-' + [guid]::NewGuid().ToString('N'))
$env:PASTE_ADMIN_TOKEN = 'local-review-only'
python -m flask --app app run --host 127.0.0.1 --port 8000
```

Or in a POSIX shell:

```sh
DATA_DIR="$(mktemp -d)" PASTE_ADMIN_TOKEN=local-review-only \
  python -m flask --app app run --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. This local development server is for the check only;
keep it bound to loopback, and stop it with Ctrl+C afterward. Do not run cleanup
commands against a real deployment or volume. Use invented text, not credentials,
private paste contents or an actual admin token.

Create a fixture containing:

- A recognizable title, such as `Responsive check`.
- A short first line, a single unbroken line of at least 250 characters, and a
  long URL such as `https://example.invalid/` followed by repeated path segments.
  These are text fixtures; do not navigate to the URL.
- At least 60 further lines, so the detail page needs vertical scrolling.

Keep the expected text in a local scratch editor for the clipboard comparison.
Repeat the title check with a long title (up to the input's 120-character limit)
when changing title/layout styles.

## Viewport and theme matrix

Use browser DevTools' responsive/device mode (built into Chrome, Edge and Firefox),
or resize the content viewport. Set dimensions in **CSS pixels**, not the outer
window size. Start at 100% browser zoom and record any additional zoom checks.

| Width × height | Purpose | Home | Paste detail |
| --- | --- | --- | --- |
| 1280 × 900 | Wide desktop | light + dark | light + dark |
| 768 × 900 | Tablet / narrow laptop | light + dark | light + dark |
| 390 × 900 | Typical narrow mobile viewport | light + dark | light + dark |
| 320 × 900 | Small-width boundary | light + dark | light + dark |

For each cell, check the page at the top and after scrolling to the bottom:

- [ ] No whole-page horizontal scrolling, overlapping panels or clipped controls.
- [ ] Headings, timestamps, paste IDs and long titles remain readable; wrapping
  is acceptable. The theme text/self-hosted badge may disappear on narrow screens;
  the theme control must still have a meaningful accessible name.
- [ ] Inputs and the expiration selector fit their panel. The save/copy buttons
  remain reachable. Narrow form controls may stack vertically.
- [ ] Recent-paste cards contain their previews and can be opened.
- [ ] The long line/URL stays within the code panel by wrapping or internal
  scrolling, without widening the page. No text disappears from the stored paste.
- [ ] The footer/back link remains reachable after the large block.
- [ ] Text and focus indicators are visible in both themes, with no obvious
  unreadable foreground/background combinations. This visual check does not
  measure contrast ratios.

## Browser workflows and keyboard checks

1. **Create and open:** enter the fixture, choose an expiration, and save. Expect
   a detail page with the correct title and exact content. Follow the new-paste
   link, then reopen the same fixture from Recent pastes. Record any lost or
   changed text; do not mistake wrapped display lines for changed stored data.
2. **Theme:** activate the theme toggle with both pointer and keyboard. Expect
   the palette and the control's action name to change. Reload, follow a link to
   the other page, and reload again; the selected theme should persist. Record
   browser storage restrictions separately if preference storage is unavailable.
3. **Copy:** activate Copy content using Enter or Space when focused. Expect a
   visible success message, then paste into the local scratch editor and compare
   the complete text. If permission fails, expect the fallback message rather
   than silent failure. A success message alone does not verify clipboard bytes;
   record the actual paste comparison, or mark it **not verified**.
4. **Validation:** submit empty Content and inspect the browser's required-field
   feedback. Then submit spaces only (which can pass native required validation).
   Expect a readable application error, with Save available for correction. Correct
   the content and submit again; expect successful navigation, not a stuck button.
5. **Keyboard:** starting at the page's first control, use Tab/Shift+Tab through
   the theme toggle, form fields, expiration selector, Save and recent-paste links.
   On the detail page, reach theme, New paste, Copy and the back link. Expect a
   logical order, visible focus, working keyboard activation and no focus trap.
6. **Status semantics:** inspect the create/copy status areas in browser
   accessibility tools: they should be status/live regions, not color-only
   feedback. If testing with a screen reader, record its name and the actual
   announcements; do not report announcement coverage from markup inspection alone.

A reproducible clipped button, page-level overflow, lost content, unreachable
keyboard action, missing focus indicator, incorrect theme persistence, or silent
failure is a failed check. Record it separately with exact steps and viewport;
do not expand a documentation-only PR into an unrelated redesign.

## Record results

Copy this into your PR description or a local report; omit tokens/private data:

```text
Commit/base:
OS; browser/version (or version not captured):
Viewport sizes (CSS px); zoom; physical device or desktop emulation:
Fixture used (invented data only):
Case | Page | Viewport | Theme | PASS / FAIL / NOT VERIFIED | Notes
Create/open:
Theme toggle/reload/navigation:
Copy feedback and exact pasted-text comparison:
Empty/whitespace error and retry:
Keyboard order/activation/focus:
Long text/URL and top-to-footer scrolling:
Status markup / actual screen-reader announcements:
Other browsers/devices or checks not exercised:
```

Keep failures and unverified checks visible. A desktop responsive viewport is not
proof of a physical touch device, Safari behavior or complete accessibility.
