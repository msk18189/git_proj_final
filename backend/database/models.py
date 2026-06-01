"""ORM models for PRISM — GitHub Engineering Intelligence Platform.

All 9 intelligence modules are represented here:
  Module 1: Pull Requests (pull_requests, pr_reviews, pr_files, pr_commits)
  Module 2: Issues       (issues, issue_comments)
  Module 3: Branches     (branches)
  Module 4: Repository   (repositories)
  Module 5: Forks        (forks)
  Module 6: Discussions  (discussions, discussion_comments)
  Module 7: Projects     (projects, project_items)
  Module 8: CI/CD        (workflows, workflow_runs, workflow_jobs)
  Module 9: Visibility   (stored on repositories)

Support tables:
  contributors, ml_predictions, analytics_snapshots, total_analysis
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    BigInteger,
    Index,
)
from sqlalchemy.orm import relationship
from .database import Base

# Helper to generate UTC timestamps
def utc_now():
    """Return current time in UTC with timezone info."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# MODULE 4 — REPOSITORY METADATA (core table, extended for all modules)
# ---------------------------------------------------------------------------

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    full_name = Column(String(511), unique=True, nullable=False, index=True)
    url = Column(String(512), unique=True, nullable=True)
    source_url = Column(String(512), nullable=True)

    # Module 4 — Repo metadata
    description = Column(Text, nullable=True)
    homepage = Column(String(1024), nullable=True)
    language = Column(String(100), nullable=True)
    default_branch = Column(String(255), nullable=True)
    repo_size = Column(Integer, default=0)           # in KB
    stars = Column(Integer, default=0, nullable=False)
    watchers = Column(Integer, default=0)
    forks_count = Column(Integer, default=0)

    # Module 9 — Visibility tracking
    visibility = Column(String(50), default="public")  # public / private / internal

    # Sync metadata
    sync_status = Column(String(50), default="IDLE", nullable=False)
    sync_mode = Column(String(50), default="full")       # full / lightweight / partial
    sync_progress = Column(String(512), nullable=True)
    # JSON blob storing per-module resume cursors/pages, e.g. {"pull_requests": "<cursor>", "issues": "https://api...&page=3"}
    sync_cursors = Column(Text, nullable=True)
    sync_error = Column(Text, nullable=True)
    sync_duration = Column(Float, nullable=True)         # seconds
    sync_started_at = Column(DateTime, nullable=True)
    initial_sync_completed = Column(Boolean, default=False)
    last_synced_at = Column(DateTime, nullable=True, index=True)
    last_successful_sync = Column(DateTime, nullable=True)
    last_synced = Column(DateTime, default=utc_now)

    # Record counts per module (for Repository Status Panel)
    total_prs = Column(Integer, default=0)
    total_issues = Column(Integer, default=0)
    total_branches = Column(Integer, default=0)
    total_forks = Column(Integer, default=0)
    total_workflow_runs = Column(Integer, default=0)
    total_discussions = Column(Integer, default=0)
    total_projects = Column(Integer, default=0)

    # Expected and Synced counts for progress tracking
    expected_prs = Column(Integer, default=0)
    expected_issues = Column(Integer, default=0)
    expected_forks = Column(Integer, default=0)
    expected_workflows = Column(Integer, default=0)

    synced_prs = Column(Integer, default=0)
    synced_issues = Column(Integer, default=0)
    synced_forks = Column(Integer, default=0)
    synced_workflows = Column(Integer, default=0)


    # Legacy sync telemetry
    error_message = Column(Text, nullable=True)
    rate_limit_remaining = Column(Integer, nullable=True)
    rate_limit_limit = Column(Integer, nullable=True)
    rate_limit_reset = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    analyses = relationship("TotalAnalysis", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="repository", cascade="all, delete-orphan")
    branches = relationship("Branch", back_populates="repository", cascade="all, delete-orphan")
    forks = relationship("Fork", back_populates="repository", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="repository", cascade="all, delete-orphan")
    discussions = relationship("Discussion", back_populates="repository", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="repository", cascade="all, delete-orphan")
    analytics_snapshots = relationship("AnalyticsSnapshot", back_populates="repository", cascade="all, delete-orphan")
    contributors = relationship("Contributor", back_populates="repository", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# SUPPORT — TOTAL ANALYSIS (aggregate KPIs per repo)
# ---------------------------------------------------------------------------

class TotalAnalysis(Base):
    """Aggregated analysis / KPI values for a repository."""
    __tablename__ = "total_analysis"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    total_prs = Column(Integer, default=0)
    open_prs = Column(Integer, default=0)
    merged_prs = Column(Integer, default=0)
    closed_prs = Column(Integer, default=0)
    avg_cycle_time = Column(Float, nullable=True)
    merge_rate = Column(Float, nullable=True)
    avg_review_duration = Column(Float, nullable=True)
    avg_wait_for_review = Column(Float, nullable=True)
    stale_pr_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    repository = relationship("Repository", back_populates="analyses")


# ---------------------------------------------------------------------------
# MODULE 1 — PULL REQUEST INTELLIGENCE
# ---------------------------------------------------------------------------

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    github_node_id = Column(String(255), nullable=True, unique=False)

    title = Column(String(1024))
    body = Column(Text, nullable=True)
    state = Column(String(50), index=True)               # OPEN / MERGED / CLOSED
    merge_state = Column(String(100), nullable=True)     # MERGEABLE / CONFLICTING / UNKNOWN
    draft = Column(Boolean, default=False)
    labels = Column(Text, nullable=True)                 # JSON array of label names
    base_branch = Column(String(255), nullable=True)
    head_branch = Column(String(255), nullable=True)

    author = Column(String(255), index=True)
    created_at = Column(DateTime, index=True)
    updated_at = Column(DateTime, nullable=True, index=True)
    merged_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    commit_count = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)
    lines_added = Column(Integer, default=0)
    lines_deleted = Column(Integer, default=0)
    review_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    # Computed metrics
    cycle_time_days = Column(Float, nullable=True)
    wait_for_review_hours = Column(Float, nullable=True)
    review_duration_hours = Column(Float, nullable=True)

    repository = relationship("Repository", back_populates="pull_requests")
    reviews = relationship("PRReview", back_populates="pull_request", cascade="all, delete-orphan")
    pr_files = relationship("PRFile", back_populates="pull_request", cascade="all, delete-orphan")
    pr_commits = relationship("PRCommit", back_populates="pull_request", cascade="all, delete-orphan")
    predictions = relationship("MLPrediction", back_populates="pull_request", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_pr_repo_number", "repo_id", "pr_number", unique=True),
    )


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_review_id = Column(BigInteger, nullable=True)
    reviewer = Column(String(255), index=True)
    state = Column(String(50))       # APPROVED / CHANGES_REQUESTED / COMMENTED / DISMISSED
    submitted_at = Column(DateTime, nullable=True, index=True)
    comment_count = Column(Integer, default=0)

    pull_request = relationship("PullRequest", back_populates="reviews")


