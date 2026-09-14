# AI Content Research and Publishing Agent — Week 4

## What this project is

A marketing agency at Koya Talent creates and publishes content across LinkedIn, X, and an email newsletter. The current workflow — brainstorming, researching, writing SEO articles, adapting them per channel, reviewing, and publishing — works but takes too much manual effort to scale while keeping quality, tone, and factual accuracy consistent.

Your job: build an **AI content research and publishing agent** that moves the team from a raw idea or source URL to reviewed, channel-ready content with as much automation as possible.

---

## The workflow you are automating

1. A content manager submits a **content request** (at minimum: raw content idea, target audience, and any supporting material or source URL — you decide what else to collect and how to collect it).
2. The system **researches the topic** and retrieves relevant source material.
3. It **chooses the sources or excerpts that matter**.
4. It **plans the content**.
5. It **generates article options**.
6. It **evaluates its own output** using the content evaluation rubric.
7. It **revises weak drafts**.
8. It **prepares the selected content** for LinkedIn, X, and an email newsletter.
9. A **human review step** where a human can approve, reject, revise, or select content before publishing or scheduling.
10. Approved content gets **published, scheduled, or saved into a clear publishing queue**.

Throughout, the content must stay **grounded in reviewed source material**, and the system must make it clear **which sources informed the output**.

---

## Constraints and rules the system must follow

### SEO best practices (from `../provided/assets/seo-best-practices.md`)

- Get the primary keyword from the content idea.
- Include the primary keyword in the article title.
- Include the primary keyword in the first 100 words.
- Analyze strong competing or reference articles to identify long-tail and short-tail keywords.
- Use relevant secondary keywords in the body and section headers.
- Use one H1 title.
- Use H2 section headers.
- Use H3 subheaders where needed.
- Use short paragraphs of 2 to 3 sentences.
- Let the depth of each main section reflect the strength and complexity of the source material.
- Include 2 to 3 relevant internal or external links.
- Keep the writing readable for a broad audience.
- Include one contextually relevant image if the content needs one.
- Keep claims grounded in reviewed source material.

### Channel formatting rules (from `../provided/assets/channel-formatting-rules.md`)

**LinkedIn Post:**
- Use the PAS copywriting structure: problem, agitation, solution.
- Keep paragraphs short.
- Use bullets or simple symbols when they improve clarity.
- Use a small number of relevant emojis only when they fit the brand voice.
- End with a clear call to action.
- Include a relevant image or carousel if useful.

**X Post:**
- Lead with the main benefit, insight, or hook.
- Keep the post focused on one core idea.
- Use line breaks for readability.
- Use no more than 1 to 2 relevant hashtags.
- Tag another account only if the tag adds value.

**Email Newsletter:**
- Use a strong subject line with a clear benefit or point of intrigue.
- Start with a short intro of 1 to 3 sentences.
- Make the main value section easy to skim with subheadings or bullets.
- Add an optional secondary item, such as a quick tip, link, or update.
- Include a clear call to action.
- Use a friendly sign-off.
- Write like you are speaking to a smart, busy reader who trusts you to send something useful.
- Keep the newsletter between 250 and 600 words.

### Content evaluation rubric (from `../provided/assets/content-evaluation-rubric.md`)

For each draft, evaluate against these criteria:

| Criterion | What to check |
| --- | --- |
| Topic Relevance | The content answers the request and stays focused on the intended topic. |
| Source Grounding | Claims, examples, and recommendations connect back to reviewed source material. |
| Factual Consistency | The content avoids contradictions, unsupported claims, and invented details. |
| Audience Fit | The content speaks to the target audience at the right level of depth. |
| Tone | The style matches the brand and channel. |
| SEO Fit | The article uses the primary keyword, relevant secondary keywords, clear headings, and useful links. |
| Channel Fit | Each adapted output follows the platform formatting rules. |
| Clarity | The content is easy to read, skimmable, and direct. |
| Completeness | The output includes every required section or channel asset. |

The evaluation output for each draft must include:
- Overall status: pass, revise, or reject
- Scores or short notes for the criteria above
- Unsupported or weak claims to remove or rewrite
- Sections that need revision
- Specific recommended changes
- Final approval status

---

## What you are allowed to use

