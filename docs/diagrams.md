# Workflow and Architecture Diagrams

[Back to README](../README.md) · [Architecture](architecture.md) · [Workflow contracts](workflow-contracts.md)

These diagrams describe the current reference implementation. Email and CRM execution is simulated, persistence is local SQL, and deterministic inference remains the default.

## Business workflow

The approval decision is a required execution boundary: rejected work does not execute, while approved work continues through the simulated tools. Evaluation follows execution, and only evaluated outcomes feed memory.

```mermaid
flowchart LR
    signal[Business Signal] --> context[Structured Context]
    context --> strategy[Strategy]
    strategy --> plan[Action Plan]
    plan --> policy[Policy Checks]
    policy --> approval{Human Approval Gate}
    approval -->|Approve| execution[Tool Execution]
    approval -->|Edit and review again| plan
    approval -->|Reject| stopped[Stopped and recorded]
    execution --> evaluation[Evaluation]
    evaluation --> memory[Memory]
```

## Technical architecture

The structured context envelope is updated across the registered agent stages. Those stages use deterministic inference by default; optional LLM-backed inference returns to the same stage contracts, and failures or invalid output take the deterministic fallback path. Neither inference path bypasses policy, approval, or the simulated adapter boundary.

```mermaid
flowchart TB
    inputs[API and Signals] --> registry[Workflow Registry]
    registry --> orchestration[Orchestrator and State Machine]

    subgraph stages[Agent Stages]
        direction LR
        signalAgent[Signal] --> contextAgent[Context]
        contextAgent --> strategyAgent[Strategy and Planning]
        strategyAgent --> actionAgent[Action]
        executionAgent[Execution]
        evaluatorAgent[Evaluation]
    end

    orchestration --> signalAgent

    envelope[Structured Context Envelope] -. updated across agent stages .-> stages

    subgraph inference[Stage Inference]
        direction LR
        deterministic[Deterministic Default]
        optionalLLM[Optional LLM-backed Inference] -->|failure or invalid output| fallback[Deterministic Fallback]
    end

    stages -. uses .-> deterministic
    stages -. optional .-> optionalLLM
    deterministic -. contract output .-> stages
    fallback -. contract output .-> stages

    actionAgent --> policy[Policy and Approval Queue]
    policy -->|human approved| executionAgent
    executionAgent --> adapters[Tool Adapters]

    subgraph simulated[Simulated Adapters]
        email[Simulated Email]
        crm[Simulated CRM]
    end

    adapters --> email
    adapters --> crm
    email --> evaluatorAgent
    crm --> evaluatorAgent
    evaluatorAgent --> evaluationMemory
    evaluationMemory --> repositories[Repositories and Audit]
    orchestration --> repositories
    policy --> repositories
    repositories --> sqlite[(Local SQL Persistence)]
```

The diagrams intentionally omit future-state services and real customer-system integrations.
