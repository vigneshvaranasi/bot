import json
import random
from datetime import datetime, timedelta
import os
import requests
import time
import requests
import time
from requests.auth import HTTPBasicAuth
import argparse

# ServiceNow Configuration (Environment-based with defaults)
DEFAULT_SN_INSTANCE = "dev266166"
DEFAULT_SN_USER = "admin"
DEFAULT_SN_PASS = "WRvm74Z*r=Ut"
DEFAULT_SN_INTERVAL_SECONDS = 360  # 6 minutes = ~10 incidents per hour
DEFAULT_SN_BATCH_SIZE = 1

# Parse CLI arguments
parser = argparse.ArgumentParser(description="Auto-ingest incidents to ServiceNow")
parser.add_argument("--instance", help="ServiceNow instance")
parser.add_argument("--user", help="ServiceNow username")
parser.add_argument("--password", help="ServiceNow password")
parser.add_argument("--interval", type=int, help="Interval in seconds between incident batches")
parser.add_argument("--batch-size", type=int, help="Number of incidents per batch")
args, unknown = parser.parse_known_args()

# Configuration priority: CLI args > Environment variables > Defaults
SN_INSTANCE = args.instance or os.getenv("SN_INSTANCE", DEFAULT_SN_INSTANCE)
SN_USER = args.user or os.getenv("SN_USER", DEFAULT_SN_USER)
SN_PASS = args.password or os.getenv("SN_PASS", DEFAULT_SN_PASS)
SN_INTERVAL_SECONDS = args.interval or int(os.getenv("SN_INTERVAL_SECONDS", DEFAULT_SN_INTERVAL_SECONDS))
SN_BATCH_SIZE = args.batch_size or int(os.getenv("SN_BATCH_SIZE", DEFAULT_SN_BATCH_SIZE))

# Debug: Print what was received
print(f"DEBUG: Instance={SN_INSTANCE}, User={SN_USER}, Pass={'*' * (len(SN_PASS)-4) + SN_PASS[-4:] if len(SN_PASS) > 4 else '***'}")
print(f"DEBUG: Interval={SN_INTERVAL_SECONDS}s, Batch Size={SN_BATCH_SIZE}")
print()

SN_BASE_URL = f"https://{SN_INSTANCE}.service-now.com"
SN_API_ENDPOINT = f"{SN_BASE_URL}/api/now/table/incident"

