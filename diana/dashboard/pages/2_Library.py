import time
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import (
    count_jobs, delete_folder, delete_job, init_db, list_folders, list_jobs,
    move_job_to_folder, rename_job,
)
from diana.models import JobStatus

st.set_page_config(
    page_title="Diana's Library",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
init_db(config.storage.database_path)
setup_sidebar()

st.markdown("## *Library*")

PAGE_SIZE = 20

# --- Search, filter, sort, folder controls ---
ctrl_cols = st.columns([3, 1, 1, 1])

with ctrl_cols[0]:
    search_query = st.text_input(
        "Search", placeholder="Search by filename...", label_visibility="collapsed"
    )

with ctrl_cols[1]:
    status_options = ["All"] + [s.value.capitalize() for s in JobStatus]
    status_filter = st.selectbox("Status", status_options, label_visibility="collapsed")

with ctrl_cols[2]:
    sort_option = st.selectbox(
        "Sort",
        ["Newest", "Oldest", "Name A-Z", "Name Z-A", "Status"],
        label_visibility="collapsed",
    )

with ctrl_cols[3]:
    folders = list_folders(config.storage.database_path)
    folder_options = ["All", "Ungrouped"] + folders
    selected_folder = st.selectbox("Folder", folder_options, label_visibility="collapsed")

# Folder management
with st.expander("Manage Folders", expanded=False):
    mgmt_cols = st.columns([3, 1])
    with mgmt_cols[0]:
        new_folder_name = st.text_input("New folder name", label_visibility="collapsed", placeholder="New folder name")
    with mgmt_cols[1]:
        if st.button("Create Folder") and new_folder_name.strip():
            # Folder created implicitly when a job is moved to it; store for use in Move
            st.session_state["_new_folder"] = new_folder_name.strip()
            st.rerun()

    if folders:
        for f in folders:
            fc1, fc2 = st.columns([4, 1])
            with fc1:
                st.text(f)
            with fc2:
                if st.button("Remove", key=f"delfolder_{f}"):
                    delete_folder(config.storage.database_path, f)
                    st.rerun()

# Include any just-created folder in the available list
available_folders = list(folders)
if st.session_state.get("_new_folder") and st.session_state["_new_folder"] not in available_folders:
    available_folders.append(st.session_state["_new_folder"])

# --- Fetch and filter jobs ---
# When filtering, fetch all; otherwise use pagination
use_client_filter = bool(search_query) or status_filter != "All" or selected_folder != "All"

if use_client_filter:
    all_jobs = list_jobs(config.storage.database_path, limit=10000)
else:
    all_jobs = list_jobs(config.storage.database_path, limit=10000)

filtered_jobs = all_jobs

if search_query:
    q = search_query.lower()
    filtered_jobs = [j for j in filtered_jobs if q in j.filename.lower()]

if status_filter != "All":
    filtered_jobs = [j for j in filtered_jobs if j.status.value == status_filter.lower()]

if selected_folder == "Ungrouped":
    filtered_jobs = [j for j in filtered_jobs if not j.folder]
elif selected_folder != "All":
    filtered_jobs = [j for j in filtered_jobs if j.folder == selected_folder]

# Sort
if sort_option == "Newest":
    filtered_jobs.sort(key=lambda j: j.created_at, reverse=True)
elif sort_option == "Oldest":
    filtered_jobs.sort(key=lambda j: j.created_at)
elif sort_option == "Name A-Z":
    filtered_jobs.sort(key=lambda j: j.filename.lower())
elif sort_option == "Name Z-A":
    filtered_jobs.sort(key=lambda j: j.filename.lower(), reverse=True)
elif sort_option == "Status":
    order = {s: i for i, s in enumerate(JobStatus)}
    filtered_jobs.sort(key=lambda j: order.get(j.status, 99))

# Pagination
total_filtered = len(filtered_jobs)
total_pages = max(1, (total_filtered + PAGE_SIZE - 1) // PAGE_SIZE)

if "library_page" not in st.session_state:
    st.session_state.library_page = 0
# Clamp page if filters changed
if st.session_state.library_page >= total_pages:
    st.session_state.library_page = max(0, total_pages - 1)

current_page = st.session_state.library_page
page_jobs = filtered_jobs[current_page * PAGE_SIZE : (current_page + 1) * PAGE_SIZE]

# --- Render jobs ---
if not filtered_jobs:
    if all_jobs:
        st.info("No jobs match your search or filters.")
    else:
        st.info("No jobs yet. Upload a document to get started.")
        st.page_link(
            "pages/1_Upload.py", label="Upload a Document", icon="\U0001f4c4"
        )
else:
    for job in page_jobs:
        with st.container(border=True):
            status = job.status

            # Row 1: file info + status
            info_col, status_col = st.columns([3, 2])

            with info_col:
                label = f"**{job.filename}**"
                if job.folder:
                    label += f"  \u2022  \U0001f4c1 {job.folder}"
                st.markdown(label)
                st.caption(
                    f"Engine: {job.tts_engine} | Voice: {job.tts_voice}"
                )

            with status_col:
                if status == JobStatus.COMPLETED:
                    st.success("Completed")
                elif status == JobStatus.FAILED:
                    st.error("Failed")
                    if job.error_message:
                        with st.expander("Error details", expanded=False):
                            st.code(job.error_message, language=None)
                elif status == JobStatus.SYNTHESIZING:
                    st.info(
                        f"Synthesizing... "
                        f"({job.completed_chunks}/{job.total_chunks})"
                    )
                    if job.total_chunks > 0:
                        st.progress(job.progress)
                elif status == JobStatus.PENDING:
                    st.warning("Pending")
                else:
                    st.info(status.value.capitalize())

            # Row 2: audio player (full width)
            if status == JobStatus.COMPLETED and job.output_path:
                output_path = Path(job.output_path)
                if output_path.exists():
                    st.audio(str(output_path), format="audio/mp3")

            # Row 3: action buttons
            if status == JobStatus.COMPLETED and job.output_path and Path(job.output_path).exists():
                btn_col1, btn_col2, btn_col3, btn_col4, spacer = st.columns([1, 1, 1, 1, 2])
            else:
                btn_col1, btn_col2, btn_col3, btn_col4, spacer = st.columns([1, 1, 1, 1, 2])
                btn_col1 = None  # no download for non-completed

            # Download (completed only)
            if status == JobStatus.COMPLETED and job.output_path:
                output_path = Path(job.output_path)
                if output_path.exists():
                    cols = st.columns([1, 1, 1, 1, 2])
                    with cols[0]:
                        with open(output_path, "rb") as f:
                            st.download_button(
                                "Download",
                                data=f.read(),
                                file_name=f"{Path(job.filename).stem}.mp3",
                                mime="audio/mpeg",
                                key=f"dl_{job.id}",
                            )
                    with cols[1]:
                        with st.popover("Rename"):
                            new_name = st.text_input(
                                "New name",
                                value=job.filename,
                                key=f"rename_input_{job.id}",
                            )
                            if st.button("Save", key=f"rename_save_{job.id}"):
                                if new_name.strip() and new_name != job.filename:
                                    rename_job(config.storage.database_path, job.id, new_name.strip())
                                    st.rerun()
                    with cols[2]:
                        with st.popover("Move"):
                            target = st.selectbox(
                                "Move to",
                                ["(None)"] + available_folders,
                                key=f"move_{job.id}",
                            )
                            if st.button("Move", key=f"move_btn_{job.id}"):
                                move_job_to_folder(
                                    config.storage.database_path,
                                    job.id,
                                    "" if target == "(None)" else target,
                                )
                                st.rerun()
                    with cols[3]:
                        # Delete with confirmation
                        delete_key = f"confirm_del_{job.id}"
                        if st.session_state.get(delete_key, False):
                            st.warning("Delete?")
                            yc, nc = st.columns(2)
                            with yc:
                                if st.button("Yes", key=f"del_yes_{job.id}"):
                                    delete_job(config.storage.database_path, job.id)
                                    st.session_state.pop(delete_key, None)
                                    st.rerun()
                            with nc:
                                if st.button("No", key=f"del_no_{job.id}"):
                                    st.session_state.pop(delete_key, None)
                                    st.rerun()
                        else:
                            if st.button("Delete", key=f"del_{job.id}", type="secondary"):
                                st.session_state[delete_key] = True
                                st.rerun()
            else:
                # Non-completed: rename, move, delete
                cols = st.columns([1, 1, 1, 3])
                with cols[0]:
                    with st.popover("Rename"):
                        new_name = st.text_input(
                            "New name",
                            value=job.filename,
                            key=f"rename_input_{job.id}",
                        )
                        if st.button("Save", key=f"rename_save_{job.id}"):
                            if new_name.strip() and new_name != job.filename:
                                rename_job(config.storage.database_path, job.id, new_name.strip())
                                st.rerun()
                with cols[1]:
                    with st.popover("Move"):
                        target = st.selectbox(
                            "Move to",
                            ["(None)"] + available_folders,
                            key=f"move_{job.id}",
                        )
                        if st.button("Move", key=f"move_btn_{job.id}"):
                            move_job_to_folder(
                                config.storage.database_path,
                                job.id,
                                "" if target == "(None)" else target,
                            )
                            st.rerun()
                with cols[2]:
                    delete_key = f"confirm_del_{job.id}"
                    if st.session_state.get(delete_key, False):
                        st.warning("Delete?")
                        yc, nc = st.columns(2)
                        with yc:
                            if st.button("Yes", key=f"del_yes_{job.id}"):
                                delete_job(config.storage.database_path, job.id)
                                st.session_state.pop(delete_key, None)
                                st.rerun()
                        with nc:
                            if st.button("No", key=f"del_no_{job.id}"):
                                st.session_state.pop(delete_key, None)
                                st.rerun()
                    else:
                        if st.button("Delete", key=f"del_{job.id}", type="secondary"):
                            st.session_state[delete_key] = True
                            st.rerun()

    # Pagination controls
    if total_pages > 1:
        st.divider()
        pag_cols = st.columns([1, 2, 1])
        with pag_cols[0]:
            if st.button("Previous", disabled=(current_page == 0)):
                st.session_state.library_page -= 1
                st.rerun()
        with pag_cols[1]:
            st.markdown(
                f"<center>Page {current_page + 1} of {total_pages} ({total_filtered} jobs)</center>",
                unsafe_allow_html=True,
            )
        with pag_cols[2]:
            if st.button("Next", disabled=(current_page >= total_pages - 1)):
                st.session_state.library_page += 1
                st.rerun()

    # Auto-refresh if any jobs are still processing
    active_statuses = {
        JobStatus.PENDING, JobStatus.EXTRACTING, JobStatus.CHUNKING,
        JobStatus.SYNTHESIZING, JobStatus.MERGING,
    }
    if any(j.status in active_statuses for j in all_jobs):
        time.sleep(3)
        st.rerun()
