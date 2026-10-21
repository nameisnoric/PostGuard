# PostGuard RULA-adapted front-camera Risk Score

PostGuard applies selected RULA principles to measurements available from one
front-facing camera. The result is an easy-to-read Risk Score from 1 to 7. It
is an application-specific screening score and is not an official Full RULA
calculation.

Primary reference: McAtamney, L. and Corlett, E. N. (1993), *RULA: a survey
method for the investigation of work-related upper limb disorders*, Applied
Ergonomics 24(2), 91-99, DOI `10.1016/0003-6870(93)90080-S`.

## Score components

| Front-camera evidence | Condition | Score contribution |
| --- | --- | ---: |
| Neck flexion/extension | 0–10° flexion | Base 1 |
| Neck flexion/extension | >10–20° flexion | Base 2 |
| Neck flexion/extension | >20° flexion | Base 3 |
| Neck flexion/extension | Extension below 0° | Base 4 |
| Lateral neck bending | Posture factor detected beyond measurement tolerance | +1 |
| Shoulder asymmetry | Left/right shoulder tilt detected beyond baseline tolerance | +1 |
| Sustained posture | Any supported posture factor remains active for more than 60 seconds | +1 |

`Risk Score = neck base + neck side-bending + shoulder asymmetry + sustained posture`

The result is capped at 7.

## User-facing risk levels

| Score | Level | Meaning shown to the user |
| ---: | --- | --- |
| 1–2 | LOW | ท่าทางมีความเสี่ยงต่ำ |
| 3–4 | MODERATE | ควรปรับท่าทางและติดตามต่อเนื่อง |
| 5–6 | HIGH | ควรปรับท่าทางโดยเร็ว |
| 7 | VERY HIGH | ควรหยุดพักและปรับท่าทางทันที |

## Data flow

1. Detection measures neck flexion, lateral neck tilt and shoulder tilt.
2. Current Posture Assessment applies camera and personal-baseline tolerance.
3. Temporal Tracking determines whether a posture remains active for more
   than 60 seconds.
4. The RULA-adapted mapper calculates a score from 1 to 7.
5. Monitoring shows the current score and risk level.
6. Session Summary stores the average and maximum scores with method
   `RULA_ADAPTED_FRONT_V1`.
7. Dashboard and History distinguish these scores from older Prototype Risk
   reports.

The score is designed for PostGuard's front-camera workflow and should not be
presented as a clinical diagnosis or Full RULA assessment.
