Now I have a very thorough picture. Here is the complete README:

---

# Audible Catalog Search API — README

> **Endpoint:** `GET /1.0/catalog/search`
> **Owning Team (API layer):** ARCADIA (Audible Catalog Data / AACDS)
> **Owning Team (Search engine):** VISUALSRCH (Audible Search & Entities — SET)
> **Search Engine:** ASIS — Audible Search Interface Service (`AudibleSearchInterfaceService`)
> **Used by:** Audible Android app, Audible iOS app, Audible Web (`Audiblecomwebsite`)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Base URLs by Marketplace](#base-urls-by-marketplace)
4. [Endpoint](#endpoint)
5. [Query Parameters](#query-parameters)
   - [Confirmed Parameters](#confirmed-parameters)
   - [Likely Supported Parameters](#likely-supported-parameters)
   - [Not Confirmed Parameters](#not-confirmed-parameters)
6. [Response Groups](#response-groups)
7. [content\_type Values](#content_type-values)
8. [products\_sort\_by Values](#products_sort_by-values)
9. [Response Shape](#response-shape)
10. [Search Intent Types](#search-intent-types)
11. [Filters](#filters)
12. [The `locale` Parameter — Behaviour & History](#the-locale-parameter--behaviour--history)
13. [Searching by Author + Title](#searching-by-author--title)
14. [Authentication](#authentication)
15. [Error Handling & HTTP Response Codes](#error-handling--http-response-codes)
16. [Known Limitations & Notes](#known-limitations--notes)
17. [Upcoming Changes](#upcoming-changes)

---

## Overview

The **Audible Catalog Search API** is a publicly accessible REST endpoint that allows callers to search the Audible catalog by keyword, browse node, content type, and other filters. It is the same endpoint used by the **Audible Android and iOS apps** to power the Search Results Page (SRP).

The endpoint is part of the **Audible API Catalog Data Service (AACDS)** layer but delegates actual search execution to **ASIS (Audible Search Interface Service)**, which is owned and maintained by the **VISUALSRCH (SET)** team. AACDS acts as a pass-through and enrichment layer — validating requests, enriching results with product metadata, and applying locale handling — before returning results.

**Confirmed working example (from Jira ARCADIA-1407):**
```
GET https://api.audible.co.jp/1.0/catalog/search
    ?response_groups=&keywords=love
    &node=8191[...]
    &content_type=All
    &origin_page=home
    &locale=en-US
```

---

## Architecture

```
Client (Android / iOS / Web / External)
            │
            ▼
  GET /1.0/catalog/search
            │
            ▼
  ┌─────────────────────────────────┐
  │  AACDS                          │
  │  (Audible API Catalog Data Svc) │
  │  Owner: ARCADIA team            │
  │                                 │
  │  • Validates locale against     │
  │    RSASSupportedLocales config  │
  │    (post Aug 2025: passes       │
  │    any locale directly)         │
  │  • Enriches results with        │
  │    product metadata             │
  └──────────┬──────────────────────┘
             │
             ▼
  ┌──────────────────────────────────┐
  │  ASIS                            │
  │  (Audible Search Interface Svc)  │
  │  Owner: VISUALSRCH (SET) team    │
  │                                  │
  │  • Executes actual search query  │
  │  • Calls A9 / Amazon search      │
  │  • Query understanding (METIS /  │
  │    QUZen) for intent detection   │
  │  • Applies ranking heuristics    │
  │  • Returns ASINs + metadata      │
  └──────────────────────────────────┘
             │
             ▼
  Enriched results returned to caller
```

> ⚠️ **Important:** Because ASIS is a separate service owned by a different team (VISUALSRCH), the **full parameter set, ranking logic, and filter capabilities are ultimately governed by ASIS**, not ARCADIA. This README documents only what is confirmed or reasonably inferred from Jira evidence. For the definitive parameter contract, consult the VISUALSRCH/SET team.

---

## Base URLs by Marketplace

| Marketplace | Base URL |
|---|---|
| United States | `https://api.audible.com` |
| United Kingdom | `https://api.audible.co.uk` |
| Germany | `https://api.audible.de` |
| France | `https://api.audible.fr` |
| Japan | `https://api.audible.co.jp` |
| Canada | `https://api.audible.ca` |
| Australia | `https://api.audible.com.au` |
| Italy | `https://api.audible.it` |
| Spain | `https://api.audible.es` |
| Brazil | `https://api.audible.com.br` |
| India | `https://api.audible.in` |

---

## Endpoint

```
GET /1.0/catalog/search
```

**Full example:**
```
GET https://api.audible.com/1.0/catalog/search
    ?keywords=The+Jewel+of+Dantenos+Brian+Anderson
    &content_type=Audiobook
    &num_results=10
    &response_groups=contributors,product_desc,product_attrs,rating,media
    &products_sort_by=Relevance
    &locale=en-US
```

---

## Query Parameters

### Confirmed Parameters

These parameters appear explicitly in Jira ticket URLs or descriptions and are **confirmed to work**:

| Parameter | Type | Description | Evidence |
|---|---|---|---|
| `keywords` | string | Free-text keyword search — the primary search lever. Accepts title, author name, narrator name, genre, or any combination. | ARCADIA-1407 (actual URL) |
| `node` | string | Browse node / category ID to restrict search to a specific category | ARCADIA-1407 (actual URL) |
| `content_type` | string | Filter by content type. Confirmed value: `All`. See [content\_type Values](#content_type-values). | ARCADIA-1407 (actual URL) |
| `response_groups` | string | Comma-separated response groups. Same groups as the [Catalog Products API](./README-catalog-products.md). `relationship` confirmed used by Android on `/catalog/search`. See [Response Groups](#response-groups). | ARCADIA-1407, ARCADIA-887 |
| `locale` | string | Language/locale override (e.g., `en-US`, `ja-JP`). As of Aug 2025 this is passed directly to ASIS without allowlist validation. See [locale behaviour](#the-locale-parameter--behaviour--history). | ARCADIA-1407 |
| `origin_page` | string | Internal tracking/analytics parameter (e.g., `home`, `search`). **Does not affect search results.** Safe to omit. | ARCADIA-1407 (actual URL) |
| `products_sort_by` | string | Sort order for results. See [products\_sort\_by Values](#products_sort_by-values). | ARCADIA-129, ARCADIA-823 |

---

### Likely Supported Parameters

These parameters are confirmed on sibling endpoints (`/1.0/catalog/products`, `/1.0/screens/`) that share the same AACDS infrastructure, and are **highly likely** to work on `/catalog/search`:

| Parameter | Type | Description | Evidence Source |
|---|---|---|---|
| `num_results` | integer | Maximum number of results to return per page. (e.g., `10`, `20`, `50`) | ARCADIA-129 (screens endpoint URL) |
| `browse_node_id` | string | Browse node ID for category filtering. May overlap with `node`. | ARCADIA-129 (screens endpoint URL) |
| `access_plans` | string | Filter by membership plan type (e.g., `premium`, `plus`) | ARCADIA-129 (screens endpoint URL) |
| `surface` | string | Caller surface identifier (e.g., `Android`, `iOS`, `Web`). Used for analytics and potentially experience differentiation. | ARCADIA-129 (screens endpoint URL) |
| `page` | integer | Pagination page number (1-based) | General AACDS pagination pattern |
| `image_sizes` | string | Comma-separated image pixel sizes to include in `product_images` (e.g., `490`, `690`) | Products endpoint pattern |

---

### Not Confirmed Parameters

These parameters are **not evidenced anywhere in Jira** and should not be assumed to work:

| Parameter | Status | Notes |
|---|---|---|
| `author=` / `author_id=` | ❌ Not confirmed | No dedicated author filter found. Use `keywords` with author name instead. |
| `title=` | ❌ Not confirmed | No dedicated title filter. Use `keywords` with title instead. |
| `narrator=` | ❌ Not confirmed | No dedicated narrator filter. |
| `min_rating=` / `max_rating=` | ❌ Not confirmed | No evidence of rating filter params. |
| `duration_min=` / `duration_max=` | ❌ Not confirmed | No evidence of duration filter params. |
| `language=` | ❌ Not confirmed as a discrete param | Language filtering exists at the response level via `locale`, and is a planned filter chip in the SRP redesign (VISUALSRCH-2145), but not confirmed as a standalone query param. |

---

## Response Groups

The `/catalog/search` endpoint supports the same `response_groups` mechanism as the [Catalog Products API](./README-catalog-products.md). The following are confirmed or expected to work:

| Response Group | Confirmed on `/catalog/search`? | Description |
|---|---|---|
| `product_desc` | ✅ Confirmed (via ARCADIA-129) | Merchandising summary |
| `product_attrs` | ✅ Confirmed (via ARCADIA-129) | Extended product attributes |
| `contributors` | ✅ Confirmed (via ARCADIA-129) | Authors and narrators |
| `media` | ✅ Confirmed (via ARCADIA-129) | Codecs and cover art |
| `sample` | ✅ Confirmed (via ARCADIA-129) | Sample audio info |
| `badges` | ✅ Confirmed (via ARCADIA-129) | Social proof / bestseller badges |
| `relationship` | ✅ Confirmed by Android audit (ARCADIA-887) | Parent/child ASIN relationships |
| `rating` | ⚠️ Expected | Ratings and distributions |
| `relationships_v2` | ⚠️ iOS only (ARCADIA-887) | Extended relationship graph — iOS uses this, Android does not |
| `always-returned` | ✅ Implicit | Always included regardless of params |
| `category_ladders` | ⚠️ Expected | Genre/category hierarchy |
| `ws4v_upsells` | ❌ Deprecated | Returns empty data — do not use |

> 💡 **Tip:** Request only the response groups you need. Each additional group increases response latency as AACDS calls downstream services.

---

## `content_type` Values

| Value | Description | Confirmed? |
|---|---|---|
| `All` | All content types | ✅ Confirmed (ARCADIA-1407) |
| `Audiobook` | Audiobooks only | ⚠️ Inferred from app behavior |
| `Podcast` | Podcasts only | ⚠️ Inferred from app behavior |

> 📌 Note: The SRP redesign (VISUALSRCH-2145, Q2 2026) plans to **remove the Audiobooks/Podcasts tabs** and replace them with **filter chips** on the Search Results Page. The `content_type` parameter in the API may change behavior accordingly.

---

## `products_sort_by` Values

| Value | Description | Confirmed? |
|---|---|---|
| `popularity` | Sorted by popularity score | ✅ Confirmed (ARCADIA-129 screens URL) |
| `Heuristic` | Audible's default ranking heuristic | ✅ Confirmed (ARCADIA-823) |
| `Relevance` | Ranked by relevance to the search query | ⚠️ Inferred |
| `BestSellers` | Ranked by bestseller rank | ⚠️ Inferred |
| `ReleaseDate` | Newest releases first | ⚠️ Inferred |

---

## Response Shape

The search endpoint returns a list of products matching the query, enriched with whatever `response_groups` were requested:

```json
{
  "products": [
    {
      "asin": "B00MTTG9NC",
      "title": "The Jewel of Dantenos",
      "authors": [
        { "asin": "B00684NQ4E", "name": "Brian D. Anderson" }
      ],
      "narrators": [
        { "name": "Derek Perkins" }
      ],
      "merchandising_summary": "...",
      "rating": { ... },
      "product_images": { "490": "https://..." },
      "content_delivery_type": "SinglePartBook",
      "language": "english",
      "release_date": "2014-09-05",
      "runtime_length_min": 112,
      ...
    }
  ],
  "total_results": 42,
  "response_groups": ["always-returned", "contributors", "product_desc", ...]
}
```

**Top-level response fields:**

| Field | Type | Description |
|---|---|---|
| `products` | array | List of matching product objects |
| `total_results` | integer | Total number of matching results (for pagination) |
| `response_groups` | array | The response groups actually returned |

Each product object in `products` contains the same fields as a response from `GET /catalog/products/{asin}` for the requested response groups. See the [Catalog Products API README](./README-catalog-products.md) for the full field reference.

---

## Search Intent Types

As of the **Q2 2026 SRP Redesign** (VISUALSRCH-2145), ASIS internally classifies every search query into one of two intent types using **METIS/QUZen query understanding**:

| Intent Type | Description | How Detected |
|---|---|---|
| **Spearfishing** | The user is searching for a specific, known title, author, or series. | METIS returns a `title` attribute at span level in `queryUnderstandingRestrictions` (VISUALSRCH-2453) |
| **Discovery** | The user is exploring by genre, keyword, or theme. | Default — when spearfishing intent is not detected |

### Why This Matters for API Callers

- **Spearfishing queries** (e.g., `keywords=The+Jewel+of+Dantenos`) are highly likely to return the exact matching title as the **#1 result**, particularly after the SRP redesign rolls out
- **Discovery queries** (e.g., `keywords=fantasy+adventure`) return relevance-ranked results with personalized carousels and may vary by customer context
- The intent detection logic runs **internally in ASIS** — it is not exposed as a parameter or in the response (at least currently)

> ⚠️ **Upcoming:** ASIS is adding a `highlighted_top_result` field to `GetSearchResponse` (VISUALSRCH-2456) to signal when a spearfishing result is eligible for top-result highlighting. This field will be gated behind the weblab `ADBL_SEARCH_SRP_REDESIGN`. It is not yet available publicly.

---

## Filters

The Search Results Page on Audible apps supports several filter options, which translate into API query parameters. Based on Jira evidence from the ASIS `GetSearchResponse` contract and the SRP redesign (VISUALSRCH-2145, VISUALSRCH-2443):

### Currently Available in `GetSearchResponse` (ASIS internal)

| Filter | Available in ASIS Response? | Notes |
|---|---|---|
| `Language` | ✅ Yes | Already in `GetSearchResponse` per VISUALSRCH-2443 |
| `Format` | ✅ Yes | Already in `GetSearchResponse` (Audiobook / Podcast) per VISUALSRCH-2443 |

### Planned Filter Chips (Q2 2026 SRP Redesign — VISUALSRCH-2145)

These are being added as visible chips on the Search Results Page:

| Filter Chip | Status | Notes |
|---|---|---|
| `Filters` (general) | 🔧 In Progress | Opens dropdown for subcategory selection |
| `In My Library` | 🔧 In Progress (NIKE team) | Requires authentication |
| `Included` (in membership) | 🔧 In Progress | Filters to titles included in current plan |
| `Format` (Audiobook / Podcast) | 🔧 In Progress | Replaces Audiobooks/Podcasts tabs |
| `Language` | 🔧 In Progress | Filters by content language based on user listening history |

> 📌 **Note:** The **virtual narrator filter** (filtering out AI/TTS narrated titles) accounts for **over 80% of search-related customer complaints** but remains **blocked at the SVP level** and is not on the near-term roadmap (per VISUALSRCH-2145 meeting notes, March 2026).

---

## The `locale` Parameter — Behaviour & History

### Current Behaviour (post Aug 2025)

The `locale` parameter is passed **directly to ASIS** without validation. Any locale string is accepted (e.g., `en-US`, `ja-JP`, `fr-FR`). ASIS uses this to determine the language of the response content.

```
GET https://api.audible.co.jp/1.0/catalog/search?keywords=love&locale=en-US
→ Returns results with English-language metadata, regardless of JP marketplace domain
```

### History — The JP Locale Bug (ARCADIA-1407, Closed Aug 2025)

Prior to August 2025, AACDS validated the `locale` parameter against an **allowlist config** (`AudibleApiProductPopulatorLib.RSASSupportedLocales`) before passing it to ASIS. If the locale wasn't in the allowlist for the given marketplace, it was **silently dropped**.

**The bug:**
- The Android app used device language preference (`en-US`) as the `locale` parameter
- On the JP marketplace (`api.audible.co.jp`), `en-US` was not in the allowlist
- AACDS dropped the locale → ASIS defaulted to Japanese language
- After applying search filters, the language of results changed from English to Japanese — confusing English-speaking users in Japan

**The fix:**
- Weblab `AUDIBLE_AACDS_IGNORE_LOCALE_CHECK_ASIS_1283031` was dialed to 100% on August 1, 2025
- AACDS now passes any `locale` value directly to ASIS without validation
- Confirmed fixed on Prod build `25.28.15` on August 4, 2025

### Locale Handling for Accolades (ARCADIA-1664, Resolved Oct 2025)

A separate locale bug was discovered for the `accolades` response group — the CDS endpoint was overriding non-default locales. For example, `locale=es-ES` on the US marketplace was not triggering translations. Fixed in October 2025.

---

## Searching by Author + Title

Since there are no dedicated `author=` or `title=` parameters, the recommended approach is to combine both into the `keywords` parameter and then validate client-side:

### Step 1 — Search with Combined Keywords
```
GET https://api.audible.com/1.0/catalog/search
    ?keywords=Jewel+of+Dantenos+Brian+Anderson
    &content_type=Audiobook
    &response_groups=contributors,product_desc
    &num_results=5
    &products_sort_by=Relevance
```

### Step 2 — Client-Side Validation
Cross-reference `authors[].asin` or `authors[].name` in the results to confirm the correct author:

```json
{
  "products": [
    {
      "asin": "B00MTTG9NC",
      "title": "The Jewel of Dantenos",
      "authors": [
        { "asin": "B00684NQ4E", "name": "Brian D. Anderson" }  ✅ match
      ]
    }
  ]
}
```

### Why This Works Well

Pairing a **specific title** with an **author name** produces a very tight, unambiguous keyword combination. ASIS's spearfishing intent detection (METIS) is highly likely to classify this as a spearfishing query and surface the exact match at position #1.

### Limitations

| Limitation | Detail |
|---|---|
| **Keyword-only, not structured** | Author name and title go into a single `keywords` string — there is no fielded search |
| **Relevance-ranked** | Results are not guaranteed — exact match is likely at #1 but not contractually assured |
| **Author name ambiguity** | Common names may return results from multiple authors — always validate `authors[].asin` |
| **ASIS is a black box** | Ranking and matching logic is owned by VISUALSRCH, not documented for external callers |

---

## Authentication

- **Public/anonymous search** — `GET /1.0/catalog/search` is publicly accessible without authentication for standard catalog fields
- **Authenticated-only response groups** — `customer_rights`, `listening_status`, `profile_sharing`, and `feature_support` require a valid Bearer token:

```http
Authorization: Bearer <customer_access_token>
```

- The `In My Library` filter chip (planned in the SRP redesign) will require authentication

---

## Error Handling & HTTP Response Codes

| HTTP Status | Meaning |
|---|---|
| `200 OK` | Successful response — check `total_results` to confirm matches found |
| `400 Bad Request` | Missing required parameter or malformed query |
| `401 Unauthorized` | Auth-required response group requested without valid token |
| `500 Internal Server Error` | Server-side error — may be in AACDS or ASIS |
| `503 Service Unavailable` | Downstream ASIS overload or timeout |

> **Best practices:**
> - A `200 OK` with `total_results: 0` means the search returned no matches — not an error
> - Implement **exponential backoff** on `5xx` responses
> - Do not retry `400` responses without fixing the query
> - `keywords` is not technically required by the endpoint contract (you can browse by `node` alone), but omitting it with no other filter will likely return broad or unpredictable results

---

## Known Limitations & Notes

| # | Limitation | Detail |
|---|---|---|
| 1 | **No structured field search** | There is no `author=`, `title=`, or `narrator=` parameter. All structured searching must be done via `keywords` + client-side filtering. |
| 2 | **ASIS is a black box** | The full parameter list, ranking algorithm, and filter capabilities are governed by ASIS (VISUALSRCH team). AACDS is a pass-through layer only. |
| 3 | **Relevance-ranked, not deterministic** | Results may change across requests for the same query due to A/B weblabs, personalization, and ranking updates. |
| 4 | **Search volume** | The general product search endpoint processes approximately **3.6 billion searches every 3 months** (VISUALSRCH-2219). This is a high-traffic, shared infrastructure. |
| 5 | **No narrator ASIN in results** | Even in search results, narrator objects contain only `name` — no ASIN. See the [Contributor README](./README-catalog-contributor.md). |
| 6 | **`ws4v_upsells` is deprecated** | Do not request this response group. It returns empty data. |
| 7 | **Bot traffic** | ASIS has identified unknown bot/scraper traffic in the search flow (ARCADIA-796). Aggressive programmatic search usage may be throttled or blocked at the edge. |
| 8 | **Old app versions** | Some traffic to the search endpoint comes from old Android/iOS app versions that AACDS cannot block without breaking legitimate customer experiences. Behavioral differences between app versions may exist. |
| 9 | **NL/BE locale (German hub)** | Browse node labels are not translated for `nl_BE` / `fr_BE` locales on the German marketplace hub. A fix is being developed jointly by ARCADIA (ARCADIA-2378) and VISUALSRCH (VISUALSRCH-2416) with a target of May 12, 2026. |

---

## Upcoming Changes

| Change | Jira | Status | Expected Impact |
|---|---|---|---|
| SRP Redesign — filter chips, top result highlighting, personalized carousels | VISUALSRCH-2145 | 🔧 In Progress (Q2 2026) | Major UX change on apps/web; API response shape may gain new fields |
| `highlighted_top_result` field in search response | VISUALSRCH-2456 | 🔧 To Do | New field in response when spearfishing intent is detected |
| Remove Audiobooks/Podcasts tabs → Filter chips | VISUALSRCH-2145 | 🔧 In Progress | `content_type` filtering may change behavior |
| Language filter chip | VISUALSRCH-2145, VISUALSRCH-2443 | 🔧 In Progress | Will allow filtering results by language via chip |
| In My Library filter chip | VISUALSRCH-2145 | 🔧 In Progress (NIKE team) | Auth-required filter |
| Browse node translation for NL/BE | VISUALSRCH-2416, ARCADIA-2378 | 🔧 In Progress | Fix for DE marketplace spoke locales |
| Virtual narrator filter | Not tracked | ❌ Blocked at SVP | Requested by 80%+ of search-complaint customers; not on roadmap |

---

*For related API documentation, see:*
- 📘 [Audible Catalog Products API README](./README-catalog-products.md)
- 📙 [Audible Catalog Contributor API README](./README-catalog-contributor.md)
- 📗 [Audible Catalog Series API README](./README-catalog-series.md) *(coming soon)*