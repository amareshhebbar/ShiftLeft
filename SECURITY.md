# Security Policy

## Supported Versions

Currently, only the latest `main` branch of ShiftLeft is supported with security updates. 

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| `< 1.0` | :x:                |

## AI & Agentic Security Considerations
ShiftLeft operates utilizing LLMs and Model Context Protocol (MCP) to execute code and terminal commands. Security is a primary concern. 
* **Prompt Injection:** We are actively monitoring and patching avenues where malicious issues or PRs could inject commands into the Sandbox Auditor.
* **Secret Management:** Never commit your `.env` file, GCP credentials, or GitHub PATs. The system is designed to read these locally or via secure secret managers.

## Reporting a Vulnerability

If you discover a security vulnerability within ShiftLeft (especially regarding execution sandbox escapes or MCP authorization bypasses), **please do not report it by creating a public GitHub issue.**

Instead, securely report it by sending an email to: **reshama0302@gmail.com**

We will acknowledge receipt of your vulnerability report within 48 hours and strive to send you regular updates about our progress. If a fix is verified, we will release a patch immediately.