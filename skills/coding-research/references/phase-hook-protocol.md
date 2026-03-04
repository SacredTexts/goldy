# Per-Phase Interview Protocol

This protocol runs at each phase boundary during `/goldy-loop` execution. It's a condensed version of the full coding-research interview, focused on the specific phase about to be executed.

## When This Fires

Goldy-loop emits a `phase_research_protocol` block before starting each new phase. Claude reads this block and runs the 4-step protocol below before executing any phase tasks.

## The Protocol

### Step 1: Scope Confirmation (Required)

Ask the user:
- "This phase touches [list files and layers from the plan]. Is that still correct?"
- "Have any constraints changed since the plan was written?"
- "Is there anything from the previous phase that affects this one?"

**If scope has changed**: Update the plan phase before executing. Do not proceed with stale scope.

### Step 2: Implementation Approach (Required)

Present 2-3 implementation approaches for the phase and ask:
- "Here are the approaches I see for this phase: [list]. Which fits best?"
- "Do you have preferences on patterns, libraries, or coding style for this phase?"
- "Should I prioritize speed, correctness, or maintainability here?"

**If the user picks an approach**: Proceed with that approach. Document the choice.
**If the user suggests something else**: Adapt the plan accordingly.

### Step 3: Risk / Edge Case Surfacing (Required)

Ask the user:
- "What could go wrong in this phase?"
- "Are there edge cases you're worried about?"
- "What's the acceptance criteria — how do we know this phase is done?"

**Example edge cases to probe** (context-dependent):
- Empty states / missing data
- Concurrent access / race conditions
- Error handling / fallback behavior
- Performance under load
- Cross-browser / mobile compatibility (for UI phases)

### Step 4: Open Brainstorming (Optional but Recommended)

Ask:
- "Anything else about this phase you want to think through before we start?"
- "Is there context I'm missing that would change how I approach this?"

**This step catches the unknown unknowns** — things the plan didn't anticipate.

## After the Phase Completes

Log the phase interview outcome by running track_outcome.py with:
- `classification_type`: the phase's primary concern (e.g., "schema_db" for a migration phase)
- `track_used`: "phase_interview"
- `rounds_completed`: number of steps completed (1-4)
- `synthesis_confirmed_first_attempt`: whether the scope/approach was confirmed without changes
- `notes`: any scope changes or new constraints discovered

## Timing

- The full protocol should take 1-3 minutes of conversation
- For simple/clear phases: Steps 1-2 may be brief, Steps 3-4 can be skipped
- For complex/risky phases: All 4 steps should be thorough
- If the user says "just go" or "skip questions": Proceed directly, but still log the outcome

## Example Phase Interview

```
Phase 3 — Goldy Auto-Invoke Integration

[Step 1 — Scope]
"This phase modifies goldy.py to add a coding_research flag and updates the
Goldy SKILL.md references table. It also adds a push_memory background call.
Does this scope still look right?"

[Step 2 — Approach]
"I see two approaches for the auto-invoke flag:
A) Add a simple boolean to the output JSON
B) Add a nested object with skill_path for flexibility
Which do you prefer?"

[Step 3 — Risk]
"The main risk I see is changing the goldy.py JSON output structure — downstream
consumers might break. Should I check for other scripts that parse goldy.py output?"

[Step 4 — Brainstorm]
"Anything else about the goldy.py integration you want to think through?"
```
