# Ideas rating against the tracks

Re-rating of the team doc "ideas for grokbot hackathon" (version of 2026-11-03) against the proposed tracks published at https://pavia.grokbot.it/tracks (full cards: [`tracks.md`](tracks.md)). Written 2026-11-04, before the common judging rubric was announced.

## The constraint that changes everything

**No track card lists drones.** Track hardware is arms 1-3, cameras 1-2 and one robot dog (1-2 teams, staff present, slots kept for track A). Drones (and rovers) were only mentioned on Discord. So a drone idea scores well only if it meets a track's minimum demo and measures without needing that track's hardware, or if the organisers confirm that a drone may stand in for it.

**Track 03 (Agent Failure Lab) needs no hardware at all.** The drone becomes a richer source of traces rather than a dependency, and it is the only track where a drone failure on demo day does not sink the project.

## How the scores work

- **Track fit (0-10):** how much of the best track's minimum demo and "How it's judged" measures the idea covers. 9-10: the idea *is* the minimum demo. 6-8: covers most of it with a reframing. 3-5: shares the flow but misses the inputs or measures. 0-2: no track.
- **Hardware (0-10):** whether it runs on what we hold (the RoboMaster TT, laptops) or on hardware we would have to win slots for.
- **Rubric (/100):** estimate on the provisional rubric from the organiser repo: Innovation 25, Technical 25, AI usage 20, UX/UI 15, Business 15. The organisers said the final KPIs will be about innovation, relevance and scalability / go-to-market, so treat this column as a rough guide.
- **Baseline:** every track requires "at least one result measured against a baseline", so each idea gets the cheapest credible baseline.

## Summary

| Rank | Idea | Best track | Track fit | Hardware | Rubric | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Prove the Mission + Ground Truth** (merge, below) | 03 Agent Failure Lab | 9 | 8 | 78 | **Recommended** |
| 2 | Prove the Mission (Ayoub) | 03 Agent Failure Lab | 9 | 9 | 73.5 | Strong; safest |
| 3 | Ground Truth (Eduard) | D Robot Dog Patrol (flow only) | 4 | 6 | 75.5 | Best wow, weakest fit; use as the demo scenario |
| 4 | Infrastructure Inspection, narrowed (Muhammad) | A CTRL+F: SEA ("What changed") | 5 | 6 | 62.5 | Only if narrowed hard |
| 5 | Guide Dog (Eduard) | none (D and A use the dog for other jobs) | 2 | 2 | 57.5 | Drop |
| 6 | Infrastructure Inspection, as written | none | 3 | 2 | 48.5 | Drop as written |
| 7 | Multi-agent news verification | none | 1 | 10 | 50 | Drop; reuse as Ground Truth's baseline |
| - | "Mass Surveillance" | - | - | - | - | Not a proposal (joke); not rated |

Rubric breakdown (Innovation / Technical / AI usage / UX / Business, each 0-10):

| Idea | I | T | AI | UX | B | Weighted |
|---|---|---|---|---|---|---|
| Prove the Mission + Ground Truth | 8 | 7 | 9 | 8 | 7 | 78 |
| Ground Truth | 9 | 5 | 9 | 9 | 6 | 75.5 |
| Prove the Mission | 7 | 8 | 9 | 6 | 6 | 73.5 |
| Infrastructure Inspection, narrowed | 5 | 6 | 7 | 6 | 8 | 62.5 |
| Guide Dog | 7 | 2 | 7 | 8 | 6 | 57.5 |
| News verification | 3 | 6 | 7 | 5 | 4 | 50 |
| Infrastructure Inspection, as written | 5 | 2 | 5 | 5 | 9 | 48.5 |

## Per idea

### Prove the Mission (Ayoub) - Track 03, fit 9

A drone agent claims it inspected three checkpoints but never saw one; Grok reviews footage and logs, finds the gap, proposes a fix, and a rerun either gets the evidence or admits it could not.

- **Track match:** this is Track 03's "Verification: success wrongly claimed" category, and the track's rule that "a fix only counts if it improves a test without obvious regressions" is exactly the rerun. Track 03 also names traces from physical tracks as "real cases".
- **Gap to the minimum demo:** the track wants 15-20 annotated traces covering at least 4 failure categories, 2 fixes, and a replay on 5 tasks. The idea as written covers one category. Drone missions produce the others on their own:
  - *Plan:* checkpoint skipped or visited out of order.
  - *Tool use:* `forward 10` rejected (minimum 20 cm), wrong mission pad ID.
  - *Execution:* 15 s auto-land while the agent "thinks", UDP timeout, a lost `ok` that makes a retried move run twice, low battery.
  - *Verification:* checkpoint reported done with no frame showing its marker.
