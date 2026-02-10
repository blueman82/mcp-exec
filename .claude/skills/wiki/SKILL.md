---
name: wiki
description: Edit Adobe Confluence wiki pages. Use when working with wiki pages, Confluence content, wiki.corp.adobe.com URLs, or documentation updates. Provides Confluence Storage Format templates and safe update workflow.
---

# Confluence Wiki Editor

Edit Adobe Confluence wiki pages using the adobe-wiki MCP server.

## Usage
```
/wiki <url> [action]
/wiki https://wiki.corp.adobe.com/display/neolane/Ketchup append
/wiki https://wiki.corp.adobe.com/display/neolane/MyPage create
```

## Actions
- **read** (default) - Get page content
- **append** - Add content to end of page
- **update** - Replace entire page content
- **create** - Create new page
- **validate** - Check content format

## MCP Access

Use `mcp__mcp-exec__execute_code_with_wrappers` with `wrappers: ["adobe-wiki"]`:

```javascript
const wiki = mcp['adobe-wiki'];

// Get content
const content = await wiki.get_wiki_content({ url: "..." });

// Validate before update
const valid = await wiki.validate_wiki_storage_format({ content: "..." });

// Update page
await wiki.update_wiki_content({
  url: "...",
  content: fullContent,
  content_type: "storage",
  minor_edit: false
});

// Get format templates
const templates = await wiki.get_confluence_format_templates({});
```

## Confluence Storage Format Reference

### Namespace Wrapper (REQUIRED)
```xml
<div xmlns:ac="http://atlassian.com/content" xmlns:ri="http://atlassian.com/resource/identifier">
  <!-- content here -->
</div>
```

### Headers (auto-numbered)
```xml
<h1 data-nh-numbering="1. ">Section Title</h1>
<h2>Subsection</h2>
<h3 data-nh-numbering="1.1. ">Numbered Subsection</h3>
```

### Code Block
```xml
<ac:structured-macro ac:name="code" ac:schema-version="1">
  <ac:parameter ac:name="language">bash</ac:parameter>
  <ac:plain-text-body><![CDATA[your code here]]></ac:plain-text-body>
</ac:structured-macro>
```

### Note/Warning/Info Panels
```xml
<ac:structured-macro ac:name="note" ac:schema-version="1">
  <ac:rich-text-body>
    <p>Note text here</p>
  </ac:rich-text-body>
</ac:structured-macro>
```
Replace `note` with: `warning`, `info`, `tip`

### Page Link
```xml
<ac:link>
  <ri:page ri:content-title="Page Name"/>
</ac:link>
```

### External Link
```xml
<a href="https://example.com">Link Text</a>
```

### Image (attachment)
```xml
<ac:image ac:height="400" ac:width="400">
  <ri:attachment ri:filename="image.png"/>
</ac:image>
```

### Table
```xml
<table class="wrapped relative-table" style="width: 100.0%;">
  <colgroup>
    <col style="width: 30.0%;"/>
    <col style="width: 70.0%;"/>
  </colgroup>
  <tbody>
    <tr>
      <th><p><strong>Header 1</strong></p></th>
      <th><p><strong>Header 2</strong></p></th>
    </tr>
    <tr>
      <td><p>Cell 1</p></td>
      <td><p>Cell 2</p></td>
    </tr>
  </tbody>
</table>
```

### JIRA Macro
```xml
<ac:structured-macro ac:name="jira" ac:schema-version="1">
  <ac:parameter ac:name="server">Adobe JIRA Data Center</ac:parameter>
  <ac:parameter ac:name="serverId">5affdfe8-ed2e-3a17-8442-0790430373f0</ac:parameter>
  <ac:parameter ac:name="key">CPGNCX-12345</ac:parameter>
</ac:structured-macro>
```

### Table of Contents
```xml
<ac:structured-macro ac:name="toc" ac:schema-version="1">
  <ac:parameter ac:name="maxLevel">1</ac:parameter>
</ac:structured-macro>
```

## Large Content Updates (Fail Fast + Graceful Fallback)

The adobe-wiki MCP now handles large content automatically:
1. **Fail Fast**: API call proceeds regardless of content size
2. **Automatic Fallback**: If Confluence returns size error (HTTP 413), `progressiveAppendFallback()` kicks in
3. **Chunking**: Content is split into 8KB chunks and applied incrementally

**Just try the update** - it will work for most pages. If it fails due to size, the fallback handles it automatically.

## IMPORTANT: Content Truncation Warning

`get_wiki_content` may return TRUNCATED content (~700 chars instead of full page). Before full-page updates:
1. Verify fetched content length matches expectations
2. Or use user-provided content directly
3. NEVER overwrite a page with truncated content

## Workflow

1. **Read**: Get current content, verify length (watch for truncation!)
2. **Prepare**: Create new content matching existing format
3. **Wrap**: Add namespace div wrapper
4. **Validate**: Run `validate_wiki_storage_format`
5. **Update**: Call `update_wiki_content` with `content_type: "storage"` - large content handled automatically