# Expanded incident templates — more variety per category
INCIDENT_TEMPLATES = [
    {
        "category": "Database Performance",
        "titles": [
            "PostgreSQL Connection Pool Exhaustion",
            "Oracle Deadlock in Transaction Table",
            "MongoDB Replica Set Lag",
            "Redis Cache Eviction Storm",
            "MySQL Slow Query Cascade",
            "PostgreSQL Bloat and Vacuum Delay",
            "Database Flush I/O Saturation",
            "Unexpected Table Lock Contention",
        ],
        "impacted_apps": [
            "Core Banking Database",
            "Transaction Processing Engine",
            "Customer Account Database",
            "Payment Authorization System",
            "Ledger Management System",
            "Customer Profile Service",
            "Analytics Reporting Database",
            "Audit Log Storage"
        ],
        "root_causes": [
            "Poorly optimized query with missing index causing full table scans on 50M+ record table",
            "Connection pool max size reached due to unclosed database connections in legacy API endpoints",
            "Database deadlock caused by concurrent transactions updating same account records without proper locking strategy",
            "Inefficient batch job holding long-running transactions and blocking other queries",
            "Memory pressure causing excessive page swapping and query timeouts",
            "Autovacuum disabled leading to table bloat and degraded performance",
            "Disk I/O saturation due to large write spikes from bulk inserts",
            "Row‐level locking conflict caused by long-running report generation query"
        ],
        "mitigations": [
            "Added composite indexes on frequently queried columns and optimized query execution plan",
            "Implemented connection pooling with aggressive timeout settings and connection health checks",
            "Introduced optimistic locking with retry logic to prevent deadlocks",
            "Refactored batch processing to use smaller transaction boundaries with commit intervals",
            "Increased database server memory allocation and tuned buffer pool settings",
            "Re-enabled autovacuum and scheduled regular maintenance windows",
            "Throttled bulk inserts and spread them over off-peak hours; upgraded disk I/O throughput",
            "Adjusted transaction isolation levels and split long report queries into smaller chunks"
        ],
        "accountable_parties": [
            "Database Administration Team",
            "Application Development Team",
            "Infrastructure Team",
            "Data Engineering Team"
        ],
        "source_systems": [
            "Database System",
            "Payment System",
            "Reporting System"
        ]
    },
    {
        "category": "Network Issues",
        "titles": [
            "Load Balancer Health Check Failure",
            "VPN Tunnel Instability",
            "DNS Resolution Timeout",
            "BGP Route Flapping",
            "Firewall Rule Misconfiguration",
            "Inter-Region Latency Spike",
            "Network Interface Duplex Mismatch",
            "SSL Handshake Timeout due to MTU Misconfiguration"
        ],
        "impacted_apps": [
            "Payment Gateway Load Balancer",
            "Cross-Border Payment Network",
            "Internal Service Mesh",
            "External Partner Integration",
            "Multi-Region Traffic Manager",
            "API Gateway Instances",
            "Service-to-Service Communication Layer",
            "User Login Portal"
        ],
        "root_causes": [
            "Misconfigured health check endpoint returning false negatives causing premature node removal",
            "Network congestion on primary ISP link causing packet loss exceeding 15% threshold",
            "DNS server cache corruption returning stale IP addresses for critical services",
            "Asymmetric routing introduced by BGP configuration change causing TCP session failures",
            "Firewall rule accidentally blocking legitimate traffic from payment processor IPs",
            "Inter-region MPLS link experienced intermittent micro-bursts causing latency spikes",
            "Duplex mismatch on network interface causing packet collisions and retransmissions",
            "Incorrect MTU setting causing fragmentation and SSL handshake timeouts"
        ],
        "mitigations": [
            "Corrected health check configuration and increased failure threshold to reduce false positives",
            "Implemented automatic failover to secondary ISP link with traffic shaping policies",
            "Flushed DNS cache and implemented multi-tier DNS resolution with redundancy",
            "Rolled back BGP changes and implemented symmetric routing policies",
            "Updated firewall rules with proper IP whitelisting and real-time rule validation",
            "Upgraded MPLS link capacity and enabled traffic smoothing to prevent bursts",
            "Fixed duplex/auto-negotiation settings on network interfaces across affected switches",
            "Adjusted MTU configuration and enabled Path MTU Discovery for optimal packet size"
        ],
        "accountable_parties": [
            "Network Operations Center",
            "Infrastructure Team",
            "DevOps Team",
            "Security Operations Team"
        ],
        "source_systems": [
            "Payment System",
            "API Gateway",
            "Network Infrastructure"
        ]
    },
    {
        "category": "Application Errors",
        "titles": [
            "Null Pointer Exception in Payment Processor",
            "Memory Leak in Transaction Service",
            "Infinite Loop in Reconciliation Job",
            "Race Condition in Balance Update",
            "Unhandled Exception in Fraud Detection",
            "Timeout Error in Notification Service",
            "API Version Mismatch Causing JSON Parse Failures",
            "Uncaught Promise Rejection in NodeJS Gateway"
        ],
        "impacted_apps": [
            "Payment Processing Service",
            "Transaction Authorization Engine",
            "Account Balance Service",
            "Fraud Detection System",
            "Settlement Reconciliation Module",
            "Notification Delivery Service",
            "Public API Gateway",
            "Mobile Banking Backend"
        ],
        "root_causes": [
            "Code deployed without null check when processing optional payment metadata fields",
            "Memory leak in HTTP client library failing to release connections after API calls",
            "Infinite retry loop triggered when external service returns ambiguous error code",
            "Race condition in concurrent balance updates lacking proper transaction isolation",
            "Unhandled exception when parsing malformed transaction data from legacy system",
            "Timeout not handled properly causing request context to be lost before response",
            "API version mismatch causing JSON schema validation failures on client payload",
            "Uncaught promise rejection due to missing error handler in asynchronous call"
        ],
        "mitigations": [
            "Deployed hotfix with defensive null checks and optional field validation",
            "Updated HTTP client library to latest version with proper connection management",
            "Implemented circuit breaker pattern with exponential backoff and max retry limit",
            "Applied database-level serializable isolation and optimistic locking with version control",
            "Added comprehensive input validation and exception handling with graceful degradation",
            "Extended default request timeout thresholds and added fallback logic for slow operations",
            "Enforced strict API version compatibility and introduced schema validation on both client and server side",
            "Added global error handlers for asynchronous code and improved logging for better traceability"
        ],
        "accountable_parties": [
            "Application Development Team",
            "DevOps Team",
            "Operations Team",
            "QA & Test Automation Team"
        ],
        "source_systems": [
            "Payment System",
            "Domestic Payment System",
            "Public API Gateway"
        ]
    },
    {
        "category": "Integration Failures",
        "titles": [
            "SWIFT Message Format Rejection",
            "FedWire Connection Timeout",
            "Third-Party API Rate Limit Exceeded",
            "Card Network Downtime",
            "Partner Bank System Unavailable",
            "External Billing API 500 Error",
            "SFTP Transfer Failure to Partner",
            "Webhook Delivery Timeout to Merchant"
        ],
        "impacted_apps": [
            "SWIFT Payment Gateway",
            "FedWire Integration Module",
            "Card Processing Interface",
            "Partner Bank Connector",
            "Payment Network Orchestrator",
            "Subscription Billing Module",
            "File Transfer Service",
            "Merchant Notification Service"
        ],
        "root_causes": [
            "SWIFT message validation failed due to incorrect field mapping after ISO 20022 migration",
            "FedWire connection timeout caused by expired SSL certificate on integration endpoint",
            "API rate limit exceeded when batch job sent requests without proper throttling",
            "Card network experiencing widespread outage affecting authorization requests",
            "Partner bank maintenance window extended beyond scheduled time causing service unavailability",
            "External billing API returned HTTP 500 due to internal error at vendor end",
            "SFTP transfer failed due to partner server rejecting keys after key rotation",
            "Webhook delivery timed out because merchant endpoint responded slowly under load"
        ],
        "mitigations": [
            "Updated SWIFT message mapper with correct ISO 20022 field mappings and validation rules",
            "Renewed SSL certificates and implemented automated certificate rotation monitoring",
            "Implemented token bucket algorithm for rate limiting with adaptive throttling",
            "Routed traffic to backup card processor and queued transactions for retry",
            "Established redundant connection to alternative partner bank clearing path",
            "Introduced retry logic with exponential backoff and request hygiene for external billing API",
            "Rotated SFTP keys properly and synchronized key changes with partner; added fallback SFTP server",
            "Added retry queue for webhooks and increased timeout threshold; notified merchant of delays"
        ],
        "accountable_parties": [
            "Network Operations Center",
            "Application Development Team",
            "Operations Team",
            "Partner Integration Team"
        ],
        "source_systems": [
            "SWIFT MT103/MT202",
            "Payment System",
            "API Gateway",
            "Partner Bank Interface"
        ]
    },
    {
        "category": "Security Incidents",
        "titles": [
            "Suspicious Authentication Pattern Detected",
            "SSL Certificate Expiration",
            "API Key Compromise Alert",
            "Brute Force Attack on Login Portal",
            "Unauthorized Access Attempt",
            "Privilege Escalation via Misconfigured IAM Role",
            "Data Leakage via Debug Logs",
            "Cross-Site Scripting (XSS) Vulnerability Exploited"
        ],
        "impacted_apps": [
            "Authentication Service",
            "Payment Portal",
            "Admin Console",
            "API Gateway",
            "Customer Portal",
            "Identity Management Service",
            "Logging Service",
            "Web Frontend"
        ],
        "root_causes": [
            "Automated credential stuffing attack from botnet targeting customer login endpoints",
            "SSL certificate expired due to missed renewal notification causing HTTPS failures",
            "API key accidentally committed to public GitHub repository triggering security alerts",
            "Insufficient rate limiting on login endpoint allowing brute force attempts",
            "Insider threat detection system flagged abnormal data access patterns from privileged account",
            "Misconfigured IAM role granted overly broad permissions allowing privilege escalation",
            "Debug logs containing sensitive data accessible publicly due to misconfigured log retention policy",
            "Cross-site scripting vulnerability in frontend not sanitized user input leading to session hijack"
        ],
        "mitigations": [
            "Implemented CAPTCHA challenge and IP-based rate limiting with account lockout policy",
            "Deployed new SSL certificate with automated renewal process and 30-day advance alerts",
            "Rotated compromised API keys immediately and implemented secret scanning in CI/CD pipeline",
            "Enhanced WAF rules with adaptive rate limiting and geographic IP blocking",
            "Suspended suspicious account and initiated forensic investigation with audit log analysis",
            "Revised IAM policies with least-privilege principle and regularly audited role permissions",
            "Sanitized debug logging to avoid sensitive data exposure and updated log retention policies",
            "Applied strict input sanitization and content security policy (CSP) headers to prevent XSS"
        ],
        "accountable_parties": [
            "Security Operations Team",
            "DevOps Team",
            "Infrastructure Team",
            "Compliance Team"
        ],
        "source_systems": [
            "Payment System",
            "Domestic Payment System",
            "Identity Management System",
            "Web Application Firewall"
        ]
    },
    {
        "category": "Infrastructure",
        "titles": [
            "Kubernetes Pod CrashLoopBackOff",
            "Auto-Scaling Policy Malfunction",
            "Disk Space Exhaustion",
            "Container Registry Unavailable",
            "Service Mesh Configuration Error",
            "NTP Drift Causing Certificate Validation Failures",
            "Load Balancer Backend Overloaded",
            "Configuration Drift in Production Cluster"
        ],
        "impacted_apps": [
            "Payment Microservices Cluster",
            "Transaction Processing Pods",
            "API Gateway Instances",
            "Background Job Workers",
            "Message Queue Cluster",
            "Monitoring & Metrics Service",
            "Authentication Service",
            "Cache Cluster"
        ],
        "root_causes": [
            "Container startup probe failing due to increased initialization time after dependency upgrade",
            "Auto-scaling policy misconfigured with incorrect CPU threshold causing premature scale-down",
            "Application logs filling disk partition due to overly verbose debug logging in production",
            "Container registry experiencing authentication failures blocking image pulls for deployments",
            "Service mesh sidecar proxy misconfiguration causing intermittent 503 errors",
            "System time drift causing TLS certificate validation failures across services",
            "Load balancer backend overwhelmed by traffic surge due to bot attack",
            "Undocumented manual configuration change leading to inconsistent production environment"
        ],
        "mitigations": [
            "Increased startup probe timeout and added readiness probe with proper health check endpoint",
            "Adjusted auto-scaling policy with appropriate CPU/memory thresholds and cooldown periods",
            "Implemented log rotation with compression and configured centralized logging to external system",
            "Switched to backup container registry and fixed authentication token expiration issue",
            "Corrected service mesh routing rules and deployed updated proxy configuration",
            "Enabled NTP sync across servers and added automated drift detection monitoring",
            "Implemented rate limiting and WAF rules to mitigate bot traffic; scaled backends to handle load",
            "Enforced configuration-as-code and drift detection; rolled back to known-good baseline"
        ],
        "accountable_parties": [
            "DevOps Team",
            "Infrastructure Team",
            "Operations Team",
            "Security Operations Team"
        ],
        "source_systems": [
            "Payment System",
            "API Gateway",
            "Container Orchestration System",
            "Monitoring System"
        ]
    },
    {
        "category": "Message Queue",
        "titles": [
            "Kafka Consumer Lag Spike",
            "RabbitMQ Queue Overflow",
            "Message Processing Deadletter Queue Buildup",
            "Event Stream Partition Rebalancing",
            "Message Serialization Failure",
            "Kafka Broker Outage",
            "Stuck Message Acknowledgement in RabbitMQ",
            "Backpressure Not Handled in Streaming Pipeline"
        ],
        "impacted_apps": [
            "Payment Event Stream",
            "Transaction Message Queue",
            "Notification Service Queue",
            "Audit Log Pipeline",
            "Settlement Message Bus",
            "Real-time Reporting Service",
            "Webhook Dispatcher",
            "Cache Invalidation Service"
        ],
        "root_causes": [
            "Kafka consumer lag increased due to slow message processing from downstream database bottleneck",
            "RabbitMQ queue overflow caused by message producer rate exceeding consumer capacity",
            "Messages accumulating in dead-letter queue due to invalid schema after breaking API change",
            "Kafka partition rebalancing storm triggered by consumer group instability",
            "Message deserialization failures due to incompatible Avro schema version",
            "Kafka broker outage due to hardware failure causing complete interruption in message flow",
            "Stuck message acknowledgements preventing new deliveries in RabbitMQ under high load",
            "Backpressure not handled in streaming pipeline causing uncontrolled resource usage and latency"
        ],
        "mitigations": [
            "Increased consumer parallelism and optimized message processing logic to reduce latency",
            "Implemented backpressure mechanism and increased queue capacity with TTL policies",
            "Fixed schema compatibility issues and implemented backward-compatible schema evolution",
            "Stabilized consumer group configuration with static membership and reduced rebalance timeout",
            "Deployed schema registry with compatibility checks and version migration strategy",
            "Replaced faulty broker node and enabled broker redundancy with automatic failover",
            "Reset message acknowledgements and improved consumer-side error handling with retries",
            "Added throttling and flow control for producers; improved resource usage monitoring and autoscaling"
        ],
        "accountable_parties": [
            "Application Development Team",
            "DevOps Team",
            "Infrastructure Team",
            "Data Engineering Team"
        ],
        "source_systems": [
            "Messaging System",
            "Payment System",
            "Event Streaming Platform"
        ]
    },
    {
        "category": "Data Consistency",
        "titles": [
            "Eventual Consistency Violation",
            "Distributed Transaction Failure",
            "Cache Invalidation Anomaly",
            "Data Replication Lag",
            "Stale Read from Read Replica",
            "Write Skew in Distributed Ledger",
            "Out-of-Sync Audit Log Between Regions",
            "Inconsistent Snapshot Read in Reporting DB"
        ],
        "impacted_apps": [
            "Distributed Ledger System",
            "Multi-Region Payment Service",
            "Account Balance Cache",
            "Transaction History Service",
            "Cross-Border Settlement Engine",
            "Reporting Service",
            "Audit Log Aggregator",
            "Analytics Dashboard"
        ],
        "root_causes": [
            "Eventual consistency window exceeded tolerance due to network partition between data centers",
            "Distributed transaction coordinator failure causing partial commits across microservices",
            "Cache invalidation event lost due to message broker outage causing stale data reads",
            "Database replication lag exceeding 30 seconds during high write volume period",
            "Read replica serving stale data before replication caught up to primary database",
            "Write skew detected due to concurrent ledger updates without proper ordering control",
            "Audit log replication across regions failed due to schema mismatch after migration",
            "Reporting DB snapshot taken during mid-transaction causing inconsistent state in analytics"
        ],
        "mitigations": [
            "Implemented compensating transactions and idempotency keys to handle consistency failures",
            "Upgraded to saga pattern with orchestrated compensation workflow for distributed transactions",
            "Added cache versioning with TTL and implemented cache-aside pattern with fallback to database",
            "Scaled read replicas horizontally and optimized replication stream with parallel apply",
            "Implemented read-after-write consistency check with automatic routing to primary for critical reads",
            "Introduced global ordering mechanism and sequence number enforcement for ledger updates",
            "Ensured schema compatibility before replication and added automated schema validation on deployment",
            "Synchronized snapshot schedule away from peak transaction times and enforced quiescent state before snapshot"
        ],
        "accountable_parties": [
            "Application Development Team",
            "Database Administration Team",
            "Infrastructure Team",
            "Data Engineering Team"
        ],
        "source_systems": [
            "Database System",
            "Payment System",
            "Event Streaming Platform",
            "Distributed Ledger"
        ]
    }
]

