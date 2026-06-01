export interface TooltipContent {
  title: string
  message: string
  calculation?: string
}

export const METRIC_TOOLTIPS = {
  // ═══════════════════════════════════════════════════════════════════════════
  // OVERVIEW DASHBOARD - HEALTH METRICS
  // ═══════════════════════════════════════════════════════════════════════════

  mergeHealth: {
    title: 'Merge Health',
    message: 'Measures how efficiently pull requests are merged. Higher values indicate smoother delivery.',
    calculation: 'Based on: Merge rate, Cycle time, Delivery consistency',
  } as TooltipContent,

  reviewHealth: {
    title: 'Review Health',
    message: 'Evaluates review responsiveness and collaboration quality.',
    calculation: 'Based on: Review wait time, Review duration, Reviewer participation',
  } as TooltipContent,

  staleRisk: {
    title: 'Stale Risk',
    message: 'Indicates the risk caused by inactive pull requests and unresolved work.',
    calculation: 'Calculated from: Stale PR count, Age of inactive items, Backlog accumulation',
  } as TooltipContent,

  cicdHealth: {
    title: 'CI/CD Health',
    message: 'Measures workflow reliability using build success and failure data.',
    calculation: 'Based on: Workflow success rate, Build frequency, Pipeline stability',
  } as TooltipContent,

  performanceTrend: {
    title: 'Performance Trend',
    message: 'Shows engineering velocity trends over time.',
    calculation: 'Tracks: Cycle time, Merge rate, Throughput movement across time periods',
  } as TooltipContent,

  reviewEfficiency: {
    title: 'Review Efficiency',
    message: 'Measures how quickly pull requests receive feedback.',
    calculation: 'Calculated as: Average time from PR creation to first review',
  } as TooltipContent,

  qualitySignals: {
    title: 'Quality Signals',
    message: 'Indicators derived from merge success, review quality, and workflow stability.',
    calculation: 'Combined metric: Merge rate, Approval rate, Test pass rate',
  } as TooltipContent,

  backlogHealth: {
    title: 'Backlog Health',
    message: 'Evaluates stale items and pending work requiring attention.',
    calculation: 'Based on: Stale PR count, Open issue count, Branch staleness',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // PULL REQUESTS MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalPRs: {
    title: 'Total PRs',
    message: 'Total pull requests analyzed for this repository.',
    calculation: 'Open PRs + Merged PRs + Closed PRs',
  } as TooltipContent,

  mergeRate: {
    title: 'Merge Rate',
    message: 'Calculated as Merged PRs divided by Closed PRs.',
    calculation: 'Merged PRs ÷ Closed PRs × 100',
  } as TooltipContent,

  avgCycleTime: {
    title: 'Avg Cycle Time',
    message: 'Average time between pull request creation and merge.',
    calculation: 'Sum of (Merged At − Created At) ÷ Merged PR count',
  } as TooltipContent,

  avgReviewWait: {
    title: 'Avg Review Wait',
    message: 'Average time from pull request creation to first review.',
    calculation: 'Sum of (First Review Time − Created Time) ÷ Reviewed PR count',
  } as TooltipContent,

  avgReviewDuration: {
    title: 'Avg Review Duration',
    message: 'Average active review time before approval or closure.',
    calculation: 'Sum of (Last Review Time − First Review Time) ÷ Reviewed PR count',
  } as TooltipContent,

  stalePRs: {
    title: 'Stale PRs',
    message: 'Open pull requests with no activity for more than 30 days.',
    calculation: 'Count of open PRs with no reviews, comments, or commits in 30+ days',
  } as TooltipContent,

  prFlowChart: {
    title: 'PR Flow',
    message: 'Trend of created, merged, and closed pull requests over time.',
    calculation: 'Created: New PRs | Merged: Completed PRs | Closed: Rejected/cancelled PRs',
  } as TooltipContent,

  topContributors: {
    title: 'Top Contributors',
    message: 'Contributors ranked by pull request participation and merges.',
    calculation: 'Rank by: Created PRs + Merged PRs + Review participation count',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // ISSUES MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalIssues: {
    title: 'Total Issues',
    message: 'Total issues detected during repository analysis.',
    calculation: 'Open Issues + Closed Issues',
  } as TooltipContent,

  openIssues: {
    title: 'Open Issues',
    message: 'Issues that are currently unresolved.',
    calculation: 'Count of issues in open state',
  } as TooltipContent,

  closedIssues: {
    title: 'Closed Issues',
    message: 'Issues successfully resolved and closed.',
    calculation: 'Count of issues in closed state',
  } as TooltipContent,

  staleIssues: {
    title: 'Stale Issues',
    message: 'Issues inactive for more than 30 days.',
    calculation: 'Count of issues with no activity (comments, updates) in 30+ days',
  } as TooltipContent,

  bugReports: {
    title: 'Bug Reports',
    message: 'Issues classified as defects or bugs.',
    calculation: 'Count of issues with bug/defect classification or label',
  } as TooltipContent,

  avgResolutionTime: {
    title: 'Avg Resolution Time',
    message: 'Average time required to resolve an issue.',
    calculation: 'Sum of (Closed At − Created At) ÷ Closed issue count',
  } as TooltipContent,

  issueTrend: {
    title: 'Issue Trend',
    message: 'Comparison of issue creation versus issue closure over time.',
    calculation: 'Opened: New issues created | Closed: Issues resolved each period',
  } as TooltipContent,

  issuesByPriority: {
    title: 'Issues by Priority',
    message: 'Distribution of issues across priority categories.',
    calculation: 'Breakdown of Critical, High, Medium, and Low priority issues',
  } as TooltipContent,

  issueHeatmap: {
    title: 'Issue Heatmap',
    message: 'Visualizes issue activity by date and weekday.',
    calculation: 'Aggregated issue creation count across days and time periods',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // BRANCHES MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalBranches: {
    title: 'Total Branches',
    message: 'Total repository branches discovered.',
    calculation: 'Count of all branches (main + feature + release + hotfix + etc.)',
  } as TooltipContent,

  activeBranches: {
    title: 'Active Branches',
    message: 'Branches updated within the last 30 days.',
    calculation: 'Count of branches with staleness_days <= 30',
  } as TooltipContent,

  protectedBranches: {
    title: 'Protected Branches',
    message: 'Branches protected by repository rules and merge restrictions.',
    calculation: 'Count of branches with branch protection enabled',
  } as TooltipContent,

  inactiveBranches: {
    title: 'Inactive Branches',
    message: 'Branches without commits for more than 30 days but less than 90 days.',
    calculation: 'Count of branches with staleness_days > 30 and < 90',
  } as TooltipContent,

  staleBranches: {
    title: 'Stale Branches',
    message: 'Branches without commits for 90 days or longer and may require cleanup.',
    calculation: 'Count of branches with staleness_days >= 90',
  } as TooltipContent,

  branchActivityBreakdown: {
    title: 'Branch Activity Breakdown',
    message: 'Distribution of active, inactive, and stale branches by last commit date.',
    calculation: 'Active (<= 30d) + Inactive (31–89d) + Stale (>=90d) = Total Branches',
  } as TooltipContent,

  branchHealth: {
    title: 'Branch Health',
    message: 'Evaluates branch maintenance and activity quality.',
    calculation: 'Based on: Active branch ratio, Stale rate, Protection coverage',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // CI/CD MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalRuns: {
    title: 'Total Runs',
    message: 'Total workflow executions detected.',
    calculation: 'Count of all workflow runs (successful, failed, cancelled)',
  } as TooltipContent,

  successfulRuns: {
    title: 'Successful Runs',
    message: 'Workflow runs completed successfully.',
    calculation: 'Count of runs with success status',
  } as TooltipContent,

  failedRuns: {
    title: 'Failed Runs',
    message: 'Workflow runs that ended in failure.',
    calculation: 'Count of runs with failure status',
  } as TooltipContent,

  successRate: {
    title: 'Success Rate',
    message: 'Calculated as Successful Runs divided by Total Runs.',
    calculation: 'Successful Runs ÷ Total Runs × 100',
  } as TooltipContent,

  avgDuration: {
    title: 'Avg Duration',
    message: 'Average workflow execution time.',
    calculation: 'Sum of all run durations ÷ Total Runs',
  } as TooltipContent,

  flakyWorkflows: {
    title: 'Flaky Workflows',
    message: 'Workflows with unstable or inconsistent execution outcomes.',
    calculation: 'Workflows with variable success rates or timeout issues',
  } as TooltipContent,

  cancelledRuns: {
    title: 'Cancelled Runs',
    message: 'Workflow runs stopped before completion.',
    calculation: 'Count of runs with cancelled status',
  } as TooltipContent,

  recentRuns: {
    title: 'Recent Runs',
    message: 'Latest workflow executions captured during analysis.',
    calculation: 'Most recent workflow run records with status and timing',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // FORKS MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalForks: {
    title: 'Total Forks',
    message: 'Total repository forks created by users.',
    calculation: 'Count of all forks from this repository',
  } as TooltipContent,

  activeForks: {
    title: 'Active Forks',
    message: 'Forks updated within the last 30 days.',
    calculation: 'Count of forks with recent activity',
  } as TooltipContent,

  staleForks: {
    title: 'Stale Forks',
    message: 'Forks inactive for more than 90 days.',
    calculation: 'Count of forks with no activity in 90+ days',
  } as TooltipContent,

  starredForks: {
    title: 'Starred Forks',
    message: 'Forks that have received GitHub stars.',
    calculation: 'Count of forks with star count > 0',
  } as TooltipContent,

  avgForkStars: {
    title: 'Avg Fork Stars',
    message: 'Average stars received per fork.',
    calculation: 'Total stars on forks ÷ Total forks',
  } as TooltipContent,

  adoptionRate: {
    title: 'Adoption Rate',
    message: 'Percentage of active forks relative to total forks.',
    calculation: 'Active Forks ÷ Total Forks × 100',
  } as TooltipContent,

  forkGrowthTrend: {
    title: 'Fork Growth Trend',
    message: 'Shows fork growth over time.',
    calculation: 'Cumulative fork count tracked across time periods',
  } as TooltipContent,

  forkEcosystem: {
    title: 'Fork Ecosystem',
    message: 'Overview of fork activity, popularity, and engagement.',
    calculation: 'Combined metric: Fork count, Activity, Stars, Adoption',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // PROJECTS MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalProjects: {
    title: 'Total Projects',
    message: 'Total GitHub project boards discovered.',
    calculation: 'Count of all project boards',
  } as TooltipContent,

  openBoards: {
    title: 'Open Boards',
    message: 'Active project boards currently in use.',
    calculation: 'Count of project boards in open state',
  } as TooltipContent,

  closedBoards: {
    title: 'Closed Boards',
    message: 'Archived or completed project boards.',
    calculation: 'Count of project boards in closed/archived state',
  } as TooltipContent,

  activeProjects: {
    title: 'Active Projects',
    message: 'Projects currently tracking repository work.',
    calculation: 'Count of projects with recent activity',
  } as TooltipContent,

  projectProgress: {
    title: 'Project Progress',
    message: 'Completion status across tracked work items.',
    calculation: 'Completed items ÷ Total tracked items × 100',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // DISCUSSIONS MODULE
  // ═══════════════════════════════════════════════════════════════════════════

  totalDiscussions: {
    title: 'Total Discussions',
    message: 'Total community discussion threads.',
    calculation: 'Count of all discussion threads',
  } as TooltipContent,

  openDiscussions: {
    title: 'Open Discussions',
    message: 'Discussions currently awaiting responses.',
    calculation: 'Count of discussions in open/unanswered state',
  } as TooltipContent,

  answeredDiscussions: {
    title: 'Answered Discussions',
    message: 'Discussions marked as resolved.',
    calculation: 'Count of discussions with accepted answers',
  } as TooltipContent,

  answerRate: {
    title: 'Answer Rate',
    message: 'Calculated as Answered Discussions divided by Total Discussions.',
    calculation: 'Answered Discussions ÷ Total Discussions × 100',
  } as TooltipContent,

  avgComments: {
    title: 'Avg Comments',
    message: 'Average number of comments per discussion.',
    calculation: 'Total comments ÷ Total discussions',
  } as TooltipContent,

  avgReactions: {
    title: 'Avg Reactions',
    message: 'Average community reactions per discussion.',
    calculation: 'Total reactions (emoji, likes) ÷ Total discussions',
  } as TooltipContent,

  discussionActivity: {
    title: 'Discussion Activity',
    message: 'Trend of discussion participation over time.',
    calculation: 'Discussion count and comment volume tracked per period',
  } as TooltipContent,

  topTopics: {
    title: 'Top Topics',
    message: 'Most active discussion categories.',
    calculation: 'Ranked by: Discussion count, Comment volume, Engagement',
  } as TooltipContent,

  discussionsWorkspace: {
    title: 'Discussions Workspace',
    message: 'Repository discussion threads and engagement activity.',
    calculation: 'Aggregated discussion metrics and community health',
  } as TooltipContent,

  // ═══════════════════════════════════════════════════════════════════════════
  // REPOSITORY HEALTH - SCORES & RECOMMENDATIONS
  // ═══════════════════════════════════════════════════════════════════════════

  repoHealthScore: {
    title: 'Repository Health Score',
    message: 'Overall engineering health score derived from repository metrics.',
    calculation: 'Weighted composite: Code Flow, Review Health, Workflow Stability, Stale Risk, Contributor Balance',
  } as TooltipContent,

  pullRequestsScore: {
    title: 'Pull Requests Score',
    message: 'Contribution of pull request activity to overall health.',
    calculation: 'Based on: Merge rate, Cycle time, Review participation',
  } as TooltipContent,

  cicdScore: {
    title: 'CI/CD Score',
    message: 'Contribution of workflow reliability to overall health.',
    calculation: 'Based on: Build success rate, Pipeline stability, Test coverage',
  } as TooltipContent,

  branchesScore: {
    title: 'Branches Score',
    message: 'Contribution of branch maintenance to overall health.',
    calculation: 'Based on: Active branch ratio, Stale rate, Protection coverage',
  } as TooltipContent,

  issuesScore: {
    title: 'Issues Score',
    message: 'Contribution of issue management quality to overall health.',
    calculation: 'Based on: Resolution time, Stale issue count, Bug resolution rate',
  } as TooltipContent,

  communityScore: {
    title: 'Community Score',
    message: 'Contribution of collaboration and discussions.',
    calculation: 'Based on: Discussion participation, Answer rate, Contributor diversity',
  } as TooltipContent,

  visibilityScore: {
    title: 'Visibility Score',
    message: 'Contribution of repository accessibility and governance.',
    calculation: 'Based on: Fork adoption, Stars, Documentation, Accessibility',
  } as TooltipContent,

  executiveRecommendations: {
    title: 'Executive Recommendations',
    message: 'Suggested actions that can improve repository health.',
    calculation: 'AI-generated recommendations based on metric analysis and thresholds',
  } as TooltipContent,

  repositoryDetails: {
    title: 'Repository Details',
    message: 'Current repository metadata and operational status.',
    calculation: 'Aggregated repository configuration, permissions, and status',
  } as TooltipContent,

  // ─── Legacy/Alias names for compatibility ─────────────────────────────────

  codeFlow: {
    title: 'Code Flow',
    message: 'Measures pull request throughput and delivery efficiency.',
    calculation: 'Factors: Merge rate, Cycle time, Pull request completion trends',
  } as TooltipContent,

  workflowStability: {
    title: 'Workflow Stability',
    message: 'Measures CI/CD reliability.',
    calculation: 'Factors: Workflow success rate, Failure frequency, Flaky workflow detection',
  } as TooltipContent,

  contributorBalance: {
    title: 'Contributor Balance',
    message: 'Measures how evenly repository contributions are distributed across contributors.',
    calculation: 'Healthy repositories avoid excessive dependency on a single contributor.',
  } as TooltipContent,
}

/**
 * Helper to get tooltip content by key with fallback
 */
export function getTooltip(key: keyof typeof METRIC_TOOLTIPS): TooltipContent {
  return METRIC_TOOLTIPS[key] || {
    title: 'Metric Information',
    message: 'Hover for details about this metric.',
  }
}

/**
 * Re-export for convenience
 */
export default METRIC_TOOLTIPS
