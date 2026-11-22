# product-web-ui Specification

## Purpose

Provide a responsive single-page product UI for paste-parse-select-download, plus platform cues, advanced-feature placeholders, and compliance copy, without requiring real AI or payment backends.

## Requirements

### Requirement: Hero entry for paste and parse
The product page MUST show the brand name「万能视频下载器」, a hero title and subtitle, a URL input, and a parse action. Activating parse MUST call the parse API and show a loading state that prevents duplicate submits until the request finishes.

#### Scenario: Page open
- **WHEN** a user opens the frontend home page
- **THEN** brand, hero copy, URL input, and parse control are visible without a blank screen

#### Scenario: Parse loading and success
- **WHEN** the user pastes a supported public URL and activates parse
- **THEN** the UI shows a parsing/loading state
- **AND** on success displays title and selectable formats (and thumbnail/duration when returned)

#### Scenario: Parse failure shown in UI
- **WHEN** the user submits an invalid or unsupported URL and activates parse
- **THEN** the UI shows the Chinese error detail in-page
- **AND** does not white-screen or show a raw stack trace

### Requirement: Select format and download to local device
After a successful parse, the UI MUST let the user select a format (or proceed with default best), activate download with a downloading state, call the download API then retrieve the file by file_id, and trigger browser save. Success MUST show a brief confirmation; failure MUST show Chinese detail.

#### Scenario: End-to-end download from UI
- **WHEN** the user selects a format and activates download after a successful parse
- **THEN** the UI shows a downloading state
- **AND** the browser begins saving a file after the backend returns a file_id

#### Scenario: Download failure in UI
- **WHEN** the download API returns an error detail
- **THEN** the UI displays that Chinese detail
- **AND** re-enables retry without crashing the page

### Requirement: Platform coverage and advanced placeholders
The page MUST display platform/capability cues stating coverage is based on yt-dlp, and MUST show placeholder sections for video summary, subtitle translation, and membership/paid benefits marked as not yet available (e.g.「即将上线」). Placeholders MUST NOT block the download flow.

#### Scenario: Placeholders visible
- **WHEN** the user scrolls to the advanced section
- **THEN** summary, translation, and membership placeholders are visible and marked as not launched

### Requirement: Compliance footer
The page MUST include a visible copyright and learning-use statement that content is for personal learning/backup, users must respect copyright, and unauthorized commercial use or distribution is prohibited. Copy MUST NOT promote DRM bypass or account cracking.

#### Scenario: Footer compliance
- **WHEN** the user views the page footer
- **THEN** learning-use and copyright respect statements are visible

### Requirement: Mobile-usable layout
At phone-width viewports the main flow MUST remain usable: input and primary actions reachable, format selection not requiring an unusable wide table, and parse/download completable without horizontal breakage of primary controls.

#### Scenario: Narrow viewport main flow
- **WHEN** the viewport is narrowed to a typical phone width
- **THEN** the user can paste a URL, parse, see results, and activate download controls