def generate_incident_id(index, date):
    """Generate unique incident ID"""
    return f"INC-{date.strftime('%Y-%m-%d')}-{index:04d}"

def generate_executive_summary(template, title):
    """Generate detailed executive summary with richer narrative and random variability."""
    timestamp = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d} UTC"
    volume = random.randint(500, 50000)
    service_count = random.randint(1, 20)
    success_rate_before = 99.9
    success_rate_after = round(random.uniform(50.0, 98.0), 2)
    latency_impacted = random.randint(5, 300)

    summary = (
        f"At {timestamp}, the payment infrastructure encountered a critical incident titled \"{title}\", impacting approximately {volume:,} transactions. "
        f"The incident affected {service_count} services/modules and resulted in transaction processing delays averaging {latency_impacted} seconds beyond normal SLA. "
        f"During the incident window, end-to-end transaction success rate dropped from {success_rate_before}% to {success_rate_after}%. "
    )

    # Add optional extra detail
    extra = [
        "Cross-border payments and high-value clearing instructions experienced elevated latency, affecting corporate treasury flows.",
        "Retail payments faced intermittent failures, leading to increased customer support escalations.",
        "Automated reconciliation jobs fell behind schedule causing cascading delays in settlements.",
        "Merchant payouts and fee calculations were delayed, impacting downstream financial operations."
    ]
    summary += random.choice(extra) + " "

    # Response description
    reactions = [
        "The incident response team was immediately mobilized and diagnostic procedures were initiated within minutes.",
        "Automated monitoring alerts triggered high-severity escalation and on-call engineers started investigation promptly.",
        "Customer support channels logged a surge in error reports correlating with the timeline of the technical failure.",
        "Engineering and operations teams opened a postmortem bridge and began collecting logs and metrics across systems."
    ]
    summary += random.choice(reactions)

    return summary