class PRFile(Base):
    __tablename__ = "pr_files"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(1024))
    status = Column(String(50))      # added / removed / modified / renamed
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    changes = Column(Integer, default=0)

    pull_request = relationship("PullRequest", back_populates="pr_files")


class PRCommit(Base):
    __tablename__ = "pr_commits"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    sha = Column(String(40), index=True)
    message = Column(Text, nullable=True)
    author = Column(String(255), nullable=True)
    committed_at = Column(DateTime, nullable=True, index=True)
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)

    pull_request = relationship("PullRequest", back_populates="pr_commits")


# ---------------------------------------------------------------------------
# MODULE 2 — ISSUE INTELLIGENCE
# ---------------------------------------------------------------------------

class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    issue_number = Column(Integer, nullable=False, index=True)
    github_id = Column(BigInteger, nullable=True)

    title = Column(String(1024))
    body = Column(Text, nullable=True)
    state = Column(String(50), index=True)       # open / closed
    state_reason = Column(String(100), nullable=True)  # completed / not_planned / reopened
    labels = Column(Text, nullable=True)         # JSON array
    assignees = Column(Text, nullable=True)      # JSON array of logins
    author = Column(String(255), index=True)
    is_bug = Column(Boolean, default=False)      # derived from labels

    created_at = Column(DateTime, index=True)
    updated_at = Column(DateTime, nullable=True, index=True)
    closed_at = Column(DateTime, nullable=True)

    comment_count = Column(Integer, default=0)
    # resolution time in hours
    resolution_hours = Column(Float, nullable=True)

    repository = relationship("Repository", back_populates="issues")
    comments = relationship("IssueComment", back_populates="issue", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_issue_repo_number", "repo_id", "issue_number", unique=True),
    )


class IssueComment(Base):
    __tablename__ = "issue_comments"

    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_comment_id = Column(BigInteger, nullable=True)
    author = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True, index=True)

    issue = relationship("Issue", back_populates="comments")


# ---------------------------------------------------------------------------
# MODULE 3 — BRANCH INTELLIGENCE
# ---------------------------------------------------------------------------

