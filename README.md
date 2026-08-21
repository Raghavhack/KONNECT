# KONNECT

KONNECT is a platform designed to process documents, extract meaningful entities and relationships, and organize information into a connected knowledge structure.

## Architecture

The project consists of multiple services:

- **Frontend** — User interface
- **Backend** — APIs and application logic
- **AI Service** — Document processing and AI-powered entity/relation extraction
- **Shared** — Common utilities and resources
- **Infrastructure** — Deployment and infrastructure configuration
- **Docs** — Project documentation

## Project Structure

```text
KONNECT/
├── ai_service/       # AI and document processing service
├── backend/          # Backend API and business logic
├── frontend/         # Frontend application
├── shared/           # Shared utilities and resources
├── infrastructure/   # Docker and deployment configuration
├── docs/             # Documentation
├── .gitignore
└── README.md