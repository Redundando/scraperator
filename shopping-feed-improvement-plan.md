# Shopping Feed Improvement Plan

## 1. Executive Summary

Our Google Shopping product feed is the primary way Google understands what we sell. It determines which searches our products appear for, how they are displayed, and ultimately whether a customer clicks through to Audible. Today, our feed contains structural data quality issues that limit Google's ability to surface our products effectively. Several fields contain broken or invalid data, internal-only fields are being sent externally, and we are missing key attributes that Google uses to match, categorise, and rank products.

This document outlines a plan to transform our Shopping feed from a basic product listing into a high-quality, fully optimised data asset. The improvements span three areas: removing fields that don't belong, fixing fields that contain bad data, and adding new fields that unlock better visibility and campaign control. The focus is on the US marketplace, with other marketplaces to follow as a second phase.

The investment is primarily engineering effort to clean the source data and enrich the feed pipeline. The expected return is a significant increase in impression share, click-through rate, and conversion — driven by better product matching, richer ad presentation, and smarter campaign segmentation.

---

## 2. The Problem

When Google ingests our product feed, it uses the data to answer three questions: *What is this product? Who is it for? Should I show it?*

Right now, our feed makes it harder than necessary for Google to answer all three.

**Google can't reliably identify our products.** Our ISBN field — the primary way Google matches audiobooks to its knowledge graph — is corrupted. Every ISBN in the feed is stored as a rounded number rather than a precise 13-digit identifier. This means Google cannot connect our products to the broader book ecosystem (reviews, related titles, author pages, knowledge panels). Products without valid identifiers are treated as generic listings and receive lower ranking priority.

**Our categorisation is flat and ambiguous.** Instead of telling Google "this is a Historical Mystery set in 1920s London, Book 2 in a series", we send a comma-separated list of top-level BISAC labels like `FICTION, HISTORY, BIOGRAPHY & AUTOBIOGRAPHY`. Google cannot parse this into a meaningful hierarchy. The result is weaker category matching and missed opportunities to appear in specific, high-intent searches.

**We are sending data that shouldn't be external.** The feed contains internal moderation fields, workflow comments, internal ticket URLs, and scoring data. Some items flagged as "Not approved for feed" with specific policy reasons (including internal tool links) appear to be present in the data sent to Google. This is both a data leak risk and a source of noise.

**Key product attributes are missing or malformed.** Series names have "(Unabridged)" appended to them. Product URLs are inconsistently formatted, with some missing path separators. The narrator field is empty for some titles and contains internal labels like "Virtual Voice" for others. Release dates use an ambiguous format. Language values include non-standard entries like "British English".

**We are not using the fields Google gives us for campaign optimisation.** Google Shopping supports five custom label fields specifically designed for bid segmentation. We are not using any of them. This means we cannot differentiate bidding between a top-100 bestseller and a long-tail title with zero ratings, between a new release and a 10-year-old backlist title, or between an Audible Exclusive and a standard ACX upload.

---

## 3. The Opportunity

A well-optimised Shopping feed is one of the highest-leverage improvements available in paid product marketing. Unlike ad copy or bidding strategy — which operate on top of the feed — feed quality determines the ceiling of what is possible. A bad feed limits everything downstream. A great feed lifts everything.

Here is what we can expect from a best-in-class feed:

**Expanded impression share.** Google can only show our products for searches it understands we're relevant for. With valid ISBNs, proper categorisation, and enriched product data, Google can match our titles to significantly more queries — including long-tail searches by narrator, series name, genre combinations, and related titles. For a catalog of 100k+ titles, even a modest improvement in match rate translates to a large absolute increase in impressions.

**Higher click-through rates.** Google Shopping ads that display richer information (product highlights, accurate titles, proper images) consistently outperform sparse listings. Adding structured attributes like product highlights — "Unabridged", "14 hours", "Book 3 in the Saffron Everleigh Mystery series", "Narrated by Cassandra Campbell" — gives customers the information they need to click with confidence. Industry benchmarks suggest that enriched product data can improve CTR by 20-40% compared to bare-minimum listings.

