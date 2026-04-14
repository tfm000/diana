import asyncio
import json
import sqlite3
import uuid
from datetime import datetime
from urllib.parse import urlparse

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import (
    add_news_feed,
    add_news_source,
    add_source_to_group,
    clear_news_feeds,
    clear_source_groups,
    create_job,
    init_db,
    list_news_groups,
    list_news_sources,
    load_latest_news,
    remove_news_feed,
    remove_news_source,
    remove_source_from_group,
    save_news_stories,
    update_news_source,
)
from diana.llm.registry import get_llm_config
from diana.models import Job, JobStatus
from diana.news.scraper import ScraperError, all_articles_stale, scrape_source
from diana.news.summarizer import Story, SummarizationError, summarize_all_sources
from diana.tts.registry import get_engine_voices, list_engines

st.set_page_config(
    page_title="Diana's News",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
db_path = config.storage.database_path
init_db(db_path)
setup_sidebar()

st.markdown("## *Diana's News*")

llm_cfg = get_llm_config(config)

# ---------------------------------------------------------------------------
# Load persisted stories into session state on cold page load
# ---------------------------------------------------------------------------
if "news_results" not in st.session_state:
    stored_stories, stored_at = load_latest_news(db_path)
    if stored_stories:
        st.session_state["news_results"] = [
            Story(
                headline=d["headline"],
                summary=d["summary"],
                category=d["category"],
                importance=d["importance"],
                url=d["url"],
                source_name=d["source_name"],
            )
            for d in stored_stories
        ]
        st.session_state["news_fetched_at"] = stored_at


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _archive_url(url: str) -> str:
    from urllib.parse import quote
    return f"https://archive.ph/submit/?url={quote(url, safe='')}"


def _valid_url(url: str) -> bool:
    if not url:
        return False
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Your Sources
# ---------------------------------------------------------------------------
st.subheader("Your Sources")

sort_col, filter_col, _ = st.columns([2, 2, 6])
with sort_col:
    sort_by = st.selectbox(
        "Sort by",
        ["Name A→Z", "Name Z→A", "Group", "Date added"],
        label_visibility="collapsed",
        key="news_src_sort",
    )
with filter_col:
    all_groups = list_news_groups(db_path)
    group_filter = st.selectbox(
        "Group filter",
        ["All groups"] + all_groups,
        label_visibility="collapsed",
        key="news_src_group_filter",
    )

sources = list_news_sources(db_path)

# Apply group filter
if group_filter != "All groups":
    sources = [s for s in sources if group_filter in s["groups"]]

# Apply sort
if sort_by == "Name A→Z":
    sources = sorted(sources, key=lambda s: s["name"].lower())
elif sort_by == "Name Z→A":
    sources = sorted(sources, key=lambda s: s["name"].lower(), reverse=True)
elif sort_by == "Group":
    sources = sorted(sources, key=lambda s: (s["groups"][0].lower() if s["groups"] else "", s["name"].lower()))
elif sort_by == "Date added":
    sources = sorted(sources, key=lambda s: s["created_at"])

editing_id: int | None = st.session_state.get("editing_source_id")

if sources:
    current_group_header = None

    for src in sources:
        sid = src["id"]
        src_groups: list[str] = src["groups"]
        src_feeds: list[dict] = src["feeds"]

        # Group header when sorted by Group
        if sort_by == "Group":
            header = src_groups[0] if src_groups else "Ungrouped"
            if header != current_group_header:
                st.markdown(f"**{header}**")
                current_group_header = header

        if editing_id == sid:
            st.markdown(f"*Editing: **{src['name']}***")

            # --- Name & URL (form to avoid re-render on feed/group button clicks) ---
            with st.form(f"edit_name_url_{sid}"):
                edit_name = st.text_input("Name", value=src["name"])
                edit_url = st.text_input(
                    "Homepage URL",
                    value=src.get("url", ""),
                    placeholder="https://www.ft.com",
                    help="Used for Visit and Archive buttons.",
                )
                sc1, sc2, _ = st.columns([1, 1, 6])
                if sc1.form_submit_button("Save"):
                    if not edit_name.strip():
                        st.error("Name is required.")
                    else:
                        update_news_source(db_path, sid, edit_name.strip(), edit_url.strip())
                        st.session_state.pop("editing_source_id", None)
                        st.rerun()
                if sc2.form_submit_button("Cancel"):
                    st.session_state.pop("editing_source_id", None)
                    st.rerun()

            # --- RSS Feeds ---
            st.caption("**RSS Feeds**")
            if src_feeds:
                for feed in src_feeds:
                    fl, fd = st.columns([9, 1])
                    if feed.get("label"):
                        fl.markdown(f"↳ `{feed['rss_url']}` — {feed['label']}")
                    else:
                        fl.markdown(f"↳ `{feed['rss_url']}`")
                    if fd.button("×", key=f"del_feed_{feed['id']}", help="Remove this feed"):
                        remove_news_feed(db_path, feed["id"])
                        st.rerun()
            else:
                st.caption("No RSS feeds added yet.")

            with st.form(f"add_feed_{sid}"):
                nf1, nf2, nf3 = st.columns([4, 2, 1])
                new_rss = nf1.text_input("RSS URL", placeholder="https://feeds.ft.com/rss/home", label_visibility="collapsed")
                new_label = nf2.text_input("Label", placeholder="optional label", label_visibility="collapsed")
                if nf3.form_submit_button("Add Feed"):
                    if _valid_url(new_rss):
                        add_news_feed(db_path, sid, new_rss.strip(), new_label.strip())
                        st.rerun()
                    else:
                        st.error("Enter a valid RSS URL.")

            # --- Groups ---
            st.caption("**Groups**")
            if src_groups:
                grp_cols = st.columns(min(len(src_groups) + 1, 8))
                for i, grp in enumerate(src_groups):
                    if grp_cols[i].button(f"{grp} ×", key=f"del_grp_{sid}_{grp}"):
                        remove_source_from_group(db_path, sid, grp)
                        st.rerun()
            else:
                st.caption("No groups assigned.")

            with st.form(f"add_group_{sid}"):
                ng1, ng2 = st.columns([4, 1])
                existing = list_news_groups(db_path)
                hint = ", ".join(existing[:5]) if existing else "Finance, Technology…"
                new_grp = ng1.text_input(
                    "Group name",
                    placeholder=f"e.g. {hint}",
                    label_visibility="collapsed",
                )
                if ng2.form_submit_button("Add Group"):
                    if new_grp.strip() and new_grp.strip() not in src_groups:
                        add_source_to_group(db_path, sid, new_grp.strip())
                        st.rerun()
                    elif new_grp.strip() in src_groups:
                        st.warning("Source is already in that group.")
                    else:
                        st.error("Enter a group name.")

            st.divider()

        else:
            # --- Normal display row ---
            c_name, c_visit, c_archive, c_edit, c_remove = st.columns([4, 1, 1, 1, 1])

            # Build name + group badges
            group_html = ""
            if src_groups and sort_by != "Group":
                badges = " ".join(
                    f"<span style='background:#e0e0e0;border-radius:4px;padding:1px 6px;"
                    f"font-size:0.78em;color:#444'>{g}</span>"
                    for g in src_groups
                )
                group_html = f" {badges}"
            c_name.markdown(f"**{src['name']}**{group_html}", unsafe_allow_html=True)

            visit_url = src.get("url", "")
            if visit_url:
                c_visit.link_button("Visit", url=visit_url, use_container_width=True)

            archive_target = src.get("url", "")
            if archive_target:
                c_archive.link_button("Archive", url=_archive_url(archive_target), use_container_width=True)

            if c_edit.button("Edit", key=f"edit_{sid}", use_container_width=True):
                st.session_state["editing_source_id"] = sid
                st.rerun()

            if c_remove.button("Remove", key=f"rm_{sid}", use_container_width=True):
                remove_news_source(db_path, sid)
                st.session_state.pop("editing_source_id", None)
                st.rerun()
else:
    st.info(
        "No sources yet — add one below."
        if group_filter == "All groups"
        else f"No sources in group '{group_filter}'."
    )

# --- Add source ---
with st.expander("Add a source"):
    st.caption(
        "Add a source by name and homepage URL. After adding, use **Edit** to attach "
        "RSS feeds and assign groups. "
        "Common RSS feeds: "
        "`https://www.ft.com/rss/home` · "
        "`https://feeds.bbci.co.uk/news/rss.xml` · "
        "`https://feeds.reuters.com/reuters/topNews`"
    )
    with st.form("add_source_form"):
        add_name = st.text_input("Name", placeholder="Financial Times")
        add_url = st.text_input(
            "Homepage URL",
            placeholder="https://www.ft.com",
            help="Homepage URL used for Visit and Archive buttons.",
        )
        if st.form_submit_button("Add Source"):
            if not add_name.strip():
                st.error("Name is required.")
            elif add_url.strip() and not _valid_url(add_url.strip()):
                st.error("Enter a valid homepage URL (or leave blank).")
            else:
                try:
                    add_news_source(db_path, add_name.strip(), add_url.strip())
                    st.success(f"Added **{add_name.strip()}**. Use Edit to add RSS feeds and groups.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("A source with that URL already exists.")

# ---------------------------------------------------------------------------
# Export sources
# ---------------------------------------------------------------------------
with st.expander("Export sources"):
    st.caption(
        "Download all your sources (names, homepage URLs, RSS feeds, and groups) "
        "as a JSON file that can be shared or imported on another device."
    )
    all_sources_for_export = list_news_sources(db_path)
    if all_sources_for_export:
        export_payload = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "sources": [
                {
                    "name": src["name"],
                    "url": src.get("url", ""),
                    "feeds": [
                        {"rss_url": f["rss_url"], "label": f.get("label", "")}
                        for f in src["feeds"]
                    ],
                    "groups": src["groups"],
                }
                for src in all_sources_for_export
            ],
        }
        export_bytes = json.dumps(export_payload, indent=2, ensure_ascii=False).encode("utf-8")
        st.download_button(
            label=f"Download diana_sources.json ({len(all_sources_for_export)} source{'s' if len(all_sources_for_export) != 1 else ''})",
            data=export_bytes,
            file_name="diana_sources.json",
            mime="application/json",
        )
    else:
        st.info("No sources to export yet.")

# ---------------------------------------------------------------------------
# Import sources
# ---------------------------------------------------------------------------
with st.expander("Import sources"):
    st.caption(
        "Upload a `diana_sources.json` file to import sources. "
        "If a source with the same homepage URL already exists, you can choose to "
        "**append** the imported feeds/groups to it or **overwrite** them entirely."
    )

    uploaded_file = st.file_uploader(
        "Choose a diana_sources.json file",
        type=["json"],
        key="news_import_uploader",
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        try:
            raw = json.loads(uploaded_file.read())
            if not isinstance(raw.get("sources"), list):
                raise ValueError("Missing 'sources' list.")
            import_sources: list[dict] = raw["sources"]
        except Exception as exc:
            st.error(f"Could not parse file: {exc}")
            import_sources = []

        if import_sources:
            existing_sources = list_news_sources(db_path)
            existing_by_url: dict[str, dict] = {
                s["url"]: s for s in existing_sources if s.get("url")
            }

            # Separate into new vs conflicting
            new_entries = [s for s in import_sources if s.get("url") not in existing_by_url]
            conflict_entries = [s for s in import_sources if s.get("url") in existing_by_url]

            st.markdown(f"**{len(import_sources)}** source(s) found in file.")
            if new_entries:
                st.markdown(f"- **{len(new_entries)}** new (will be added automatically)")
            if conflict_entries:
                st.markdown(f"- **{len(conflict_entries)}** already exist — choose action below:")

            conflict_actions: dict[str, str] = {}
            for src in conflict_entries:
                existing = existing_by_url[src["url"]]
                conflict_actions[src["url"]] = st.radio(
                    f'**{src["name"]}** (`{src["url"]}`)',
                    options=["append", "overwrite"],
                    format_func=lambda x: (
                        "Append feeds & groups" if x == "append"
                        else "Overwrite feeds & groups"
                    ),
                    horizontal=True,
                    key=f"import_action_{src['url']}",
                )

            if st.button("Import", type="primary", key="news_import_confirm_btn"):
                added_count = 0
                updated_count = 0

                for src in import_sources:
                    name = src.get("name", "").strip()
                    url = src.get("url", "").strip()
                    feeds: list[dict] = src.get("feeds", [])
                    groups: list[str] = src.get("groups", [])

                    if not name:
                        continue

                    if url in existing_by_url:
                        # Existing source — apply chosen action
                        existing = existing_by_url[url]
                        sid = existing["id"]
                        action = conflict_actions.get(url, "append")

                        if action == "overwrite":
                            clear_news_feeds(db_path, sid)
                            clear_source_groups(db_path, sid)
                            update_news_source(db_path, sid, name, url)
                            for feed in feeds:
                                rss = feed.get("rss_url", "").strip()
                                label = feed.get("label", "").strip()
                                if rss:
                                    try:
                                        add_news_feed(db_path, sid, rss, label)
                                    except sqlite3.IntegrityError:
                                        pass
                            for grp in groups:
                                if grp.strip():
                                    add_source_to_group(db_path, sid, grp.strip())
                        else:  # append
                            for feed in feeds:
                                rss = feed.get("rss_url", "").strip()
                                label = feed.get("label", "").strip()
                                if rss:
                                    try:
                                        add_news_feed(db_path, sid, rss, label)
                                    except sqlite3.IntegrityError:
                                        pass
                            for grp in groups:
                                if grp.strip():
                                    add_source_to_group(db_path, sid, grp.strip())
                        updated_count += 1
                    else:
                        # New source
                        try:
                            sid = add_news_source(db_path, name, url)
                        except sqlite3.IntegrityError:
                            continue
                        for feed in feeds:
                            rss = feed.get("rss_url", "").strip()
                            label = feed.get("label", "").strip()
                            if rss:
                                try:
                                    add_news_feed(db_path, sid, rss, label)
                                except sqlite3.IntegrityError:
                                    pass
                        for grp in groups:
                            if grp.strip():
                                add_source_to_group(db_path, sid, grp.strip())
                        added_count += 1

                parts = []
                if added_count:
                    parts.append(f"{added_count} added")
                if updated_count:
                    parts.append(f"{updated_count} updated")
                st.success(f"Import complete: {', '.join(parts)}.")
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Fetch stories
# ---------------------------------------------------------------------------
all_sources = list_news_sources(db_path)

if not all_sources:
    st.stop()

if llm_cfg is None:
    st.info(
        "Configure an LLM in **Settings → LLM Text Cleaning** to enable "
        "the 'Get Latest Stories' feature.",
        icon="ℹ️",
    )

if st.button("Get Latest Stories", type="primary", disabled=llm_cfg is None):
    scrape_errors: list[str] = []
    total = len(all_sources)
    progress = st.progress(0, text="Fetching stories…")

    async def _fetch_all():
        all_scraped: list[dict] = []
        archive_blocked = False  # stop trying archive.ph after a 429

        for i, src in enumerate(all_sources):
            name = src["name"]
            homepage = src.get("url", "") or ""
            feed_urls = [f["rss_url"] for f in src["feeds"] if f.get("rss_url")]

            # Order: RSS feeds → homepage → archive.ph (last resort)
            urls_to_try: list[str] = [*feed_urls]
            if homepage:
                urls_to_try.append(homepage)
            if homepage and not archive_blocked:
                urls_to_try.append(f"https://archive.ph/newest/{homepage}")

            if not urls_to_try:
                scrape_errors.append(f"**{name}**: no URL configured. Use Edit to add an RSS feed or homepage URL.")
                continue

            progress.progress((i + 0.5) / (total + 1), text=f"Scraping {name}…")

            scraped_articles = None
            last_err = ""
            for fetch_url in urls_to_try:
                try:
                    articles, _ = scrape_source(fetch_url)
                    if not articles:
                        last_err = "no articles found"
                        continue
                    if all_articles_stale(articles):
                        last_err = "all articles are older than 3 days — trying next source"
                        continue
                    scraped_articles = articles
                    break
                except ScraperError as exc:
                    last_err = str(exc)
                    # If archive.ph rate-limits us, stop trying it for remaining sources
                    if "archive.ph" in fetch_url and "429" in str(exc):
                        archive_blocked = True
                        last_err = "archive.ph rate-limited — try adding an RSS feed via Edit"

            if scraped_articles is not None:
                all_scraped.append({"name": name, "url": homepage, "articles": scraped_articles})
            else:
                scrape_errors.append(f"**{name}**: {last_err}")

        if not all_scraped:
            return []

        progress.progress(float(total) / (total + 1), text="Summarising with AI…")
        stories = await summarize_all_sources(
            all_scraped, llm_cfg,
            max_per_category=config.news.max_stories_per_category,
        )
        return stories

    try:
        fetched_stories: list[Story] = asyncio.run(_fetch_all())
    except SummarizationError as exc:
        fetched_stories = []
        st.error(f"Summarisation failed: {exc}")

    progress.empty()

    if fetched_stories:
        fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.session_state["news_results"] = fetched_stories
        st.session_state["news_fetched_at"] = fetched_at
        story_dicts = [
            {
                "headline": s.headline, "summary": s.summary, "category": s.category,
                "importance": s.importance, "url": s.url, "source_name": s.source_name,
            }
            for s in fetched_stories
        ]
        save_news_stories(db_path, story_dicts, fetched_at)
    st.session_state["news_fetch_errors"] = scrape_errors

# ---------------------------------------------------------------------------
# Display stories
# ---------------------------------------------------------------------------
all_stories: list[Story] = st.session_state.get("news_results", [])
fetched_at: str = st.session_state.get("news_fetched_at", "")

if not all_stories:
    st.stop()

st.caption(f"Last fetched: {fetched_at}")

all_stories_sorted = sorted(all_stories, key=lambda s: s.importance, reverse=True)

by_category: dict[str, list[Story]] = {}
for story in all_stories_sorted:
    by_category.setdefault(story.category, []).append(story)

ordered_cats = sorted(
    by_category.keys(),
    key=lambda c: max(s.importance for s in by_category[c]),
    reverse=True,
)

selected_story_keys: set[str] = set()

for cat in ordered_cats:
    with st.expander(cat, expanded=False):
        for story in by_category[cat]:
            story_key = f"{story.source_name}::{story.headline}"
            cols = st.columns([0.03, 0.97])
            if cols[0].checkbox(f"Select story: {story.headline}", key=f"chk_{story_key}", label_visibility="collapsed"):
                selected_story_keys.add(story_key)
            with cols[1]:
                title = (
                    f"**[{story.headline}]({story.url})**" if story.url
                    else f"**{story.headline}**"
                )
                st.markdown(title)
                st.caption(f"🗞 {story.source_name} · Importance: {story.importance}/10")
                st.write(story.summary)
                if story.url:
                    lc1, lc2, _ = st.columns([1, 1, 8])
                    lc1.link_button("Visit", url=story.url)
                    lc2.link_button("Archive", url=_archive_url(story.url))
            st.divider()

# ---------------------------------------------------------------------------
# TTS conversion
# ---------------------------------------------------------------------------
st.subheader("Convert to Audio")

tts_mode = st.selectbox(
    "Convert",
    ["All stories", "By category", "Selected stories"],
    key="news_tts_mode",
)

selected_categories: list[str] = []
if tts_mode == "By category":
    selected_categories = st.multiselect(
        "Choose categories", ordered_cats, default=ordered_cats[:1]
    )

tc1, tc2, tc3 = st.columns(3)
with tc1:
    tts_engine = st.selectbox("Engine", list_engines(), index=0, key="news_tts_engine")
with tc2:
    tts_voices = get_engine_voices(tts_engine, config=config)
    tts_voice_opts = {v.name: v.id for v in tts_voices}
    tts_voice_name = st.selectbox(
        "Voice", list(tts_voice_opts.keys()), key=f"news_voice_{tts_engine}"
    )
    tts_voice_id = tts_voice_opts.get(tts_voice_name, "")
with tc3:
    tts_speed = st.slider("Speed", 0.5, 2.0, config.tts.speed, 0.1, key="news_tts_speed")

if st.button("Convert to Audio", type="primary", key="news_convert_btn"):
    if tts_mode == "All stories":
        chosen = all_stories_sorted
    elif tts_mode == "By category":
        chosen = [s for s in all_stories_sorted if s.category in selected_categories]
    else:
        chosen = [s for s in all_stories_sorted if f"{s.source_name}::{s.headline}" in selected_story_keys]

    if not chosen:
        st.warning("No stories selected.")
    elif not tts_voice_id:
        st.warning("No voice available for this engine.")
    else:
        lines: list[str] = [f"Diana's News — {fetched_at}\n"]
        for story in chosen:
            lines.append(story.headline)
            lines.append(f"Source: {story.source_name}")
            lines.append(story.summary)
            lines.append("")
        news_text = "\n".join(lines)

        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, dir=config.storage.upload_dir,
        )
        tmp.write(news_text.encode("utf-8"))
        tmp.close()

        job_id = str(uuid.uuid4())
        filename = f"News_{fetched_at.replace(':', '-').replace(' ', '_')}.txt"
        job = Job(
            id=job_id, filename=filename, file_type="txt",
            upload_path=tmp.name, status=JobStatus.PENDING,
            tts_engine=tts_engine, tts_voice=tts_voice_id,
        )
        create_job(db_path, job)
        st.success(f"Job created for **{filename}**.")
        st.page_link("pages/2_Library.py", label="Go to Library", icon="📚")

# ---------------------------------------------------------------------------
# Scrape warnings (shown below stories so they don't interrupt reading)
# ---------------------------------------------------------------------------
for msg in st.session_state.get("news_fetch_errors", []):
    st.warning(msg, icon="⚠️")
