# Rafa Studio

Private creative editing workspace for Rafa Pizza.

## Product promise
Turn long, unordered user-shot footage into a deliberate, premium 20–30 second food/restaurant Reel. Behave like a specialist editor and creative director: every selected moment and every cut must have an editorial reason.

## Non-negotiable creative rules
- Use only footage supplied by Rafa. Never generate synthetic video shots.
- Accept long recordings (including ~20-minute videos) and many short clips in arbitrary order.
- Target runtime: 20–30 seconds maximum; shorter if the story is stronger.
- No random trimming and no fixed-duration chopping. Cuts must follow action boundaries, visual changes, narrative logic, emotional beats or intentional audio rhythm.
- Preserve a consistent Rafa visual signature while adapting each story to the actual footage.
- Premium, cinematic food-commercial finish: tactile detail, natural movement, precise cuts, restrained transitions and typography.
- Do not promise virality. Optimize testable creative hypotheses and learn from actual performance.

## Cross-event intelligence and visual continuity
Rafa Studio must be able to create one coherent film from footage captured at different events, dates, venues, cameras and shot types. It must not assume that adjacent clips belong to the same event, nor treat chronological order as the default story.

### Build a story across different sources
1. **Understand each clip independently:** identify the visible subject, action, event context clues, shot size, camera angle, camera movement, lighting, dominant colors, people/food/environment and technical quality.
2. **Build a searchable visual inventory:** tag moments by action and semantic role (dough preparation, topping, oven, reveal, serving, guest interaction, atmosphere, setup, etc.), plus source event when it can be inferred. Keep uncertain event assignments explicitly uncertain.
3. **Find narrative relationships:** connect clips through shared action, matching shapes or movement, ingredient continuity, cause-and-effect, visual contrast, recurring motifs, sound or a clear emotional progression.
4. **Plan transitions before cutting:** decide why shot B should follow shot A. Examples: a hand movement can continue across two different events; a raw dough shot can lead into a finished pizza; oven heat can bridge into a lively service scene. A transition must feel intentional, not merely possible.
5. **Control continuity:** compare screen direction, movement direction, eyelines where relevant, shot scale, camera height, color temperature, exposure, white balance, background clutter and action phase. Use a motivated contrast when exact matching is impossible.
6. **Manage event changes honestly:** if a recap spans multiple events, use visual or narrative bridges (repeated actions, details, sound, rhythm, brief establishing shots) so the viewer experiences one deliberate montage. Do not create a false impression that two moments happened in the same event when that would mislead.
7. **Protect pacing and variety:** avoid consecutive shots with the same composition, repeated action or identical visual energy unless repetition is a deliberate rhythmic device. Alternate detail, medium and wide shots when the available footage supports it.
8. **Run a continuity review:** inspect every adjacent pair and the whole sequence at normal speed. Flag abrupt lighting/location/wardrobe/prop changes, mismatched movement, incomplete gestures, confusing chronology and shots that weaken the emotional arc.

### Transition relationship scoring
For each proposed adjacent pair, estimate and retain separate signals:
- semantic/story connection;
- action or movement match;
- composition and shape match;
- color/light compatibility;
- camera direction and screen direction;
- audio/beat compatibility;
- temporal/event consistency;
- contrast value when the edit intentionally changes energy or setting.

Do not collapse these into a single opaque score. A strong creative contrast can be better than a technically perfect match. The editor must explain the intended relationship in plain language and mark low-confidence transitions for review.

### Two editing modes
- **Single-event story:** preserve the event's natural progression when useful, from arrival/setup through preparation, cooking, service and guest experience.
- **Multi-event brand recap:** build a thematic progression across events (craft, energy, hospitality, abundance, signature pizzas) rather than stitching together unrelated highlights. The sequence should feel like one film about Rafa Pizza, not a random slideshow of past jobs.

## Long-footage intelligence pipeline
1. **Ingest and inspect:** read duration, frame rate, resolution, orientation, audio tracks and codec; create proxy/thumbnail assets without altering originals.
2. **Detect structure:** identify shot/scene boundaries, camera movement, changes in framing, silence/speech/music and meaningful action phases.
3. **Understand content:** sample frames over time and inspect promising intervals more densely; classify pizza, dough, ingredients, hands, oven, plating, guests, environment and other visible subjects/actions. Transcribe speech when present.
4. **Find usable moments:** detect action starts, peak moments and natural endings (e.g. dough stretch reaches full extension, pizza enters/leaves oven, knife completes a cut, slice lifts, cheese pull peaks). Preserve handles before/after the action.
5. **Score candidates:** combine visual clarity/focus, exposure, composition, motion, uniqueness, sensory appeal, story relevance, action completeness and technical quality. A score is a ranking aid, not the editor's only decision.
6. **Build narrative:** choose a hook, context/promise, escalating process, payoff and close. Ensure continuity and variety in shot size, angle, subject and motion.
7. **Place edits precisely:** cut on meaningful action boundaries or visual/audio beats when they improve the story. Avoid cutting mid-gesture, repeating nearly identical shots, dead time and transitions that distract.
8. **Render and review:** create a low-resolution preview first, inspect pacing and continuity, then render high-quality MP4 using source-appropriate resolution and frame rate.

