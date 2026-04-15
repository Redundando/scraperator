Now I have everything I need. Let me write a comprehensive, well-structured README:

---

# Audible Catalog Products API — README

> **Service:** Audible API Catalog Data Service (AACDS)
> **Internal Service ID:** `com.amazon.audibleapicatalogdata#AudibleApiCatalogDataService`
> **Owning Team:** ARCADIA (Audible Catalog Data)
> **Datapath Package:** `AudibleApiCatalogDatapath` / `AudibleConsumptionDatapath`

---

## Table of Contents

1. [Overview](#overview)
2. [Base URLs by Marketplace](#base-urls-by-marketplace)
3. [Endpoints](#endpoints)
   - [Get Single Product](#1-get-single-product)
   - [Get Multiple Products](#2-get-multiple-products)
   - [Get Similar Products](#3-get-similar-products)
   - [Search Products](#4-search-products)
4. [Query Parameters](#query-parameters)
5. [Response Groups](#response-groups)
6. [Field Reference](#field-reference)
   - [Always-Returned Fields](#always-returned-fields)
   - [product\_desc](#product_desc)
   - [product\_attrs](#product_attrs)
   - [contributors](#contributors)
   - [media](#media)
   - [rating](#rating)
   - [relationships / relationship\_to\_product\_v2](#relationships--relationship_to_product_v2)
   - [category\_ladders](#category_ladders)
   - [reviews / review\_attrs](#reviews--review_attrs)
   - [customer\_rights](#customer_rights)
   - [product\_plans](#product_plans)
   - [profile\_sharing](#profile_sharing)
   - [tags / spotlight\_tags](#tags--spotlight_tags)
   - [chart\_ranks](#chart_ranks)
   - [feature\_support](#feature_support)
   - [tax\_content\_type](#tax_content_type)
   - [storycard](#storycard)
   - [sample](#sample)
   - [ws4v\_upsells ⚠️ DEPRECATED](#ws4v_upsells-%EF%B8%8F-deprecated)
7. [Content Delivery Types](#content-delivery-types)
8. [Error Handling & HTTP Response Codes](#error-handling--http-response-codes)
9. [Authentication](#authentication)
10. [Known Limitations & Notes](#known-limitations--notes)
11. [Upcoming / In-Progress Changes](#upcoming--in-progress-changes)

---

## Overview

The **Audible Catalog Products API** is a publicly accessible REST API that returns metadata for Audible products (audiobooks, podcasts, periodicals, etc.) by ASIN. It is powered by the **Audible API Catalog Data Service (AACDS)**, which aggregates data from internal Audible catalog systems via the **AudibleApiCatalogDatapath** (a Datapath-based data service).

The API follows a **response group** model: you specify which subsets of data you want returned, rather than always receiving the full payload. This allows callers to minimize response size and latency.

**Confirmed working example:**
```
GET https://api.audible.com/1.0/catalog/products/B00MTTG9NC
    ?response_groups=product_desc,product_attrs,contributors,rating,media
    &image_sizes=490
```

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

All endpoints below are relative to the marketplace base URL.

---

## Endpoints

### 1. Get Single Product

Retrieve full metadata for a single product by ASIN.

```
GET /1.0/catalog/products/{asin}
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `asin` | string | ✅ | The Audible ASIN for the product (e.g., `B00MTTG9NC`) |

**Example:**
```
GET https://api.audible.com/1.0/catalog/products/B00MTTG9NC
    ?response_groups=product_desc,product_attrs,contributors,rating,media
    &image_sizes=490
```

**Response shape:**
```json
{
  "product": { ... },
  "response_groups": ["always-returned", "product_desc", "contributors", ...]
}
```

---

### 2. Get Multiple Products

Retrieve metadata for multiple ASINs in a single request.

```
GET /1.0/catalog/products?asins={asin1},{asin2},...
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `asins` | string | ✅ | Comma-separated list of ASINs |
| `response_groups` | string | ❌ | Comma-separated response groups |

> ⚠️ **Batch limit note:** When using response groups that call downstream services (e.g., `feature_support`), batches are processed in groups of up to 10 ASINs internally. Providing more than 10 ASINs may produce inconsistent results for certain response groups (see [ARCADIA-2279](https://jira.audible.com/browse/ARCADIA-2279) — resolved).

**Example:**
```
GET https://api.audible.com/1.0/catalog/products
    ?asins=B017V4IM1G,B00MTTG9NC
    &response_groups=product_desc,contributors,rating
```

**Response shape:**
```json
{
  "products": [ { ... }, { ... } ],
  "response_groups": ["always-returned", "product_desc", "contributors", "rating"],
  "total_results": 2
}
```

---

### 3. Get Similar Products

Retrieve products similar to a given ASIN (recommendations/SIMS).

```
GET /1.0/catalog/products/{asin}/sims
```

**Example:**
```
GET https://api.audible.com/1.0/catalog/products/B00MTTG9NC/sims
    ?response_groups=product_desc,contributors
```

---

### 4. Search Products

Search the catalog by keyword, category, or other filters.

```
GET /1.0/catalog/products?keywords={query}
```

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `keywords` | string | Keyword search query |
| `category_id` | string | Filter by category ID |
| `products_sort_by` | string | Sort results (e.g., `BestSellers`, `Relevance`, `Title`) |
| `num_results` | integer | Number of results to return |
| `page` | integer | Page number for pagination |
| `response_groups` | string | Comma-separated response groups |

**Example:**
```
GET https://api.audible.com/1.0/catalog/products
    ?keywords=harry+potter
    &products_sort_by=BestSellers
    &num_results=10
    &response_groups=product_desc,contributors,rating
```

---

## Query Parameters

The following query parameters apply across endpoints:

| Parameter | Type | Description |
|---|---|---|
| `response_groups` | string | Comma-separated list of response groups (see below) |
| `image_sizes` | string | Comma-separated image dimension(s) to include (e.g., `490`, `690`, `490,690`) |
| `asins` | string | Comma-separated ASIN list (for multi-product requests) |
| `num_results` | integer | Max number of results |
| `keywords` | string | Keyword search |
| `category_id` | string | Category filter |
| `products_sort_by` | string | Sort order |
| `page` | integer | Pagination page number |

---

## Response Groups

Response groups are the primary mechanism for controlling which fields are returned. Specify them as a comma-separated list in the `response_groups` query parameter.

| Response Group | Auth Required | Description |
|---|---|---|
| `always-returned` | ❌ | Core fields always included automatically (see below) |
| `product_desc` | ❌ | Marketing description / merchandising summary |
| `product_attrs` | ❌ | Extended product attributes (TTS, content type, season, etc.) |
| `contributors` | ❌ | Authors and narrators |
| `media` | ❌ | Available audio codecs and cover art images |
| `rating` | ❌ | Overall, performance, and story ratings + distributions |
| `relationships` | ❌ | Parent/child ASIN relationships (series, episodes) |
| `relationship_to_product_v2` | ❌ | Extended relationship graph (v2) |
| `category_ladders` | ❌ | Full genre/category hierarchy |
| `reviews` | ❌ | Review data and metadata |
| `review_attrs` | ❌ | Review attribute details |
| `sample` | ❌ | Sample audio stream information |
| `sku` | ❌ | Full SKU identifier details |
| `product_plans` | ❌ | Pricing and membership plan information |
| `buying_options` | ❌ | Purchase/offer options |
| `tags` | ❌ | Personalized content tags (from P13N) |
| `spotlight_tags` | ❌ | LLM-selected spotlight tags (2–3 most relevant tags) |
| `chart_ranks` | ❌ | Bestseller/chart ranking data |
| `tax_content_type` | ❌ | Tax classification for the product |
| `storycard` | ❌ | Story card display data |
| `customer_rights` | ✅ | Customer's ownership/entitlement/consumption rights |
| `listening_status` | ✅ | Customer's current listening progress |
| `profile_sharing` | ✅ | Family/child profile sharing eligibility |
| `feature_support` | ✅ | PageSync and Whispersync for Voice (WS4V) eligibility |
| `ws4v_upsells` | ✅ | ⚠️ **DEPRECATED** — Returns empty data. Do not use. |

> **Tip:** Always request only the response groups you need. Unnecessary groups increase response time and payload size, particularly those that require downstream service calls.

---

## Field Reference

### Always-Returned Fields

These fields are included in every response regardless of which `response_groups` are requested.

| Field | Type | Description |
|---|---|---|
| `asin` | string | Unique product identifier |
| `title` | string | Full product title |
| `subtitle` | string | Series subtitle or episode title |
| `content_type` | string | Top-level type, always `"Product"` |
| `content_delivery_type` | string | Delivery format (see [Content Delivery Types](#content-delivery-types)) |
| `format_type` | string | `"unabridged"` or `"abridged"` |
| `has_children` | boolean | Whether this product has child ASINs |
| `is_adult_product` | boolean | Adult/explicit content flag |
| `is_listenable` | boolean | Whether this product can be played |
| `is_preview_enabled` | boolean | Whether a preview is available |
| `is_purchasability_suppressed` | boolean | Whether purchasing is suppressed |
| `is_vvab` | boolean | Virtual Voice Audiobook flag (determined by `text_to_speech` field; true when TTS is non-null, non-empty, non-`"FALSE"`) |
| `issue_date` | string (date) | Original issue/release date (`YYYY-MM-DD`) |
| `release_date` | string (date) | Platform release date (`YYYY-MM-DD`) |
| `publication_datetime` | string (ISO 8601) | Full publication timestamp |
| `publication_name` | string | Series name |
| `publisher_name` | string | Publisher |
| `language` | string | Language (e.g., `"english"`) |
| `runtime_length_min` | integer | Duration in minutes |
| `sku` | string | Internal SKU identifier |
| `sku_lite` | string | Simplified SKU identifier |
| `asset_details` | array | List of asset detail objects (may be empty) |
| `thesaurus_subject_keywords` | array | Genre/subject keywords (e.g., `["literature-and-fiction"]`) |
| `social_media_images` | object | Social sharing image URLs (Facebook, Twitter, Instagram static/sticker/BG) |

---

### `product_desc`

| Field | Type | Description |
|---|---|---|
| `merchandising_summary` | string | Short marketing blurb. May contain limited HTML tags (e.g., `<b>`, `<i>`). Sanitized server-side to prevent XSS. |

---

### `product_attrs`

| Field | Type | Description |
|---|---|---|
| `language` | string | Product language |
| `content_delivery_type` | string | Delivery type (mirrors always-returned) |
| `text_to_speech` | string | TTS availability indicator; non-null/non-`"FALSE"` means VVAB |
| `text_to_speech_channel` | string | TTS channel (e.g., `"KDP"`, `"OTHER"`). *Coming soon — [ARCADIA-2348](https://jira.audible.com/browse/ARCADIA-2348)* |
| `is_adult_product` | boolean | Adult content flag |
| `season_number` | integer | Season number for podcast episodes. Support for `PodcastSeason` ASINs in progress — [ARCADIA-2277](https://jira.audible.com/browse/ARCADIA-2277) |
| `tax_content_type` | string | Tax classification. See [`tax_content_type`](#tax_content_type) response group. |
| `short_description` | string | Brief product description |
| `video_url` | string | URL for video content (if applicable) |

---

### `contributors`

| Field | Type | Description |
|---|---|---|
| `authors` | array | List of author objects: `{ "asin": "...", "name": "..." }` |
| `narrators` | array | List of narrator objects: `{ "name": "..." }` |

---

### `media`

| Field | Type | Description |
|---|---|---|
| `available_codecs` | array | List of available audio codec objects |
| `product_images` | object | Cover art image URLs keyed by pixel size (e.g., `{ "490": "https://..." }`) |

**Codec object fields:**

| Field | Type | Description |
|---|---|---|
| `name` | string | Codec identifier (e.g., `"aax"`, `"aax_22_32"`, `"format4"`) |
| `format` | string | Human-readable format name (`"Format4"`, `"Enhanced"`) |
| `enhanced_codec` | string | Enhanced codec string (e.g., `"LC_64_22050_stereo"`) |
| `is_kindle_enhanced` | boolean | Whether this is a Kindle-enhanced format |

> ⚠️ **Note:** Future versions of the API may stop returning codec information as part of a planned server-side asset selection migration ([ARCADIA-514](https://jira.audible.com/browse/ARCADIA-514)).

---

### `rating`

| Field | Type | Description |
|---|---|---|
| `num_reviews` | integer | Number of written reviews |
| `overall_distribution` | object | Overall rating breakdown (see below) |
| `performance_distribution` | object | Narrator performance rating breakdown |
| `story_distribution` | object | Story/content rating breakdown |

**Distribution object fields (applies to all three distributions):**

| Field | Type | Description |
|---|---|---|
| `average_rating` | float | Raw average rating |
| `display_average_rating` | string | Formatted average (e.g., `"4.0"`) |
| `display_stars` | float | Rounded star display value |
| `num_ratings` | integer | Total number of ratings |
| `num_five_star_ratings` | integer | Count of 5-star ratings |
| `num_four_star_ratings` | integer | Count of 4-star ratings |
| `num_three_star_ratings` | integer | Count of 3-star ratings |
| `num_two_star_ratings` | integer | Count of 2-star ratings |
| `num_one_star_ratings` | integer | Count of 1-star ratings |

---

### `relationships` / `relationship_to_product_v2`

Returns parent/child ASIN relationships, such as a book's position in a series, or episodes within a podcast season.

| Field | Type | Description |
|---|---|---|
| `relationships` | array | List of related product objects with `asin`, `relationship_to_product`, `sort_position`, `title`, etc. |

> **Note:** Usage of `relationship` and `relationship_v2` was audited across all Audible web and app surfaces in early 2025 ([ARCADIA-887](https://jira.audible.com/browse/ARCADIA-887)). Use `relationship_to_product_v2` for new integrations where available.

---

### `category_ladders`

Returns the full genre/category hierarchy for the product.

| Field | Type | Description |
|---|---|---|
| `category_ladders` | array | List of category ladder objects, each containing a `ladder` array of `{ "id": "...", "name": "..." }` nodes from root to leaf |

---

### `reviews` / `review_attrs`

Returns user review data for the product.

| Field | Type | Description |
|---|---|---|
| `reviews` | object | Review list and metadata |
| `review_attrs` | object | Additional review attribute details |

> **Note:** Fields `has_current_user_authored_review` and `has_current_user_voted_helpful` were proposed ([ARCADIA-2210](https://jira.audible.com/browse/ARCADIA-2210)) but the Epic was subsequently canceled.

---

### `customer_rights`

> 🔒 **Requires authentication.**

Returns the authenticated customer's entitlement and consumption rights for the product.

| Field | Type | Description |
|---|---|---|
| `is_consumable` | boolean | Whether the customer can consume this title |
| `is_consumable_indefinitely` | boolean | Whether consumption rights are permanent |
| `is_consumable_offline` | boolean | Whether the title can be downloaded/used offline |
| `is_book_qa_eligible` | boolean | Whether eligible for Book QA (quality assurance) |
| `is_recap_eligible` | boolean | Whether the customer is eligible to play a recap of this title |

---

### `product_plans`

Returns pricing and membership plan information for the product, including credit eligibility and offer pricing.

---

### `profile_sharing`

> 🔒 **Requires authentication.**

Returns whether the product is eligible to be shared with family/child profiles.

| Field | Type | Description |
|---|---|---|
| `is_shareable` | boolean | Whether this product can be shared |
| `shareable_with` | array | List of eligible profile IDs for sharing |

> **Note:** `PodcastParent` content type was added to the shareable content delivery types ([ARCADIA-1114](https://jira.audible.com/browse/ARCADIA-1114)). Individual podcast episodes (not the parent show) are shareable with child profiles.

---

### `tags` / `spotlight_tags`

Returns personalized content tags sourced from the P13N (Personalization) service.

| Field | Type | Description |
|---|---|---|
| `tags` | array | Full list of content tags for the product |
| `spotlight_tags` | array | 2–3 LLM-selected tags that best describe the title (distinct and relevant). Uses an LLM-based ranking strategy from P13N ([ARCADIA-1969](https://jira.audible.com/browse/ARCADIA-1969)). |

---

### `chart_ranks`

Returns bestseller and chart ranking data for the product. Data is sourced from **AudibleRecommendationService (ARS)** (migrated from a Datapath view in [ARCADIA-892](https://jira.audible.com/browse/ARCADIA-892)).

**Example request:**
```
GET https://api.audible.com/1.0/catalog/products?asins=B017V4IM1G&response_groups=chart_ranks
```

---

### `feature_support`

> 🔒 **Requires authentication.**

Returns eligibility for advanced features such as PageSync and Whispersync for Voice (WS4V).

| Field | Type | Description |
|---|---|---|
| `entitled_features` | array | List of enabled features (e.g., `["PageSync"]`) |
| `is_ws4v_enabled` | boolean | Whether Whispersync for Voice is enabled for this product |
| `is_ws4v_companion_asin_owned` | boolean | Whether the customer owns the WS4V companion ASIN (e.g., Kindle edition) |
| `ws4v_companion_asin` | string | ASIN of the WS4V companion product |

> ⚠️ **Child Profile restriction:** PageSync (`entitled_features`) is blocked for Child Profile accounts ([ARCADIA-2236](https://jira.audible.com/browse/ARCADIA-2236)).

---

### `tax_content_type`

Returns the tax classification of the product. Used for dual-tax handling across international marketplaces.

| Value | Condition |
|---|---|
| `"Audiobook"` | Standard audiobook with no related print edition and no adult content |
| `"Non-Audiobook"` | No related ASIN, tagged with `tax_non_audiobook`, or `is_adult_product = true` |
| `"Periodical"` | `content_delivery_type` is `SinglePartIssue`, `MultiPartIssue`, `Periodical`, or `Subscription` |
| `"Podcast"` | `content_delivery_type` is `PodcastParent`, `PodcastSeason`, or `PodcastEpisode` |

---

### `storycard`

Returns story card display data used for product detail page (PDP) surfaces. Content is updated regularly. Supported marketplaces for integration testing: US, AU, UK, CA (English locale).

---

### `sample`

Returns sample audio stream information, including URLs and duration for the product's audio preview.

---

### `ws4v_upsells` ⚠️ DEPRECATED

> ❌ **Do not use.** This response group is deprecated.

As of [ARCADIA-2109](https://jira.audible.com/browse/ARCADIA-2109), this response group returns **empty data** and no longer calls the `AudibleCompanionEligibilityService (ACES)`. The response group key is retained in the codebase for backwards compatibility with older iOS and Android app versions, but will not return meaningful data. Use `feature_support` instead.

---

## Content Delivery Types

The `content_delivery_type` field identifies the structural type of the product:

| Value | Description |
|---|---|
| `SinglePartBook` | Standard single-part audiobook |
| `MultiPartBook` | Multi-part audiobook |
| `SinglePartIssue` | Single-issue periodical |
| `MultiPartIssue` | Multi-part periodical issue |
| `Periodical` | Periodical/magazine |
| `Subscription` | Subscription-based content |
| `PodcastParent` | Top-level podcast show |
| `PodcastSeason` | A podcast season |
| `PodcastEpisode` | An individual podcast episode |

---

## Error Handling & HTTP Response Codes

| HTTP Status | Meaning |
|---|---|
| `200 OK` | Successful response |
| `400 Bad Request` | Invalid query parameter or malformed request |
| `404 Not Found` | ASIN not found in the catalog |
| `401 Unauthorized` | Missing or invalid authentication token (for auth-required response groups) |
| `500 Internal Server Error` | Server-side error |

> **Note:** A fix was made ([ARCADIA-824](https://jira.audible.com/browse/ARCADIA-824)) to ensure that requests for non-existent or invalid ASINs return `404` rather than `200`. If you encounter a `200` response with an empty or null product, this may indicate a stale client or edge case.

---

## Authentication

- **Public/anonymous endpoints** (e.g., `product_desc`, `contributors`, `rating`, `media`) work without authentication.
- **Customer-specific response groups** (`customer_rights`, `listening_status`, `profile_sharing`, `feature_support`) require a valid **Audible customer access token** passed as a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <customer_access_token>
```

Authentication is enforced via **CloudAuth** (migrated as part of [ARCADIA-1716](https://jira.audible.com/browse/ARCADIA-1716)).

---

## Known Limitations & Notes

1. **Batch size for `feature_support`:** Processing more than 10 ASINs in a single `asins=...` request with the `feature_support` response group may yield inconsistent results due to internal batching. A bug fix was shipped for this ([ARCADIA-2279](https://jira.audible.com/browse/ARCADIA-2279)).

2. **HTML in `merchandising_summary`:** This field may contain limited HTML tags. Content is sanitized server-side using JSoup to prevent XSS. Clients should still handle HTML safely when rendering.

3. **`is_vvab` detection:** The `is_vvab` field is derived from the `text_to_speech` attribute — it is `true` when `text_to_speech` is non-null, non-empty, and not equal to `"FALSE"`. It is not a direct Sable field.

4. **Tombstoned ASINs in relationships:** The relationships datapath may return tombstoned (deleted/inactive) ASINs. Clients should handle null or inactive related products gracefully.

5. **`ws4v_upsells` is empty:** Do not rely on this response group for any data. It returns an empty response.

6. **`available_codecs` future deprecation:** The codec list in the `media` response group may be removed in the future as part of a server-side asset selection migration. Avoid building hard dependencies on specific codec values.

---

## Upcoming / In-Progress Changes

| Change | Jira | Status |
|---|---|---|
| Add `text_to_speech_channel` to `product_attrs` (values: `"KDP"`, `"OTHER"`)