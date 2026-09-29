import sys
import time

import requests
from bs4 import BeautifulSoup

from .models import XbrlFact

TICKER_TO_CIK_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{document}"

# SEC's fair-access policy requires every request to identify a real
# requester by name and contact email, and will block a generic or missing
# User-Agent outright -- the same class of thing that got Wikipedia's
# default urllib User-Agent a 403, except SEC publishes this requirement
# explicitly rather than leaving it to be discovered. There is no key to
# apply for (unlike CFBD); there is a header you must set honestly instead.
DEFAULT_USER_AGENT_TEMPLATE = "options-screener research project ({contact})"
FALLBACK_CONTACT = "no-contact-set@example.com"

REQUEST_DELAY_SECONDS = 0.15  # SEC publishes a 10 req/s cap; this stays well under it

# Revenue is reported under different XBRL tags depending on when and how a
# company filed -- tried in order, first one with any data wins.
REVENUE_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]
EPS_TAGS = ["EarningsPerShareDiluted", "EarningsPerShareBasic"]

_cik_cache: dict[str, str] | None = None


def _user_agent(contact_email: str | None) -> str:
    return DEFAULT_USER_AGENT_TEMPLATE.format(contact=contact_email or FALLBACK_CONTACT)


def _get(url: str, contact_email: str | None):
    headers = {"User-Agent": _user_agent(contact_email)}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response


def fetch_cik(ticker: str, contact_email: str | None = None) -> str | None:
    """The 10-digit, zero-padded CIK every other EDGAR endpoint needs,
    looked up from SEC's own ticker list (cached in-process since it's a
    ~800KB file covering every ticker, not something to re-fetch per
    lookup within one run).
    """
    global _cik_cache
    if _cik_cache is None:
        try:
            data = _get(TICKER_TO_CIK_URL, contact_email).json()
        except Exception as e:
            print(f"  (couldn't fetch SEC's ticker list: {e})", file=sys.stderr)
            return None
        _cik_cache = {row["ticker"].upper(): str(row["cik_str"]).zfill(10) for row in data.values()}

    return _cik_cache.get(ticker.upper())


def fetch_recent_8k_texts(
    ticker: str, contact_email: str | None = None, count: int = 3, max_chars: int = 4000
) -> list[str]:
    """Plain-text excerpts of the most recent 8-Ks (material event filings
    -- earnings releases, M&A, guidance changes), meant to be scored by the
    same lexicon `sentiment.py` already applies to news headlines rather
    than a separate mechanism. `max_chars` keeps this to roughly the actual
    press-release content at the top of the filing rather than pulling in
    exhibits and legal boilerplate that follow it.
    """
    cik = fetch_cik(ticker, contact_email)
    if cik is None:
        return []

    try:
        submissions = _get(SUBMISSIONS_URL.format(cik10=cik), contact_email).json()
    except Exception as e:
        print(f"  (couldn't fetch SEC filing history for {ticker}: {e})", file=sys.stderr)
        return []

    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    documents = recent.get("primaryDocument", [])

    texts = []
    fetched = 0
    for form, accession, document in zip(forms, accessions, documents):
        if form != "8-K" or fetched >= count:
            continue
        if fetched > 0:
            time.sleep(REQUEST_DELAY_SECONDS)
        url = FILING_DOC_URL.format(cik=int(cik), accession_nodash=accession.replace("-", ""), document=document)
        try:
            html = _get(url, contact_email).text
        except Exception as e:
            print(f"  (couldn't fetch 8-K document for {ticker}: {e})", file=sys.stderr)
            continue
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        texts.append(text[:max_chars])
        fetched += 1

    return texts


def _extract_facts(company_facts: dict, tags: list[str], forms: tuple[str, ...]) -> list[XbrlFact]:
    us_gaap = company_facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        concept = us_gaap.get(tag)
        if not concept:
            continue
        facts = []
        for unit_values in concept.get("units", {}).values():
            for entry in unit_values:
                if entry.get("form") not in forms:
                    continue
                fp = entry.get("fp")
                fy = entry.get("fy")
                val = entry.get("val")
                filed = entry.get("filed")
                if fp is None or fy is None or val is None or filed is None:
                    continue
                facts.append(XbrlFact(fiscal_year=fy, fiscal_period=fp, value=float(val), form=entry["form"], filed=filed))
        if facts:
            return facts
    return []


def fetch_financial_facts(
    ticker: str, contact_email: str | None = None
) -> tuple[list[XbrlFact], list[XbrlFact]]:
    """Revenue and diluted-EPS facts from 10-Q/10-K filings, as reported --
    what `financials.py` needs to compute real year-over-year growth. Tries
    several XBRL tags per concept (see REVENUE_TAGS/EPS_TAGS) since which
    one a company uses has changed across taxonomy versions and varies by
    filer. Empty lists, not an exception, when nothing is found -- the same
    "missing data votes neutral" shape as every other signal here.
    """
    cik = fetch_cik(ticker, contact_email)
    if cik is None:
        return [], []

    try:
        company_facts = _get(COMPANY_FACTS_URL.format(cik10=cik), contact_email).json()
    except Exception as e:
        print(f"  (couldn't fetch SEC financial facts for {ticker}: {e})", file=sys.stderr)
        return [], []

    forms = ("10-Q", "10-K")
    revenue_facts = _extract_facts(company_facts, REVENUE_TAGS, forms)
    eps_facts = _extract_facts(company_facts, EPS_TAGS, forms)
    return revenue_facts, eps_facts
