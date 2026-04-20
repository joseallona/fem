"""
Source Discovery — Phase 4, Stage 1.

Given a theme, generates and scores candidate sources.

Architecture (per Technical Architecture doc):
  Deterministic first:
    - keyword expansion from theme + primary subject + related subjects
    - subject ontology / domain type classification
    - source scoring: topical relevance + freshness + authority + signal density
  LLM only if:
    - related subjects are too sparse to infer adjacent domains
    - user explicitly triggers subject expansion

Source score formula (Decision Logic Specification §3):
  source_score = w1 * topical_relevance
               + w2 * freshness_score
               + w3 * authority_score
               + w4 * signal_density_estimate

Thresholds:
  > T1 (0.6) → suggested
  < T2 (0.3) → discarded
  between   → optional suggestion
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Source score weights
W_TOPICAL = 0.40
W_FRESHNESS = 0.25
W_AUTHORITY = 0.20
W_DENSITY = 0.15

T_SUGGEST = 0.45   # above → auto-suggest
T_DISCARD = 0.25   # below → discard

# Domain ontology: subject keyword → list of known source domains + feed URLs
# Deterministic lookup — expand over time
SUBJECT_ONTOLOGY: dict[str, list[dict]] = {
    "longevity": [
        {"name": "Nature Aging", "url": "https://www.nature.com/nataging/rss/current", "domain": "nature.com", "type": "academic", "authority": 0.95},
        {"name": "Longevity Technology", "url": "https://www.longevity.technology/feed/", "domain": "longevity.technology", "type": "news", "authority": 0.75},
        {"name": "Fight Aging!", "url": "https://www.fightaging.org/feed/", "domain": "fightaging.org", "type": "blog", "authority": 0.65},
        {"name": "Lifespan.io", "url": "https://www.lifespan.io/feed/", "domain": "lifespan.io", "type": "news", "authority": 0.72},
        {"name": "ScienceDaily Aging", "url": "https://www.sciencedaily.com/rss/health_medicine/aging.xml", "domain": "sciencedaily.com", "type": "news", "authority": 0.80},
        {"name": "The Scientist", "url": "https://www.the-scientist.com/rss", "domain": "the-scientist.com", "type": "news", "authority": 0.82},
        {"name": "Longevity Facts", "url": "https://longevityfacts.com/feed/", "domain": "longevityfacts.com", "type": "blog", "authority": 0.60},
        {"name": "Rejuvenation Research", "url": "https://www.liebertpub.com/action/showFeed?ui=0&mi=3fndc5&ai=rs&jc=rej&type=etoc&feed=rss", "domain": "liebertpub.com", "type": "academic", "authority": 0.85},
        {"name": "npj Aging", "url": "https://www.nature.com/npjamd/rss/current", "domain": "npjamd.nature.com", "type": "academic", "authority": 0.88},
        {"name": "Longevity.Technology News", "url": "https://www.longevity.technology/category/news/feed/", "domain": "longevity.technology/news", "type": "news", "authority": 0.74},
    ],
    "aging": [
        {"name": "GeroScience", "url": "https://link.springer.com/search.rss?facet-journal-id=11357&query=", "domain": "springer.com", "type": "academic", "authority": 0.90},
        {"name": "Aging Cell", "url": "https://onlinelibrary.wiley.com/feed/14749726/most-recent", "domain": "wiley.com", "type": "academic", "authority": 0.90},
        {"name": "Aging (journal)", "url": "https://www.aging-us.com/rss/articles", "domain": "aging-us.com", "type": "academic", "authority": 0.85},
        {"name": "Age and Ageing", "url": "https://academic.oup.com/rss/site_5193/advanceAccess_5193.xml", "domain": "academic.oup.com", "type": "academic", "authority": 0.88},
        {"name": "Journals of Gerontology", "url": "https://academic.oup.com/rss/site_5192/advanceAccess_5192.xml", "domain": "gerontologyjournals.com", "type": "academic", "authority": 0.87},
        {"name": "Cell Metabolism", "url": "https://www.cell.com/cell-metabolism/rss/current.xml", "domain": "cell.com", "type": "academic", "authority": 0.93},
        {"name": "Nature Reviews Aging", "url": "https://www.nature.com/natrevaging/rss/current", "domain": "natrevaging.nature.com", "type": "academic", "authority": 0.94},
        {"name": "bioRxiv Aging", "url": "https://connect.biorxiv.org/biorxiv_xml.php?subject=aging", "domain": "biorxiv.org", "type": "academic", "authority": 0.78},
        {"name": "PubMed Aging Research", "url": "https://pubmed.ncbi.nlm.nih.gov/rss/search/1m4E6nLCqnGHLiCBVDH7kJqPsOmYvkqHFg5f2dKH6CE/?limit=20&utm_campaign=pubmed-2", "domain": "pubmed.ncbi.nlm.nih.gov", "type": "academic", "authority": 0.90},
    ],
    "biotech": [
        {"name": "STAT News", "url": "https://www.statnews.com/feed/", "domain": "statnews.com", "type": "news", "authority": 0.85},
        {"name": "BioPharma Dive", "url": "https://www.biopharmadive.com/feeds/news/", "domain": "biopharmadive.com", "type": "news", "authority": 0.80},
        {"name": "Fierce Biotech", "url": "https://www.fiercebiotech.com/rss/xml", "domain": "fiercebiotech.com", "type": "news", "authority": 0.78},
        {"name": "Endpoints News", "url": "https://endpts.com/feed/", "domain": "endpts.com", "type": "news", "authority": 0.82},
        {"name": "MedCity News", "url": "https://medcitynews.com/feed/", "domain": "medcitynews.com", "type": "news", "authority": 0.74},
        {"name": "GenomeWeb", "url": "https://www.genomeweb.com/rss.xml", "domain": "genomeweb.com", "type": "news", "authority": 0.80},
        {"name": "Drug Discovery News", "url": "https://www.drugdiscoverynews.com/feed/", "domain": "drugdiscoverynews.com", "type": "news", "authority": 0.72},
        {"name": "BioWorld", "url": "https://www.bioworld.com/rss/headlines", "domain": "bioworld.com", "type": "news", "authority": 0.76},
        {"name": "Nature Biotechnology", "url": "https://www.nature.com/nbt/rss/current", "domain": "nbt.nature.com", "type": "academic", "authority": 0.95},
        {"name": "Science Translational Medicine", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=stm", "domain": "science.org", "type": "academic", "authority": 0.94},
        {"name": "Cell", "url": "https://www.cell.com/cell/rss/current.xml", "domain": "cell.com/cell", "type": "academic", "authority": 0.96},
        {"name": "eLife Sciences", "url": "https://elifesciences.org/rss/recent.xml", "domain": "elifesciences.org", "type": "academic", "authority": 0.88},
        {"name": "PLoS Biology", "url": "https://journals.plos.org/plosbiology/feed/atom", "domain": "plosbiology.org", "type": "academic", "authority": 0.87},
    ],
    "healthcare": [
        {"name": "NEJM", "url": "https://www.nejm.org/action/showFeed?type=etoc&feed=rss&jc=nejm", "domain": "nejm.org", "type": "academic", "authority": 0.98},
        {"name": "Health Affairs", "url": "https://www.healthaffairs.org/rss/site_3/41.xml", "domain": "healthaffairs.org", "type": "academic", "authority": 0.88},
        {"name": "Fierce Healthcare", "url": "https://www.fiercehealthcare.com/rss/xml", "domain": "fiercehealthcare.com", "type": "news", "authority": 0.75},
        {"name": "MedPage Today", "url": "https://www.medpagetoday.com/rss/headlines.xml", "domain": "medpagetoday.com", "type": "news", "authority": 0.78},
        {"name": "BMJ", "url": "https://www.bmj.com/rss/current.xml", "domain": "bmj.com", "type": "academic", "authority": 0.95},
        {"name": "The Lancet", "url": "https://www.thelancet.com/rssfeed/lancet_online.xml", "domain": "thelancet.com", "type": "academic", "authority": 0.97},
        {"name": "JAMA Network", "url": "https://jamanetwork.com/rss/site_3/67.xml", "domain": "jamanetwork.com", "type": "academic", "authority": 0.97},
        {"name": "Modern Healthcare", "url": "https://www.modernhealthcare.com/rss/news", "domain": "modernhealthcare.com", "type": "news", "authority": 0.78},
        {"name": "HealthLeaders", "url": "https://www.healthleadersmedia.com/rss.xml", "domain": "healthleadersmedia.com", "type": "news", "authority": 0.72},
        {"name": "Medical Xpress", "url": "https://medicalxpress.com/rss-feed/", "domain": "medicalxpress.com", "type": "news", "authority": 0.72},
        {"name": "Harvard Health", "url": "https://www.health.harvard.edu/blog/feed", "domain": "health.harvard.edu", "type": "blog", "authority": 0.85},
        {"name": "NIH News", "url": "https://www.nih.gov/rss/allevents.xml", "domain": "nih.gov", "type": "government", "authority": 0.92},
        {"name": "Annals of Internal Medicine", "url": "https://www.acpjournals.org/action/showFeed?ui=0&mi=3fndc5&ai=6nl&jc=aim&type=etoc&feed=rss", "domain": "acpjournals.org", "type": "academic", "authority": 0.94},
        {"name": "Becker's Hospital Review", "url": "https://www.beckershospitalreview.com/rss/all-topics.rss", "domain": "beckershospitalreview.com", "type": "news", "authority": 0.76},
        {"name": "KFF Health News", "url": "https://kffhealthnews.org/feed/", "domain": "kffhealthnews.org", "type": "news", "authority": 0.88},
        {"name": "PNAS", "url": "https://www.pnas.org/rss/current.xml", "domain": "pnas.org", "type": "academic", "authority": 0.95},
        {"name": "Science Advances", "url": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv", "domain": "science.org/sciadv", "type": "academic", "authority": 0.93},
        {"name": "Cell Medicine", "url": "https://www.cell.com/cell-medicine/rss/current.xml", "domain": "cell.com/medicine", "type": "academic", "authority": 0.92},
        {"name": "Commonwealth Fund", "url": "https://www.commonwealthfund.org/publications/rss.xml", "domain": "commonwealthfund.org", "type": "academic", "authority": 0.87},
        {"name": "Biotechnology Healthcare", "url": "https://www.ncbi.nlm.nih.gov/pmc/journals/232/feed/", "domain": "ncbi.nlm.nih.gov/biotech", "type": "academic", "authority": 0.90},
    ],
    "digital health": [
        {"name": "MobiHealthNews", "url": "https://www.mobihealthnews.com/rss.xml", "domain": "mobihealthnews.com", "type": "news", "authority": 0.78},
        {"name": "Healthcare IT News", "url": "https://www.healthcareitnews.com/rss.xml", "domain": "healthcareitnews.com", "type": "news", "authority": 0.76},
        {"name": "Digital Health Today", "url": "https://digitalhealthtoday.com/feed/", "domain": "digitalhealthtoday.com", "type": "news", "authority": 0.72},
        {"name": "Rock Health", "url": "https://rockhealth.com/feed/", "domain": "rockhealth.com", "type": "blog", "authority": 0.80},
        {"name": "Fierce Health IT", "url": "https://www.fiercehealthit.com/rss/xml", "domain": "fiercehealthit.com", "type": "news", "authority": 0.74},
        {"name": "Health Data Management", "url": "https://www.healthdatamanagement.com/rss/news", "domain": "healthdatamanagement.com", "type": "news", "authority": 0.72},
        {"name": "HIMSS News", "url": "https://www.himss.org/news/rss.xml", "domain": "himss.org", "type": "news", "authority": 0.80},
        {"name": "npj Digital Medicine", "url": "https://www.nature.com/npjdigitalmed/rss/current", "domain": "npjdigitalmed.nature.com", "type": "academic", "authority": 0.90},
        {"name": "Journal of Medical Internet Research", "url": "https://www.jmir.org/feed/atom", "domain": "jmir.org", "type": "academic", "authority": 0.86},
    ],
    "public health": [
        {"name": "CDC Newsroom", "url": "https://tools.cdc.gov/api/v2/resources/media/404952.rss", "domain": "cdc.gov/newsroom", "type": "government", "authority": 0.92},
        {"name": "WHO News", "url": "https://www.who.int/rss-feeds/news-english.xml", "domain": "who.int/news", "type": "government", "authority": 0.93},
        {"name": "ECDC News", "url": "https://www.ecdc.europa.eu/en/rss.xml", "domain": "ecdc.europa.eu", "type": "government", "authority": 0.90},
        {"name": "American Journal of Public Health", "url": "https://ajph.aphapublications.org/action/showFeed?ui=0&mi=3fndc5&ai=ri&jc=ajph&type=etoc&feed=rss", "domain": "ajph.aphapublications.org", "type": "academic", "authority": 0.89},
        {"name": "Bulletin of the World Health Organization", "url": "https://www.who.int/bulletin/en/rss.xml", "domain": "who.int/bulletin", "type": "academic", "authority": 0.91},
        {"name": "Public Health England", "url": "https://phescreening.blog.gov.uk/feed/", "domain": "phescreening.blog.gov.uk", "type": "government", "authority": 0.82},
        {"name": "Global Health Now", "url": "https://globalhealthnow.org/rss.xml", "domain": "globalhealthnow.org", "type": "news", "authority": 0.78},
    ],
    "ai": [
        {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/", "domain": "technologyreview.com", "type": "news", "authority": 0.90},
        {"name": "AI News", "url": "https://www.artificialintelligence-news.com/feed/", "domain": "artificialintelligence-news.com", "type": "news", "authority": 0.70},
        {"name": "The Gradient", "url": "https://thegradient.pub/rss/", "domain": "thegradient.pub", "type": "blog", "authority": 0.75},
        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "domain": "venturebeat.com", "type": "news", "authority": 0.78},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss", "domain": "wired.com", "type": "news", "authority": 0.85},
        {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/feeds/feed.rss", "domain": "spectrum.ieee.org", "type": "academic", "authority": 0.88},
        {"name": "Nature Machine Intelligence", "url": "https://www.nature.com/natmachintell/rss/current", "domain": "natmachintell.nature.com", "type": "academic", "authority": 0.93},
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "domain": "techcrunch.com", "type": "news", "authority": 0.80},
        {"name": "Google DeepMind Blog", "url": "https://www.deepmind.com/blog/rss.xml", "domain": "deepmind.com", "type": "blog", "authority": 0.88},
    ],
    "energy": [
        {"name": "Bloomberg NEF", "url": "https://about.bnef.com/blog/feed/", "domain": "bnef.com", "type": "news", "authority": 0.92},
        {"name": "S&P Global Commodity Insights", "url": "https://www.spglobal.com/commodityinsights/en/rss-feed", "domain": "spglobal.com", "type": "news", "authority": 0.88},
        {"name": "Energy Monitor", "url": "https://www.energymonitor.ai/feed/", "domain": "energymonitor.ai", "type": "news", "authority": 0.80},
        {"name": "IEA News", "url": "https://www.iea.org/rss/news.xml", "domain": "iea.org", "type": "government", "authority": 0.93},
        {"name": "Canary Media", "url": "https://www.canarymedia.com/rss", "domain": "canarymedia.com", "type": "news", "authority": 0.78},
        {"name": "Electrek", "url": "https://electrek.co/feed/", "domain": "electrek.co", "type": "news", "authority": 0.76},
        {"name": "PV Magazine", "url": "https://www.pv-magazine.com/feed/", "domain": "pv-magazine.com", "type": "news", "authority": 0.78},
        {"name": "Greentech Media", "url": "https://www.greentechmedia.com/rss/articles", "domain": "greentechmedia.com", "type": "news", "authority": 0.82},
        {"name": "Energy Policy (Elsevier)", "url": "https://rss.sciencedirect.com/publication/science/03014215", "domain": "sciencedirect.com", "type": "academic", "authority": 0.88},
        {"name": "Nature Energy", "url": "https://www.nature.com/nenergy/rss/current", "domain": "nenergy.nature.com", "type": "academic", "authority": 0.94},
        {"name": "Renewable Energy World", "url": "https://www.renewableenergyworld.com/feed/", "domain": "renewableenergyworld.com", "type": "news", "authority": 0.74},
        {"name": "Wood Mackenzie Insight", "url": "https://www.woodmac.com/news/rss/", "domain": "woodmac.com", "type": "news", "authority": 0.85},
    ],
    "climate": [
        {"name": "Carbon Brief", "url": "https://www.carbonbrief.org/feed", "domain": "carbonbrief.org", "type": "news", "authority": 0.88},
        {"name": "Scientific American", "url": "https://www.scientificamerican.com/section/earth-environment/feed/", "domain": "scientificamerican.com", "type": "news", "authority": 0.85},
        {"name": "Nature Climate Change", "url": "https://www.nature.com/nclimate/rss/current", "domain": "nclimate.nature.com", "type": "academic", "authority": 0.94},
        {"name": "Climate Home News", "url": "https://www.climatechangenews.com/feed/", "domain": "climatechangenews.com", "type": "news", "authority": 0.80},
        {"name": "Inside Climate News", "url": "https://insideclimatenews.org/feed/", "domain": "insideclimatenews.org", "type": "news", "authority": 0.82},
    ],
    "labor": [
        {"name": "ILO News", "url": "https://www.ilo.org/global/about-the-ilo/newsroom/news/WCMS_RSS.xml", "domain": "ilo.org", "type": "government", "authority": 0.88},
        {"name": "MIT Sloan Work Future", "url": "https://sloanreview.mit.edu/tag/future-of-work/feed/", "domain": "sloanreview.mit.edu", "type": "academic", "authority": 0.82},
        {"name": "Work Shift", "url": "https://workshift.substack.com/feed", "domain": "workshift.substack.com", "type": "newsletter", "authority": 0.68},
        {"name": "Bureau of Labor Statistics", "url": "https://www.bls.gov/feed/bls_latest.rss", "domain": "bls.gov", "type": "government", "authority": 0.90},
        {"name": "People Management", "url": "https://www.peoplemanagement.co.uk/rss/", "domain": "peoplemanagement.co.uk", "type": "news", "authority": 0.72},
        {"name": "HR Dive", "url": "https://www.hrdive.com/feeds/news/", "domain": "hrdive.com", "type": "news", "authority": 0.74},
    ],
    "insurance": [
        {"name": "Risk & Insurance", "url": "https://riskandinsurance.com/feed/", "domain": "riskandinsurance.com", "type": "news", "authority": 0.72},
        {"name": "Business Insurance", "url": "https://www.businessinsurance.com/rss/news/", "domain": "businessinsurance.com", "type": "news", "authority": 0.70},
        {"name": "Reinsurance News", "url": "https://www.reinsurancene.ws/feed/", "domain": "reinsurancene.ws", "type": "news", "authority": 0.68},
        {"name": "Insurance Journal", "url": "https://www.insurancejournal.com/rss/", "domain": "insurancejournal.com", "type": "news", "authority": 0.72},
        {"name": "AM Best News", "url": "https://news.ambest.com/rss/newsfeed.aspx", "domain": "ambest.com", "type": "news", "authority": 0.80},
        {"name": "Artemis", "url": "https://www.artemis.bm/feed/", "domain": "artemis.bm", "type": "news", "authority": 0.75},
    ],
    "regulation": [
        {"name": "FDA News", "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/fda-news-releases/rss.xml", "domain": "fda.gov", "type": "government", "authority": 0.95},
        {"name": "Regulatory Affairs Professionals", "url": "https://www.raps.org/rss-feeds", "domain": "raps.org", "type": "news", "authority": 0.80},
        {"name": "EMA News", "url": "https://www.ema.europa.eu/en/rss/news.xml", "domain": "ema.europa.eu", "type": "government", "authority": 0.93},
        {"name": "CDC Newsroom", "url": "https://tools.cdc.gov/api/v2/resources/media/404952.rss", "domain": "cdc.gov", "type": "government", "authority": 0.90},
        {"name": "WHO News", "url": "https://www.who.int/rss-feeds/news-english.xml", "domain": "who.int", "type": "government", "authority": 0.93},
        {"name": "PharmaPhorum", "url": "https://pharmaphorum.com/feed/", "domain": "pharmaphorum.com", "type": "news", "authority": 0.74},
        {"name": "Pink Sheet (Citeline)", "url": "https://pink.citeline.com/rss", "domain": "citeline.com", "type": "news", "authority": 0.82},
    ],
    "future of work": [
        {"name": "World Economic Forum", "url": "https://www.weforum.org/rss.xml", "domain": "weforum.org", "type": "news", "authority": 0.88},
        {"name": "MIT Sloan Management Review", "url": "https://sloanreview.mit.edu/feed/", "domain": "sloanreview.mit.edu", "type": "academic", "authority": 0.85},
        {"name": "Harvard Business Review", "url": "https://hbr.org/feed/the-latest", "domain": "hbr.org", "type": "academic", "authority": 0.88},
        {"name": "McKinsey Global Institute", "url": "https://www.mckinsey.com/mgi/rss", "domain": "mckinsey.com", "type": "news", "authority": 0.86},
        {"name": "Fast Company Work", "url": "https://www.fastcompany.com/section/work-life/rss", "domain": "fastcompany.com", "type": "news", "authority": 0.78},
    ],
    "general": [
        {"name": "The Economist", "url": "https://www.economist.com/the-world-this-week/rss.xml", "domain": "economist.com", "type": "news", "authority": 0.92},
        {"name": "Reuters Health", "url": "https://feeds.reuters.com/reuters/healthNews", "domain": "reuters.com", "type": "news", "authority": 0.95},
        {"name": "ScienceDaily All", "url": "https://www.sciencedaily.com/rss/all.xml", "domain": "sciencedaily.com", "type": "news", "authority": 0.80},
        {"name": "Science Magazine", "url": "https://www.science.org/rss/news_current.xml", "domain": "science.org", "type": "academic", "authority": 0.95},
        {"name": "Nature News", "url": "https://www.nature.com/news/rss/current", "domain": "nature.com/news", "type": "academic", "authority": 0.96},
        {"name": "New Scientist", "url": "https://www.newscientist.com/feed/home/", "domain": "newscientist.com", "type": "news", "authority": 0.83},
        {"name": "Phys.org Life Sciences", "url": "https://phys.org/rss-feed/biology/medical-research/", "domain": "phys.org", "type": "news", "authority": 0.75},
        {"name": "EurekAlert", "url": "https://www.eurekalert.org/rss.xml", "domain": "eurekalert.org", "type": "news", "authority": 0.78},
        {"name": "ScienceAlert", "url": "https://www.sciencealert.com/feed", "domain": "sciencealert.com", "type": "news", "authority": 0.74},
        {"name": "Quanta Magazine", "url": "https://www.quantamagazine.org/feed/", "domain": "quantamagazine.org", "type": "news", "authority": 0.88},
    ],
}

# Adjacent subject inference (deterministic ontology)
ADJACENT_SUBJECTS: dict[str, list[str]] = {
    "longevity": ["aging", "biotech", "healthcare", "insurance", "labor", "regulation"],
    "aging": ["longevity", "healthcare", "labor", "insurance"],
    "ai": ["labor", "regulation", "healthcare", "biotech"],
    "energy": ["climate", "regulation", "ai", "labor"],
    "climate": ["regulation", "labor", "insurance", "energy"],
    "digital health": ["healthcare", "ai", "regulation", "biotech"],
    "public health": ["healthcare", "regulation", "labor"],
    "healthcare": ["biotech", "regulation", "insurance", "aging"],
    "biotech": ["healthcare", "regulation", "longevity", "ai"],
    "future of work": ["labor", "ai", "regulation"],
}


def _normalize(text: str) -> str:
    return text.lower().strip()


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    text_lower = text.lower()
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return min(hits / len(keywords), 1.0)


def _topical_relevance(source: dict, all_subjects: list[str]) -> float:
    domain = source.get("domain", "")
    name = source.get("name", "")
    text = f"{domain} {name}".lower()
    return _keyword_overlap(text, [s.lower() for s in all_subjects])


def _freshness_score(source_type: str) -> float:
    return {"news": 0.9, "blog": 0.75, "academic": 0.5, "government": 0.6, "newsletter": 0.8}.get(source_type, 0.5)


def _score_source(source: dict, all_subjects: list[str]) -> float:
    topical = _topical_relevance(source, all_subjects)
    freshness = _freshness_score(source.get("type", "news"))
    authority = source.get("authority", 0.5)
    density = 0.5  # unknown until crawled; default to neutral

    score = (
        W_TOPICAL * topical
        + W_FRESHNESS * freshness
        + W_AUTHORITY * authority
        + W_DENSITY * density
    )
    return round(min(score, 1.0), 4)


def _infer_adjacent_subjects(
    primary_subject: Optional[str],
    related_subjects: list[str],
) -> list[str]:
    """Deterministic lookup of adjacent subjects from ontology."""
    all_subjects = set()
    subjects_to_check = []
    if primary_subject:
        subjects_to_check.append(_normalize(primary_subject))
    subjects_to_check.extend([_normalize(s) for s in related_subjects])

    for subject in subjects_to_check:
        # Always include the subject itself so SUBJECT_ONTOLOGY is checked for it
        all_subjects.add(subject)
        subject_words = set(subject.split())
        for key, adjacents in ADJACENT_SUBJECTS.items():
            key_words = set(key.split())
            # Match if any word from either side is a substring of any word on the other side
            # e.g. "health" (from "human health") matches inside "healthcare"
            matched = any(
                sw in kw or kw in sw
                for sw in subject_words
                for kw in key_words
            )
            if matched:
                all_subjects.add(key)
                all_subjects.update(adjacents)

    # Also add the originals
    all_subjects.update(subjects_to_check)
    return list(all_subjects)


def _llm_expand_subjects(theme_name: str, primary_subject: str, focal_question: str) -> list[str]:
    """LLM fallback for subject expansion when ontology is insufficient."""
    from app.services.llm_gateway import call_llm
    prompt = f"""Theme: {theme_name}