You may use any of the following — pick what fits your implementation:
- n8n
- Custom code
- Claude API
- Claude through n8n
- A backend application
- A simple front-end
- Search or scraping tools
- A retrieval system
- A database
- A publishing queue
- Any other tools that fit

---

## Testing — 8 scenarios you must verify before submission

1. **Raw Idea Request**: A content request with only a topic or idea should produce relevant article options.
2. **URL-Based Request**: A content request with a source URL should extract useful source material and use it in the generated content.
3. **Research and Source Grounding**: The system should show which sources informed the output and avoid claims that are not supported by the available material.
4. **Evaluation and Revision Loop**: The system should evaluate draft quality using the content evaluation rubric, revise weak sections, and preserve the review history.
5. **Human Approval**: The system should not publish or schedule content until a human approves it.
6. **Channel Formatting**: The selected article should be adapted into LinkedIn, X, and newsletter formats that follow the formatting rules.
7. **Publishing or Scheduling**: Approved content should be published, scheduled, or saved into a clear publishing queue.
8. **Failure Handling**: If research, retrieval, generation, evaluation, approval, publishing, or logging fails, the system should make the failure clear enough to debug.

Submit the completed testing evidence table from the project page with your project.

---

## Deliverables you must submit

- A working **front-end or application link**
- A generated **content sample pack** that shows the input given to the system and the outputs it produced, including the article, LinkedIn post, X post, email newsletter, and source list
- Completed **testing evidence**
- A short **Loom video** showing how the automation works
- Answers to the questions in your **reflection sheet** for this project
- A **one-page document** explaining how your automation works and how to use it

---

## Reference resources provided in this project folder

**Local assets (use these first):**
- `../provided/assets/seo-best-practices.md` — SEO rules for article generation
- `../provided/assets/channel-formatting-rules.md` — formatting rules for LinkedIn, X, and email newsletter outputs
- `../provided/assets/content-evaluation-rubric.md` — evaluation criteria for the review and revision loop

**External resources you can use while designing and building:**

**Claude and AI generation:**
- Get started with Claude: https://platform.claude.com/docs/en/get-started
- Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Context windows: https://platform.claude.com/docs/en/build-with-claude/context-windows
- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing

**Research, scraping, and retrieval:**
- Firecrawl API introduction: https://docs.firecrawl.dev/api-reference/v2-introduction
- Firecrawl scrape endpoint: https://docs.firecrawl.dev/api-reference/endpoint/scrape
- Crawl4AI quickstart: https://docs.crawl4ai.com/core/quickstart/
- Supabase AI and Vectors: https://supabase.com/docs/guides/ai
- Supabase vector columns: https://supabase.com/docs/guides/ai/vector-columns

**Optional workflow automation:**
- n8n HTTP Request node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
- n8n Code node: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.code/
- n8n executions: https://docs.n8n.io/workflows/executions/all-executions/

---

## What you need to decide and build (summary checklist)

1. **Input mechanism**: How does a content manager submit a request? What fields do you collect beyond the minimum (idea, audience, source URL)?
2. **Research and retrieval**: How does the system find and extract source material? (Firecrawl, Crawl4AI, search, scraping, etc.)
3. **Source selection**: How does the system choose which sources or excerpts matter?
4. **Content planning**: How does the system plan the article structure?
5. **Article generation**: How does the system generate article options? How does it apply SEO best practices?
6. **Evaluation**: How does the system evaluate drafts against the rubric? How does it decide pass / revise / reject?
7. **Revision**: How does the system revise weak sections? How does it preserve review history?
8. **Channel adaptation**: How does the system adapt the selected article into LinkedIn, X, and newsletter formats following the formatting rules?
9. **Human review interface**: How does a human approve, reject, revise, or select content? How does the system block publishing before approval?
10. **Publishing / scheduling**: How does approved content get published, scheduled, or queued?
11. **Failure handling**: How does the system report failures clearly enough to debug at each stage (research, retrieval, generation, evaluation, approval, publishing, logging)?
12. **Source attribution**: How does the system make it clear which sources informed the output?
13. **Front-end or application**: What do you ship as the working link?
14. **Sample pack**: What input and outputs do you capture to demonstrate the system works?
15. **Testing evidence**: Which 8 scenarios did you test and what were the results?
16. **Loom video**: What does the demo show?
17. **Reflection sheet**: What questions do you answer?
18. **One-page document**: How do you explain the automation and how to use it?
