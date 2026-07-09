# Pre-CRM Scoring Rubric

The scoring model evaluates whether a company should be added to CRM before a sales rep spends time on outreach.

## Total score

Maximum score: `100`

| Category | Max score | What it evaluates |
| --- | ---: | --- |
| Firmographic ICP fit | 20 | B2B fit, SaaS / tech-enabled fit, industry fit, stage, employee count |
| Sales motion fit | 20 | Demo-led or sales-led motion, talk-to-sales CTAs, multi-touch sales complexity |
| GTM pain intensity | 25 | GTM hiring, SDR/AE growth, RevOps/Sales Ops evidence, follow-up complexity, CRM hygiene pain |
| Tool/data readiness | 15 | CRM evidence, email/calendar stack, sales engagement tools, structured GTM data likelihood |
| Urgency trigger strength | 10 | Funding, hiring, new sales leader, expansion, launch, recent GTM activity |
| Buyer accessibility | 10 | Identified founder, sales leader, RevOps buyer, public accessibility, relevance |

## Decision thresholds

| Score range | Fit level | Default action |
| --- | --- | --- |
| 80-100 | strong_fit | add_to_crm if buyer access is medium/high |
| 65-79 | good_fit | add_to_crm if pain and buyer access are strong; otherwise manual_review or research_more |
| 50-64 | unclear_fit | add_to_watchlist or research_more |
| below 50 | poor_fit | reject |

## Action logic

Allowed final decisions:

- add_to_crm
- research_more
- add_to_watchlist
- manual_review
- reject

Rules:

1. If score is `>= 80` and buyer access is medium/high, decision = `add_to_crm`.
2. If score is `>= 80` but no buyer is found, decision = `research_more`.
3. If score is `65-79` and pain evidence is strong, decision = `manual_review` or `add_to_crm`.
4. If score is `50-64`, decision = `add_to_watchlist` or `research_more`.
5. If score is `< 50`, decision = `reject`.
6. If there are conflicting signals, decision = `manual_review`.

## Evaluation JSON contract

```json
{
  "pre_crm_evaluation": {
    "company_name": "",
    "icp_score": {
      "total_score": 0,
      "max_score": 100,
      "fit_level": ""
    },
    "score_breakdown": {
      "firmographic_icp_fit": {
        "score": 0,
        "max_score": 20,
        "notes": "",
        "evidence": [],
        "confidence": ""
      },
      "sales_motion_fit": {
        "score": 0,
        "max_score": 20,
        "notes": "",
        "evidence": [],
        "confidence": ""
      },
      "gtm_pain_intensity": {
        "score": 0,
        "max_score": 25,
        "notes": "",
        "evidence": [],
        "confidence": ""
      },
      "tool_data_readiness": {
        "score": 0,
        "max_score": 15,
        "notes": "",
        "evidence": [],
        "confidence": ""
      },
      "urgency_trigger_strength": {
        "score": 0,
        "max_score": 10,
        "notes": "",
        "evidence": [],
        "confidence": ""
      },
      "buyer_accessibility": {
        "score": 0,
        "max_score": 10,
        "notes": "",
        "evidence": [],
        "confidence": ""
      }
    },
    "evaluation_notes": {
      "summary": "",
      "strong_positive_signals": [],
      "weak_or_missing_signals": [],
      "red_flags": [],
      "research_gaps": [],
      "pain_hypothesis": "",
      "mawi_relevance": ""
    },
    "recommended_workflow": {
      "primary_workflow": "",
      "secondary_workflows": [],
      "why_this_workflow": ""
    },
    "buyer_recommendation": {
      "best_buyer_persona": "",
      "identified_contact": {
        "name": "",
        "title": "",
        "linkedin_url": ""
      },
      "buyer_access_confidence": ""
    },
    "outreach_recommendation": {
      "first_outreach_angle": "",
      "personalization_points": [],
      "suggested_message_theme": ""
    },
    "final_action": {
      "decision": "",
      "reason": "",
      "human_review_required": true,
      "next_action": ""
    }
  }
}
```
