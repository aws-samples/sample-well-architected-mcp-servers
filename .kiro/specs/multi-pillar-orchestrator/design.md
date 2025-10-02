# Design Document

## Overview

The Multi-Pillar Assessment Orchestrator is a central coordination service that extends the existing AWS Well-Architected Cloud Optimization Suite to provide comprehensive, unified assessments across all five Well-Architected pillars. This orchestrator integrates with the existing FastAPI backend, MCP servers, and Bedrock agents to coordinate multi-pillar evaluations, prioritize findings, and generate executive-level reports.

The orchestrator addresses the current gap where individual pillar assessments (currently only Security is fully implemented) operate in isolation without cross-pillar analysis, prioritization, or unified reporting capabilities.

## Architecture

### LLM-Enhanced Assessment Workflow

The orchestrator follows an intelligent analysis workflow that transforms raw MCP server data into actionable insights:

```
1. MCP Data Collection
   ├── Security MCP → Raw security findings
   ├── Cost MCP → Raw cost data  
   ├── Performance MCP → Raw performance metrics
   └── Reliability MCP → Raw reliability data

2. LLM Analysis Engine
   ├── Context Analysis → Understand workload patterns
   ├── Finding Analysis → Interpret raw data with domain expertise
   ├── Recommendation Generation → Create actionable recommendations
   └── Cross-Pillar Synthesis → Identify synergies and conflicts

3. Intelligent Aggregation
   ├── Priority Scoring → AI-powered impact assessment
   ├── Dependency Mapping → Cross-pillar relationship analysis
   └── Trade-off Analysis → Balanced recommendation synthesis

4. Report Generation
   ├── Executive Summary → Business-focused insights
   ├── Technical Report → Implementation-focused details
   └── Action Plan → Prioritized implementation roadmap
```

### High-Level Architecture

The Multi-Pillar Assessment Orchestrator follows the existing 5-layer architecture pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend Layer                               │
│  Enhanced Web Interface with Multi-Pillar Dashboard            │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Backend Services Layer                       │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐   │
│  │   FastAPI Backend   │  │  Multi-Pillar Orchestrator     │   │
│  │   (Existing)        │◄─┤  - Assessment Coordinator      │   │
│  └─────────────────────┘  │  - LLM Analysis Engine         │   │
│                           │  - Result Aggregator           │   │
│                           │  - Intelligent Report Generator│   │
│                           │  - Scheduler Service            │   │
│                           └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Analysis Layer                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Amazon Bedrock                             │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │   │
│  │  │   Claude    │ │    GPT-4    │ │  Custom Models  │   │   │
│  │  │ (Analysis)  │ │(Synthesis)  │ │ (Specialized)   │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Raw MCP Data → LLM Analysis → Intelligent Recommendations     │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    Bedrock Agents Layer                        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ Security Agent  │ │ Reliability     │ │ Cost Optimization│   │
│  │ (Active)        │ │ Agent (Planned) │ │ Agent (Planned)  │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Servers Layer                           │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │ Security MCP    │ │ Reliability MCP │ │ Cost MCP        │   │
│  │ (6 tools)       │ │ (Planned)       │ │ (Planned)       │   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Services Layer                          │
│  Security Hub, GuardDuty, Inspector, Cost Explorer, etc.       │
└─────────────────────────────────────────────────────────────────┘
```

### Integration Points

The orchestrator integrates with existing components through:

1. **FastAPI Backend Integration**: Extends existing endpoints and services
2. **MCP Client Service**: Leverages existing MCP client infrastructure
3. **Bedrock Chat Service**: Coordinates with existing Bedrock integration
4. **Database Layer**: New persistence layer for assessment history and scheduling

## Components and Interfaces

### 1. Assessment Coordinator

**Purpose**: Orchestrates multi-pillar assessments by coordinating calls to various MCP servers and Bedrock agents.

**Key Classes**:
```python
class AssessmentCoordinator:
    async def initiate_multi_pillar_assessment(
        self, 
        pillars: List[str], 
        target_accounts: List[str],
        regions: List[str]
    ) -> AssessmentSession
    
    async def get_assessment_status(self, session_id: str) -> AssessmentStatus
    
    async def cancel_assessment(self, session_id: str) -> bool

class PillarAssessmentStrategy:
    async def assess_security_pillar(self, context: AssessmentContext) -> PillarResult
    async def assess_reliability_pillar(self, context: AssessmentContext) -> PillarResult
    async def assess_performance_pillar(self, context: AssessmentContext) -> PillarResult
    async def assess_cost_pillar(self, context: AssessmentContext) -> PillarResult
    async def assess_operational_pillar(self, context: AssessmentContext) -> PillarResult
