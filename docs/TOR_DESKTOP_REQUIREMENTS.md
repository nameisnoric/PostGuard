# PostGuard TOR Traceability — Desktop Scope

This document records the implementation scope extracted from `ToR.pdf` and
uses `Proposal (1).pdf` only to clarify the selected desktop architecture.

## Requirement priority

1. The TOR is the primary source for required behavior and acceptance.
2. The proposal clarifies implementation details where the TOR is ambiguous.
3. The current product is a Desktop Application. The proposal specifies
   Python, PySide6, FastAPI, JWT, Argon2, Resend and PostgreSQL/Supabase.
4. Posture detection, posture scoring and blink analysis are deferred
   temporarily. Camera preparation is implemented as a local reference-card
   step before the personal posture baseline.
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

### Required architecture

- Desktop UI: Python and PySide6.
- Backend API: FastAPI.
- Authentication: JWT and Argon2 password hashes.
- Password reset delivery: Resend.
- Persistence: PostgreSQL hosted through Supabase.
- Camera processing remains on the user's device; only calculated results and
  required records are sent to the backend.

## Current implementation gap

| TOR area | Status | Remaining work |
| --- | --- | --- |
| Register, login and logout | Implemented | Keep the current `@ku.th` email/password flow |
| Password reset with OTP | Implemented | Final live-email acceptance test |
| Email and password validation | Implemented | Frozen for the current phase; no changes requested |
| Profile photo | Implemented | Final end-to-end persistence test |
| Username and full name editing | Implemented | Final end-to-end persistence test with Supabase |
| Account deletion and recovery | Implemented | Backend checks due accounts at startup and every 6 hours |
| Privacy Notice and consent | Missing | Add consent model, API and desktop flow |
| Settings | Implemented | Final live sound and persistence acceptance test |
| Dashboard, history and reports | Implemented for available data | Complete detection-derived TOR fields when their source calculations are available |
| Session controls and navigation | Implemented | Continue regression and minimize behavior testing |
| Camera preparation | Implemented | Run final acceptance test with the printed 85.60 x 53.98 mm reference card |
| Image/video privacy | Implemented by design | Add explicit user-facing notice and acceptance test |
| Desktop packaging | Missing | Produce and test the Windows executable/installer |

## Implementation order for the current desktop phase

1. Run the physical reference-card acceptance test for camera preparation.
2. Implement Privacy Notice and stored consent management.
3. Run final live acceptance tests for history, reports and account-specific data.
4. Package and test the Windows application.

Detection-related requirements remain part of the TOR and must be completed
later, but they are outside the current desktop-system phase.

## Camera preparation traceability

The desktop flow is `Camera Setup -> Camera Preview -> Camera Preparation ->
Personal Baseline -> Session`. Camera Preparation was adapted from the latest
`feature/camera` reference-card implementation at commit `04211ba` without
merging that branch or importing its posture-detection models.

The preparation page uses the standard 85.60 x 53.98 mm card dimensions and
requires ten consecutive valid frames. It checks card size, position, aspect
ratio, roll and perspective locally. Only the resulting numeric reference is
attached to the Personal Baseline: frame dimensions, X/Y/average scale, card
roll, horizontal/vertical perspective and capture time. Camera frames, card
images, contours and transform matrices are not persisted or uploaded.

The Session API accepts a new session only when its Personal Baseline contains
the camera scale and preparation timestamp. Existing baseline records remain
readable because the new database columns are nullable, but they must be
recreated through Camera Preparation before starting another session.
