# Adding KB Entries (PM Guide)

Pawly's general knowledge base feeds the bot facts about pet care, behaviour,
nutrition, life stages, regional norms, and breed-specific care. Every entry
in the KB can be retrieved during a chat and used to ground an answer.

This guide is for **adding new entries** as a PM, without touching code or git.

---

## TL;DR

1. Open the shared Google Sheet (link in #pawly-kb channel)
2. Add a row. Fill in `id`, `domain`, `content`, `keywords_en`, `keywords_cn`,
   `citations`. Leave `status` as `draft`.
3. When the entry is finished and reviewed, change `status` to `ready`.
4. Within a day, sync runs and the entry goes live in production.
5. If something is wrong, the `notes` column will tell you what to fix.

That's it. The rest of this doc explains how to write a *good* entry.

---

## What belongs in the KB

**Yes** — evergreen, factual information about:
- General pet care (grooming, dental, nail trimming, microchipping)
- Behaviour fundamentals (separation anxiety, resource guarding, training)
- Life stages (puppy socialization, senior signs, spay/neuter timing)
- Nutrition basics (life-stage diets, body condition scoring)
- Regional norms (Singapore HDB rules, tropical climate care)
- Breed-care basics (brachycephalic, giant breeds, long-back breeds)

**No** — these go elsewhere:
- Symptom triage / "my dog ate X" → already in `followups.yaml` (technical)
- Safety rules / non-negotiable bot constraints → `special_rules.yaml` (technical)
- Single-case answers ("what should owner Y do about pet Z") → out of scope
- Specific drug doses, prescriptions → bot refuses these by design

---

## Column reference

| Column         | Required | Format                                                                  | Example                                                      |
|----------------|----------|-------------------------------------------------------------------------|--------------------------------------------------------------|
| `id`           | yes      | `lowercase_snake_case`, must be unique                                  | `litter_box_setup`                                           |
| `domain`       | yes      | one of: `care`, `behavior`, `stage`, `region`, `nutrition`, `breed_care` | `care`                                                       |
| `content`      | yes      | 30–250 words, factual paragraph, no diagnosis, no specific drug doses   | "The standard guideline is n+1 litter boxes for n cats…"     |
| `keywords_en`  | no       | comma- or newline-separated phrases                                     | `litter box, litter tray, n+1 rule, cat toilet`              |
| `keywords_cn`  | no       | comma- or newline-separated phrases                                     | `猫砂盆, 厕所, 猫砂, 铲屎`                                   |
| `citations`    | no       | comma-separated source list                                             | `AAFP/ISFM 2014 Inappropriate Elimination`                   |
| `status`       | yes      | `draft` while writing, `ready` when done, `live` set automatically      | `draft` → `ready`                                            |
| `notes`        | auto     | leave empty; sync writes error messages here                            | _(auto-populated)_                                           |

---

## How to write good content

**Length:** 50–150 words is the sweet spot. Under 30 = rejected by the sync.
Over 250 = also rejected; split into multiple entries.

**Voice:** Third-person, factual, like a textbook entry. The bot will rephrase
it for the user — don't write the bot's reply, write the source material.

**Bad:**

> Hi! Litter boxes are super important. I always tell my cats they need their
> own boxes. The number is n+1 boxes! Have fun cleaning! 😊

**Good:**

> The standard guideline is n+1 litter boxes for n cats (e.g. 3 boxes for 2
> cats), placed in separate quiet locations. Box size should be 1.5× the
> length of the cat from nose to base of tail; most commercial trays are too
> small. Litter depth 5–8 cm of unscented clumping clay. Scoop at least once
> daily, full litter replacement every 1–2 weeks. Sudden avoidance of the
> box usually has a medical or environmental cause, not a behaviour issue.

**Keywords:** Anything a user might literally type into chat. Include
synonyms ("brushing teeth" + "dental care" + "oral hygiene"). Chinese
keywords are matched as substrings, so prefer common phrases.

**Citations:** Optional but helpful. Use the source organisation +
guideline name when possible (e.g. `AAFP 2024 Senior Care Guidelines`,
`WSAVA Vaccination Guidelines`). Don't link to random blogs.

---

## What happens after you set `status=ready`

1. Daily sync (or manual trigger by a dev) runs `scripts/sheet_to_yaml.py`
2. The script validates every `status=ready` row:
   - id format, domain validity, content length, no duplicates
   - All errors go into the `notes` column of *your* row
3. If **all** ready rows pass → yaml is updated, embeddings refreshed, KB live
4. If **any** ready row fails → no yaml write; fix your row's notes and the
   next sync will pick it up
5. Successful rows get `status` flipped to `live` and `notes` cleared

You don't need to ping anyone for normal additions. Engineering only gets
involved if you need a new `domain` or want to change the schema.

---

## Editing or removing an existing entry

- **Edit:** find the row in the sheet, change the content, leave status as
  `live`. Then change status to `ready` again. Next sync re-publishes.
- **Remove:** delete the row from the sheet. The next sync will not remove
  the entry from the yaml on its own — ping a dev to run
  `scripts/kb_ingest.py --delete-stale` after the sync.
- The yaml file is the source of truth for the database. The sheet is the
  source of truth for the yaml. Always edit at the sheet level.

---

## When to ask engineering

- You want a new `domain` value (current list: care, behavior, stage,
  region, nutrition, breed_care)
- You want to remove entries en masse
- You see validation errors you don't understand
- The KB seems to be giving wrong answers in eval / production
- You want to extend regional coverage beyond Singapore

Slack: #pawly-kb or @atlas