**Better conversion rates.** When the feed accurately represents the product, customers arrive at the landing page with correct expectations. Mismatches between the ad and the landing page (wrong title formatting, missing series info, ambiguous categorisation) create friction that reduces conversion. A clean, accurate feed reduces this friction.

**Smarter spend allocation.** Custom labels allow us to segment our catalog for bidding purposes. We already have the internal data to do this — trial ranks, ratings, release dates, exclusivity status — but none of it is being passed to Google in a usable form. With proper custom labels, we can bid aggressively on proven performers and conservatively on long-tail titles, dramatically improving return on ad spend.

**Reduced disapprovals.** Invalid data (broken ISBNs, zero sale prices, malformed URLs, non-standard language codes) causes Google to reject or suppress products. Every disapproved product is a product that cannot generate impressions. Fixing these issues recovers lost inventory.

**Foundation for multi-marketplace expansion.** Getting the US feed right establishes the data model, transformation logic, and quality standards that can be replicated across our other 10 marketplaces. The investment pays dividends at scale.

In a perfect execution scenario — valid identifiers, rich categorisation, optimised descriptions, full use of custom labels, and clean data across the board — we would expect to see a step-change in Shopping performance rather than an incremental improvement. The current feed is leaving significant money on the table.


---

## 4. Current Feed Fields