```

**Interfaces**:
- REST API endpoints for assessment initiation and status
- WebSocket connections for real-time progress updates
- Integration with existing MCP client service

### 2. LLM Analysis Engine

**Purpose**: Processes raw MCP server results through LLM analysis to generate intelligent, contextual recommendations based on AWS Well-Architected best practices.

**Key Classes**:
```python
class LLMAnalysisEngine:
    async def analyze_pillar_results(self, raw_results: List[MCPResult]) -> AnalyzedResult
    
    async def generate_best_practice_recommendations(self, findings: List[Finding]) -> List[Recommendation]
    
    async def create_contextual_insights(self, workload_context: WorkloadContext, findings: List[Finding]) -> List[Insight]
    
    async def explain_trade_offs(self, conflicting_recommendations: List[Recommendation]) -> TradeOffAnalysis

class RecommendationGenerator:
    async def generate_security_recommendations(self, security_data: SecurityData) -> List[SecurityRecommendation]
    
    async def generate_cost_optimization_recommendations(self, cost_data: CostData) -> List[CostRecommendation]
    
    async def generate_performance_recommendations(self, performance_data: PerformanceData) -> List[PerformanceRecommendation]
    
    async def synthesize_cross_pillar_recommendations(self, all_recommendations: List[Recommendation]) -> List[SynthesizedRecommendation]

class ContextualAnalyzer:
    async def analyze_workload_patterns(self, infrastructure_data: InfrastructureData) -> WorkloadPattern
    
    async def identify_architecture_anti_patterns(self, findings: List[Finding]) -> List[AntiPattern]
    
    async def suggest_architecture_improvements(self, current_state: ArchitectureState) -> List[ArchitectureImprovement]
```

**LLM Integration**:
- Bedrock Claude/GPT integration for intelligent analysis
- Prompt engineering for Well-Architected best practices
- Context-aware recommendation generation
- Multi-turn conversations for complex analysis

### 3. Result Aggregator

**Purpose**: Aggregates LLM-analyzed results and prioritizes findings from multiple pillars, identifying cross-pillar dependencies and conflicts.

**Key Classes**:
```python
class ResultAggregator:
    def aggregate_analyzed_results(self, analyzed_results: List[AnalyzedResult]) -> AggregatedResult
    
    def prioritize_recommendations(self, recommendations: List[Recommendation]) -> List[PrioritizedRecommendation]
    
    def identify_cross_pillar_dependencies(self, results: List[AnalyzedResult]) -> List[Dependency]

class IntelligentPrioritizer:
    def calculate_impact_score(self, recommendation: Recommendation, context: WorkloadContext) -> float
    
    def identify_business_impact(self, recommendation: Recommendation) -> BusinessImpact
    
    def resolve_recommendation_conflicts(self, conflicting_recommendations: List[Recommendation]) -> Resolution
```

**Interfaces**:
- LLM-enhanced data transformation APIs
- AI-powered risk scoring algorithms
- Intelligent conflict resolution engine

### 4. Intelligent Report Generator

**Purpose**: Generates comprehensive, LLM-enhanced reports with contextual explanations and actionable insights tailored for different audiences.

**Key Classes**:
```python
class IntelligentReportGenerator:
    async def generate_executive_summary(self, assessment: AggregatedResult) -> ExecutiveReport
    
    async def generate_technical_report(self, assessment: AggregatedResult) -> TechnicalReport
    
    async def generate_compliance_report(self, assessment: AggregatedResult) -> ComplianceReport
    
    async def generate_action_plan(self, recommendations: List[Recommendation]) -> ActionPlan

class NarrativeGenerator:
    async def create_executive_narrative(self, findings: List[Finding]) -> str
    
    async def explain_technical_recommendations(self, recommendations: List[Recommendation]) -> str
    
    async def generate_implementation_guidance(self, action_items: List[ActionItem]) -> str

class ReportFormatter:
    def format_as_pdf(self, report: Report) -> bytes
    
    def format_as_json(self, report: Report) -> dict
    
    def format_as_html(self, report: Report) -> str
    
    def format_as_interactive_dashboard(self, report: Report) -> DashboardData
```

**LLM-Enhanced Features**:
- Natural language explanations of technical findings
- Context-aware executive summaries
- Personalized implementation roadmaps
- Interactive Q&A capabilities for report clarification

### 5. Scheduler Service

**Purpose**: Manages automated assessment scheduling and triggers based on infrastructure changes or time-based rules.

**Key Classes**:
```python
class SchedulerService:
    async def create_assessment_schedule(self, schedule: AssessmentSchedule) -> str
    
    async def trigger_scheduled_assessment(self, schedule_id: str) -> AssessmentSession
    
    async def handle_infrastructure_change_trigger(self, event: InfrastructureEvent) -> None

