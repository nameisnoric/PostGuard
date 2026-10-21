# PostGuard TOR Traceability — Desktop Scope

This document records the implementation scope extracted from `ToR.pdf` and
uses `Proposal (1).pdf` only to clarify the selected desktop architecture.

## Requirement priority

1. The TOR is the primary source for required behavior and acceptance.
2. The proposal clarifies implementation details where the TOR is ambiguous.
3. The current product is a Desktop Application. The proposal specifies
   Python, PySide6, FastAPI, JWT, Argon2, Resend and PostgreSQL/Supabase.
4. Camera preparation, posture detection, temporal tracking, prototype risk,
   blink analysis and alert persistence are connected in the local desktop
   pipeline. The current 0-3 risk value is an engineering prototype, not a
   Full RULA score or clinical diagnosis.
5. Authentication uses the existing email/password flow and accepts only
   `@ku.th` email addresses. Google OAuth is not in the current scope.
6. Existing email and password validation rules are frozen for the current
   phase and must not be changed.

## Desktop requirements from the TOR

### Authentication and user accounts

- Register with a unique `@ku.th` email through the existing email/password
  flow.
- Require matching password confirmation.
- Enforce a password longer than eight characters with uppercase, lowercase,
  number and special character requirements.
- Store only an Argon2 password hash.
- Login and logout with clear invalid-credential feedback.
- Reset a forgotten password with a single-use, expiring email OTP.
- Allow the user to change username, full name and profile photo.
- Allow the user to request account deletion.
- Put a deletion request in `PENDING_DELETION` for 14 days.
- Block normal application use while deletion is pending.
- Allow account recovery within 14 days after confirmation.
- Permanently remove the account and related data after the waiting period.

### Privacy and consent

- Show a Privacy Notice before camera-based processing starts.
- Request camera permission explicitly.
- Process camera frames for the stated purpose only.
- Do not persist or upload monitoring images or video.
- Store only necessary session, event, duration and report data.
- Store the user's consent status and allow consent to be reviewed or
  withdrawn.

### Desktop application behavior

- Keep an active session running when the window is minimized.
- Pause only after the user explicitly selects Pause.
- Resume the same session after an explicit Resume.
- Stop the camera and end the session after an explicit Stop.
- Show camera access and availability errors clearly.
- Provide history and reports for the signed-in user.
- Provide a Dashboard with historical usage information.
- Provide Settings stored per user, including notification enablement, sound,
  volume and reminder/break interval.
- Show a non-blocking in-app popup when a new posture alert is created; sound
  remains optional and follows the user's notification settings.

### Required architecture

- Desktop UI: Python and PySide6.
- Backend API: FastAPI.
- Authentication: JWT and Argon2 password hashes.
- Password reset delivery: Resend.
- Production sender identity: `PostGuard <no-reply@postguardapp.xyz>` after
  `postguardapp.xyz` is verified in Resend.
- Persistence: PostgreSQL hosted through Supabase.
- Camera processing remains on the user's device; only calculated results and
  required records are sent to the backend.

## Current implementation gap

| TOR area | Status | Remaining work |
| --- | --- | --- |
| Register, login and logout | Implemented | Keep the current `@ku.th` email/password flow |
| Password reset with OTP | Implemented; live delivery confirmed on 20 October 2026 | Complete one manual OTP flow through the Desktop UI |
| Email and password validation | Implemented | Frozen for the current phase; no changes requested |
| Profile photo | Implemented | Final end-to-end persistence test |
| Username and full name editing | Implemented | Final end-to-end persistence test with Supabase |
| Account deletion and recovery | Implemented | Backend checks due accounts at startup and every 6 hours |
| Privacy Notice and consent | Implemented | Complete final live Desktop acceptance test |
| Settings | Implemented with popup and optional sound alerts | Final live popup, sound and persistence acceptance test |
| Dashboard, history and reports | Implemented with saved Session, Prototype Risk, Full RULA, Blink Rate and Alert data | Complete final live Supabase acceptance test |
| Session controls and navigation | Implemented | Continue regression and minimize behavior testing |
| Camera preparation and detection pipeline | Implemented | Run final hardware acceptance with the reference card, webcam and sustained posture alerts |
| Image/video privacy | Implemented by design | Add explicit user-facing notice and acceptance test |
| Desktop packaging | Missing | Produce and test the Windows executable/installer |

## Implementation order for the current desktop phase

1. Run the physical reference-card and full webcam acceptance flow.
2. Hold each supported posture long enough to verify popup, sound, persisted
   Alert Events and the resulting Dashboard/Report values.
3. Run the Privacy Notice, profile and account-specific data acceptance flows
   against the production Supabase configuration.
4. Run a long-session/minimize/pause/resume performance test.
5. Package and test the Windows application and its backend startup strategy.

## Camera preparation traceability

The desktop flow is `Camera Setup -> Camera Preview -> Camera Preparation ->
Personal Baseline -> Session`. Camera Preparation was adapted from the latest
`feature/camera` reference-card implementation at commit `04211ba`. The
posture-detection and camera-session modules were later integrated on
`feature/detection` without merging or modifying their source branches.

The preparation page uses the standard 85.60 x 53.98 mm card dimensions and
requires ten consecutive valid frames. It checks card size, position, aspect
ratio, roll and perspective locally. Only the resulting numeric reference is
attached to the Personal Baseline: frame dimensions, X/Y/average scale, card
roll, horizontal/vertical perspective and capture time. Camera frames, card
images, contours and transform matrices are not persisted or uploaded.

The Personal Baseline collector was adapted from the same `feature/camera`
commit. It accepts only Detection Contract 1.0 frames with valid shoulder tilt,
neck lateral tilt, neck flexion and eye-distance proxy values. Collection needs
at least 60 valid samples, 15 seconds of coverage, a valid-frame ratio of at
least 70 percent and stable measurements. Passing those checks creates a
candidate only; the user must explicitly confirm the candidate before it can be
saved or used by a Session.

The Session API accepts a new session only when its Personal Baseline contains
the camera preparation values, all four finite posture measurements and the
`SUCCESS` / `CONFIRMED` validation state. Existing baseline records remain
readable because the added database columns are nullable, but incomplete older
records cannot start another session.

Privacy Notice version `2026-10-20` is enforced before Camera Setup in the
Desktop application and again by the Session API. Acceptance version,
acceptance time and withdrawal time are stored per user. Migration
`a91f4c2d7e30` is applied to Supabase. Withdrawing consent is blocked while a
session is RUNNING or PAUSED and prevents future monitoring until the current
notice is accepted again.