| # | Field | Description | Status |
|---|---|---|---|
| 1 | `audible_asin` | Audible product identifier | ✅ Good |
| 2 | `amazon_asin` | Amazon product identifier | ⚠️ Has `UNKNOWN` values |
| 3 | `marketplace` | Target marketplace (e.g. `US`) | ✅ Good |
| 4 | `title` | Product title | ✅ Good |
| 5 | `description` | Product description | ⚠️ Truncated, not optimised for search |
| 6 | `availability` | Stock status | ✅ Good |
| 7 | `condition` | Product condition (always `New`) | ✅ Good |
| 8 | `production_type` | Internal production label (e.g. `Audiobook, Exclusive`, `Audiobook, ACX`) | ⚠️ Not a Google attribute |
| 9 | `price` | Product price (e.g. `17.24 USD`) | ✅ Good |
| 10 | `language` | Content language | ⚠️ Non-standard values like `British English` |
| 11 | `sale_price` | Sale price | ❌ Always `0`, invalid |
| 12 | `sale_price_effective_date` | Sale price date range | ❌ Always empty |
| 13 | `link` | Product page URL | ⚠️ Some URLs have missing `/` separator |
| 14 | `product_image_large` | Large product image URL | ⚠️ Not a Google attribute name |
| 15 | `image_link` | Primary product image URL | ✅ Good |
| 16 | `author` | Author name(s) | ⚠️ Roles, multi-author ambiguity |
| 17 | `google_product_category` | Google taxonomy ID (always `543541`) | ✅ Acceptable |
| 18 | `narrator` | Narrator name(s) | ⚠️ Empty or `Virtual Voice` for some titles |
| 19 | `publisher` | Publisher name | ⚠️ Empty for Virtual Voice titles |
| 20 | `product_type` | Always `Audiobook` | ⚠️ Wasted — should carry taxonomy |
| 21 | `category` | BISAC top-level categories, comma-separated | ⚠️ Not a hierarchy |
| 22 | `subcategory_1` | BISAC label overflow | ⚠️ Not a real subcategory |
| 23 | `subcategory_2` | BISAC label overflow | ⚠️ Not a real subcategory |
| 24 | `subcategory_3` | BISAC label overflow | ⚠️ Not a real subcategory |
| 25 | `subcategory_4` | BISAC label overflow | ⚠️ Not a real subcategory |
| 26 | `subcategory_5` | BISAC label overflow | ⚠️ Not a real subcategory |
| 27 | `product_primary_category` | Audible browse category path | ⚠️ Inconsistent depth |
| 28 | `audiobook_duration` | Runtime in minutes | ✅ Good as source data |
| 29 | `release_date` | Release date | ⚠️ Ambiguous `DD.MM.YYYY` format |
| 30 | `book_series` | Series name | ⚠️ Has `(Unabridged)` appended |
| 31 | `total_ratings` | Number of ratings | ✅ Good as source data |
| 32 | `average_rating` | Average star rating | ✅ Good as source data |
| 33 | `total_reviews` | Number of reviews | ✅ Good as source data |
| 34 | `isbn` | ISBN identifier | ❌ Scientific notation, corrupted |
| 35 | `product_credits_required` | Whether a credit can be used | ⚠️ Internal concept |
| 36 | `ios_app_store_id` | iOS app ID | ❌ Wrong feed type |
| 37 | `ios_app_name` | iOS app name | ❌ Wrong feed type |
| 38 | `android_package` | Android package name | ❌ Wrong feed type |
| 39 | `android_app_name` | Android app name | ❌ Wrong feed type |
| 40 | `audiosnippet_link` | Sample audio MP3 URL | ❌ Not used by Google Shopping |
| 41 | `trials_rank_90` | Internal 90-day trial rank | ❌ Internal metric |
| 42 | `trials_rank_30` | Internal 30-day trial rank | ❌ Internal metric |
| 43 | `trials_rank_all` | Internal all-time trial rank | ❌ Internal metric |
| 44 | `trials_directs_rank_90` | Internal 90-day direct trial rank | ❌ Internal metric |
| 45 | `trials_directs_rank_30` | Internal 30-day direct trial rank | ❌ Internal metric |
| 46 | `trials_directs_rank_all` | Internal all-time direct trial rank | ❌ Internal metric |
| 47 | `book_distribution_rights` | Geographic rights (e.g. `Worldwide`, `US Only`) | ⚠️ Useful source data, not a Google field |
| 48 | `aycl_title` | Internal flag (Y/N) | ❌ Internal |
| 49 | `random_30` | Unknown internal metric | ❌ Internal |
| 50 | `random_90` | Unknown internal metric | ❌ Internal |
| 51 | `random_120` | Unknown internal metric | ❌ Internal |
| 52 | `model_xyz` | Unknown internal metric | ❌ Internal |
| 53 | `parent_product_id` | Internal content ID | ⚠️ Could map to `item_group_id` |
| 54 | `bisac_genre_code` | BISAC codes (e.g. `FIC022040, FIC022060`) | ✅ Good as source data |
| 55 | `bisac_genre_key` | Always `BISAC` | ❌ Redundant |
| 56 | `product_keywords` | Keyword tags | ⚠️ Useful source data, not directly a Google field |
| 57 | `raunchiness_score` | Internal content score | ❌ Internal |
| 58 | `product_short_title` | Shortened title | ⚠️ Could be useful if cleaned |
| 59 | `janus_score` | Internal scoring metric | ❌ Internal |
| 60 | `product_member_price` | Audible member price | ⚠️ Internal pricing concept |
| 61 | `review_id` | Internal review/moderation ID | ❌ Internal, data leak risk |
| 62 | `update_dt` | Internal update timestamp | ❌ Internal |
| 63 | `cleared_for_merch` | Internal approval flag | ❌ Internal |
| 64 | `user_name` | Internal reviewer username | ❌ Internal, data leak risk |
| 65 | `policy` | Internal policy flag | ❌ Internal, data leak risk |
| 66 | `comment` | Internal moderation comment | ❌ Internal, data leak risk |
| 67 | `is_active` | Internal active flag | ❌ Internal |
| 68 | `Janus_Segments` | Internal segmentation label | ❌ Internal |
| 69 | `___id` | Internal row ID | ❌ Internal |


---

## 5. Fields to Remove

These fields should be stripped from the feed entirely before submission to Google. They provide no value to Google Shopping and several pose a data leak risk.

### Internal scoring and ranking metrics

