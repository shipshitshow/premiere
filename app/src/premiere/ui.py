"""Streamlit UI for video review and approval."""

import streamlit as st
from pathlib import Path

from premiere.jobs import Job, JobQueue, JobStatus, get_queue
from premiere.worker import Worker


def init_session_state():
    """Initialize session state."""
    if "queue" not in st.session_state:
        st.session_state.queue = get_queue()
    if "worker" not in st.session_state:
        st.session_state.worker = Worker(st.session_state.queue)
    if "selected_job" not in st.session_state:
        st.session_state.selected_job = None


def render_sidebar():
    """Render sidebar with job list and actions."""
    st.sidebar.title("Premiere")
    st.sidebar.markdown("---")

    # Add new job
    st.sidebar.subheader("Add Video")

    source_type = st.sidebar.radio("Source", ["YouTube", "Local File"], horizontal=True)

    if source_type == "YouTube":
        url = st.sidebar.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
        if st.sidebar.button("Add from YouTube", use_container_width=True):
            if url:
                job = st.session_state.queue.create_job(
                    source_type="youtube",
                    source_url=url,
                )
                st.sidebar.success(f"Added job {job.id}")
                st.rerun()
    else:
        uploaded = st.sidebar.file_uploader("Upload Video", type=["mp4", "mov", "mkv", "avi"])
        if uploaded and st.sidebar.button("Add Local File", use_container_width=True):
            # Save uploaded file
            output_dir = Path.home() / ".premiere" / "uploads"
            output_dir.mkdir(parents=True, exist_ok=True)
            file_path = output_dir / uploaded.name
            with open(file_path, "wb") as f:
                f.write(uploaded.read())

            job = st.session_state.queue.create_job(
                source_type="local",
                source_path=str(file_path),
                title=uploaded.name,
            )
            st.sidebar.success(f"Added job {job.id}")
            st.rerun()

    st.sidebar.markdown("---")

    # Process pending jobs
    pending = st.session_state.queue.get_pending_jobs()
    if pending:
        if st.sidebar.button(f"Process {len(pending)} Pending", use_container_width=True):
            with st.spinner("Processing..."):
                st.session_state.worker.process_pending(limit=1)
            st.rerun()

    # Upload approved jobs
    approved = st.session_state.queue.get_approved_jobs()
    if approved:
        if st.sidebar.button(f"Upload {len(approved)} Approved", use_container_width=True):
            with st.spinner("Uploading..."):
                st.session_state.worker.upload_approved(limit=1)
            st.rerun()

    st.sidebar.markdown("---")

    # Job list
    st.sidebar.subheader("Jobs")

    status_filter = st.sidebar.selectbox(
        "Filter",
        ["All", "Pending", "Processing", "Review", "Approved", "Completed", "Failed"],
    )

    jobs = st.session_state.queue.list_jobs()

    if status_filter != "All":
        status = JobStatus(status_filter.lower())
        jobs = [j for j in jobs if j.status == status]

    for job in jobs:
        status_emoji = {
            JobStatus.PENDING: "⏳",
            JobStatus.DOWNLOADING: "📥",
            JobStatus.PROCESSING: "⚙️",
            JobStatus.REVIEW: "👀",
            JobStatus.APPROVED: "✅",
            JobStatus.UPLOADING: "📤",
            JobStatus.COMPLETED: "🎉",
            JobStatus.FAILED: "❌",
        }.get(job.status, "")

        label = f"{status_emoji} {job.title[:30] or job.id}"
        if st.sidebar.button(label, key=f"job_{job.id}", use_container_width=True):
            st.session_state.selected_job = job.id
            st.rerun()


def render_job_detail(job: Job):
    """Render job detail view."""
    col1, col2 = st.columns([2, 1])

    with col1:
        st.title(job.title or f"Job {job.id}")
        st.caption(f"Status: **{job.status.value.upper()}** | Created: {job.created_at[:16]}")

    with col2:
        if job.status == JobStatus.REVIEW:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Approve", use_container_width=True, type="primary"):
                    job.status = JobStatus.APPROVED
                    st.session_state.queue.update_job(job)
                    st.success("Approved!")
                    st.rerun()
            with c2:
                if st.button("❌ Reject", use_container_width=True):
                    job.status = JobStatus.FAILED
                    job.error = "Rejected by user"
                    st.session_state.queue.update_job(job)
                    st.rerun()

        if st.button("🗑️ Delete Job", use_container_width=True):
            st.session_state.queue.delete_job(job.id)
            st.session_state.selected_job = None
            st.rerun()

    if job.error:
        st.error(f"Error: {job.error}")

    # Video preview
    if job.output_path and Path(job.output_path).exists():
        st.subheader("Processed Video")
        st.video(job.output_path)
    elif job.input_path and Path(job.input_path).exists():
        st.subheader("Source Video")
        st.video(job.input_path)

    # Tabs for different sections
    tabs = st.tabs(["Metadata", "Clips", "Transcript", "Settings"])

    with tabs[0]:
        render_metadata_tab(job)

    with tabs[1]:
        render_clips_tab(job)

    with tabs[2]:
        render_transcript_tab(job)

    with tabs[3]:
        render_settings_tab(job)


