# GEMINI CLI Operational Guidelines and Role Definition

This document records key operational guidelines and role definitions for the GEMINI CLI agent.

## 1. Document Management in `devlog/`

*   **Always verify the latest sequence number**: Before creating any new document in the `devlog/` directory, always list the directory contents to determine the highest existing sequence number. The new document's sequence number must be the next available integer.
*   **Example**: If the highest is `019`, the next document should be `020`.
*   **Reason**: To maintain proper chronological order and avoid conflicts, especially when other agents (e.g., Claude Code) also generate documents.

## 2. Role Definition in Project Workflow

*   **GEMINI CLI's Primary Role**: Focus on strategic planning, breaking down complex tasks into detailed steps, and evaluating implementation results (e.g., reviewing code, assessing test reports).
*   **Claude Code's Primary Role**: Focus on the actual implementation of features, writing code, and conducting detailed testing.
*   **Collaboration**: GEMINI CLI will provide detailed plans for Claude Code, and then evaluate Claude Code's completed work.
