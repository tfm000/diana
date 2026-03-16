import time
from pathlib import Path

import streamlit as st

from diana.config import get_config
from diana.dashboard.sidebar import get_icon_image, setup_sidebar
from diana.database import delete_job, init_db, list_jobs, rename_job
from diana.models import JobStatus

st.set_page_config(
    page_title="Diana's Library",
    page_icon=get_icon_image(),
    layout="wide",
)

config = get_config()
init_db(config.storage.database_path)
setup_sidebar()

st.header("Library")

jobs = list_jobs(config.storage.database_path, limit=100)

if not jobs:
    st.info("No jobs yet. Upload a document to get started.")
    st.page_link(
        "pages/1_Upload.py", label="Upload a Document", icon="\U0001f4c4"
    )
else:
    for job in jobs:
        with st.container(border=True):
            status = job.status

            # Row 1: file info + status
            info_col, status_col = st.columns([3, 2])

            with info_col:
                st.markdown(f"**{job.filename}**")
                st.caption(
                    f"Engine: {job.tts_engine} | Voice: {job.tts_voice}"
                )

            with status_col:
                if status == JobStatus.COMPLETED:
                    st.success("Completed")
                elif status == JobStatus.FAILED:
                    st.error("Failed")
                    if job.error_message:
                        st.caption(job.error_message[:200])
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

                    # Row 3: download + rename + delete side by side
                    btn_col1, btn_col2, btn_col3, spacer = st.columns([1, 1, 1, 3])
                    with btn_col1:
                        with open(output_path, "rb") as f:
                            st.download_button(
                                "Download MP3",
                                data=f.read(),
                                file_name=f"{Path(job.filename).stem}.mp3",
                                mime="audio/mpeg",
                                key=f"dl_{job.id}",
                            )
                    with btn_col2:
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
                    with btn_col3:
                        if st.button(
                            "Delete", key=f"del_{job.id}", type="secondary"
                        ):
                            delete_job(config.storage.database_path, job.id)
                            st.rerun()
            else:
                # Rename + delete buttons for non-completed jobs
                btn_col1, btn_col2, spacer = st.columns([1, 1, 4])
                with btn_col1:
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
                with btn_col2:
                    if st.button(
                        "Delete", key=f"del_{job.id}", type="secondary"
                    ):
                        delete_job(config.storage.database_path, job.id)
                        st.rerun()

    # Auto-refresh if any jobs are still processing
    active_statuses = {
        JobStatus.PENDING, JobStatus.EXTRACTING, JobStatus.CHUNKING,
        JobStatus.SYNTHESIZING, JobStatus.MERGING,
    }
    if any(j.status in active_statuses for j in jobs):
        time.sleep(3)
        st.rerun()
