# Project Context: Production Vehicle Access Logging System

**CRITICAL RULE: Always keep the production context in mind for all tasks.**

## System Purpose
This project is a market-ready product designed to operate in real-world scenarios. Its primary use-case is logging vehicle entries and exits for premises. 

## Core Requirements
1. **Accuracy**: We must know exactly when a vehicle entered and exited a premise.
2. **Reliability**: We must capture the exact number plate text and ensure it is stored reliably in the Supabase database.
3. **Production Quality**: Code must be robust, handle edge cases (e.g. tracking disconnections, API limits, bad network conditions), and be structured cleanly for scalability and maintainability.

## Guidelines for Future Development
- Do not write "hacky" scripts or temporary workarounds as final solutions.
- Ensure proper error handling, logging, and state management.
- When configuring visual coordinates (like LineZones), ensure they dynamically scale with video resolution rather than relying on hardcoded screen bounds.
- Treat the Supabase database as the definitive source of truth for the product's live state.

## Deployment Architecture Constraints
- **100% On-Premise / Local Server**: There will be absolutely NO cloud storage or cloud service usage involved in the final product. All processing and data storage must occur locally.
- **No Edge Deployments**: The system runs on a centralized on-premise server, not on distributed low-power edge devices (e.g., no Raspberry Pi or Jetson Nano deployments at individual gates).