class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    protected = Column(Boolean, default=False, index=True)
    last_commit_sha = Column(String(40), nullable=True)
    last_commit_message = Column(Text, nullable=True)
    last_commit_author = Column(String(255), nullable=True)
    last_commit_at = Column(DateTime, nullable=True, index=True)
    # age in days since last commit
    staleness_days = Column(Integer, nullable=True)

    synced_at = Column(DateTime, default=utc_now)
    repository = relationship("Repository", back_populates="branches")

    __table_args__ = (
        Index("ix_branch_repo_name", "repo_id", "name", unique=True),
    )


# ---------------------------------------------------------------------------
# MODULE 5 — FORK ANALYTICS
# ---------------------------------------------------------------------------

class Fork(Base):
    __tablename__ = "forks"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_id = Column(BigInteger, nullable=True, index=True)
    full_name = Column(String(511), nullable=True, index=True)
    owner = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    open_issues = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    language = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True, index=True)
    pushed_at = Column(DateTime, nullable=True, index=True)
    # Derived: days since last push
    staleness_days = Column(Integer, nullable=True)

    synced_at = Column(DateTime, default=utc_now)
    repository = relationship("Repository", back_populates="forks")

    __table_args__ = (
        Index("ix_fork_repo_github_id", "repo_id", "github_id", unique=True),
    )


# ---------------------------------------------------------------------------
# MODULE 6 — DISCUSSION ANALYTICS
# ---------------------------------------------------------------------------

class Discussion(Base):
    __tablename__ = "discussions"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    github_id = Column(String(255), nullable=True)    # GraphQL node ID
    discussion_number = Column(Integer, nullable=True, index=True)
    title = Column(String(1024), nullable=True)
    body = Column(Text, nullable=True)
    category = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True, index=True)
    state = Column(String(50), nullable=True)         # OPEN / CLOSED
    answer_chosen = Column(Boolean, default=False)

    comment_count = Column(Integer, default=0)
    reaction_count = Column(Integer, default=0)
    participant_count = Column(Integer, default=0)

    created_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)

    synced_at = Column(DateTime, default=utc_now)
    repository = relationship("Repository", back_populates="discussions")
    comments = relationship("DiscussionComment", back_populates="discussion", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_discussion_repo_number", "repo_id", "discussion_number", unique=True),
    )


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"

    id = Column(Integer, primary_key=True)
    discussion_id = Column(Integer, ForeignKey("discussions.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_id = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    reaction_count = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=True, index=True)

    discussion = relationship("Discussion", back_populates="comments")

    __table_args__ = (
        Index("ix_discussion_comment_repo_github_id", "repo_id", "github_id", unique=True),
    )


# ---------------------------------------------------------------------------
# MODULE 7 — PROJECT ANALYTICS
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_id = Column(BigInteger, nullable=True, index=True)
    github_node_id = Column(String(255), nullable=True)
    number = Column(Integer, nullable=True)
    name = Column(String(512), nullable=True)
    body = Column(Text, nullable=True)
    state = Column(String(50), nullable=True)   # open / closed
    creator = Column(String(255), nullable=True)
    project_type = Column(String(20), default="v1")  # v1 or v2

    columns_count = Column(Integer, default=0)
    items_count = Column(Integer, default=0)
    open_items = Column(Integer, default=0)
    closed_items = Column(Integer, default=0)
    in_progress_items = Column(Integer, default=0)

    created_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)

    synced_at = Column(DateTime, default=utc_now)
    repository = relationship("Repository", back_populates="projects")
    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_project_repo_github_node_id", "repo_id", "github_node_id", unique=True),
    )


class ProjectItem(Base):
    __tablename__ = "project_items"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_id = Column(String(255), nullable=True)
    content_type = Column(String(50), nullable=True)  # Issue / PullRequest / DraftIssue
    title = Column(String(1024), nullable=True)
    status = Column(String(255), nullable=True)        # column name / status field
    assignees = Column(Text, nullable=True)            # JSON array
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="items")

    __table_args__ = (
        Index("ix_project_item_repo_github_id", "repo_id", "github_id", unique=True),
    )


