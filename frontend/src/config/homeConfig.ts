const landing = {
  "nav": {
    "brand": "Support Bot",
    "signIn": {
      "label": "Sign in",
      "href": "/auth"
    }
  },
  "hero": {
    "badge": "AI copilot for IT support",
    "title": [
      "Resolve faster."
    ],
    "lede": "Support Bot reads your ticket history so your team doesn't have to. Instant resolutions, zero context switching.",
    "metrics": [
      {
        "label": "Resolution time",
        "value": "↓ 62%"
      },
      {
        "label": "Auto handled",
        "value": "↑ 48%"
      },
      {
        "label": "Onboarding",
        "value": "2 weeks → 3 days"
      }
    ]
  },
  "stats": [
    {
      "big": "60",
      "unit": "%",
      "caption": "of tickets are repeats your team already solved"
    },
    {
      "big": "4.2",
      "unit": "h",
      "caption": "average time to resolve critical incidents"
    },
    {
      "big": "7",
      "unit": "+",
      "caption": "tools jumped between per ticket"
    },
    {
      "big": "1",
      "unit": "",
      "caption": "engineer leaves, half the knowledge goes"
    }
  ],
  "problem": {
    "eyebrow": "The real cost",
    "title": "Same ticket. Different day. That's the problem.",
    "lede": "The answer already exists - scattered across Jira, ServiceNow. Support Bot finds it instantly.",
    "items": [
      {
        "num": "01",
        "title": "Repetitive tickets drain your best engineers."
      },
      {
        "num": "02",
        "title": "Context is scattered across too many tools."
      },
      {
        "num": "03",
        "title": "Quality depends on who picks up the ticket."
      },
      {
        "num": "04",
        "title": "Resolution time compounds while queues grow."
      },
      {
        "num": "05",
        "title": "Manual triage quietly inflates cost."
      },
      {
        "num": "06",
        "title": "When people leave, knowledge leaves with them."
      }
    ]
  },
  "how": {
    "eyebrow": "How it works",
    "title": "Four steps. One answer.",
    "lede": "No migration. No new workflow. Just plug in and go.",
    "steps": [
      {
        "num": "01",
        "title": "Connect.",
        "body": "Point it at ServiceNow and Jira."
      },
      {
        "num": "02",
        "title": "Ask.",
        "body": "Describe the problem. It searches."
      },
      {
        "num": "03",
        "title": "Resolve.",
        "body": "Find what broke. Fix it."
      },
      {
        "num": "04",
        "title": "Learn.",
        "body": "Every correction makes bot better."
      }
    ]
  },
  "guardrails": {
    "eyebrow": "Built-in guardrails",
    "title": "Safe by default.",
    "lede": "Every prompt is screened before the model sees it. Off-topic, deny-listed, or suspicious - caught at the gate.",
    "pipeline": [
      {
        "kind": "step",
        "num": "// 01",
        "title": "Prompt arrives",
        "body": "Every request enters the safety layer first."
      },
      {
        "kind": "step",
        "num": "// 02",
        "title": "Screened",
        "body": "Checked against deny lists, conversation history, and safety rules."
      },
      {
        "kind": "gate",
        "num": "// 03",
        "title": "Allow or block",
        "body": "Clean prompts continue. Flagged ones stop. No half-answers."
      },
      {
        "kind": "step",
        "num": "// 04",
        "title": "Answer delivered",
        "body": "Safe prompt gets the full AI resolution.",
        "outcome": "allow"
      },
      {
        "kind": "step",
        "num": "// 05",
        "title": "Blocked & logged",
        "body": "Full audit trail. Nothing slips through.",
        "outcome": "block"
      }
    ]
  },
  "integrations": {
    "eyebrow": "Integrations",
    "title": "Works where you work.",
    "lede": "Two connectors. Zero migration. Your data stays in your tenant.",
    "cards": [
      {
        "id": "servicenow",
        "name": "ServiceNow",
        "desc": "Reads incidents with full context - priority, impact, notes, and resolution - straight from your instance."
      },
      {
        "id": "jira",
        "name": "Jira",
        "desc": "Custom JQL support. Ingests issues with full resolution history and comment threads"
      }
    ]
  },
  "features": {
    "eyebrow": "Capabilities",
    "title": "Five things it does. Brilliantly.",
    "items": [
      {
        "id": "tools",
        "num": "01",
        "title": "Finds the right answer, the right way.",
        "body": "Ask naturally. It searches the right way.",
        "variant": "dark",
        "size": "tall",
        "span": 7,
        "visual": {
          "type": "tools",
          "items": [
            {
              "symbol": "ID",
              "label": "Lookup"
            },
            {
              "symbol": "≈",
              "label": "Similar"
            },
            {
              "symbol": "!",
              "label": "Impact"
            },
            {
              "symbol": "∞",
              "label": "Recurring"
            },
            {
              "symbol": "Σ",
              "label": "Stats"
            }
          ]
        }
      },
      {
        "id": "shape",
        "num": "02",
        "title": "Root cause. Fix. Citation.",
        "body": "Every answer follows the same shape - what broke, how to fix it, and the past ticket it came from.",
        "variant": "accent",
        "size": "tall",
        "span": 5,
        "visual": {
          "type": "flow",
          "items": [
            {
              "label": "▸ What broke",
              "score": "Why",
              "highlight": true
            },
            {
              "label": "↳ How to fix it",
              "score": "Steps"
            },
            {
              "label": "↳ Pulled from",
              "score": "INC-…"
            }
          ]
        }
      },
      {
        "id": "tracing",
        "num": "03",
        "title": "Every token tracked.",
        "body": "Complete tracing - who asked, which model answered, what it cost, how long it took",
        "variant": "light",
        "span": 4
      },
      {
        "id": "feedback",
        "num": "04",
        "title": "Learns from your team.",
        "body": "A thumbs up or a correction is all it needs to get better.",
        "variant": "dark",
        "span": 4,
        "visual": {
          "type": "chips",
          "items": [
            {
              "label": "+ Helpful",
              "tone": "pos"
            },
            {
              "label": "↳ Edit"
            },
            {
              "label": "✕ Wrong"
            }
          ]
        }
      },
      {
        "id": "providers",
        "num": "05",
        "title": "Bring your own model.",
        "body": "Anthropic, OpenAI, Gemini, or a self-hosted Ollama. Swap any time, no code changes.",
        "variant": "light",
        "span": 4
      }
    ]
  },
  "feedback": {
    "eyebrow": "Self-improving",
    "title": "It gets smarter. Automatically.",
    "lede": "Good answers are reinforced. Bad ones are rewritten. The next similar question gets the better version - no retraining needed.",
    "loop": [
      {
        "position": "top",
        "label": "Ask",
        "sub": "Engineer asks"
      },
      {
        "position": "right",
        "label": "React",
        "sub": "👍 or 👎"
      },
      {
        "position": "bottom",
        "label": "Store",
        "sub": "Verified answer saved"
      },
      {
        "position": "left",
        "label": "Apply",
        "sub": "Better next time"
      }
    ]
  },
  "demo": {
    "eyebrow": "In action",
    "title": "Watch it work.",
    "placeholder": "Ask a follow-up…",
    "tabs": [
      {
        "id": "triage",
        "label": "Triage",
        "exchanges": [
          {
            "user": "Users say the mobile banking app keeps logging them out even though they just signed in. What have we seen before and what was the root cause?",
            "bot": "Based on past incidents, this issue could be happening for a couple of reasons:\n\n1. **Outdated App Version:** A previous incident (INC-2024-09-11-0141) found that customers using older versions of the mobile app were logged out because the app didn't support an updated authentication process. Please advise users to update their mobile banking app to the latest version.\n2. **Token Expiration Mismatch:** Another incident (INC-2024-06-26-0075) was caused by a time synchronization problem between the app and the server, leading to token expiration issues and inconsistent logins. A session persistence error in NetBanking has also caused high logout rates in the past (INC-2025-12-25-0783).\n\nThe most common cause has been an outdated app version. Can you please check if the affected users are on the latest version of the app?",
            "ttft": 1812,
            "rt": 3247,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      },
      {
        "id": "stats",
        "label": "Stats",
        "exchanges": [
          {
            "user": "Hey, how many incidents do we have in january,",
            "bot": "In January 2026, we logged 63 incidents.",
            "ttft": 2412,
            "rt": 4474,
            "provider": "custom",
            "model": "gpt-oss:20b"
          },
          {
            "user": "Compare the incidents from 2025 Q1 & 2026 Q1",
            "bot": "Here is a comparison of incidents for Q1 2025 and Q1 2026:\n\n| Month | Q1 2025 Incidents | Q1 2026 Incidents |\n| :--- | :--- | :--- |\n| January | 45 | 64 |\n| February | 36 | 60 |\n| March | 49 | 15 |\n| **Total** | **130** | **139** |\n\nIn summary, Q1 2026 saw a slight increase in total incidents (139) compared to Q1 2025 (130). The primary difference was a significant increase in incidents in January and February 2026, followed by a sharp decrease in March.",
            "ttft": 3303,
            "rt": 5483,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      },
      {
        "id": "specific",
        "label": "Specific incident",
        "exchanges": [
          {
            "user": "Tell me about INC-2025-01-18-0278.",
            "bot": "**INC-2025-01-18-0278 - UPI Refund Webhook Failure**\n\nOn 18 Jan 2025 at 14:22 IST, refund webhooks to merchant endpoints started failing with HTTP 502. Roughly 3,400 refunds were stuck in `PENDING_NOTIFY` for 47 minutes before the issue was caught.\n\n**Root cause**\n\nAn NGINX upstream timeout was reduced from 30s to 5s in a config rollout earlier that day. The webhook signing service occasionally takes 6–8s under burst load - which now hit the timeout and bubbled up as a 502.\n\n**Resolution**\n\n- Reverted the NGINX timeout to 30s within 12 minutes of detection.\n- Replayed all stuck refund notifications from the dead-letter queue.\n- Added an alert on upstream timeouts > 1% of webhook traffic.",
            "ttft": 2715,
            "rt": 4832,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      },
      {
        "id": "by-app",
        "label": "By App",
        "exchanges": [
          {
            "user": "What incidents have we had for the UPI service?",
            "bot": "Here are the incidents I found for the UPI service:\n\n- **INC-2026-01-28-0859 — UPI PSP Callback Failure:** The PSP callback handler failed to respond within the defined SLA because the downstream reconciliation queue was saturated. Delayed payment status updates for merchants, affecting 18,000 UPI transactions over a 45-minute period.\n- **INC-2025-06-30-0505 — UPI PSP Callback Skew:** The UPI callback service processed confirmations out of order because the PSP returned responses asynchronously without sequence identifiers. Led to settlement mismatches where successful transactions were temporarily marked as pending.\n- **INC-2024-11-23-0202 — UPI Mandate Cancellation Lag:** Caused by an expired OAuth token between the mandate management service, linked to a time-drift bug in the token manager.\n- **INC-2024-06-13-0060 — UPI Callback Latency Surge:** Asynchronous worker queues accumulated a backlog during high-volume transaction bursts due to retry backoffs exceeding consumer concurrency limits.",
            "ttft": 1943,
            "rt": 3611,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      },
      {
        "id": "recent",
        "label": "Recent",
        "exchanges": [
          {
            "user": "What incidents happened in the last 7 days?",
            "bot": "Here are the **5 incidents** from the last 7 days:\n\n| Incident ID | Title | App |\n|-------------|-------|-----|\n| INC0010021 | Unexpected Table Lock Contention | Customer Account Database |\n| INC0010018 | Unauthorized Access Attempt | Customer Portal |\n| INC0010019 | Event Stream Partition Rebalancing | Audit Log Pipeline |\n| INC0010015 | Third-Party API Rate Limit Exceeded | SWIFT Payment Gateway |\n| INC0010016 | PostgreSQL Bloat and Vacuum Delay | Customer Profile Service |\n\n2 are **High** severity — table lock contention and unauthorized access attempt. Both resolved. Want details on any of these?",
            "ttft": 2108,
            "rt": 3894,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      },
      {
        "id": "recurring",
        "label": "Recurring",
        "exchanges": [
          {
            "user": "What are the most recurring issues from the past year?",
            "bot": "Based on the last 6 months, the most frequently recurring issue is **ECS Mandate Resubmission Failure** (5 times). Several others - **Eventual Consistency Violation**, **Payment Webhook Timeout** - have each appeared twice.\n\n| Title | App | Count |\n|-------|-----|:-----:|\n| ECS Mandate Resubmission Failure | Resubmission API | 5 |\n| Eventual Consistency Violation | Distributed Ledger | 2 |\n| Payment Webhook Timeout | Webhook Dispatch | 2 |\n| Cashback Duplication Issue | Cashback Service | 2 |\n| IAM Role Escalation | Internal Service | 2 |\n| SWIFT Message Queue Freeze | Queue Service | 2 |\n| API Gateway Header Injection | API Gateway | 2 |\n| Cloud Storage Access Denied | Security Engine | 2 |",
            "ttft": 3041,
            "rt": 5127,
            "provider": "custom",
            "model": "gpt-oss:20b"
          }
        ]
      }
    ]
  },
  "footer": {
    "bottomLeft": "© 2026 · Support Bot",
    "bottomCenter": "Pluggable by design",
    "bottomRight": "Same ticket, never twice"
  }
} as const;

export default landing;