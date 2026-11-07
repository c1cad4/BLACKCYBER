# BLACKCYBER — Incident review policy

BLACKCYBER maintains a research archive, not a public blacklist or an automated fraud verdict.

## How reports enter the project

1. A visitor selects **Propose an incident** on the website, completes the form, and opens a prefilled **GitHub Issue**.
2. The visitor signs into GitHub and presses **Submit new issue**. Until that action, nothing is sent to BLACKCYBER.
3. The repository maintainer **c1cad4**, or another maintainer expressly appointed by them, screens incoming reports. GitHub users cannot approve or publish incident records merely by submitting or voting.
4. The reviewer checks duplicates; source authenticity and dates; which legal claims are allegations, charges, findings, settlements or convictions; technical incident reports; and whether proposed amounts are properly described.
5. For uncertain, financially material, or reputation-sensitive claims, ask a second independent reviewer before publication.
6. A reviewer can request more evidence, close the report as unsubstantiated, or approve a factual record. Publication requires an intentional code/data change reviewed in GitHub. **Closing an issue or adding a label never automatically publishes a case.**
7. Record later reversals, corrections, appeals, compensations, and the date of source verification. Allow correction requests and responses from named parties.

## Report status definitions

- **Submitted:** user claim, not reviewed or validated.
- **Needs evidence:** supporting documentation missing or incomplete.
- **Under review:** validating source provenance, role, timeline and amounts.
- **Approved for publication:** all material claims are supported and categorized.
- **Published:** evidence-linked record is present in website data.
- **Rejected / closed:** not substantiated, duplicated, irrelevant, or unsafe to publish.
- **Correction requested:** existing record is being rechecked.

These are editorial workflow statuses, **not judgments of anyone's criminal liability**.

## Evidence standard

Prefer primary sources: judicial records, enforcement notices, bankruptcy filings, first-party post-mortems, on-chain transaction references, public company statements with dates, and original security reports. Secondary reports should be independently corroborated for material assertions.

Track amounts independently:
- value allegedly stolen or diverted;
- directly realized customer loss;
- assets frozen or at risk;
- market capitalization decline;
- recovery, reimbursement, creditor distributions;
- estimate currency and as-of date.

Do not sum unlike metrics as if they were a single total loss. Do not publish personal contact details, home addresses, private individuals' identifying information or unverified accusations. A public employment or team relationship alone does not establish wrongdoing.

## Price history

The static site makes optional browser-side requests to CoinGecko using a **curated project-to-token-ID mapping**. A company's equity, a blockchain ecosystem and a token must not be conflated. Historical charts are limited to the supported request window (currently selectable 7, 30, 90, or 365 days) and availability of public/demo API access.

Never represent price-chart minimum/maximum for a short window as all-time high or low. Do not fabricate a zero price or synthetic chart if data is missing. For longer histories and exact price at incident time, use licensed market data or a server-side service with archived snapshots; **never put private API keys into public frontend HTML**.

## Current operational limitations

This is a GitHub Pages static website. It does not have a database, authenticated reviewer dashboard, automatic approved-publication pipeline or guaranteed market-data API access. GitHub Issues provides intake and collaboration; a repository maintainer must update the data to publish.