# ---------------------------------------------------------------------------
# MODULE 8 — ACTIONS / CI-CD INTELLIGENCE
# ---------------------------------------------------------------------------

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    github_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(512), nullable=True)
    path = Column(String(1024), nullable=True)
    state = Column(String(50), nullable=True)          # active / disabled_manually / disabled_inactivity
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    synced_at = Column(DateTime, default=utc_now)
    repository = relationship("Repository", back_populates="workflows")
    runs = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workflow_repo_github_id", "repo_id", "github_id", unique=True),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_run_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(512), nullable=True)
    head_branch = Column(String(255), nullable=True, index=True)
    head_sha = Column(String(40), nullable=True)
    event = Column(String(100), nullable=True)          # push / pull_request / schedule / etc.
    status = Column(String(50), nullable=True, index=True)     # queued / in_progress / completed
    conclusion = Column(String(50), nullable=True, index=True)  # success / failure / cancelled / skipped
    run_number = Column(Integer, nullable=True)
    run_attempt = Column(Integer, default=1)
    actor = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, nullable=True)
    run_started_at = Column(DateTime, nullable=True)
    # Duration in seconds
    duration_seconds = Column(Integer, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    jobs = relationship("WorkflowJob", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_wf_run_repo_github", "repo_id", "github_run_id", unique=True),
    )


class WorkflowJob(Base):
    __tablename__ = "workflow_jobs"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, nullable=False, index=True)
    github_job_id = Column(BigInteger, nullable=True, index=True)
    name = Column(String(512), nullable=True)
    status = Column(String(50), nullable=True)
    conclusion = Column(String(50), nullable=True, index=True)
    runner_name = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    run = relationship("WorkflowRun", back_populates="jobs")


# ---------------------------------------------------------------------------
# SUPPORT — CONTRIBUTOR STATS (retained from original schema)
# ---------------------------------------------------------------------------

class Contributor(Base):
    __tablename__ = "contributors"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    username = Column(String(255), index=True)
    github_user_id = Column(Integer, nullable=True, index=True)
    contributions = Column(Integer, default=0, nullable=False)
    type = Column(String(50), default="User", nullable=False)
    total_prs = Column(Integer, default=0)
    merged_prs = Column(Integer, default=0)
    avg_cycle_time = Column(Float, default=0)
    avg_review_time = Column(Float, default=0)
    stale_pr_count = Column(Integer, default=0)
    repository = relationship("Repository", back_populates="contributors")

    __table_args__ = (
        Index("ix_contributor_repo_user", "repo_id", "username", unique=True),
        Index("ix_contributor_repo_github_user_id", "repo_id", "github_user_id", unique=True),
    )


# ---------------------------------------------------------------------------
# SUPPORT — ML PREDICTIONS
# ---------------------------------------------------------------------------

class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    predicted_delay_days = Column(Float, nullable=True)
    bottleneck_probability = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    predicted_review_wait = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    pull_request = relationship("PullRequest", back_populates="predictions")


# ---------------------------------------------------------------------------
# SUPPORT — ANALYTICS SNAPSHOTS (point-in-time historical records)
# ---------------------------------------------------------------------------

class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(DateTime, default=utc_now, index=True)
    module = Column(String(100), nullable=False, index=True)  # pull_requests / issues / cicd / etc.

    # Snapshot JSON data (stored as text for flexibility)
    data_json = Column(Text, nullable=True)

    # Key scalar metrics for quick queries without JSON parsing
    metric_1_name = Column(String(100), nullable=True)
    metric_1_value = Column(Float, nullable=True)
    metric_2_name = Column(String(100), nullable=True)
    metric_2_value = Column(Float, nullable=True)
    metric_3_name = Column(String(100), nullable=True)
    metric_3_value = Column(Float, nullable=True)

    repository = relationship("Repository", back_populates="analytics_snapshots")

    __table_args__ = (
        Index("ix_snapshot_repo_module_date", "repo_id", "module", "snapshot_date"),
    )


# ---------------------------------------------------------------------------
# SUPPORT — USER AUTHENTICATION
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    repositories = relationship("UserRepository", backref="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", backref="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# SUPPORT — REFRESH TOKEN STORAGE
# ---------------------------------------------------------------------------

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_value = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    revoked = Column(Boolean, default=False, index=True)  # For token revocation support


# ---------------------------------------------------------------------------
# SUPPORT — USER ↔ REPOSITORY ASSOCIATION
# ---------------------------------------------------------------------------

class UserRepository(Base):
    __tablename__ = "user_repositories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="owner")  # owner / viewer
    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_user_repo_unique", "user_id", "repo_id", unique=True),
    )

    # Relationship to repository
    repository = relationship("Repository", backref="user_associations")


# ---------------------------------------------------------------------------
# SUPPORT — SYNC JOB TRACKING
# ---------------------------------------------------------------------------

class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    celery_task_id = Column(String(255), nullable=True, unique=True, index=True)
    status = Column(String(50), default="PENDING")  # PENDING/SYNCING/COMPLETED/FAILED/RATE_LIMITED
    progress_message = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    repository = relationship("Repository", backref="sync_jobs")
