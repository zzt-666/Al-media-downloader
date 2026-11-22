# video-parse Specification

## Purpose

Accept a public video page URL, extract metadata and downloadable format options, and return a frontend-ready payload or a clear Chinese error without downloading media.

## Requirements

### Requirement: Validate http(s) video URL before parsing
The system MUST reject empty, malformed, or non-http(s) URLs before invoking any media extractor, and MUST return a Chinese error detail suitable for display.

#### Scenario: Empty or invalid URL
- **WHEN** a client submits an empty string or a value that is not a valid http(s) URL
- **THEN** the system responds with a client error and Chinese detail such as asking for a valid http(s) video link
- **AND** no media extraction is attempted

#### Scenario: Disallowed scheme
- **WHEN** a client submits a URL using a non-http(s) scheme (for example `file://`)
- **THEN** the system rejects the request with a Chinese error detail
- **AND** no filesystem path from the URL is opened

### Requirement: Parse public video metadata without downloading
The system MUST extract video metadata for a supported public URL without downloading the media file, and MUST return at least id, title, optional thumbnail, duration when available, webpage_url, and extractor identity fields.

#### Scenario: Successful parse of supported public URL
- **WHEN** a client submits a publicly accessible URL supported by the download engine
- **THEN** the system returns JSON including id, title, webpage_url, and extractor fields
- **AND** thumbnail and duration are included when the engine provides them
- **AND** no media file is written for the parse request

### Requirement: Return filtered selectable formats
The system MUST return a formats list with user-meaningful entries including format_id, ext, and available quality fields (resolution, fps, codecs, size, format_note when present), MUST filter out storyboard or tiny preview-only streams when identifiable, and MUST order formats with video tracks first then higher resolution before lower.

#### Scenario: Formats list after successful parse
- **WHEN** parse succeeds and the engine provides formats
- **THEN** the response includes a formats array of selectable entries with format_id and ext
- **AND** storyboard or non-playable preview-only entries are omitted when identifiable
- **AND** remaining entries are ordered video-first then higher resolution before lower

#### Scenario: No useful formats
- **WHEN** parse succeeds but no useful formats remain after filtering
- **THEN** the system returns a failure with Chinese detail explaining that no suitable format is available

### Requirement: Map parse failures to Chinese errors
The system MUST map extractor failures (unsupported site, missing video, network/timeout) to Chinese detail messages and MUST NOT expose raw stack traces to the client.

#### Scenario: Unsupported or unrecognized link
- **WHEN** the engine cannot identify a suitable extractor for the URL
- **THEN** the client receives a Chinese detail indicating the link may not be supported

#### Scenario: Unavailable video
- **WHEN** the video does not exist, was removed, or is inaccessible
- **THEN** the client receives a Chinese detail indicating the video is unavailable

#### Scenario: Network or timeout during parse
- **WHEN** parse fails due to network error or timeout
- **THEN** the client receives a Chinese detail asking to retry later
