---
allowed-tools: Read, Glob, Grep, Bash(git*), Bash(ls*), mcp__mcp-exec__execute_code_with_wrappers
argument-hint: "--check | --suggest-updates | --compare <section> | --verbose | --diagrams-only | --semantic | --config <path>"
description: Analyze documentation drift and generate sync reports for any project (includes diagrams, architecture, and code docs). Use --semantic for Theo+Serena enhanced discovery.
---

# Sync Docs - Universal Documentation Synchronization

Analyze any codebase and its documentation to identify drift and generate actionable sync reports. Use this command to keep documentation aligned with current code state.

## Command Usage

```
/sync-docs                          # Generate full drift report (includes all docs, diagrams, architecture)
/sync-docs --check                  # Only show drift report (no suggestions)
/sync-docs --suggest-updates        # Include proposed markdown for updates
/sync-docs --compare <section>      # Deep-dive analysis of specific section
/sync-docs --verbose                # Include detailed file references and line numbers
/sync-docs --diagrams-only          # Audit only docs/diagrams/ for outdated content
/sync-docs --semantic               # Use Theo+Serena for deep semantic code discovery
/sync-docs --config <path>          # Use custom configuration file
```

## Your Task

You are a documentation auditor analyzing project documentation to identify what's out of sync with codebase reality.

## Project Configuration

This command adapts to your project structure automatically. For custom behavior, create `.sync-docs-config.json`:

```json
{
  "documentation_files": ["README.md", "CLAUDE.md", "ARCHITECTURE.md"],
  "documentation_dirs": ["docs/", "documentation/", "wiki/"],
  "service_discovery": {
    "mode": "automatic",
    "patterns": ["src/services/*", "services/*", "apps/*", "packages/*"],
    "ignore": ["node_modules", ".git", "dist", "build"]
  },
  "architecture_patterns": ["microservices", "monolithic", "event-driven", "serverless"],
  "infrastructure_files": ["docker-compose.yml", "kubernetes/*.yaml", ".env.example"],
  "check_feature_flags": true,
  "check_diagrams": true,
  "project_type": "auto"
}
```

### Phase 1: Discover Project Structure

1. **Identify Documentation Sources**
   - Look for primary documentation files: README.md, CLAUDE.md, CONTRIBUTING.md, ARCHITECTURE.md
   - Scan for documentation directories: docs/, documentation/, wiki/, guides/
   - Check for API documentation: openapi.yaml, swagger.json, api-docs/
   - Identify diagram directories: diagrams/, architecture/, visuals/

2. **Analyze Project Type**
   Automatically detect project type from:
   - **Microservices**: Multiple service directories, docker-compose.yml, kubernetes configs
   - **Monolithic**: Single main application directory, traditional MVC structure
   - **Library/Package**: package.json/setup.py/Cargo.toml with library configuration
   - **Frontend**: React/Vue/Angular configuration files, public/static directories
   - **Full-Stack**: Both frontend and backend directories
   - **Serverless**: serverless.yml, SAM templates, Lambda functions

3. **Discover Components**
   Based on project type, discover:
   - Services/applications (directory structure analysis)
   - Packages/modules (language-specific patterns)
   - Infrastructure components (Docker, K8s, Terraform)
   - External dependencies (databases, queues, APIs)
   - CI/CD pipelines (.github/workflows, .gitlab-ci.yml, Jenkinsfile)

4. **Extract Documented Elements**
   From discovered documentation:
   - List all mentioned services/components with descriptions
   - Extract architectural patterns and design decisions
   - Identify technology stack and dependencies
   - Note performance requirements or optimizations
   - Review deployment procedures
   - Check for feature flags or configuration options
   - Find API endpoints and schemas

### Phase 2: Audit Codebase Against Documentation

For each discovered system, verify documentation accuracy:

1. **Component Verification**
   - Compare documented components against actual directory structure
   - Verify component descriptions match implementation
   - Check if all discovered services/modules are documented
   - Identify orphaned documentation (describes non-existent components)
   - Validate inter-component dependencies

2. **Configuration Audit**
   - If infrastructure files exist (docker-compose.yml, k8s manifests):
     * Extract all environment variables and configuration
     * Compare against documented configuration
     * Identify undocumented settings
     * Check for deprecated configurations
   - Review feature flags if present
   - Validate port mappings and network configuration

3. **Architecture Patterns**
   - Verify documented patterns exist in code
   - Check if design patterns are consistently applied
   - Validate API contracts and interfaces
   - Confirm data flow documentation matches implementation
   - Review error handling and retry strategies

4. **Technology Stack**
   - Verify language versions match documentation
   - Check dependency versions (package.json, requirements.txt, go.mod)
   - Confirm database/cache/queue technologies
   - Validate third-party service integrations
   - Review security configurations

