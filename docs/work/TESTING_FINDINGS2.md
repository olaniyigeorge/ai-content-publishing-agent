
# Test Findings WHen Testing the [Test Intake Requests](TEST_INTAKE_REQUESTS.md)

1. Clean raw-idea request (happy path baseline)


Planning(attempt 2)
Planning
10:12 AM
Claude's planning response was missing required field(s) ['target_keywords'] — got: ['outline'] — retrying (attempt 1/3)

Planning
10:14 AM
Claude's planning response was missing required field(s) ['target_keywords'] — got: ['outline'] — retrying (attempt 2/3)


This is still stuck on planning
















2.  URL-based request, single good source 
What the State of AI Report Means for Marketing Investment
v1
discarded

What the State of AI Report Means for Marketing Investment
v2
regenerated from v1
draft
Sources (1)
State of AI Report 2025 | AI Research, Industry and Policy
selected
“Commercial traction accelerated sharply. Forty-four percent of U.S. businesses now pay for AI tools (up from 5% in 2023), average contracts reached $530,000, and AI-first startups grew 1.5× faster than peers, according to Ramp and Standard Metrics. Our inaugural AI Practitioner Survey, with over 1,200 respondents, shows that 95% of professionals now use AI at work or home, 76% pay for AI tools out of pocket, and most report sustained productivity gains, evidence that real adoption has gone mainstream.”

This is the core data marketing/demand gen leaders need to justify AI investment decisions: concrete commercial adoption metrics (44% of businesses paying for AI tools, contract sizes, startup growth rates) and a large practitioner survey showing near-universal usage and productivity gains. These figures directly ground claims about where AI investment is moving and why agencies should act now.

discard
Channel adaptations (0)
channel content is prepared after a draft is approved

Publishing queue (0)
what do these statuses mean?
nothing queued yet

Manage scheduling, cancelling, and retrying from the publishing queue page.

API usage
$0.1007
15,438 in / 6,981 out · 6 calls
show every pass
Pipeline activity
Intake
1 attachment(s)
10:12 AM

Research(attempt 2)
Planning
10:12 AM



44 is actualling in in the excerpt but written as fourty four... is claude not intellignet enough to understand this
ooh it gave itself that instruction What the State of AI Report Means for Marketing Investment
v2
regenerated from v1
3.1/5
8 flagged claims
draft

Instructions given to the AI for this version
The pre-flight grounding check found problems that must be fixed before this goes to evaluation: quantitative_paraphrase_drift: draft states ['44'] attributed to https://www.stateof.ai/, but its cited excerpt doesn't contain that figure




























3. Multi-source request with one dead link mixed in — Scenario


Koya Content Agent
Requests
New request
Publishing queue
Access
olaniyigeorge77@gmail.com
Log out
back to requests
How LinkedIn's algorithm changes this year should change B2B posting strategy
Audience: B2B marketing managers running organic LinkedIn programs#61cb187f

in review
original submission (3 attachments)

Intake

Research

Planning

Drafting

Review

Publishing
Article options (5)

How LinkedIn Algorithm Changes Should Shape B2B Strategy
v1
2.6/5
11 flagged claims
discarded

How LinkedIn Algorithm Changes Should Shape B2B Strategy
v2
regenerated from v1
discarded

How LinkedIn Algorithm Changes Should Shape B2B Strategy
v3
regenerated from v2
2.8/5
7 flagged claims
discarded

How LinkedIn Algorithm Changes Should Shape B2B Strategy
v4
regenerated from v3
2.8/5
8 flagged claims
discarded

How LinkedIn Algorithm Changes Should Shape B2B Strategy
v5
regenerated from v4
2.9/5
6 flagged claims
evaluated

Instructions given to the AI for this version
Implement all the recommendations given to resolve the concerns in the version. You can use https://business.linkedin.com/advertise for source and factual grounding too Prior evaluation feedback: The draft is unusually disciplined about epistemics — it repeatedly flags that LinkedIn publishes no ranking documentation and hedges the two biggest practitioner myths (comments/saves as stronger signals; outbound-link suppression) as untested hypotheses. That honesty is the draft's main strength and it should be preserved in revision. But the review has to be judged against what was actually supplied, and the "Available source excerpts" section is empty. There are zero source excerpts — strong or thin — behind this article. That means every substantive claim, recommendation, and numeric threshold in the piece is ungrounded by definition, and source_grounding cannot be scored above the floor. The hedged claims are handled honestly in prose, but hedging is only a partial defense when there is no source at all to hedge against; the more serious problems are the claims stated as flat fact.