Primary subject: {primary_subject}
Focal question: {focal_question}

List 5-8 adjacent subject areas that would produce relevant signals for this theme.
Return a JSON array of short subject names only. Example: ["biotech", "regulation", "insurance"]
JSON only:"""
    import json
    try:
        raw = call_llm(prompt, job_type="triage")
        raw = raw.strip().strip("```json").strip("```").strip()
        subjects = json.loads(raw)
        return [s.lower() for s in subjects if isinstance(s, str)]
    except Exception as e:
        logger.warning("LLM subject expansion failed: %s", e)
        return []


def discover_sources(
    theme_name: str,
    primary_subject: Optional[str],
    related_subjects: list[str],
    focal_question: Optional[str],
    existing_domains: set[str],
    use_llm: bool = False,
    limit: int = 50,
) -> list[dict]:
    """
    Returns a scored list of candidate sources for a theme.
    Deterministic first. LLM only if use_llm=True and ontology is sparse.
    """
    # Build full subject set
    all_subjects = _infer_adjacent_subjects(primary_subject, related_subjects)

    # LLM expansion if ontology is sparse or subjects are few
    if use_llm and primary_subject:
        llm_subjects = _llm_expand_subjects(
            theme_name, primary_subject, focal_question or ""
        )
        all_subjects.extend(llm_subjects)
        logger.info("LLM expanded subjects to: %s", all_subjects)

    all_subjects = list(set(all_subjects))

    # Collect candidate sources from ontology
    seen_domains: set[str] = set(existing_domains)
    candidates = []

    # Always include general sources
    for subject in (all_subjects + ["general"]):
        for source in SUBJECT_ONTOLOGY.get(subject, []):
            domain = source.get("domain", "")
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            score = _score_source(source, all_subjects + [theme_name] + ([primary_subject] if primary_subject else []))
            if score < T_DISCARD:
                continue
            candidates.append({
                "name": source["name"],
                "url": source["url"],
                "domain": domain,
                "source_type": source.get("type", "news"),
                "relevance_score": score,
                "trust_score": source.get("authority", 0.5),
                "discovery_mode": "system",
                "status": "approved",
                "crawl_frequency": "daily",
            })

    # Sort by score desc, cap before reachability checks to avoid unnecessary requests
    candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
    candidates = candidates[:limit * 4]  # fetch a buffer; after reachability check we'll trim to limit

    # Filter out unreachable URLs concurrently
    candidates = _filter_reachable(candidates)
    candidates = candidates[:limit]

    logger.info("Source discovery: %d reachable candidates for theme '%s'", len(candidates), theme_name)
    return candidates


def _is_reachable(url: str) -> bool:
    """Quick HEAD (or GET) check. Returns False on any error or 4xx/5xx."""
    import requests
    from app.services.crawler import _make_headers
    headers = _make_headers(url)
    try:
        resp = requests.head(url, headers=headers, timeout=8, allow_redirects=True)
        if resp.status_code == 405:
            resp = requests.get(url, headers=headers, timeout=8, stream=True)
            resp.close()
        return resp.status_code < 400
    except Exception:
        return False


def _filter_reachable(candidates: list[dict]) -> list[dict]:
    """Remove candidates whose URLs are not reachable. Checked concurrently."""
    if not candidates:
        return candidates
    reachable = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_candidate = {pool.submit(_is_reachable, c["url"]): c for c in candidates}
        for future in as_completed(future_to_candidate):
            candidate = future_to_candidate[future]
            try:
                ok = future.result()
            except Exception:
                ok = False
            if ok:
                reachable.append(candidate)
            else:
                logger.info("Source discovery: dropping unreachable URL %s", candidate["url"])
    # Restore original score order after concurrent collection
    reachable.sort(key=lambda x: x["relevance_score"], reverse=True)
    return reachable