## Editorial decision model
For every chosen segment, retain:
- source filename and in/out timecodes;
- what is visible and what action occurs;
- why the moment is selected;
- its role (hook, setup, build, transition, payoff, close);
- technical confidence and any quality caveat;
- for cross-event edits, the reason it follows the previous shot and the continuity strategy used.

For every rejected candidate, retain a short reason when useful (blur, duplicate action, weak framing, no complete action, irrelevant to story). This makes decisions explainable and lets Rafa correct the system.

## Masterpiece quality gate
A draft is not ready merely because it contains attractive shots. Before export, evaluate it as a complete film:
- **Story:** one clear idea, purposeful progression, satisfying payoff and a memorable ending.
- **Editing:** every cut has a reason; no accidental jump, dead beat, arbitrary speed ramp or decorative transition.
- **Continuity:** adjacent shots connect or create a deliberate, legible contrast; cross-event changes never feel like mistakes.
- **Rhythm:** pacing varies with the action and emotional energy; music supports rather than dictates the edit.
- **Image:** focus, exposure, color and crop are consistent enough for a polished finish without making source footage look artificial.
- **Sound:** retain useful natural sounds (dough, oven, slicing, room atmosphere) where they add tactility; balance them with music and speech.
- **Brand:** premium, warm, confident and recognizably Rafa; no generic social-template aesthetic.
- **Truth:** no misleading event continuity, fabricated moments or synthetic footage.
- **Platform delivery:** vertical framing and export settings are checked; text remains legible and within safe areas.

The system should produce an edit decision list and a preview first. It must identify unresolved weak points rather than silently hiding them. Rafa can approve, reject or request a revision before the final render.

## Reference learning: compare to real successful Reels
Maintain a curated reference library of public food/restaurant Reels with:
- source URL, creator, capture date and visible performance context where available;
- opening hook type, first-frame composition and time-to-payoff;
- narrative beats, shot duration distribution, framing changes and audio strategy;
- format archetype (sensory process, transformation, tutorial, reveal, behind-the-scenes, event story, etc.);
- why the structure may work and how to adapt the principle to Rafa without copying footage, script or distinctive creative expression.

Compare Rafa's draft to references structurally, not by blindly imitating them. Separate verified platform guidance from third-party sample analyses and editorial hypotheses. Recheck current platform guidance periodically.

## Psychology and performance loop
Design each Reel around:
- **Attention:** immediate visual curiosity or a compelling question.
- **Comprehension:** viewers quickly understand what they are watching.
- **Anticipation:** a process or transformation creates a reason to stay.
- **Sensory reward:** texture, sound, heat, stretch, crispness, cut or reveal.
- **Social value:** a moment people might send to a friend or use to start a conversation.

Measure after publication:
- average watch time and retention/completion;
- likes per reach;
- sends/shares per reach;
- saves, profile visits and booking enquiries as business outcomes.

Store the creative hypothesis, hook, runtime, edit decisions and Instagram Insights for each published Reel. Compare against Rafa's own baseline and identify repeatable wins. Do not infer that views alone prove a format is successful.

## Creative framework (flexible starting hypothesis)
- 0–2s: hook (strongest visual or intriguing moment).
- 2–6s: promise/context.
- 6–17s: process and escalation (hands, dough, ingredients, oven, detail).
- 17–24s: payoff (finished pizza, slice, guest moment).
- 24–30s: memorable close and subtle booking cue only when appropriate.

This is a flexible grammar, not a mandatory formula. A video may open with the payoff and then reveal how it happened.

## Current prototype
`index.html` is a responsive front-end prototype with local multi-video import, clip previews, a creative brief and a downloadable brief JSON. It does **not** yet analyze footage with AI, automatically edit video, sync music, or export a finished MP4.

## Engineering milestones
1. Clip ingestion, proxy generation, metadata extraction and thumbnail/contact-sheet creation.
2. Long-video shot detection, audio analysis and semantic/action segmentation with timecodes.
3. Candidate moment ranking with transparent editorial reasons.
4. Cross-event visual inventory, transition compatibility and continuity review.
5. Storyboard proposals with alternative hooks and shot selections.
6. Deterministic timeline engine for cuts, crop, speed, audio and restrained color treatment.
7. Preview, natural-language revisions and high-quality MP4 export.
8. Performance log to learn Rafa's actual winning formats over time.
