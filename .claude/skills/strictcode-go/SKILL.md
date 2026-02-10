---
name: strictcode-go
description: Go-specific coding standards and idioms. Invoked by strictcode coordinator or directly for Go files.
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__mcp-exec__*
---

# StrictCode Go - Language-Specific Standards

**Version:** 1.0.0
**Purpose:** Enforce Go idioms and patterns on `.go` files.

---

## Go Idioms (MANDATORY)

### Interface & Struct Patterns
- **Accept interfaces, return structs** — Functions should accept interface parameters for flexibility, return concrete struct types for clarity
- **Package-level organization** — No class-level thinking; organize by package responsibility

### Error Handling
- **Errors are values** — Handle them or return them, never ignore with `_ =`
- **Wrap errors with context** — Use `fmt.Errorf("context: %w", err)` for stack traces
- **Early returns** — Check errors immediately, return early

### Testing
- **Table-driven tests** — Use `[]struct{ name string; ... }` pattern for test cases
- **Subtests** — Use `t.Run(tt.name, func(t *testing.T) { ... })`

### Naming & Style
- **Short variable names in small scopes** — `i`, `n`, `err` are fine locally
- **Exported = PascalCase, unexported = camelCase**
- **Acronyms stay uppercase** — `HTTPClient`, not `HttpClient`

---

## Reduction Patterns (APPLY)

| Pattern | Before | After |
|---------|--------|-------|
| Early return | `if err != nil { ... } else { ... }` | `if err != nil { return err }` |
| Error wrapping | `return err` | `return fmt.Errorf("context: %w", err)` |
| No empty structs | `Type{}` without purpose | Remove or use `var t Type` |
| No unused vars | `_ = validateInput(data)` | `if err := validateInput(data); err != nil { ... }` |
| Named returns | `func() (int, error)` | `func() (count int, err error)` for docs |
| No TODO comments | `// TODO: fix later` | Fix now or remove |

---

## Example: Before/After

```go
// BEFORE (violations: error handling, nested if/else, unused var)
func ProcessData(data []byte) (Result, error) {
    _ = validateInput(data)
    result, err := parse(data)
    if err != nil {
        return Result{}, err
    } else {
        if result.Valid {
            return result, nil
        } else {
            return Result{}, fmt.Errorf("invalid result")
        }
    }
}
```

```go
// AFTER (early returns, errors handled, no unused vars)
func ProcessData(data []byte) (Result, error) {
    if err := validateInput(data); err != nil {
        return Result{}, fmt.Errorf("validation failed: %w", err)
    }

    result, err := parse(data)
    if err != nil {
        return Result{}, fmt.Errorf("parse failed: %w", err)
    }

    if !result.Valid {
        return Result{}, fmt.Errorf("invalid result")
    }

    return result, nil
}
```

---

## Table-Driven Test Template

```go
func TestProcessData(t *testing.T) {
    tests := []struct {
        name    string
        input   []byte
        want    Result
        wantErr bool
    }{
        {"valid input", []byte("data"), Result{Valid: true}, false},
        {"empty input", []byte{}, Result{}, true},
        {"nil input", nil, Result{}, true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ProcessData(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("ProcessData() error = %v, wantErr %v", err, tt.wantErr)
                return
            }
            if !reflect.DeepEqual(got, tt.want) {
                t.Errorf("ProcessData() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

---

## Interface Pattern Template

```go
// Accept interface
type DataProcessor interface {
    Process(ctx context.Context, data []byte) (Result, error)
}

// Return struct
type processor struct {
    timeout time.Duration
    logger  Logger
}

func NewProcessor(timeout time.Duration, logger Logger) *processor {
    return &processor{
        timeout: timeout,
        logger:  logger,
    }
}

func (p *processor) Process(ctx context.Context, data []byte) (Result, error) {
    // implementation
}
```

---

## Checklist

Before completing Go code changes:

- [ ] All errors handled or returned (no `_ =`)
- [ ] Errors wrapped with `fmt.Errorf("context: %w", err)`
- [ ] Early returns used (no nested if/else)
- [ ] Functions accept interfaces where appropriate
- [ ] Functions return concrete structs
- [ ] Tests are table-driven with subtests
- [ ] No TODO comments
- [ ] No empty structs without purpose
