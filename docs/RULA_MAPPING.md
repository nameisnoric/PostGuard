# PostGuard camera-supported RULA neck mapping

PostGuard uses only the RULA neck criteria that the current camera contract
can observe: neck flexion/extension and lateral side-bending. Neck twist is
not measured, so the displayed value is a lower bound (`≥N`) and is stored as
`rula_neck_score`. The application does not calculate a Full RULA score or an
RULA action level.

Primary reference: McAtamney, L. and Corlett, E. N. (1993), *RULA: a survey
method for the investigation of work-related upper limb disorders*, Applied
Ergonomics 24(2), 91-99, DOI `10.1016/0003-6870(93)90080-S`. The neck criteria
were cross-checked against the Cornell RULA Employee Assessment Worksheet.

## Implemented scoring

| Camera observation | Base score | Adjustment | Displayed result |
| --- | ---: | ---: | --- |
| Neck extension below 0° | 4 | +1 if lateral side-bending is detected | ≥4–5 |
| Neck flexion 0–10° | 1 | +1 if lateral side-bending is detected | ≥1–2 |
| Neck flexion >10–20° | 2 | +1 if lateral side-bending is detected | ≥2–3 |
| Neck flexion >20° | 3 | +1 if lateral side-bending is detected | ≥3–4 |

The maximum camera-derived value is 5. The RULA neck component can reach 6
when both twist and side-bending adjustments apply, but neck twist is not
available from the current Detection Contract.

## Application flow

1. Detection provides `neck_flexion.current` and the evaluated state of
   `neck_lateral_tilt`.
2. The RULA mapper selects the flexion/extension base score.
3. It adds one when lateral side-bending passes the PostGuard measurement
   tolerance and is classified as a posture factor.
4. Monitoring shows `RULA Neck (camera): ≥N/6 | Partial assessment`.
5. The highest observed neck score in the session is stored in Session
   Summary and displayed in History/Report and Dashboard.

The existing PostGuard Prototype Risk 0–3 remains separate. It uses supported
posture factors and continuous duration for alerts; it is not a Full RULA
score or a clinical diagnosis.