5. **Cloud/Infrastructure Resources**
   - If cloud resources are documented:
     * Verify service names and configurations
     * Check region/zone specifications
     * Validate IAM/permission documentation
     * Confirm resource naming conventions
   - Review container/VM specifications
   - Check network topology documentation

6. **Deployment & CI/CD**
   - Verify build process documentation
   - Check deployment script references
   - Confirm environment-specific configurations
   - Validate version management approach
   - Review rollback procedures

7. **Diagrams & Visual Documentation**
   - List all diagrams in documentation directories
   - Verify diagrams are referenced in main documentation
   - Check that diagram labels match actual component names
   - Validate data flow and sequence diagrams
   - Confirm architecture diagrams reflect current structure
   - Check for outdated information (dates, versions, deprecated services)
   - Ensure diagram index/catalog is current

### Phase 2.5: Semantic Code Discovery (--semantic flag)

**When `--semantic` flag is provided**, use Theo and Serena MCP servers for deep code discovery that goes beyond file-based analysis. This phase finds undocumented code that traditional grep/glob cannot discover.

#### Prerequisites
- Theo MCP server must be running with project indexed
- Serena MCP server must be running with project activated

#### Step 1: Theo Semantic Discovery

Run parallel semantic searches to find code patterns that may be undocumented:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["theo"]

// Search for architectural patterns
const searches = await Promise.all([
  theo.search({ query: "scheduler service background task cron poll cycle", n_results: 8 }),
  theo.search({ query: "button handler interactive action callback modal", n_results: 8 }),
  theo.search({ query: "feature flag enabled disabled environment variable", n_results: 8 }),
  theo.search({ query: "container docker service deployment singleton", n_results: 8 }),
  theo.search({ query: "protocol interface typed DI dependency injection", n_results: 8 }),
  theo.search({ query: "state tracker database record persistence", n_results: 8 })
]);
```

**Search Categories:**

| Category | Theo Query | Finds |
|----------|--------------|-------|
| Background Services | `"scheduler service background task orchestration"` | Undocumented schedulers, cron jobs |
| Interactive Components | `"button handler interactive component callback"` | UI handlers, modal submissions |
| Feature Flags | `"feature flag environment variable enabled"` | Configuration not in docs |
| Containers | `"docker container service singleton distributed"` | Missing service documentation |
| Protocols | `"protocol interface typed DI dependency"` | Undocumented interfaces |
| State Management | `"state tracker database record persistence"` | Data layer gaps |

#### Step 2: Compare Theo Results to Documentation

For each discovered file:
1. Check if file/class is mentioned in any documentation
2. If NOT mentioned → flag as **UNDOCUMENTED**
3. Build list of undocumented entities with source files

#### Step 3: Serena Precise Navigation

For each undocumented entity, get precise details:

```javascript
// Execute via mcp__mcp-exec__execute_code_with_wrappers with wrappers: ["serena"]

// First activate project
await serena.activate_project({ project: "/path/to/project" });

// Get symbol overview for each discovered file
const symbols = await serena.get_symbols_overview({
  relative_path: "path/to/undocumented/file.py"
});

// Get detailed class structure
const details = await serena.find_symbol({
  name: "DiscoveredClassName",
  symbol_type: "class"
});
```

**Extract for documentation:**
- Class names and their purposes
- Method signatures and key functionality
- Constants and configuration values
- Protocol/interface definitions
- Dependencies on other services

#### Step 4: Semantic Discovery Report Section

Add to drift report:

```markdown
## 🔍 Semantic Discovery Findings (Theo + Serena)

### Undocumented Code Discovered

#### 1. [Component Name]
- **Source Files**: `path/to/file.py` (Theo score: 0.XXX)
- **Classes** (Serena): ClassName1, ClassName2
- **Protocols**: ProtocolName1, ProtocolName2
- **Key Methods**: method1(), method2(), method3()
- **Missing From**: doc1.md, doc2.md, doc3.md
- **Recommended Action**: Add section to [specific doc file]

### Semantic Coverage Summary
- Files discovered by Theo: X
- Undocumented entities found: Y
- Documentation coverage: Z%
```

---

### Phase 3: Generate Comprehensive Drift Report

Create a structured report adapted to the project:

```
# Documentation Drift Report - [Project Name]

## 📊 Overall Health Score
[X% of documentation is current and accurate]

## 🔴 Critical Updates Needed
[Blocks understanding or deployment - must fix]
- [ ] Item: [description with file reference]

## 🟠 High Priority Updates
[Important for developers - impacts daily workflow]
- [ ] Item: [description with file reference]

## 🟡 Medium Priority Updates
[Nice to have - improves clarity]
- [ ] Item: [description with file reference]