class TriggerManager:
    def register_cloudwatch_trigger(self, rule: CloudWatchRule) -> str
    
    def register_config_change_trigger(self, rule: ConfigRule) -> str
    
    def register_time_based_trigger(self, cron_expression: str) -> str
```

**Interfaces**:
- CloudWatch Events integration for infrastructure change detection
- Cron-based scheduling for regular assessments
- Webhook endpoints for external system integration

### 6. Data Persistence Layer

**Purpose**: Stores assessment history, LLM analysis results, configurations, and metadata for trend analysis and compliance reporting.

**Key Classes**:
```python
class AssessmentRepository:
    async def save_assessment(self, assessment: Assessment) -> str
    
    async def save_llm_analysis(self, analysis: LLMAnalysis) -> str
    
    async def get_assessment_history(self, filters: HistoryFilters) -> List[Assessment]
    
    async def get_trend_analysis(self, timeframe: Timeframe) -> TrendAnalysis

class RecommendationRepository:
    async def save_recommendations(self, recommendations: List[Recommendation]) -> None
    
    async def track_recommendation_implementation(self, rec_id: str, status: ImplementationStatus) -> None
    
    async def get_recommendation_effectiveness(self, rec_id: str) -> EffectivenessMetrics

class ConfigurationRepository:
    async def save_schedule_config(self, config: ScheduleConfig) -> str
    
    async def get_user_preferences(self, user_id: str) -> UserPreferences
    
    async def save_notification_settings(self, settings: NotificationSettings) -> None
    
    async def save_llm_prompts(self, prompts: LLMPromptTemplates) -> None
```

**Enhanced Database Schema**:
- Assessment sessions and LLM-analyzed results
- Recommendation tracking and implementation status
- LLM analysis metadata and prompt templates
- User configurations and preferences
- Historical trend data with AI insights
- Compliance mapping and frameworks

## Data Models

### Core Assessment Models

```python
@dataclass
class AssessmentSession:
    session_id: str
    user_id: str
    pillars: List[str]
    target_accounts: List[str]
    regions: List[str]
    status: AssessmentStatus
    created_at: datetime
    completed_at: Optional[datetime]
    progress: Dict[str, float]  # pillar -> completion percentage
    llm_analysis_status: Dict[str, AnalysisStatus]  # pillar -> LLM analysis status

@dataclass
class MCPResult:
    """Raw result from MCP server before LLM analysis"""
    pillar: str
    region: str
    account_id: str
    tool_name: str
    raw_data: Dict[str, Any]
    execution_time: float
    status: ExecutionStatus

@dataclass
class AnalyzedResult:
    """LLM-analyzed result with intelligent insights"""
    pillar: str
    region: str
    account_id: str
    findings: List[Finding]
    recommendations: List[Recommendation]
    insights: List[Insight]
    score: float
    compliance_status: Dict[str, float]
    llm_analysis_metadata: LLMAnalysisMetadata
    raw_mcp_data: MCPResult

@dataclass
class Finding:
    id: str
    pillar: str
    severity: Severity
    title: str
    description: str
    resource_arn: str
    risk_score: float
    business_impact: BusinessImpact
    remediation_steps: List[str]
    compliance_frameworks: List[str]
    llm_explanation: str  # Natural language explanation from LLM
    confidence_score: float  # LLM confidence in the finding

@dataclass
class Recommendation:
    id: str
    title: str
    description: str
    pillar: str
    priority: Priority
    implementation_effort: ImplementationEffort
    expected_impact: ExpectedImpact
    prerequisites: List[str]
    implementation_steps: List[str]
    cost_estimate: Optional[CostEstimate]
    timeline_estimate: str
    llm_rationale: str  # LLM explanation of why this recommendation is important
    related_findings: List[str]  # Finding IDs that led to this recommendation

@dataclass
class Insight:
    id: str
    type: InsightType  # PATTERN, TREND, OPTIMIZATION, RISK
    title: str
    description: str
    affected_pillars: List[str]
    confidence_score: float
    supporting_evidence: List[str]
    actionable_items: List[str]

@dataclass
class AggregatedResult:
    session_id: str
    overall_score: float
    pillar_scores: Dict[str, float]
    prioritized_findings: List[PrioritizedFinding]
    synthesized_recommendations: List[SynthesizedRecommendation]
    cross_pillar_insights: List[CrossPillarInsight]
    executive_summary: str  # LLM-generated executive summary
    technical_summary: str  # LLM-generated technical summary
    action_plan: ActionPlan  # LLM-generated prioritized action plan
    trade_off_analysis: List[TradeOffAnalysis]