Specifically: the "eight to ten posts" minimum sample threshold appears twice and is presented as an operational rule with no attribution, no derivation, and no stated basis — it reads like a borrowed statistical convention but nothing supports it. The preference for comments-per-impression and shares-per-impression over raw totals is asserted as methodology without support. The claim that LinkedIn's marketing resources "focus on platform features and campaign guidance rather than a line-by-line account of ranking mechanics" is a characterization of a linked page, not a cited excerpt. And "LinkedIn will keep adjusting how it ranks content" is a flat prediction, stated without hedge, in a piece that elsewhere insists we cannot observe the ranking system at all — that is an internal contradiction, not just an unsupported claim.

SEO is the other blocking issue. The primary keyword resolves cleanly and sits in the H1 and the first sentence, secondary variants are distributed naturally, and the H1/H2/H3 hierarchy is well formed. But there are only two links and both point to the identical URL (linkedin.com/business/marketing). That is one real link, duplicated — below the 2-3 distinct-links requirement, which fails the seo_fit >= 4 bar on its own regardless of the sourcing problems.

Audience fit and clarity are genuinely good: the quarterly-test cadence, the one-page log template, and the pre-committed decision rule are concrete enough for a marketing manager to implement on Monday. Completeness cannot be fully verified because no outline was provided, but the piece has a coherent intro/body/conclusion arc with no obvious structural gaps. One prose nit that recurs: several sentences use commas where em-dashes or parentheses are needed to set off appositives ("pick one variable per quarter, posting frequency, format mix, or link placement, and hold..."), which makes list-heavy sentences hard to parse on first read.

This is a revise, not a reject — the thinking is sound and the structure is sturdy. It needs sources attached to its factual and numeric claims, a second distinct link, and one internal contradiction resolved. Previously flagged unsupported/overstated claims: 'don't act on a format with fewer than eight to ten posts in the comparison window' — a specific numeric threshold stated as an operational rule, with no source, derivation, or hedge. Needs to be attributed to a source or explicitly relabeled as an arbitrary internal heuristic, or dropped.; 'only change the standing content calendar if a format beats the account average by a meaningful margin across at least eight to ten posts' — the same unsourced numeric threshold restated as a decision rule. Same fix required.; 'LinkedIn will keep adjusting how it ranks content' — flat, unhedged prediction that also contradicts the draft's own claim that the ranking system's pace is unknowable from outside. Hedge it or cite documented past ranking changes.; 'We prefer these ratios over raw totals because raw totals can be skewed by follower growth, and a bigger audience alone will inflate absolute numbers' — methodological assertion presented as established reasoning with no supporting source. Attribute to an analytics source or mark plainly as author preference.; "LinkedIn's marketing resources focus on platform features and campaign guidance rather than a line-by-line account of ranking mechanics" — a factual characterization of a linked page's contents with no excerpt quoted to back it. Quote the page or rephrase as a could-not-find statement.; 'likes are the easiest metric to inflate, a quick tap requires almost no consideration from the reader, which makes likes a weak signal of real interest' — hedged only as 'in our experience'; the causal conclusion about signal quality is still stated firmly with no evidence. Either cite data or reduce to an explicitly stated opinion.; 'A single post that goes unexpectedly viral can distort a 90-day average badly enough to point your whole calendar in the wrong direction' — plausible but stated as fact with no source or worked example. Hedge or support.; NOTE: the two claims the draft DOES hedge well — comments/saves as stronger intent signals ('LinkedIn has published nothing confirming this ranking behavior... a working hypothesis') and outbound-link suppression ('we haven't been able to trace to a primary source... LinkedIn has not confirmed this publicly') — are acceptable handling of weak evidence and are NOT counted as unsupported claims. Preserve that hedging verbatim in revision. Previously recommended changes: Attach real source excerpts to the draft. No excerpts were provided with this submission, so every factual and methodological claim is currently ungrounded. Either supply the excerpts the piece was written from, or cite a named source inline for each of the claims listed in unsupported_claims.; Fix the link problem in 'What B2B Marketing Managers Can Actually Verify' and 'Conclusion': both links currently point to the same URL (linkedin.com/business/marketing), so the piece effectively has one link, not two. Replace one of them with a distinct, real, non-duplicate source — e.g. LinkedIn's official engineering or product blog post on feed ranking, or a named third-party analysis of LinkedIn organic reach — and add a third distinct link so the article carries 2-3 genuinely separate references.; Justify or attribute the 'eight to ten posts' sample-size threshold in 'Auditing Your Current Organic LinkedIn Marketing Approach' and 'Building a More Adaptable B2B LinkedIn Strategy'. Either cite the source it came from, or rewrite it as an explicitly arbitrary internal heuristic: e.g. 'we use eight to ten posts as an internal rule of thumb — it is not a statistically derived threshold, just a guard against single-post outliers.'; Resolve the internal contradiction in the 'Conclusion'. The line 'LinkedIn will keep adjusting how it ranks content' is stated as flat fact, but the 'Building a More Adaptable B2B LinkedIn Strategy' section argues 'we genuinely don't know its pace from the outside' and that the ranking system cannot be observed directly. Hedge the conclusion to match — e.g. 'LinkedIn has changed how it ranks content before, and there's no reason to assume it has stopped' — or cite a source documenting past ranking changes.; Support or hedge the metric-choice methodology in 'Auditing Your Current Organic LinkedIn Marketing Approach'. The preference for comments-per-impression and shares-per-impression over raw totals is currently asserted. Either cite an analytics source recommending normalized engagement rates, or mark it plainly as the author's own reporting preference rather than a best practice.; Soften or source the characterization of LinkedIn's marketing resources in 'What B2B Marketing Managers Can Actually Verify'. Saying those resources 'focus on platform features and campaign guidance rather than a line-by-line account of ranking mechanics' is a claim about the content of a page with no excerpt behind it. Quote the page directly or rephrase to 'as of this writing, we could not find published ranking mechanics in LinkedIn's marketing resources.'; Repunctuate the comma-spliced appositive lists for readability. Use em-dashes or parentheses in: 'pick one variable per quarter, posting frequency, format mix, or link placement, and hold everything else constant'; 'Flag any format, video, document carousel, text-only post, or link post, where...'; 'The specific tactics, posting times, formats, or link placements, will keep evolving'; and 'likes are the easiest metric to inflate, a quick tap requires almost no consideration'.; Supply the content outline with the next draft so completeness can be verified against the sections it actually called for. It was not included in this submission.