def generate_action_taken(template):
    """Generate detailed action taken description with detection, remediation, and preventive measures."""
    detection_time = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d} UTC"
    detection_method = random.choice([
        "automated monitoring dashboards detected anomalous patterns",
        "synthetic transaction tests failed consecutively triggering alerts",
        "customer support tickets escalated rapidly indicating widespread issues",
        "real-time metrics showed degraded service performance",
        "log aggregation platform identified critical error patterns"
    ])

    investigation_steps = random.choice([
        "Engineers immediately accessed production logs and traced the error stack to identify root cause. ",
        "The on-call team initiated runbook procedures and gathered diagnostic data from affected services. ",
        "Cross-functional incident response bridge was established with representatives from engineering, operations, infrastructure, and QA teams. ",
        "Detailed correlation analysis was performed across multiple monitoring systems to isolate the failure domain. ",
        "Forensic investigation included analyzing database query patterns, network traffic flows, service logs, and application performance metrics. "
    ])

    remediation = random.choice([
        "A targeted hotfix was deployed to production following expedited change control approval. ",
        "Failed services were restarted with corrected configuration parameters. ",
        "Traffic was temporarily routed to redundant backup systems while primary infrastructure was stabilized. ",
        "Emergency scaling procedures were executed to increase capacity and handle backlog. ",
        "Database connection pools were reset and cache layers were cleared to restore normal operations. ",
        "Schema migrations were rolled back and service versions reverted to known stable release. ",
        "New configuration was rolled out with corrected settings via infrastructure-as-code pipeline. "
    ])

    preventive = random.choice([
        "Post-incident, the team implemented enhanced monitoring with lower alert thresholds for early detection. ",
        "Additional unit tests, integration tests, and end-to-end tests were added to the CI/CD pipeline to catch similar issues early. ",
        "Infrastructure-as-code configurations were updated with improved validation checks and enforced through automated audits. ",
        "Runbook documentation was enhanced with step-by-step remediation procedures for similar scenarios. ",
        "Capacity planning models were updated to account for observed failure patterns and peak load characteristics. ",
        "Access control policies and secret management practices were tightened; IAM roles and permissions reviewed. ",
        "Service-level retry and fallback strategies were implemented to improve resilience during transient failures. "
    ])

    followup = random.choice([
        "A comprehensive postmortem document was circulated to engineering leadership with actionable items assigned. ",
        "Change advisory board reviewed the incident timeline and approved process improvements. ",
        "Customer communications team sent proactive notifications explaining the incident resolution and advising compensation. ",
        "SLA metrics were analyzed and compensatory credits were processed for affected customers. ",
        "Incident retrospective meeting scheduled to discuss lessons learned and prevention strategies. ",
        "Monthly drills scheduled to simulate similar scenarios and test incident readiness. "
    ])

    action = (
        f"Detection & Triage: At {detection_time}, {detection_method}. "
        + investigation_steps
        + remediation
        + preventive
        + followup
    )

    return action

