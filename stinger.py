import os, re, sys
from datetime import datetime, UTC

if sys.version_info[0] != 3 or sys.version_info[1] < 11:
    print("Version Error: Version: %s.%s.%s incompatible please use Python 3.11+" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    sys.exit(0)

try:
    import requests
    from git import Repo
    from lxml import html
    from kometautils import KometaArgs, KometaLogger, YAML
    from tmdbapis import TMDbAPIs, TMDbException
except (ModuleNotFoundError, ImportError):
    print("Requirements Error: Requirements are not installed")
    sys.exit(0)

options = [
    {"arg": "ta", "key": "tmdbapi",      "env": "TMDBAPI",      "type": "str",  "default": None,  "help": "TMDb V3 API Key for restoring posters from TMDb."},
    {"arg": "tr", "key": "trace",        "env": "TRACE",        "type": "bool", "default": False, "help": "Run with extra trace logs."},
    {"arg": "lr", "key": "log-requests", "env": "LOG_REQUESTS", "type": "bool", "default": False, "help": "Run with every request logged."}
]
script_name = "Media Stinger"
base_dir = os.path.dirname(os.path.abspath(__file__))
args = KometaArgs("Kometa-Team/Mediastingers", base_dir, options, use_nightly=False)
logger = KometaLogger(script_name, "stinger", os.path.join(base_dir, "logs"), is_trace=args["trace"], log_requests=args["log-requests"])
logger.screen_width = 175
logger.secret([args["tmdbapi"]])
logger.header(args, sub=True)
logger.separator("Validating Options", space=False, border=False)
logger.start()
tmdb = TMDbAPIs(args["tmdbapi"])
logger.info("TMDb Connected Successfully")
url = "http://www.mediastinger.com/movies-with-stingers/"
page_num = 0
override = {t: i for t, i in YAML(path=os.path.join(base_dir, "tmdb_override.yml"), create=True).items()}
rows = []
data = YAML(path=os.path.join(base_dir, "stingers.yml"), start_empty=True)
while url:
    page_num += 1
    logger.info(f"Parsing Page {page_num}: {url}")
    response = html.fromstring(requests.get(url).content)
    next_page = response.xpath("//a[@title='Next page']/@href")
    url = next_page[0] if next_page else None
    for item in response.xpath("//ul[@class='highlights showhidehtml commonclssearch divwidth']/li"): # noqa
        title = item.xpath("a/span/div/text()")
        if title:
            title = title[0].strip()
            try:
                rating = int(item.xpath("span/div/text()")[0].strip())
            except ValueError:
                rating = 0
            rating_str = f"{'+' if rating > 0 else ''}{rating}"
            vgs = item.xpath("span/span/a/@href")
            if any(["video-games" in v for v in vgs]):
                rows.append(("", rating_str, title, "WARNING IGNORED: Item is a Video Game"))
                continue

            res = re.search(r"(.*) \((\d*)\)", title)
            search_title = res.group(1) if res else title
            search_year = int(res.group(2)) if res else None
            tmdb_id = None
            tmdb_title = None
            tmdb_item = None
            if title in override:
                tmdb_item = tmdb.movie(override[title])
            else:
                try:
                    searches = tmdb.movie_search(search_title, year=search_year)
                    tmdb_item = searches.results[0]
                except TMDbException:
                    try:
                        searches = tmdb.movie_search(search_title)
                        tmdb_item = searches.results[0]
                    except TMDbException:
                        rows.append(("", rating_str, title, "WARNING IGNORED: TMDb ID Not Found"))
                        continue
            tmdb_title = f"{tmdb_item.name} ({tmdb_item.release_date.year})"
            if tmdb_title == title:
                tmdb_title = ""
            rows.append((str(tmdb_item.id), rating_str, title, tmdb_title))
            data[tmdb_item.id] = rating

headers = ["TMDb ID", "Rating", "MediaStinger Title", "Warning Message or TMDb Title When Different"]
widths = []
for i, header in enumerate(headers):
    _max = len(max(rows, key=lambda t: len(t[i]))[i])
    widths.append(_max if _max > len(header) else len(header))

data.save()

if [item.a_path for item in Repo(path=".").index.diff(None) if item.a_path.endswith(".yml")]:

    with open("README.md", "r") as f:
        readme_data = f.readlines()

    readme_data[1] = f"Last generated at: {datetime.now(UTC).strftime('%B %d, %Y %I:%M %p')} UTC\n"

    with open("README.md", "w") as f:
        f.writelines(readme_data)

logger.separator("Stinger Report")
logger.info(f"{headers[0]:^{widths[0]}} | {headers[1]:^{widths[1]}} | {headers[2]:<{widths[2]}} | {headers[3]:<{widths[3]}}")
logger.separator(f"{'-' * widths[0]}|{'-' * (widths[1] + 2)}|{'-' * (widths[2] + 2)}|{'-' * (widths[3] + 1)}", space=False, border=False, side_space=False, sep="-", left=True)
for tmdb_id, rating, title, message in rows:
    logger.info(f"{tmdb_id:>{widths[0]}} | {rating:>{widths[1]}} | {title:<{widths[2]}} | {message:<{widths[3]}}")

logger.separator(f"{script_name} Finished\nTotal Runtime: {logger.runtime()}")
