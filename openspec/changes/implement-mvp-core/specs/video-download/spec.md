# Spec Delta

## Purpose

Download a selected or default media format into an isolated temp directory, register it by file_id, serve it as an attachment, and clean expired files under a single-concurrency limit.

## ADDED Requirements

### Requirement: Synchronous download returns file_id
The system MUST accept a URL and optional format_id, download synchronously until the file is ready or a configured timeout elapses, and MUST return file_id, filename, and size on success. When format_id is omitted, the system MUST use the default best format selector that may merge video and audio.

#### Scenario: Download with explicit format_id
- **WHEN** a client posts a valid URL and a format_id from a prior parse
- **THEN** the system downloads that format into the isolated download directory
- **AND** responds with file_id, filename, and size after the file is ready

#### Scenario: Download with default best format
- **WHEN** a client posts a valid URL without format_id
- **THEN** the system downloads using the default best selector
- **AND** returns file_id, filename, and size on success

#### Scenario: Download timeout
- **WHEN** the download does not finish within the configured timeout (default 10 minutes)
- **THEN** the client receives a Chinese timeout/retry error
- **AND** partial artifacts are cleaned up when feasible

### Requirement: Serve file by file_id as attachment
The system MUST expose a file retrieval endpoint that streams the registered file as a downloadable attachment using a server-generated safe path bound to file_id (UUID). Clients MUST NOT supply filesystem paths.

#### Scenario: Successful file retrieval
- **WHEN** a client requests a valid, non-expired file_id
- **THEN** the system returns the file with Content-Disposition attachment and the registered filename

#### Scenario: Missing or expired file_id
- **WHEN** a client requests an unknown or expired file_id
- **THEN** the system responds with not found and a Chinese detail that the file was cleaned or does not exist

### Requirement: Limit concurrent downloads to one
The system MUST allow at most one active download at a time. Additional download requests while a download is in progress MUST be rejected with a Chinese busy message.

#### Scenario: Second download while one is running
- **WHEN** a download is already in progress
- **AND** another client requests a new download
- **THEN** the system rejects the new request with a Chinese detail that a task is already running

### Requirement: Isolate and expire temporary files
The system MUST write downloads only under the configured downloads directory, MUST NOT accept user-controlled output templates or engine option injection, MUST register created_at for each file_id, and MUST delete files older than the configured TTL (default 1 hour).

#### Scenario: Path isolation
- **WHEN** a download completes
- **THEN** the media file exists only under the configured downloads directory
- **AND** the client can retrieve it only via file_id

#### Scenario: TTL cleanup
- **WHEN** a registered file exceeds the configured TTL
- **THEN** the system deletes the file and invalidates its file_id

### Requirement: Map download failures to Chinese errors
The system MUST map download and merge failures (including missing ffmpeg when merge is required) to Chinese detail messages without exposing stack traces to clients.

#### Scenario: Missing ffmpeg for merge
- **WHEN** the selected format requires audio/video merge and ffmpeg is unavailable
- **THEN** the client receives a Chinese detail instructing to install ffmpeg

#### Scenario: Engine download error
- **WHEN** the download engine fails for network or site reasons
- **THEN** the client receives a Chinese failure detail suitable for display

### Requirement: Default single-video playlist behavior
The system MUST set playlist-avoiding behavior so that ambiguous playlist URLs download a single video rather than the whole playlist.

#### Scenario: Playlist-capable URL without explicit playlist intent
- **WHEN** a URL could resolve to a playlist
- **THEN** the system downloads only a single video entry rather than the full playlist