```

### LLM Analysis Models

```python
@dataclass
class LLMAnalysisMetadata:
    model_used: str
    analysis_timestamp: datetime
    prompt_version: str
    tokens_used: int
    analysis_duration: float
    confidence_score: float

@dataclass
class WorkloadContext:
    """Context information for LLM analysis"""
    workload_type: str  # web-app, data-pipeline, microservices, etc.
    industry: Optional[str]
    compliance_requirements: List[str]
    business_criticality: BusinessCriticality
    current_architecture_patterns: List[str]
    technology_stack: List[str]

@dataclass
class SynthesizedRecommendation:
    """Cross-pillar recommendation synthesized by LLM"""
    id: str
    title: str
    description: str
    affected_pillars: List[str]
    source_recommendations: List[str]  # Original recommendation IDs
    priority: Priority
    implementation_complexity: ImplementationComplexity
    expected_benefits: Dict[str, str]  # pillar -> benefit description
    implementation_roadmap: List[ImplementationPhase]
    llm_synthesis_rationale: str

@dataclass
class CrossPillarInsight:
    id: str
    title: str
    description: str
    insight_type: CrossPillarInsightType  # SYNERGY, CONFLICT, DEPENDENCY
    involved_pillars: List[str]
    impact_analysis: str
    recommended_approach: str
    confidence_score: float

@dataclass
class TradeOffAnalysis:
    scenario: str
    conflicting_recommendations: List[str]
    trade_offs: Dict[str, TradeOffOption]
    llm_recommendation: str
    decision_factors: List[str]

@dataclass
class ActionPlan:
    phases: List[ActionPhase]
    total_estimated_duration: str
    total_estimated_cost: Optional[CostEstimate]
    success_metrics: List[str]
    risk_mitigation_steps: List[str]
```

### Configuration Models

```python
@dataclass
class AssessmentSchedule:
    schedule_id: str
    name: str
    pillars: List[str]
    target_accounts: List[str]
    regions: List[str]
    cron_expression: str
    notification_settings: NotificationSettings
    enabled: bool

@dataclass
class UserPreferences:
    user_id: str
    default_regions: List[str]
    notification_preferences: Dict[str, bool]
    report_formats: List[str]
    risk_tolerance: RiskTolerance
```

## Error Handling

### Error Categories

1. **MCP Service Errors**: Handle individual pillar service failures gracefully
2. **Authentication Errors**: Cross-account role assumption failures
3. **Rate Limiting**: AWS API throttling and MCP server limits
4. **Data Consistency**: Partial assessment results and retry logic
5. **Timeout Handling**: Long-running assessment timeouts

### Error Handling Strategy

```python
class ErrorHandler:
    async def handle_pillar_failure(self, pillar: str, error: Exception) -> PartialResult
    
    async def handle_timeout(self, session_id: str) -> TimeoutResponse
    
    async def handle_rate_limit(self, service: str, retry_after: int) -> RetryStrategy

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60)
    
    async def call_with_circuit_breaker(self, func: Callable) -> Any
```

### Resilience Patterns

- **Circuit Breaker**: Prevent cascading failures from individual pillar services
- **Retry with Exponential Backoff**: Handle transient AWS API failures
- **Graceful Degradation**: Continue assessment with available pillars if some fail
- **Partial Results**: Return meaningful results even with incomplete data

## Testing Strategy

### Unit Testing

- **Component Isolation**: Mock MCP services and AWS APIs for unit tests
- **Business Logic**: Test assessment coordination, result aggregation, and prioritization logic
- **Error Scenarios**: Comprehensive error handling and edge case testing

### Integration Testing

- **MCP Integration**: Test with actual MCP servers in development environment
- **Cross-Pillar Workflows**: End-to-end multi-pillar assessment scenarios
- **Database Operations**: Test persistence layer with real database

### Performance Testing

- **Concurrent Assessments**: Test multiple simultaneous multi-pillar assessments
- **Large Account Sets**: Test performance with many accounts and regions
- **Memory Usage**: Monitor memory consumption during long-running assessments

### Test Data Strategy

```python
class TestDataFactory:
    def create_mock_security_findings(self, count: int) -> List[Finding]
    
    def create_mock_pillar_results(self, pillars: List[str]) -> List[PillarResult]
    
    def create_assessment_scenarios(self) -> List[AssessmentScenario]
