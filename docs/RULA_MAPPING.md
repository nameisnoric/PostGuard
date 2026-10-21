# PostGuard RULA mapping

PostGuard implements the RULA scoring tables as a screening calculation based
on McAtamney and Corlett (1993). A Full RULA score is produced only when every
required observation is available. Camera-only results are marked `PARTIAL`
and never receive a fabricated final score or action level.

Primary reference: McAtamney, L. and Corlett, E. N. (1993), *RULA: a survey
method for the investigation of work-related upper limb disorders*, Applied
Ergonomics 24(2), 91-99, DOI `10.1016/0003-6870(93)90080-S`. The lookup-table
transcription is cross-checked against the Cornell RULA Employee Assessment
Worksheet by Alan Hedge.

## Body-part scoring

| RULA input | Score | Criterion | Current PostGuard source |
| --- | ---: | --- | --- |
| Upper arm | 1 | 20° extension to 20° flexion | Manual Full RULA form |
| Upper arm | 2 | More than 20° extension or 20–45° flexion | Manual Full RULA form |
| Upper arm | 3 | 45–90° flexion | Manual Full RULA form |
| Upper arm | 4 | More than 90° flexion | Manual Full RULA form |
| Upper-arm adjustment | +1 / +1 / −1 | Shoulder raised / abducted / arm supported | Manual Full RULA form |
| Lower arm | 1 | 60–100° elbow angle | Manual Full RULA form |
| Lower arm | 2 | Outside 60–100° | Manual Full RULA form |
| Lower-arm adjustment | +1 | Across body midline or outside the body | Manual Full RULA form |
| Wrist | 1 | Neutral | Manual Full RULA form |
| Wrist | 2 | Up to 15° flexion or extension | Manual Full RULA form |
| Wrist | 3 | More than 15° flexion or extension | Manual Full RULA form |
| Wrist adjustment | +1 | Bent away from midline | Manual Full RULA form |
| Wrist twist | 1 / 2 | Mid-range / near end range | Manual Full RULA form |
| Neck | 1 | 0–10° flexion | `neck_flexion` |
| Neck | 2 | More than 10° up to 20° flexion | `neck_flexion` |
| Neck | 3 | More than 20° flexion | `neck_flexion` |
| Neck | 4 | Extension | `neck_flexion` |
| Neck adjustment | +1 / +1 | Twisted / side-bending | Twist missing; side-bending from `neck_lateral_tilt` |
| Trunk | 1 | Erect or supported neutral posture | Manual Full RULA form |
| Trunk | 2 | More than 0° up to 20° flexion | Manual Full RULA form |
| Trunk | 3 | More than 20° up to 60° flexion | Manual Full RULA form |
| Trunk | 4 | More than 60° flexion | Manual Full RULA form |
| Trunk adjustment | +1 / +1 | Twisted / side-bending | Manual Full RULA form |
| Legs | 1 / 2 | Supported and balanced / unsupported or unbalanced | Manual Full RULA form |
| Muscle use | +1 | Static longer than 60 seconds or repeated at least 4 times/minute | Continuous duration available; repetition rate missing |
| Force/load | 0 | Less than 2 kg intermittent | Manual Full RULA form |
| Force/load | 1 | 2–10 kg intermittent | Manual Full RULA form |
| Force/load | 2 | 2–10 kg static or repeated | Manual Full RULA form |
| Force/load | 3 | More than 10 kg, repeated, shock, or rapid force | Manual Full RULA form |

The camera uses a measurement tolerance before declaring neck side-bending so
normal landmark noise is not treated as an observed RULA adjustment. This is a
PostGuard implementation constraint, not a replacement RULA threshold.

## Score combination

| Stage | Inputs | Output |
| --- | --- | --- |
| Table A | Upper arm, lower arm, wrist and wrist twist | Posture Score A |
| Final A | Posture Score A + muscle use + force/load | Wrist and Arm Score |
| Table B | Neck, trunk and legs | Posture Score B |
| Final B | Posture Score B + muscle use + force/load | Neck, Trunk and Leg Score |
| Table C | Final A and Final B | Full RULA score 1–7 |

## Full RULA action levels

| Final score | Action level | Meaning |
| ---: | ---: | --- |
| 1–2 | 1 | Posture is acceptable if it is not maintained or repeated for long periods |
| 3–4 | 2 | Further investigation is needed; change may be required |
| 5–6 | 3 | Investigation and changes are needed soon |
| 7 | 4 | Investigation and changes are required immediately |

## Current application behavior

The camera contract returns `RULA-derived neck: ≥N` as a lower bound. The
lower-bound marker is required because neck twist is not measured. During an
active session, `Full RULA Assessment` collects every missing scored
observation, calculates Tables A, B and C, and keeps the highest completed
score for that session. The final score and action level are persisted in the
Session Summary and shown in History/Report and Dashboard. If the form is not
completed, Full RULA remains `N/A`. The existing PostGuard Prototype Risk 0–3
remains separate from the official RULA final score and action level.
