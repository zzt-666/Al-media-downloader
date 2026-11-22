# Spec Delta

## Purpose

Expose a lightweight health endpoint so operators and implementers can verify the API is up and whether yt-dlp and ffmpeg dependencies are available before running parse or download flows.

## ADDED Requirements

### Requirement: Health endpoint reports service and dependencies
The system MUST provide a health check that indicates the API is reachable, includes the yt-dlp version string when importable, and reports whether ffmpeg is detectable on PATH as a boolean.

#### Scenario: Healthy local environment
- **WHEN** a client requests the health endpoint and dependencies are installed
- **THEN** the response indicates ok is true
- **AND** includes a non-empty yt-dlp version string
- **AND** reports ffmpeg as true

#### Scenario: Missing ffmpeg
- **WHEN** a client requests the health endpoint and ffmpeg is not on PATH
- **THEN** the response still indicates the API is reachable
- **AND** reports ffmpeg as false so operators know merge may fail