```

## LLM Integration Strategy

### Prompt Engineering Framework

The orchestrator uses a sophisticated prompt engineering approach to ensure consistent, high-quality analysis:

```python
class PromptTemplateManager:
    def get_pillar_analysis_prompt(self, pillar: str, raw_data: Dict) -> str
    
    def get_cross_pillar_synthesis_prompt(self, pillar_results: List[AnalyzedResult]) -> str
    
    def get_executive_summary_prompt(self, aggregated_result: AggregatedResult) -> str
    
    def get_recommendation_generation_prompt(self, findings: List[Finding], context: WorkloadContext) -> str
```

### LLM Analysis Patterns

**Single-Pillar Analysis**:
- Input: Raw MCP server data + workload context
- Process: Domain-specific analysis with Well-Architected principles
- Output: Structured findings with explanations and recommendations

**Cross-Pillar Synthesis**:
- Input: Multiple analyzed pillar results
- Process: Identify synergies, conflicts, and optimization opportunities
- Output: Synthesized recommendations with trade-off analysis

**Executive Communication**:
- Input: Technical findings and recommendations
- Process: Business impact translation and strategic prioritization
- Output: Executive-friendly summaries with ROI estimates

### Quality Assurance

```python
class LLMQualityController:
    def validate_analysis_completeness(self, analysis: AnalyzedResult) -> ValidationResult
    
    def check_recommendation_feasibility(self, recommendation: Recommendation) -> FeasibilityScore
    
    def ensure_consistency_across_pillars(self, results: List[AnalyzedResult]) -> ConsistencyReport
```

## Security Considerations

### Authentication and Authorization

- **JWT Token Validation**: Integrate with existing auth service
- **Cross-Account Permissions**: Validate IAM roles for target accounts
- **API Rate Limiting**: Prevent abuse of assessment endpoints
- **Audit Logging**: Log all assessment activities and access

### Data Protection

- **Encryption at Rest**: Encrypt stored assessment results and configurations
- **Encryption in Transit**: TLS for all API communications
- **Data Retention**: Configurable retention policies for assessment history
- **PII Handling**: Ensure no sensitive data in logs or reports

### Access Control

```python
class AccessController:
    async def validate_account_access(self, user_id: str, account_id: str) -> bool
    
    async def check_pillar_permissions(self, user_id: str, pillar: str) -> bool
    
    async def audit_assessment_access(self, user_id: str, session_id: str) -> None
```

## Performance Optimization

### Caching Strategy

- **Result Caching**: Cache pillar results for configurable time periods
- **Tool Discovery Caching**: Cache MCP tool discovery results
- **Report Caching**: Cache generated reports for repeated access

### Parallel Processing

- **Concurrent Pillar Assessments**: Run pillar assessments in parallel
- **Batch Processing**: Process multiple accounts/regions concurrently
- **Async Operations**: Non-blocking assessment coordination

### Resource Management

```python
class ResourceManager:
    def __init__(self, max_concurrent_assessments: int = 10)
    
    async def acquire_assessment_slot(self) -> AssessmentSlot
    
    async def release_assessment_slot(self, slot: AssessmentSlot) -> None
```

## Monitoring and Observability

### Metrics Collection

- **Assessment Duration**: Track time for each pillar and overall assessment
- **Success/Failure Rates**: Monitor assessment completion rates
- **Resource Utilization**: Track CPU, memory, and network usage
- **User Activity**: Monitor assessment frequency and patterns

### Logging Strategy

```python
class AssessmentLogger:
    def log_assessment_start(self, session: AssessmentSession) -> None
    
    def log_pillar_completion(self, pillar: str, duration: float, status: str) -> None
    
    def log_assessment_completion(self, session_id: str, summary: AssessmentSummary) -> None
```

### Health Checks

- **Service Health**: Monitor orchestrator service health
- **Dependency Health**: Check MCP server and Bedrock agent availability
- **Database Health**: Monitor persistence layer connectivity and performance

## Deployment Considerations

### Infrastructure Requirements

- **Compute Resources**: Sufficient CPU and memory for concurrent assessments
- **Database**: PostgreSQL or DynamoDB for assessment data persistence
- **Message Queue**: Redis or SQS for async task processing
- **Load Balancing**: Support for horizontal scaling

### Configuration Management

```python
class OrchestratorConfig:
    max_concurrent_assessments: int = 10
    assessment_timeout_minutes: int = 30
    cache_ttl_minutes: int = 60
    retry_attempts: int = 3
    supported_pillars: List[str] = ["security", "reliability", "performance", "cost", "operational"]
```

### Scaling Strategy

- **Horizontal Scaling**: Multiple orchestrator instances behind load balancer
- **Database Scaling**: Read replicas for historical data queries
- **Cache Scaling**: Distributed caching for large deployments