| Field | Reason |
|---|---|
| `trials_rank_90` | Internal performance metric. Google cannot use it. Should be transformed into a `custom_label` bucket instead (see Section 7). |
| `trials_rank_30` | Same as above. |
| `trials_rank_all` | Same as above. |
| `trials_directs_rank_90` | Same as above. |
| `trials_directs_rank_30` | Same as above. |
| `trials_directs_rank_all` | Same as above. |
| `random_30` | Unknown internal metric. Always `0` in sampled data. |
| `random_90` | Same as above. |
| `random_120` | Same as above. |
| `raunchiness_score` | Internal content moderation score. |
| `janus_score` | Internal scoring metric. |
| `Janus_Segments` | Internal segmentation label. |
| `model_xyz` | Unknown internal metric. Always empty in sampled data. |

### Internal workflow and moderation fields

| Field | Reason |
|---|---|
| `review_id` | Internal moderation review ID. |
| `update_dt` | Internal timestamp. |
| `cleared_for_merch` | Internal approval flag. |
| `user_name` | Internal reviewer username. **Data leak risk** — exposes employee names. |
| `policy` | Internal policy classification (e.g. `Hate`, `Suggestive`, `Length`). **Data leak risk** — exposes moderation decisions. |
| `comment` | Internal moderation notes. **Data leak risk** — contains internal tool URLs (e.g. `https://tt.amazon.com/...`, `https://t.corp.amazon.com/...`) and suppression reasons. |
| `is_active` | Internal active flag. Should be used to *filter* the feed, not included as a field. |
| `___id` | Internal row identifier. |

### Wrong feed type

| Field | Reason |
|---|---|
| `ios_app_store_id` | Describes the Audible iOS app, not the product. Belongs in an app campaign feed, not a Shopping feed. |
| `ios_app_name` | Same as above. Always `Audible for iOS`. |
| `android_package` | Same as above. Always `com.audible.application`. |
| `android_app_name` | Same as above. Always `Audible for Android`. |

### Redundant or unused

| Field | Reason |
|---|---|
| `sale_price` | Always `0`. Google interprets `0` as "free". Must be either a valid price or omitted entirely. |
| `sale_price_effective_date` | Always empty. Required by Google when `sale_price` is present, but since `sale_price` should be removed when there's no sale, this goes too. |
| `audiosnippet_link` | Sample audio MP3 URL. Google Shopping does not use audio samples. Not used by Meta product feeds in practice either. |
| `bisac_genre_key` | Always `BISAC`. Adds no information. |
| `aycl_title` | Internal flag (Y/N). Not a Google attribute. |
| `product_credits_required` | Internal Audible concept. Google does not understand credit-based pricing. |

**Note:** Several of these fields (`trials_rank_*`, `book_distribution_rights`, `production_type`, `bisac_genre_code`) contain valuable *source data* that should be used to *derive* feed fields (custom labels, excluded destinations, product type). They should be consumed by the transformation layer but not passed through to the output feed.


---

## 6. Fields to Fix

These fields exist in the feed but contain data quality issues that reduce their effectiveness or cause Google to reject/downrank products.

### 6.1 `isbn` — Corrupted identifiers

**What's wrong:** Every ISBN in the feed is stored in scientific notation (e.g. `9.7818E+12` instead of `9781799750507`). This is caused by the source system (likely Excel or a numeric database column) treating 13-digit ISBNs as numbers rather than strings. Many titles have `UNKNOWN` as the ISBN value.

**Why it matters:** The ISBN/GTIN is the single most important identifier for Google's knowledge graph matching. A valid ISBN allows Google to connect our product to its global book database — unlocking rich results, related product suggestions, author knowledge panels, and better category inference. Without it, our products are treated as unrecognised generic listings.

**What good looks like:**
- Titles with a known ISBN: `9781799750507` (13-digit string, no rounding)
- Titles without an ISBN: field should be omitted entirely, and `identifier_exists` should be set to `no`

---

### 6.2 `link` — Inconsistent URL formatting