def generate_incidents(num_incidents=1000, start_date=None, start_index=0):
    """Generate specified number of realistic incidents."""
    if start_date is None:
        # default start_date is 60 days before today
        start_date = datetime.now() - timedelta(days=60)

    incidents = []

    for i in range(num_incidents):
        template = random.choice(INCIDENT_TEMPLATES)
        incident_date = start_date + timedelta(days=random.randint(0, 90))
        incident_id = generate_incident_id(start_index + i + 1, incident_date)
        title = random.choice(template["titles"])
        impacted_app = random.choice(template["impacted_apps"])
        root_cause = random.choice(template["root_causes"])
        mitigation = random.choice(template["mitigations"])
        accountable_party = random.choice(template["accountable_parties"])
        source_system = random.choice(template["source_systems"])
        repeat_incident = "True" if random.random() < 0.10 else "False"  # 10% repeat rate

        executive_summary = generate_executive_summary(template, title)
        action_taken = generate_action_taken(template)

        incident_description = (
            f"impactedApplication: {impacted_app}\n"
            f"rootCause: {root_cause}\n"
            f"mitigation: {mitigation}\n"
            f"accountableParty: {accountable_party}\n"
            f"sourceSystem: {source_system}\n"
            f"repeatIncident: {repeat_incident}\n"
            f"executiveSummary: {executive_summary}"
        )

        incident = {
            "incident_id": incident_id,
            "incident_title": title,
            "incident_description": incident_description,
            "action_taken": action_taken
        }

        incidents.append(incident)

        if (i + 1) % 100 == 0:
            print(f"Generated {i + 1}/{num_incidents} incidents...")

    return incidents