def render_metadata_tab(job: Job):
    """Render metadata editing tab."""
    st.subheader("YouTube Metadata")

    # Title selection
    if job.generated_titles:
        st.markdown("**Select Title:**")
        for i, title in enumerate(job.generated_titles):
            selected = job.selected_title == title
            if st.checkbox(title, value=selected, key=f"title_{i}"):
                job.selected_title = title
                st.session_state.queue.update_job(job)

    # Or custom title
    custom_title = st.text_input("Custom Title", value=job.selected_title)
    if custom_title != job.selected_title:
        job.selected_title = custom_title
        st.session_state.queue.update_job(job)

    # Description
    st.markdown("**Description:**")
    description = st.text_area(
        "Description",
        value=job.selected_description or job.generated_description,
        height=200,
        label_visibility="collapsed",
    )
    if description != job.selected_description:
        job.selected_description = description
        st.session_state.queue.update_job(job)

    # Tags
    st.markdown("**Tags:**")
    tags_str = ", ".join(job.selected_tags or job.generated_tags)
    new_tags = st.text_input("Tags (comma-separated)", value=tags_str)
    new_tags_list = [t.strip() for t in new_tags.split(",") if t.strip()]
    if new_tags_list != job.selected_tags:
        job.selected_tags = new_tags_list
        st.session_state.queue.update_job(job)

    # Thumbnail preview
    if job.thumbnail_path and Path(job.thumbnail_path).exists():
        st.markdown("**Thumbnail:**")
        st.image(job.thumbnail_path, width=400)


def render_clips_tab(job: Job):
    """Render clips selection tab."""
    st.subheader("Generated Clips")

    if not job.clips:
        st.info("No clips generated. Process the video with clips enabled.")
        return

    for i, clip in enumerate(job.clips):
        clip_path = Path(clip["path"])

        with st.expander(f"Clip {i+1}: {clip['title'][:50]}", expanded=i == 0):
            col1, col2 = st.columns([2, 1])

            with col1:
                if clip_path.exists():
                    st.video(str(clip_path))
                else:
                    st.warning("Clip file not found")

            with col2:
                st.markdown(f"**Duration:** {clip['end'] - clip['start']:.1f}s")
                st.markdown(f"**Caption:** {clip['caption']}")
                if clip["hashtags"]:
                    st.markdown(f"**Hashtags:** {' '.join(clip['hashtags'])}")

                # Select for upload
                is_selected = str(clip_path) in job.selected_clips
                if st.checkbox("Include in upload", value=is_selected, key=f"clip_select_{i}"):
                    if str(clip_path) not in job.selected_clips:
                        job.selected_clips.append(str(clip_path))
                        st.session_state.queue.update_job(job)
                else:
                    if str(clip_path) in job.selected_clips:
                        job.selected_clips.remove(str(clip_path))
                        st.session_state.queue.update_job(job)


def render_transcript_tab(job: Job):
    """Render transcript tab."""
    st.subheader("Transcript")

    if job.transcript_path and Path(job.transcript_path).exists():
        with open(job.transcript_path, "r") as f:
            transcript = f.read()
        st.markdown(transcript)

        # Download button
        st.download_button(
            "Download Transcript",
            transcript,
            file_name=f"{job.id}_transcript.md",
            mime="text/markdown",
        )
    else:
        st.info("Transcript not generated yet.")


def render_settings_tab(job: Job):
    """Render job settings tab."""
    st.subheader("Job Details")

    st.json({
        "id": job.id,
        "status": job.status.value,
        "source_type": job.source_type,
        "source_url": job.source_url,
        "source_path": job.source_path,
        "input_path": job.input_path,
        "output_path": job.output_path,
        "transcript_path": job.transcript_path,
        "thumbnail_path": job.thumbnail_path,
        "clips_dir": job.clips_dir,
        "youtube_url": job.youtube_url,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    })

    # Reprocess button
    if st.button("🔄 Reprocess Video"):
        job.status = JobStatus.PENDING
        st.session_state.queue.update_job(job)
        st.rerun()


def render_dashboard():
    """Render main dashboard."""
    st.title("Video Review Dashboard")

    # Stats
    jobs = st.session_state.queue.list_jobs()
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        pending = len([j for j in jobs if j.status == JobStatus.PENDING])
        st.metric("Pending", pending)

    with col2:
        review = len([j for j in jobs if j.status == JobStatus.REVIEW])
        st.metric("Ready for Review", review)

    with col3:
        approved = len([j for j in jobs if j.status == JobStatus.APPROVED])
        st.metric("Approved", approved)

    with col4:
        completed = len([j for j in jobs if j.status == JobStatus.COMPLETED])
        st.metric("Completed", completed)

    st.markdown("---")

    # Quick actions
    review_jobs = st.session_state.queue.get_review_jobs()
    if review_jobs:
        st.subheader("Ready for Review")
        for job in review_jobs[:5]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{job.title or job.id}**")
            with col2:
                if st.button("Review", key=f"review_{job.id}"):
                    st.session_state.selected_job = job.id
                    st.rerun()
    else:
        st.info("No videos pending review. Add a video from the sidebar.")


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Premiere",
        page_icon="🎬",
        layout="wide",
    )

    init_session_state()
    render_sidebar()

    # Main content
    if st.session_state.selected_job:
        job = st.session_state.queue.get_job(st.session_state.selected_job)
        if job:
            render_job_detail(job)
        else:
            st.session_state.selected_job = None
            st.rerun()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