**What's wrong:** Some product URLs are missing the `/` separator between the slug and `Audiobook`:
- ❌ `https://www.audible.com/pd/comentando-lecturas-terap-uticasAudiobook/B0F3C5G4J6`
- ❌ `https://www.audible.com/pd/return-to-the-westAudiobook/B0GN9X3LJN`
- ❌ `https://www.audible.com/pd/rome-1960Audiobook/B002UZN7DU`
- ✅ `https://www.audible.com/pd/an-unequal-defense-Audiobook/1799750507`

**Why it matters:** Broken URLs mean Google cannot crawl the landing page. Products with unreachable landing pages are disapproved and receive zero impressions.

**What good looks like:** All URLs should follow the pattern `https://www.audible.com/pd/{slug}-Audiobook/{asin}` with a consistent `-` before `Audiobook`.

---

### 6.3 `language` — Non-standard values

**What's wrong:** Some titles use `British English` instead of `English`. Google's `content_language` attribute expects ISO 639-1 codes (`en`, `es`, `fr`, etc.) or at minimum standard language names.

**Why it matters:** Non-standard language values may cause Google to misclassify or ignore the language attribute, affecting which marketplace and audience the product is served to.

**What good looks like:** `English` or `en` for all English-language titles regardless of accent. `Spanish` or `es` for Spanish titles. Ideally use ISO 639-1 codes.

---

### 6.4 `author` — Unstructured multi-value field

**What's wrong:** The author field contains multiple issues:
- Role suffixes mixed in: `James Buckley, Jr., Who HQ, Yanitzia Canetti - translator`
- Illustrator credits: `Tom Angleberger, Cece Bell - Illustrator`
- Five authors in one string: `Ivy Caldwell, Kamilah Ellis, Monique Rodgers, Celia McIntosh, Phylicia Spaulding`
- Comma ambiguity with suffixes: `James Buckley, Jr.` — is "Jr." a second author or a suffix?
- Corporate authors mixed with person names: `Mickie Matheis, Nickelodeon Publishing`

**Why it matters:** Google treats the entire string as a single author name. It cannot parse roles, distinguish corporate entities, or handle comma-separated lists where commas also appear within names. This reduces the chance of matching author-specific searches.

**What good looks like:**
- Primary author only in the `author` field: `James Buckley Jr.`
- No role suffixes
- Co-authors, translators, illustrators in separate custom attributes or omitted
- Corporate authors (publishers acting as author) flagged and handled separately

---

### 6.5 `narrator` — Empty or internal labels

**What's wrong:**
- Some titles have an empty narrator field (e.g. ¿Quién es Cristiano Ronaldo?)
- Many titles have `Virtual Voice` or `Voz Virtual` — these are internal production labels for AI-generated narration, not meaningful to customers

**Why it matters:** Narrator is a genuine search signal for audiobooks. Customers search by narrator name. An empty field is a missed opportunity. "Virtual Voice" is meaningless to a customer and could be confusing or off-putting.

**What good looks like:**
- Human-narrated titles: clean narrator name(s)
- AI-narrated titles: either `AI Narrated` (transparent) or omit the field. Decision depends on brand strategy, but `Virtual Voice` should not be customer-facing.

---

### 6.6 `publisher` — Empty for Virtual Voice titles

**What's wrong:** Several AI-narrated titles have a blank publisher field: Return to the West, Starlight Wishes, ETERNOS AL FIN, Relationship Resolution, Dark Psychology journal, ZINC.

**Why it matters:** Google may flag products with missing publisher as incomplete. Publisher is also a trust signal for customers.

**What good looks like:** Every title should have a publisher. For self-published titles, the author name or imprint can serve as publisher. For Virtual Voice titles specifically, a consistent publisher value should be assigned.

---

### 6.7 `product_type` — Wasted field

**What's wrong:** Every single item has `product_type: Audiobook`. This field is meant to carry your internal product taxonomy as a `>` delimited hierarchy. It is one of the most valuable fields Google offers for product categorisation and campaign segmentation.

**Why it matters:** Google uses `product_type` to understand what your product is at a granular level. `Audiobook` tells Google nothing it doesn't already know from `google_product_category: 543541`. A proper hierarchy enables better search matching and allows campaign managers to create product groups by category.