def save_incidents(incidents, output_folder="data", append=False):
    """Save incidents to JSON file."""
    # Use current working directory (script location) for output folder
    output_path = os.path.join(os.getcwd(), output_folder, "ingested_incidents.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if append and os.path.exists(output_path):
        # Load existing incidents and append new ones
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_incidents = json.load(f)
            all_incidents = existing_incidents + incidents
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_incidents, f, indent=2, ensure_ascii=False)
            return output_path, len(existing_incidents)
        except (json.JSONDecodeError, Exception):
            # If file is corrupted, just overwrite
            pass
    
    # Normal save (overwrite)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(incidents, f, indent=2, ensure_ascii=False)
    return output_path, 0

def create_servicenow_incident(incident_data):
    """
    Create a ServiceNow incident via REST API.
    
    Args:
        incident_data: Dictionary containing incident details
        
    Returns:
        Response object from ServiceNow API
    """
    # Convert entire incident JSON to string for description field
    incident_json_str = json.dumps(incident_data, indent=2, ensure_ascii=False)
    
    # Build ServiceNow payload with EXACT requirements
    payload = {
        "short_description": f"{incident_data['incident_id']} | {incident_data['incident_title']}",
        "description": incident_json_str,
        "impact": "2",
        "urgency": "2"
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        response = requests.post(
            SN_API_ENDPOINT,
            auth=HTTPBasicAuth(SN_USER, SN_PASS),
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        return response
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating ServiceNow incident: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        raise

def auto_ingest_to_servicenow(incidents, interval_seconds=360, batch_size=1):
    """
    Automatically ingest incidents to ServiceNow at a specified rate.
    
    Args:
        incidents: List of incident dictionaries
        interval_seconds: Time to wait between batches (default 360 = ~10/hour)
        batch_size: Number of incidents per batch (default 1)
    """
    print("="*70)
    print("ServiceNow Auto-Ingestion Started")
    print("="*70)
    print(f"Target: {SN_BASE_URL}")
    print(f"Rate: ~{3600/interval_seconds:.1f} incidents per hour")
    print(f"Interval: {interval_seconds} seconds between batches")
    print(f"Batch size: {batch_size} incident(s) per batch")
    print(f"Total incidents to process: {len(incidents)}")
    print("="*70)
    print()
    
    created_count = 0
    failed_count = 0
    
    for i in range(0, len(incidents), batch_size):
        batch = incidents[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        
        print(f"[Batch {batch_num}] Processing {len(batch)} incident(s)...")
        
        for incident in batch:
            try:
                response = create_servicenow_incident(incident)
                
                if response.status_code == 201:
                    result = response.json()
                    sys_id = result.get('result', {}).get('sys_id', 'N/A')
                    number = result.get('result', {}).get('number', 'N/A')
                    
                    created_count += 1
                    print(f"  ✓ Created: {incident['incident_id']} → ServiceNow {number} (sys_id: {sys_id})")
                else:
                    failed_count += 1
                    print(f"  ✗ Failed: {incident['incident_id']} (Status: {response.status_code})")
                    
            except Exception as e:
                failed_count += 1
                print(f"  ✗ Error processing {incident['incident_id']}: {str(e)}")
        
        # Wait before next batch (skip wait after last batch)
        if i + batch_size < len(incidents):
            print(f"  ⏳ Waiting {interval_seconds} seconds before next batch...")
            print(f"  📊 Progress: {created_count} created, {failed_count} failed out of {i+batch_size} processed")
            print()
            time.sleep(interval_seconds)
    
    print()
    print("="*70)
    print("Auto-Ingestion Complete")
    print("="*70)
    print(f"✓ Successfully created: {created_count} incidents")
    print(f"✗ Failed: {failed_count} incidents")
    print(f"📊 Success rate: {(created_count/(created_count+failed_count)*100):.1f}%")
    print("="*70)

def main():
    print("="*70)
    print("Auto-Ingestion Script for Payment System Incidents")
    print("ServiceNow Integration Enabled")
    print("="*70)
    print()

    # Mode selection
    print("Select mode:")
    print("1. Generate incidents and save to file only (no ServiceNow)")
    print("2. Generate incidents and auto-ingest to ServiceNow (~10/hour)")
    print("3. Load existing incidents file and ingest to ServiceNow")
    print()
    
    try:
        mode = input("Enter mode (1-3, default: 2): ").strip() or "2"
    except:
        mode = "2"
    
    print()

    # Mode 1: Generate and save only
    if mode == "1":
        try:
            num_incidents = int(input("Enter number of incidents to generate (default: 1000): ") or "1000")
        except ValueError:
            num_incidents = 1000
            print(f"Using default: {num_incidents} incidents")

        # Check if file exists and ask to append or overwrite
        output_path = os.path.join(os.getcwd(), "data", "ingested_incidents.json")
        start_index = 0
        append_mode = False
        
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing_incidents = json.load(f)
                existing_count = len(existing_incidents)
                print()
                print(f"Found existing file with {existing_count} incidents")
                choice = input("Append to existing file? (y/n, default: y): ").strip().lower() or "y"
                if choice == "y":
                    append_mode = True
                    start_index = existing_count
                    print(f"Will continue from incident #{start_index + 1}")
            except:
                pass

        print()
        print(f"Generating {num_incidents} realistic payment system incidents ...")
        print()
        incidents = generate_incidents(num_incidents, start_index=start_index)

        print()
        print(f"✓ Generated {len(incidents)} incidents")
        print()

        output_path, prev_count = save_incidents(incidents, append=append_mode)
        if append_mode:
            print(f"✓ Appended to: {output_path} (Total: {prev_count + len(incidents)} incidents)")
        else:
            print(f"✓ Saved to: {output_path}")
        print()

        print("="*70)
        print("Sample Incident (first one):")
        print("="*70)
        sample = incidents[0]
        print(f"ID: {sample['incident_id']}")
        print(f"Title: {sample['incident_title']}")
        print(f"\nDescription Preview:")
        desc_lines = sample['incident_description'].split('\n')
        for line in desc_lines[:7]:
            print(f"  {line}")
        print(f"\nAction Taken Preview:")
        print(f"  {sample['action_taken'][:200]}...")
        print("="*70)
        print()
        print("✅ Successfully generated incidents — ready for ingestion")
        print()
    
    # Mode 2: Generate and auto-ingest to ServiceNow
    elif mode == "2":
        try:
            num_incidents = int(input("Enter number of incidents to generate (default: 10): ") or "10")
        except ValueError:
            num_incidents = 10
            print(f"Using default: {num_incidents} incidents")
        
        print()
        print(f"Generating {num_incidents} realistic payment system incidents ...")
        print()
        incidents = generate_incidents(num_incidents)
        
        print()
        print(f"✓ Generated {len(incidents)} incidents")
        print()
        
        # Optional: Save to file as backup
        try:
            save_backup = input("Save incidents to file as backup? (y/n, default: y): ").strip().lower() or "y"
            if save_backup == "y":
                output_path = save_incidents(incidents)
                print(f"✓ Backup saved to: {output_path}")
                print()
        except:
            pass
        
        # Start auto-ingestion
        print("Starting ServiceNow auto-ingestion...")
        print()
        auto_ingest_to_servicenow(
            incidents, 
            interval_seconds=SN_INTERVAL_SECONDS, 
            batch_size=SN_BATCH_SIZE
        )
    
    # Mode 3: Load existing file and ingest
    elif mode == "3":
        try:
            file_path = input("Enter path to incidents JSON file (default: data/ingested_incidents.json): ").strip() or "data/ingested_incidents.json"
            
            print()
            print(f"Loading incidents from: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                incidents = json.load(f)
            
            print(f"✓ Loaded {len(incidents)} incidents")
            print()
            
            # Start auto-ingestion
            print("Starting ServiceNow auto-ingestion...")
            print()
            auto_ingest_to_servicenow(
                incidents, 
                interval_seconds=SN_INTERVAL_SECONDS, 
                batch_size=SN_BATCH_SIZE
            )
            
        except FileNotFoundError:
            print(f"❌ Error: File not found at {file_path}")
            print()
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON format in {file_path}")
            print()
        except Exception as e:
            print(f"❌ Error loading file: {e}")
            print()
    
    else:
        print("❌ Invalid mode selected. Exiting.")
        print()

if __name__ == "__main__":
    main()