Evaluation: revise/reject
by ai
2.90 / 5
▲ 0.10 vs previous version
No source excerpts were provided with this submission — the "Available source excerpts" section is empty. Under a strict reading of the rubric, that means every factual or semi-factual assertion in the draft is, by definition, ungrounded: source_grounding and factual_consistency cannot score above the floor because there is nothing to check against. That said, the draft deserves genuine credit for how it handles evidence. It is unusually disciplined about epistemic hedging: the likes-vs-comments hierarchy, the outbound-link penalty folklore, the eight-to-ten-post threshold, and the comments-per-impression preference are all explicitly labeled as internal judgment, practitioner rumor, or untraceable claims rather than stated as fact. That is exactly the honest handling the rubric rewards, and those items are NOT listed as unsupported claims below. The draft also never invents a LinkedIn announcement, statistic, or ranking factor — a common failure mode it avoids entirely. The problems that remain are of two kinds. First, a small number of claims are stated flatly without hedging or attribution and need fixing: the assertion that LinkedIn does not publish a technical breakdown of its ranking system is presented as established fact (the draft's own "we checked and couldn't find one" is an absence-of-evidence observation, not a verified negative), and the claim that raw engagement totals get skewed by follower growth is stated as a mechanism rather than the reporting preference it's framed as elsewhere. Second, the draft is built almost entirely on first-party "in our experience" authority. With zero source excerpts supplied, an article whose entire evidentiary base is unverifiable internal opinion cannot pass editorial review no matter how carefully it is hedged — a reader has no way to check anything in it. Audience fit and clarity are the draft's real strengths. The three concrete habits in the adaptability section, the 90-day audit walkthrough, and the specific metrics (comments-per-impression, shares-per-impression) are directly actionable for a B2B marketing manager running an organic program, and the heading hierarchy is clean and skimmable. Tone is measured and credible without being stiff. SEO is the clearest fixable gap. The primary keyword appears in the H1 and first sentence, and secondary terms are woven in reasonably, but there is exactly one external link — to LinkedIn's advertise page — where the rubric requires two to three. That single deficiency alone blocks a pass, independent of the sourcing issue. Recommendation: revise. The structure, framing, and intellectual honesty are sound enough that this is a fixable draft, not a rewrite. But it needs source excerpts attached and the flat claims either attributed or softened before it can clear review.

Claims not backed by a provided source, or stated more confidently than the evidence supports:

'LinkedIn ... doesn't publish a detailed technical breakdown of exactly how its ranking system works' — stated as flat fact in the introduction. This is an unverified negative claim about what a company has or hasn't published; the draft's own search is absence of evidence, not proof. Needs scoping/hedging ('we could not locate...' with a date) or a citation, or drop it.
'We checked LinkedIn's own business marketing page for a technical explanation of how the feed ranks content. As of this writing, we couldn't find one there.' — presented as a verification step, but there is no source excerpt corroborating that this page was checked or what it contains. Needs the underlying source attached or the claim removed.
'raw totals get skewed by follower growth, and a bigger audience alone can inflate absolute numbers without reflecting a real change in content performance' — asserted as a causal mechanism. Partially framed as 'our reporting preference' but the mechanism itself is stated flatly. Needs attribution/hedging or a supporting source.
'reach fluctuates from quarter to quarter for reasons that aren't always obvious' across 'the accounts we manage' — unhedged first-party performance claim with no sample size, timeframe, or data behind it. Needs scoping or softening.
'a content calendar built on last year's assumptions can start underperforming without anyone noticing right away' — stated as an observed pattern in the introduction with no supporting data or source. Needs hedging as hypothesis or a citation.
Entire article: zero source excerpts were provided, so every claim above and all first-party assertions are ungrounded by default. This is the root issue driving the source_grounding score of 1.
why this score?




Review this option
Sources (3)
https://www.linkedin.com/business/marketing
failed
Couldn't retrieve this source: Firecrawl returned 403 for https://www.linkedin.com/business/marketing: {"success":false,"error":"We apologize for the inconvenience but we do not support this site. If you are part of an enterprise and want to have a further conversation about this, please fill out our intake form here: https://fk4bvu0n5qp.typeform.com/to/Ej6oydlg"}

Example Domain
discarded
Not used: This is the generic example.com placeholder page with only boilerplate text about the domain being reserved for documentation examples; it contains no article content relevant to LinkedIn's algorithm or B2B posting strategy.

mark selected
https://www.nytimes.com/section/technology
failed
Couldn't retrieve this source: Firecrawl returned 403 for https://www.nytimes.com/section/technology: {"success":false,"error":"We apologize for the inconvenience but we do not support this site. If you are part of an enterprise and want to have a further conversation about this, please fill out our intake form here: https://fk4bvu0n5qp.typeform.com/to/Ej6oydlg"}

Channel adaptations (0)
channel content is prepared after a draft is approved

Publishing queue (0)
what do these statuses mean?
nothing queued yet

Manage scheduling, cancelling, and retrying from the publishing queue page.

API usage
$0.6624
40,338 in / 35,683 out · 11 calls
show every pass
Pipeline activity
Intake
3 attachment(s)
09:11 AM

Research(attempt 2)
Planning
09:11 AM

Draft revisions
5 draft attempts completed. This didn't meet quality checks, so it's ready for your review.
Draft generation
option A · v1
09:11 AM
Evaluation
result: revise
09:12 AM
Evaluation
09:12 AM
this draft has no source material to ground claims in, and revising the wording can't fix that — skipping the remaining automatic revisions and sending it to human review now instead of spending the full revision cap

Draft generation
option A · v2 (regenerated from v1)
09:20 AM
grounding validation
09:20 AM
fabricated_url: draft cites https://www.linkedin.com/business/marketing, which was never provided as a source

Draft generation
option A · v3 (regenerated from v2)
09:21 AM
Evaluation
result: revise
09:22 AM
Evaluation
09:22 AM
This draft was revised the maximum number of times but still didn't clear the automatic quality checks (see the feedback on that draft above). Rather than loop forever, it was sent to you to review and decide manually.

Draft generation
option A · v4 (regenerated from v3)
09:29 AM
grounding validation
09:29 AM
revision cap reached with unresolved grounding issues; sending to evaluation anyway: fabricated_url: draft cites https://www.linkedin.com/business/marketing, which was never provided as a source; fabricated_url: draft cites https://www.linkedin.com/business/marketing, which was never provided as a source

Evaluation
result: revise
09:30 AM
Evaluation
09:30 AM
This draft was revised the maximum number of times but still didn't clear the automatic quality checks (see the feedback on that draft above). Rather than loop forever, it was sent to you to review and decide manually.

Draft generation
option A · v5 (regenerated from v4)
09:57 AM
grounding validation
09:57 AM
revision cap reached with unresolved grounding issues; sending to evaluation anyway: fabricated_url: draft cites https://business.linkedin.com/advertise, which was never provided as a source; unsupported_causal_claim: "### Treat Engagement Metrics as Measurement, Not Algorithm Proof In our view, likes are the easiest metric to inflate (a quick tap requires almost no considera"

Evaluation
result: revise
09:58 AM
Evaluation
09:58 AM
This draft was revised the maximum number of times but still didn't clear the automatic quality checks (see the feedback on that draft above). Rather than loop forever, it was sent to you to review and decide manually.




I think i can see the reason why it doesnt always follow the instrinction given as intented, it si too verbose and not structured well with headers and there by making the model confused... also maybe start a conversation for each request so it can keep a session(context window) and not have to add what it has already done before to the context window of that convo or a new one