**What good looks like:** `Audiobook > Fiction > Mystery, Thriller & Suspense > Cozy Mystery` or `Audiobook > Non-Fiction > Health & Wellness > Nutrition`. Derived from `bisac_genre_code` and/or `product_primary_category`.

---

### 6.8 `category` / `subcategory_1-5` — Flat list, not a hierarchy

**What's wrong:** These fields contain comma-separated BISAC top-level labels spread across numbered columns:
- `category: SOCIAL SCIENCE, HISTORY, BIOGRAPHY & AUTOBIOGRAPHY, POLITICAL SCIENCE`
- `subcategory_1: SOCIAL SCIENCE`
- `subcategory_2: HISTORY`
- `subcategory_3: BIOGRAPHY & AUTOBIOGRAPHY`

This is not a parent → child hierarchy. It's the same flat list split arbitrarily.

**Why it matters:** Google cannot parse this into meaningful categorisation. These fields are not standard Google Shopping attributes and are likely ignored entirely.

**What good looks like:** Replace with a properly structured `product_type` field (see 6.7). These source fields can be removed from the output feed.

---

### 6.9 `release_date` — Ambiguous format

**What's wrong:** Dates use `DD.MM.YYYY` format (e.g. `06.03.2020`). This is ambiguous — is that March 6th or June 3rd?

**Why it matters:** Google expects ISO 8601 format. An ambiguous date may be misinterpreted, affecting "new release" signals and any date-based filtering.

**What good looks like:** `2020-03-06` (ISO 8601).

---

### 6.10 `book_series` — Format info appended

**What's wrong:** Series names have `(Unabridged)` appended:
- `David Adams (Unabridged)`
- `Like Us (Unabridged)`
- `Soho Noir (Unabridged)`

**Why it matters:** "Unabridged" is a format attribute, not part of the series name. This pollutes the series data and makes it harder to match series-based searches.

**What good looks like:** `David Adams`, `Like Us`, `Soho Noir`. Format information belongs in a separate field or in `product_highlight`.

---

### 6.11 `amazon_asin` — Invalid values

**What's wrong:** At least one title has `amazon_asin: UNKNOWN` (Word of the Day: Taciturn).

**Why it matters:** If this field is used for any matching or linking, an invalid value could cause errors. Should be null/empty or omitted when unknown.

**What good looks like:** Valid 10-character ASIN or empty.

---

### 6.12 `product_primary_category` — Inconsistent depth

**What's wrong:** Category paths vary wildly in specificity:
- Very specific: `Mystery, Thriller & Suspense/Thriller & Suspense/Legal` (3 levels)
- Very broad: `Literature & Fiction` (1 level)
- Arguably wrong: `Classics` for a children's biography about Cristiano Ronaldo

**Why it matters:** Inconsistent categorisation means Google gets strong signals for some products and weak signals for others. Miscategorised products appear in wrong search results.

**What good looks like:** Consistent depth (minimum 2-3 levels) across all titles, derived from a standardised mapping.

---

### 6.13 `description` — Not optimised for Shopping

**What's wrong:** Descriptions are publisher-provided blurbs, often truncated, and not optimised for search discovery. They don't front-load key search terms (author, narrator, series, genre) and some are cut off mid-sentence.

**Why it matters:** Google indexes description text for query matching. The first ~500 characters carry the most weight. A description that buries the author name in paragraph three and never mentions the narrator or series position is missing high-intent search matches.

**What good looks like:** Descriptions that lead with the most searchable attributes — author, series name and position, narrator (for well-known narrators), genre, and a compelling hook — followed by the publisher summary. This is a candidate for AI-assisted rewriting at scale.

---

### 6.14 `product_image_large` — Non-standard field name

**What's wrong:** This field contains a valid image URL but uses a non-standard field name that Google does not recognise. Google expects `image_link` (which we already have) and `additional_image_link` for secondary images.

**Why it matters:** The data is there but Google can't use it because the field name is wrong.

**What good looks like:** Rename to `additional_image_link` so Google picks up both images.