## 🟢 Low Priority Updates
[Minor improvements]
- [ ] Item: [description with file reference]

## 📋 Detailed Action Items

### Critical Updates
1. **[File Path]** - [Issue Description]
   - Current state: [what's documented]
   - Actual state: [what's in codebase]
   - Suggested update: [markdown snippet or description]

### Project-Specific Findings
[Tailored to project type - e.g., API endpoints for REST services, component hierarchy for frontend]

## 💡 Summary
- Total gaps identified: X
- Estimated update effort: Y hours
- Most critical area: Z
- Project type detected: [type]
```

### Phase 4: Present Results

Deliver the drift report with:
- Clear prioritization (critical → low)
- Specific file paths to update
- Project-appropriate recommendations
- Effort estimates where applicable

If `--suggest-updates`: Include proposed markdown/content for each update
If `--compare <section>`: Deep-dive analysis of just that section
If `--verbose`: Include file paths, line numbers, and full context
If `--diagrams-only`: Focus exclusively on visual documentation audit
If `--semantic`: Execute Phase 2.5 using Theo+Serena for deep code discovery
If `--config <path>`: Use specified configuration file

## Example Configurations

### Microservices Project (with Semantic Discovery)
```json
{
  "project_type": "microservices",
  "service_discovery": {
    "patterns": ["services/*", "apps/*"],
    "mode": "directory"
  },
  "infrastructure_files": ["docker-compose*.yml", "k8s/*.yaml"],
  "check_feature_flags": true,
  "semantic_discovery": {
    "enabled": true,
    "theo_queries": [
      "scheduler service background task",
      "handler callback interactive",
      "feature flag enabled"
    ],
    "serena_symbols": ["class", "protocol", "function"]
  }
}
```

### Monolithic Application
```json
{
  "project_type": "monolithic",
  "documentation_files": ["README.md", "docs/ARCHITECTURE.md"],
  "architecture_patterns": ["MVC", "layered"],
  "infrastructure_files": ["Dockerfile", "deploy/production.yml"]
}
```

### Frontend Project
```json
{
  "project_type": "frontend",
  "documentation_dirs": ["docs/", "storybook/"],
  "service_discovery": {
    "patterns": ["src/components/*", "src/pages/*"],
    "mode": "component"
  },
  "check_feature_flags": false
}
```

### Library/Package
```json
{
  "project_type": "library",
  "documentation_files": ["README.md", "API.md", "CHANGELOG.md"],
  "service_discovery": {
    "patterns": ["src/*", "lib/*"],
    "mode": "module"
  },
  "check_diagrams": false
}
```

## Migration Guide for Specific Projects

### For Ketchup Project
The command will automatically detect:
- 7 core services in root directory
- docker-compose.yml with 12 containers (7 on prod1, 5 on prod2)
- TypedDI architecture patterns
- AWS infrastructure components
- Feature flags in environment variables

**With `--semantic` flag**, also discovers:
- CSOPM notification system components via Theo
- TypedDI protocols and service registrations via Serena
- Interactive button handlers and state trackers
- Undocumented services that traditional file scanning misses

No configuration needed - the tool will discover this structure automatically.

### For Other Projects
1. Run without configuration first to see auto-detection
2. Create `.sync-docs-config.json` if needed for customization
3. Adjust patterns based on your project structure
4. Focus on your specific architecture patterns

## Advanced Features

### Custom Validators
Add project-specific validation by including in config:
```json
{
  "custom_validators": {
    "api_versions": "Check API version consistency",
    "security_headers": "Validate security documentation",
    "performance_metrics": "Verify SLA documentation"
  }
}
```

### Integration with CI/CD
Run in CI pipelines to catch documentation drift:
```bash
# In GitHub Actions, GitLab CI, etc.
/sync-docs --check --fail-on-drift
```

## Notes

- The tool adapts to any project structure
- Configuration is optional - auto-discovery handles most cases
- Prioritization helps focus on important updates first
- Works with any programming language or framework
- Supports monorepo and polyrepo structures
- Can validate both code documentation and architectural docs

### Semantic Discovery Notes (`--semantic`)

- **Theo** provides semantic/fuzzy search - finds code by meaning, not just keywords
- **Serena** provides precise symbol navigation - extracts exact class/method structures
- Combined approach catches undocumented code that file-based scanning misses
- Requires Theo index to be built (`theo.index_directory`) and Serena project activated
- Best for large codebases where manual discovery is impractical
- Phase 2.5 runs automatically when `--semantic` flag is provided

**When to use `--semantic`:**
- After major refactoring or new service deployment
- When documentation health score is low
- For comprehensive quarterly audits
- When you suspect undocumented features exist