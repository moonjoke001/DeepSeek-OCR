# Requirements Document

## Introduction

本功能为 DeepSeek-OCR Web UI 添加批量 PDF 处理能力，允许用户一次性上传多个 PDF 文件，系统将自动队列处理并展示每个文件的识别进度和结果。

## Glossary

- **Batch_Processor**: 批量处理引擎，负责管理多文件上传队列和并行/串行处理
- **File_Queue**: 文件队列，存储待处理的 PDF 文件列表
- **Progress_Tracker**: 进度追踪器，跟踪每个文件和整体批次的处理进度
- **Result_Aggregator**: 结果聚合器，收集并组织所有文件的 OCR 结果
- **Web_UI**: 前端用户界面

## Requirements

### Requirement 1: 批量文件上传

**User Story:** As a user, I want to upload multiple PDF files at once, so that I can process a batch of documents without uploading them one by one.

#### Acceptance Criteria

1. WHEN a user drags multiple PDF files to the upload area, THE Web_UI SHALL accept all files and add them to the File_Queue
2. WHEN a user clicks the upload area, THE Web_UI SHALL open a file picker that allows multiple file selection
3. THE Web_UI SHALL display a list of all queued files with their names and sizes
4. WHEN a file in the queue is clicked, THE Web_UI SHALL allow the user to remove it from the queue
5. THE Web_UI SHALL validate that all uploaded files are PDF format and reject non-PDF files with a clear error message
6. THE Web_UI SHALL limit the maximum number of files per batch to 20 files
7. THE Web_UI SHALL limit the maximum total size per batch to 500MB

### Requirement 2: 批量处理队列管理

**User Story:** As a user, I want to see and manage the processing queue, so that I can track which files are pending, processing, or completed.

#### Acceptance Criteria

1. THE Web_UI SHALL display a queue panel showing all files with their current status (pending, processing, completed, error)
2. WHEN a file starts processing, THE Progress_Tracker SHALL update the file status to "processing" and show a progress indicator
3. WHEN a file completes processing, THE Progress_Tracker SHALL update the file status to "completed" and show a success icon
4. IF a file fails to process, THEN THE Progress_Tracker SHALL update the file status to "error" and display the error message
5. THE Web_UI SHALL display an overall batch progress bar showing percentage of completed files
6. WHEN the user clicks "Start Batch Processing", THE Batch_Processor SHALL begin processing files sequentially

### Requirement 3: 批量处理后端 API

**User Story:** As a developer, I want a batch processing API endpoint, so that the frontend can submit and track batch OCR jobs.

#### Acceptance Criteria

1. WHEN a batch upload request is received, THE Batch_Processor SHALL create a unique batch_id and return it immediately
2. THE Batch_Processor SHALL process files sequentially to avoid GPU memory issues
3. WHEN processing each file, THE Batch_Processor SHALL emit progress updates via WebSocket
4. THE Batch_Processor SHALL save each file's result to a separate output file
5. WHEN all files are processed, THE Result_Aggregator SHALL create a combined result file with all OCR outputs
6. THE Batch_Processor SHALL support cancellation of pending files in the queue

### Requirement 4: 批量结果展示与下载

**User Story:** As a user, I want to view and download all OCR results, so that I can use the extracted text from my documents.

#### Acceptance Criteria

1. WHEN a file completes processing, THE Web_UI SHALL allow the user to preview its OCR result
2. THE Web_UI SHALL provide a "Download All" button to download all results as a ZIP file
3. THE Web_UI SHALL provide individual download buttons for each completed file's result
4. WHEN displaying results, THE Web_UI SHALL show the filename and page count for each processed PDF
5. THE Result_Aggregator SHALL generate a combined Markdown file with clear separators between documents

### Requirement 5: 批量处理状态持久化

**User Story:** As a user, I want my batch processing progress to be preserved, so that I can refresh the page without losing my work.

#### Acceptance Criteria

1. THE Batch_Processor SHALL save batch state to disk after each file completes
2. WHEN the page is refreshed during processing, THE Web_UI SHALL restore the batch progress from the server
3. IF the server restarts during processing, THEN THE Batch_Processor SHALL resume from the last completed file
4. THE Batch_Processor SHALL clean up old batch data after 24 hours