- **Baseline:** the same agent without the evidence check. Measure false "completed" claims, true completions (regressions), time and API cost before and after each fix. For the classifier, deterministic rules alone (timeouts, loops, failed tests) against rules plus Grok.
- **Risks:** a repeatable failure is easy, because we inject it (cover a marker). Most traces can come from a mocked drone, so the 30-minute flight slots are not on the critical path.
- **Weakness:** the least spectacular demo on its own. It is a timeline UI plus a short flight.

### Ground Truth (Eduard) - closest to Track D, fit 4

Someone tags Grok under a post; Grok geolocates the claim, sends a drone, looks, and replies with footage and a verdict.

- **Track match:** no track asks for it. It shares Track D's event -> mission -> check -> alert flow, but D is judged on dog arrival time, staged anomalies, forwarded false alarms and the log, with a robot dog and phone cameras as inputs.
- **Strengths:** the strongest wow, and it uses what only xAI has (X search, Grok on X). It also follows the past-winner pattern of crossing into the physical world (Grok for Mayor, Nova).
- **Baseline:** Grok text-only fact-checking the same 10 staged posts, against Grok with the drone. "Grok without eyes vs. Grok with eyes" is a clean, demo-friendly number.
- **Risks:** reading mentions may need a paid X tier (fallback: a feed that looks like X), and "geolocating" inside one room is contrived. Indoor autonomous flight on the demo path is the riskiest piece of all the ideas.

### Prove the Mission + Ground Truth (merge) - Track 03, fit 9, recommended

Enter Track 03 with Prove the Mission as the system, and use Ground Truth as the mission it audits:

1. A post claims something about the room ("the exhibit on table 2 is gone"). The drone agent flies to check and drafts a verdict.
2. The audit layer refuses any verdict that has no frame proving it, classifies what went wrong when the agent overclaims, and proposes a fix.
3. The before/after numbers are the Track 03 deliverable; the post -> flight -> reply loop is the pitch.

This keeps Track 03's fit and safety (it all works on mocked traces if the drone misbehaves) and adds Ground Truth's wow and xAI-specific story. The pitch line: *"Grok never says 'verified' without the frame that proves it."*

Scope guard: the X integration is a stretch goal. The minimum demo runs on a local feed that looks like X.

### Infrastructure Inspection (Muhammad) - fit 3 as written, 5 narrowed

3D multispectral capture with drones and ground robots, point-cloud cleaning, comparison with CAD/BIM, ML anomaly detection, reports.

- **As written:** the TT carries one 720p RGB camera: no multispectral, thermal or LiDAR sensor. There is no CAD/BIM data, and five subsystems will not fit in 30 hours. The organisers' own principle is "a robust end-to-end pipeline on a narrow use case beats a broad but fragile demo."
- **The real asset is the business case.** Muhammad's numbers (6 people, 2-3 weeks per PV plant) are first-hand and judges value that.
- **Narrowed version:** the drone flies over a mock solar array (printed panels on the floor), Grok compares what it sees with the design layout, and it flags missing, swapped or soiled panels in a report. That is Track A's "What changed" mode on a different scene, measured on false alarms. Track A expects its own table station and the arm, though, so the fit stays partial.
- **Best use:** fold his numbers into the business slide of the recommended project (drone inspection agents that must prove completion are his industry's problem).

### Guide Dog (Eduard) - fit 2

- The dog is shared by 1-2 teams in 30-minute supervised slots, with priority for Track A. Tracks A and D both put autonomous dog navigation out of scope.
- Walking a blindfolded judge is a safety case staff are unlikely to approve. Drop.

### Multi-agent news verification - fit 1

- Its author already marked it "seems not viable", and it overlaps with what Grok and Community Notes already do on X.
- Its value is as the **text-only baseline** for Ground Truth.

## Open questions for the organisers (today, at the hardware tour)

1. Can a drone project enter a track whose card does not list drones (03, or D with a drone instead of the dog)?
2. Are the RoboMaster TT drones ours for both days, or slot-based like the arms and the dog?
3. Is there a Wi-Fi network or router the drones can join in station mode, with internet for the Grok API?
4. When and where is the common judging rubric published?
